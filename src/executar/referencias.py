"""Mede os números de referência contra a base, de forma REPRODUTÍVEL.

A skill `verificar-contra-spec` manda, no passo 5, "rodar a implementação contra a
base e comparar com os números de referência". Até aqui isso era feito à mão, e o
resultado vivia como prosa num documento — o que tem dois defeitos: ninguém
reproduz, e a comparação seguinte não sabe se mediu a mesma coisa.

Este módulo é essa medição, com três compromissos:

**1. Reaproveita o código do sistema, nunca reimplementa o funil.** As contagens
saem de `dados.coletor_interno.coletar` e `dominio.elegibilidade.regras_reprovadas`
— exatamente o que a rodada de sexta executa. Reimplementar em SQL daria um segundo
funil, livre para divergir do primeiro, e aí a "conferência" passaria a medir a
própria cópia em vez do sistema.

**2. Os valores publicados são LIDOS do `docs/mapa-de-dados.md`**, não copiados
para cá. Os mesmos números já vivem no PRD, no mapa, na skill, no `CLAUDE.md`, em
`decisoes.md` e em `perguntas-abertas.md` — mais uma cópia é mais uma para esquecer
de atualizar, e o modo de falhar seria a ferramenta de CONFERÊNCIA afirmar que bate
contra um número que o documento não diz mais. (A ferramenta resolveu isso só para
si: nada guarda as outras seis cópias entre elas.)

**3. Não altera número nenhum.** Medir e publicar são atos diferentes: incorporar
uma medição aos valores de referência exige repetir a contagem noutro dia — uma
medição só não separa deriva estrutural de oscilação — e conciliar PRD, CLAUDE.md e
mapa, que publicam os mesmos números. Aqui só se mede e se registra.

## O diagnóstico que a skill define, e que este módulo aplica

"Divergência pequena e uniforme sugere deriva; divergência concentrada numa etapa
sugere bug naquela regra." É a leitura que separa base que mudou de código que
quebrou, e ela precisa sair junto do número — um funil de sete linhas sem
diagnóstico é convite a conclusão apressada nos dois sentidos.

Cuidado ao ler: "concentrada numa etapa" **sugere** bug, não o prova. A etapa pode
concentrar a diferença porque o INSUMO dela mudou — foi o caso medido em
2026-09-02, em que a etapa das cinco regras finais concentrou toda a diferença
porque a produtividade de corretor caiu, com o código correto. Por isso a saída
nomeia a etapa e para: quem investiga decide, a ferramenta não.

Uso:
    uv run python -m executar.referencias
    uv run python -m executar.referencias --registrar   # anexa ao mapa de dados
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

# A definição de "corretor ativo no distrito" é DECISÃO (D-015) e tem uma casa só:
# `config/recorte.py`. Nem literal repetido aqui — revista a D-015, a sexta mudaria e
# a medição passaria a medir outro funil em silêncio —, nem importada de
# `executar.sexta`, que arrastaria LangGraph e psycopg (575 ms de 630 ms) para uma
# ferramenta que lê markdown e conta imóveis, e faria qualquer efeito colateral
# futuro daquele módulo virar efeito colateral desta medição.
from config.recorte import DEFINICAO_ATIVO
from dados.coletor_interno import coletar
from dados.vendas import coletar_vendas
from dominio.elegibilidade import (
    PRECO_MINIMO_SUPER_DESTAQUE,
    ImovelCandidato,
    Regra,
    regras_reprovadas,
)

log = logging.getLogger("executar.referencias")

MAPA = Path(__file__).resolve().parents[2] / "docs" / "mapa-de-dados.md"

# Os rótulos como o mapa os escreve. Mudou o rótulo lá, esta ferramenta para com
# erro claro em vez de comparar contra o vazio.
ROTULO_ELEGIVEIS = "Imóveis elegíveis"
ROTULO_SUPER = "Candidatos ao super destaque (≥ R$ 700.000)"
ROTULO_VENDAS = "Vendas assinadas em 180 dias"
ETAPAS_DO_FUNIL = ("Ativos", "Nas cinco categorias", "Preço ≥ R$ 300.000")
# "Medidos em 28/08/2026." — a data também é lida, não fixada: quando a fatia
# seguinte incorporar a deriva, o cabeçalho da coluna acompanha sozinho.
_DATA_PUBLICADA = re.compile(r"Medidos em (\d{2}/\d{2})/\d{4}")
# O bloco de deriva entra DENTRO desta seção, junto do de 29/08 — não no fim do
# arquivo, onde ficaria órfão sob um título que não tem nada a ver.
SECAO_REFERENCIAS = "## Números de referência medidos"

# Diferença até aqui é ruído de base, não sinal. O número não é parâmetro de
# decisão: governa só a leitura desta ferramenta, e está aqui declarado.
RUIDO = 0.01


class MedicaoFalhou(RuntimeError):
    """Falha ao LER O MAPA — rótulo ausente, arquivo ilegível. Falha de base não
    passa por aqui: cai no tratamento genérico do `main` e sai por código próprio."""


@dataclass(frozen=True)
class Comparacao:
    rotulo: str
    publicado: int
    medido: int

    @property
    def delta(self) -> int:
        return self.medido - self.publicado

    @property
    def fracao(self) -> float:
        return self.delta / self.publicado if self.publicado else 0.0

    @property
    def dentro_do_ruido(self) -> bool:
        return abs(self.fracao) <= RUIDO


def _numero(texto: str) -> int:
    """`**10.290**` ou `48.964` → int. O ponto é separador de milhar (pt-BR)."""
    limpo = re.sub(r"[^\d]", "", texto)
    if not limpo:
        raise MedicaoFalhou(f"sem número em {texto!r}")
    return int(limpo)


def referencias_publicadas(mapa: Path = MAPA) -> dict[str, int]:
    """Os valores de referência, LIDOS do mapa de dados — a única cópia.

    Lê as duas tabelas da seção "Números de referência medidos": a de referências
    e a do funil. Rótulo ausente é erro, não zero: comparar contra zero produziria
    um "delta" enorme e falso."""
    try:
        texto = mapa.read_text(encoding="utf-8")
    except OSError as e:
        raise MedicaoFalhou(f"não consegui ler {mapa}: {type(e).__name__}") from e

    encontrados: dict[str, int] = {}
    for linha in texto.split("\n"):
        if not linha.startswith("|"):
            continue
        celulas = [c.strip() for c in linha.strip("|").split("|")]
        if len(celulas) != 2:
            continue
        rotulo, valor = celulas
        if rotulo in (*ETAPAS_DO_FUNIL, ROTULO_ELEGIVEIS, ROTULO_SUPER, ROTULO_VENDAS):
            encontrados.setdefault(rotulo, _numero(valor))

    faltando = {ROTULO_ELEGIVEIS, ROTULO_SUPER, ROTULO_VENDAS, *ETAPAS_DO_FUNIL} - set(encontrados)
    if faltando:
        raise MedicaoFalhou(
            f"rótulos não encontrados em {mapa.name}: {sorted(faltando)} — o documento "
            "mudou de forma e esta ferramenta compararia contra o vazio"
        )
    return encontrados


def contar_funil(candidatos: Sequence[ImovelCandidato], hoje: date) -> dict[str, int]:
    """O funil acumulado, pelas MESMAS regras que a rodada aplica.

    Acumulado, não por etapa: cada linha conta quem passou por todas as anteriores
    também — é como o mapa publica, e comparar acumulado contra por-etapa daria
    diferença inteiramente artificial."""
    reprovadas = [(c, regras_reprovadas(c, hoje)) for c in candidatos]
    ativos = [(c, r) for c, r in reprovadas if Regra.STATUS_ATIVO not in r]
    categoria_ok = [(c, r) for c, r in ativos if Regra.CATEGORIA not in r]
    preco_ok = [(c, r) for c, r in categoria_ok if Regra.PRECO_GERAL not in r]
    elegiveis = [c for c, r in preco_ok if not r]
    return {
        # Pela REGRA do domínio, não pelo `WHERE` do coletor: hoje dá o mesmo
        # número (o SQL já filtra ativos), mas quem define a etapa passa a ser
        # `Regra.STATUS_ATIVO`, coerente com o compromisso de não ter segunda fonte.
        "Ativos": len(ativos),
        "Nas cinco categorias": len(categoria_ok),
        "Preço ≥ R$ 300.000": len(preco_ok),
        ROTULO_ELEGIVEIS: len(elegiveis),
        ROTULO_SUPER: sum(1 for c in elegiveis if c.preco >= PRECO_MINIMO_SUPER_DESTAQUE),
    }


def passagem_por_regra(candidatos: Sequence[ImovelCandidato], hoje: date) -> dict[str, int]:
    """Quantos dos que chegaram à etapa final passam em CADA uma das cinco regras
    restantes, isoladamente. É o que localiza a diferença: um funil acumulado só
    diz que encolheu, não onde."""
    base = [
        (c, regras_reprovadas(c, hoje))
        for c in candidatos
        if not (
            {Regra.CATEGORIA, Regra.PRECO_GERAL, Regra.STATUS_ATIVO} & regras_reprovadas(c, hoje)
        )
    ]
    restantes = (
        Regra.FOTOS,
        Regra.ATUALIZACAO_90D,
        Regra.CADASTRO_COMPLETO,
        Regra.GESTOR_PRODUTIVO,
        Regra.CAPACIDADE_DISTRITO,
    )
    return {r.value: sum(1 for _, reprov in base if r not in reprov) for r in restantes}


def diagnosticar(comparacoes: Sequence[Comparacao]) -> str:
    """A leitura que a skill `verificar-contra-spec` define, aplicada.

    Deliberadamente conservadora: nomeia a etapa e para. "Concentrada numa etapa"
    SUGERE bug naquela regra — mas pode ser o insumo dela que mudou, e foi o que
    aconteceu na medição de 2026-09-02. Uma ferramenta que concluísse "é bug"
    mandaria alguém caçar defeito onde não há."""
    # Vendas fica FORA desta leitura, e por dois motivos. Não é etapa do funil: não
    # tem regra de elegibilidade nenhuma (vem de `coletar_vendas`), então mandar
    # conferir "a passagem por regra dessa etapa" apontaria para uma tabela onde a
    # linha acusada não aparece. E a base é 176, então o mesmo 1% vale menos de duas
    # vendas — o mapa já registra 176→177 num único dia, ou seja, mais de meia banda
    # consumida por um caso. Sob a régua do funil, duas vendas de deriva produziriam
    # alarme de bug numa regra que não existe.
    etapas = [c for c in comparacoes if c.rotulo != ROTULO_VENDAS]
    fora = [c for c in etapas if not c.dentro_do_ruido]
    if not fora:
        return (
            f"Tudo dentro do ruído (até {RUIDO:.0%} de diferença): os números de "
            "referência continuam válidos."
        )
    if len(fora) == len(etapas):
        return (
            "Diferença em TODAS as etapas, incluindo as iniciais: deriva uniforme da "
            "base. Sugere estoque que mudou, não regra que quebrou."
        )
    nomes = ", ".join(c.rotulo for c in fora)
    return (
        f"Diferença CONCENTRADA em: {nomes}. Pela skill `verificar-contra-spec`, isso "
        "sugere bug na regra dessa etapa — mas pode ser o INSUMO dela que mudou. "
        "Confira a passagem por regra abaixo antes de concluir: se uma regra isolada "
        "explica a diferença, investigue o dado que ela lê antes do código dela."
    )


def nota_sobre_vendas(comparacoes: Sequence[Comparacao]) -> str | None:
    """Vendas, quando fora do ruído, dita à parte — com o motivo de ser à parte.

    Sai como nota, não como veredito: com base 176, a banda do funil é apertada
    demais para ela, e a causa não está em regra nenhuma."""
    for c in comparacoes:
        if c.rotulo == ROTULO_VENDAS and not c.dentro_do_ruido:
            return (
                f"Nota: {ROTULO_VENDAS} variou {c.delta:+d} ({c.fracao:+.1%}). Não é etapa "
                "do funil e não passa por regra de elegibilidade — a passagem por regra "
                f"acima não a explica. Base pequena ({c.publicado}): a banda de {RUIDO:.0%} "
                "vale menos de duas vendas aqui."
            )
    return None


def medir(
    candidatos: Sequence[ImovelCandidato], ancoraveis: int, descartadas: int, hoje: date
) -> dict[str, int]:
    """As contagens medidas, prontas para comparar — pura, para o caminho do `main`
    deixar de ser inalcançável sem banco.

    **A linha de vendas SOMA as descartadas.** `coletar_vendas` devolve só as
    ANCORÁVEIS (oferta sem `Realty_Id` não vira `ImovelVendido`) e entrega o descarte
    à parte, "NUNCA em silêncio". Mas o valor publicado no mapa é a métrica D-013
    INTEIRA. Comparar ancoráveis contra o total mediria populações diferentes: ~2 de
    diferença sobre 176 é 1,1%, ACIMA da banda de ruído — a ferramenta acusaria
    deriva em toda rodada, para sempre, por construção. E o descarte que
    `vendas.py` faz questão de não engolir seria engolido justamente na ferramenta de
    conferência. Achado do portão de código."""
    return {**contar_funil(candidatos, hoje), ROTULO_VENDAS: ancoraveis + descartadas}


def comparar(publicado: dict[str, int], medido: dict[str, int]) -> list[Comparacao]:
    ordem = (*ETAPAS_DO_FUNIL, ROTULO_ELEGIVEIS, ROTULO_SUPER, ROTULO_VENDAS)
    return [
        Comparacao(rotulo=r, publicado=publicado[r], medido=medido[r])
        for r in ordem
        if r in publicado and r in medido
    ]


def _milhar(n: int, *, sinal: bool = False) -> str:
    """Separador de milhar em pt-BR, explícito. `:n` depende do locale — que no CI
    é `C` e não separa nada, produzindo um documento diferente do da máquina de
    quem rodou."""
    texto = f"{abs(n):,}".replace(",", ".")
    if sinal:
        return f"{'+' if n >= 0 else '-'}{texto}"
    return f"-{texto}" if n < 0 else texto


def _pct(fracao: float) -> str:
    """Percentual com vírgula decimal, como o resto do documento escreve."""
    return f"{fracao:+.1%}".replace(".", ",")


def data_publicada(mapa: Path = MAPA) -> str:
    """A data da medição publicada, do próprio mapa (`28/08`)."""
    achado = _DATA_PUBLICADA.search(mapa.read_text(encoding="utf-8"))
    if achado is None:
        raise MedicaoFalhou(
            f'não achei "Medidos em DD/MM/AAAA" em {mapa.name} — o cabeçalho da '
            "coluna afirmaria uma data que o documento não diz"
        )
    return achado.group(1)


def inserir_no_mapa(texto: str, bloco: str, *, data: str = "") -> str:
    """Insere o bloco logo APÓS o bloco de deriva irmão, dentro da seção.

    Duas versões erraram isto, e a segunda errou afirmando ter corrigido a primeira.
    Anexar no fim do ARQUIVO punha o bloco sob um título alheio. Anexar no fim da
    SEÇÃO — procurando o próximo `##` — caía DEPOIS do `---` que fecha a seção e logo
    abaixo de `### Aviso sobre os ganhos de relaxamento`, um nível abaixo e sobre
    outro assunto. Formato certo, lugar errado, duas vezes; e a docstring anterior
    descrevia como consertado o defeito que ela mesma tinha. Achado do portão de
    código, que simulou a inserção contra o documento real em vez de sintético.

    A âncora certa é o irmão: o bloco novo entra junto do de 29/08, antes do primeiro
    `###`, `---` ou `##` que vier depois dele.

    `data`, quando dada, torna a operação idempotente. Registrar duas vezes no mesmo
    dia deixaria dois blocos com a mesma data e — se o estoque mudou entre as
    execuções — dois registros CONTRADITÓRIOS, sem critério para escolher qual vale.
    Recusar é mais coerente com a postura do módulo do que sobrescrever em silêncio.
    """
    inicio = texto.find(SECAO_REFERENCIAS)
    if inicio < 0:
        raise MedicaoFalhou(f"seção {SECAO_REFERENCIAS!r} não encontrada — bloco órfão")
    fim_secao = texto.find("\n## ", inicio + len(SECAO_REFERENCIAS))
    fim_secao = len(texto) if fim_secao < 0 else fim_secao
    secao = texto[inicio:fim_secao]
    if data and f"Deriva medida em {data}" in secao:
        raise MedicaoFalhou(
            f"já existe bloco de deriva de {data} na seção de referências. Dois "
            "registros da mesma data se contradizem quando o estoque mudou entre "
            "eles, e nada diz qual vale — remova o anterior antes de registrar"
        )
    irmao = secao.rfind("Deriva medida em")
    if irmao < 0:
        return texto[:fim_secao] + bloco + texto[fim_secao:]
    cortes = [pos for pos in (secao.find(m, irmao) for m in ("\n### ", "\n---")) if pos >= 0]
    corte = min(cortes) if cortes else len(secao)
    return texto[: inicio + corte] + bloco + texto[inicio + corte :]


def bloco_para_o_mapa(
    comparacoes: Sequence[Comparacao], hoje: date, diagnostico: str, publicado_em: str
) -> str:
    """O registro datado, no formato que o mapa já usa para deriva."""
    linhas = [
        f"\nDeriva medida em {hoje:%d/%m/%Y} "
        f"(`uv run python -m executar.referencias`, reprodutível):\n",
        f"| Contagem | Publicado ({publicado_em}) | Medido | Deriva |",
        "|---|---|---|---|",
    ]
    for c in comparacoes:
        linhas.append(
            f"| {c.rotulo} | {_milhar(c.publicado)} | **{_milhar(c.medido)}** | "
            f"{_milhar(c.delta, sinal=True)} ({_pct(c.fracao)}) |"
        )
    linhas.append(f"\n*Leitura:* {diagnostico}\n")
    linhas.append(
        "*Nenhum valor de referência acima foi alterado por esta medição: incorporar "
        "exige repetir a contagem noutro dia e conciliar PRD, CLAUDE.md e este mapa.*\n"
    )
    return "\n".join(linhas)


def _registrar(comparacoes: Sequence[Comparacao], medido_em: date, diagnostico: str) -> None:
    """Grava o bloco no mapa, de forma ATÔMICA: escreve ao lado e troca.

    `medido_em` é a data REAL da medição, não o `--hoje`. Os dois são coisas
    diferentes: `--hoje` é a data de referência das regras (a dos 90 dias), e serve
    para reproduzir uma medição antiga — usá-lo aqui gravaria no mapa que a medição
    aconteceu num dia em que ela não aconteceu.

    `write_text` direto deixaria truncado um documento que é referência derivada do
    PRD, se o processo caísse no meio."""
    bloco = bloco_para_o_mapa(comparacoes, medido_em, diagnostico, data_publicada())
    novo = inserir_no_mapa(MAPA.read_text(encoding="utf-8"), bloco, data=f"{medido_em:%d/%m/%Y}")
    temporario = MAPA.with_suffix(".md.tmp")
    temporario.write_text(novo, encoding="utf-8")
    os.replace(temporario, MAPA)


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Mede os números de referência contra a base.")
    p.add_argument(
        "--registrar",
        action="store_true",
        help="anexa o resultado ao docs/mapa-de-dados.md, no formato de deriva datada. "
        "NÃO altera nenhum valor de referência publicado.",
    )
    p.add_argument("--hoje", type=date.fromisoformat, help="data de referência (AAAA-MM-DD)")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    hoje = args.hoje or date.today()

    try:
        publicado = referencias_publicadas()
        candidatos, _ = coletar(DEFINICAO_ATIVO)
        ancoraveis, descartadas = coletar_vendas()
    except MedicaoFalhou as e:
        log.error("%s", e)
        return 1
    except Exception as e:
        log.error("falha ao medir contra a base: %s", type(e).__name__)
        log.debug("causa completa", exc_info=True)
        return 3

    medido = medir(candidatos, len(ancoraveis), descartadas, hoje)
    comparacoes = comparar(publicado, medido)
    diagnostico = diagnosticar(comparacoes)

    for c in comparacoes:
        marca = " " if c.dentro_do_ruido else "!"
        log.info(
            "%s %-42s publicado %8d  medido %8d  %+d (%+.1f%%)",
            marca,
            c.rotulo,
            c.publicado,
            c.medido,
            c.delta,
            c.fracao * 100,
        )
    log.info("passagem por regra (dos que chegam à etapa final):")
    for regra, n in passagem_por_regra(candidatos, hoje).items():
        log.info("    %-24s %6d", regra, n)
    log.info("LEITURA: %s", diagnostico)
    nota = nota_sobre_vendas(comparacoes)
    if nota:
        log.info("%s", nota)

    if args.registrar:
        bloco = bloco_para_o_mapa(comparacoes, hoje, diagnostico, data_publicada())
        MAPA.write_text(inserir_no_mapa(MAPA.read_text(encoding="utf-8"), bloco), encoding="utf-8")
        log.info("registrado em %s, na seção de referências", MAPA.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
