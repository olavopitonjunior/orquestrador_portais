"""Ponto de entrada da rodada de SEXTA (decisão) — Spec §1.

Simétrico ao de segunda: até aqui o grafo da decisão existia e passava nos testes,
mas quem o invocava era script solto e não versionado — a planilha em `saida/piloto/`
saiu de um desses. Aqui a fiação é commitada, reproduzível e auditável.

    uv run python -m executar.sexta --parametros ARQUIVO.toml [--externo DIR]
                                    [--destino DIR] [--dry-run] [--hoje AAAA-MM-DD]

## Por que `--parametros` é OBRIGATÓRIO e não tem default

Treze dos quatorze parâmetros da decisão são NULOS (D-004, D-017) e o CLAUDE.md proíbe
preenchê-los com valor inventado. A sexta não calcula nada sem eles. A saída não é
embutir um default "razoável" — seria exatamente o valor inventado que a regra
proíbe, com o agravante de ficar invisível numa planilha aprovada. É exigir que o
dono da decisão declare os valores num arquivo, fora do repositório, e recusar a
rodada quando faltar qualquer um (`src/config/parametros.py` faz o exame).

Tudo que entra por ali é PROVISÓRIO: carregar não é adotar. A procedência viaja para
a planilha (nota de abertura) e o TOML declarado vai verbatim para o Registro, junto
da data de referência e da definição de gestor ativo, para que **os parâmetros e o
recorte** da rodada sejam reconstituíveis a partir do que ficou gravado.

Note o que essa frase NÃO diz: que a rodada é reproduzível. O estoque não é
reconstituível — as janelas de 30 dias do gestor e as vendas de 180 dias saem de
`NOW()` no SQL, então reexecutar lê o banco de hoje (ver a ressalva de `--hoje`). O
invariante 5 vale sobre a mesma entrada, e "mesma entrada" inclui o banco no instante
da rodada.

## Por que o runner NÃO abre o fluxo de aprovação

A aprovação é grafo à parte (`grafo/aprovacao.py`), e o que a dispara sozinha é o
PRAZO da aprovação tácita — parâmetro pendente nº 10, **nulo**. Abrir aqui uma thread
de aprovação sem prazo seria afirmar um prazo que ninguém definiu. O runner termina
registrando a rodada e informando o `rodada_id`; quem tem o prazo (console ou
agendador) abre a aprovação com ele.

## Fiação dos sinks

Espelha a disciplina da segunda: falha de ESCRITA é distinta de falha de FONTE.
`registrar` é chamado de DENTRO do grafo (último nó); se o Postgres cair, avisa por
outro canal e propaga como `SinkFalhou` — a planilha não é escrita, porque uma
planilha sem rodada no Registro é uma decisão sem trilha. A planilha é escrita pelo
runner DEPOIS do `invoke`, então a ordem é sempre Registro → planilha.

**Essa ordem DIVERGE dos documentos e a divergência está declarada**, não resolvida
em silêncio: o PRD (fluxo de sexta, passos 6 e 7) e a Spec §5 ("Registro | Consome:
saídas do Decisor, DO REDATOR e do Monitor") põem o Redator antes. O contra-argumento
é real — sob a D-001 uma rodada gravada sem planilha pode ser aprovada por decurso de
prazo e virar a "carga vigente" contra a qual a segunda mede, uma lista que ninguém
recebeu. A pergunta está em `docs/decisoes.md`; até a resposta do dono, esta ordem
permanece.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime
from functools import partial
from pathlib import Path
from typing import Any

from config.parametros import ParametroAusente, ParametroInvalido, ParametrosDaRodada, carregar
from dados.candidatos_perfil import coletar_dimensoes_candidatos
from dados.coletor_externo import ler_coleta
from dados.coletor_interno import DefinicaoAtivoDistrito, coletar
from dados.registro.conexao import conectar
from dados.registro.escrita import gravar_rodada_decisao
from dados.vendas import coletar_vendas
from dominio.penalidades import ImovelPenalizavel
from dominio.perfil import ImovelVendido
from entrega.planilha_piloto import escrever_planilha
from grafo.estado import Estado, EstadoRodada, Fontes
from grafo.fluxo import construir_grafo

# D-015 fixou a definição de gestor ativo do distrito usada na elegibilidade.
# Constante nomeada e não argumento de linha de comando: trocá-la muda a regra de
# decisão, e regra se muda por decisão registrada, não por flag de invocação.
DEFINICAO_ATIVO = DefinicaoAtivoDistrito.PRODUTIVOS

# O modelo ilustrativo, recusado como entrada real (ver `main`). Num wheel instalado
# este caminho não existe, e a comparação simplesmente nunca casa — que é o correto:
# o modelo é documentação, não vai no pacote.
MODELO_DE_DOCS = (
    Path(__file__).resolve().parent.parent.parent / "docs" / "parametros-da-rodada.exemplo.toml"
)

log = logging.getLogger("rodada.sexta")


class SinkFalhou(RuntimeError):
    """Falha de ESCRITA (Registro ou planilha). Distinta de falha de fonte."""


def _fontes(externo: Path | None) -> tuple[Fontes, list[tuple[list[ImovelVendido], int]]]:
    """As fontes da sexta, mais o cache das vendas.

    `coletar_vendas` é MEMOIZADO e o cache devolvido ao chamador porque o nó do
    Analista de Perfil descarta a contagem de vendas sem imóvel amarrado
    (`vendas, _descartadas = ...`) — e esse número é nota de coleta da planilha.
    Sem o cache, o runner teria de consultar o Newcore uma segunda vez para
    recuperá-lo, e as duas leituras poderiam divergir.
    """
    cache: list[tuple[list[ImovelVendido], int]] = []

    def vendas_memoizadas() -> tuple[list[ImovelVendido], int]:
        if not cache:
            cache.append(coletar_vendas())
        return cache[0]

    fontes = Fontes(
        # `coletar` recebe a definição de ativo; o grafo espera zero-argumento.
        coletar_interno=partial(coletar, DEFINICAO_ATIVO),
        coletar_dimensoes=coletar_dimensoes_candidatos,
        coletar_vendas=vendas_memoizadas,
        # Tudo ou nada: o grafo recusa meia-fiação, e o nó declara a degradação
        # quando não há raspagem — rodada DEGRADADA nesse fator, nunca silenciosa.
        coletar_externo=(lambda: ler_coleta(externo)) if externo else None,
    )
    return fontes, cache


def _serializaveis(
    parametros: ParametrosDaRodada, hoje: date, externo: Path | None
) -> dict[str, object]:
    """O que vai para `parametros_da_rodada` do Registro.

    É o TOML declarado VERBATIM mais a procedência — não uma reconstrução a partir
    de `ParametrosDecisao`. As duas FORMAS (decaimento da penalidade e composição do
    F3) viram função e não sobrevivem à dataclass: gravar só os números deixaria a
    rodada irreproduzível a partir do Registro.

    Mas o TOML não é a entrada inteira. Três coisas fora dele também mudam a lista e
    por isso viajam junto:

    - `data_referencia` é entrada da decisão (decide a regra de atualização em 90
      dias) e o Registro não tem coluna para ela. Sem gravá-la, uma rodada feita com
      `--hoje` ficaria irreproduzível — justamente a opção cujo help promete "fixa o
      recorte, tornando a rodada reproduzível".
    - `definicao_ativo_distrito` é entrada de elegibilidade fixada em código (D-015):
      se a decisão mudar, as rodadas antigas precisam dizer sob qual regra saíram.
    - `coleta_externa` identifica a raspagem que alimentou o F3. Fica o CAMINHO, que
      é o que o runner tem; a identificação plena da coleta (`coletado_em`,
      `total_linhas`) mora na `ColetaExterna` dentro do grafo e ainda não sobe até
      aqui — lacuna DECLARADA, não resolvida.
    """
    return {
        "rotulo": parametros.rotulo,
        "origem": parametros.origem,
        "data_referencia": hoje.isoformat(),
        "definicao_ativo_distrito": DEFINICAO_ATIVO.value,
        "coleta_externa": str(externo) if externo else None,
        **parametros.declarado,
    }


def _avisar(destino: Path, *, dry_run: bool) -> Callable[[str], None]:
    def avisar(mensagem: str) -> None:
        log.warning(mensagem)  # o log sai SEMPRE, primeiro
        if dry_run:
            return
        try:
            destino.mkdir(parents=True, exist_ok=True)
            with (destino / "aviso.txt").open("a", encoding="utf-8") as f:
                f.write(f"{datetime.now().isoformat()} {mensagem}\n")
        except OSError as e:
            # Chamado de dentro de handlers de falha: se levantasse, trocaria a
            # exceção original por outra e esconderia a causa.
            log.error("não foi possível gravar aviso.txt (%s); o aviso está no log", e)

    return avisar


def _registrador(
    parametros: ParametrosDaRodada,
    hoje: date,
    externo: Path | None,
    agora: datetime,
    *,
    dry_run: bool,
    avisar: Callable[[str], None],
) -> tuple[Callable[[EstadoRodada], object], list[int]]:
    """O sink `registrar` do grafo, mais a caixa onde o `rodada_id` é capturado.

    O grafo descarta o retorno de `registrar`, e o `rodada_id` é o que o dono precisa
    para aprovar a rodada — por isso a captura por closure. A caixa é lida com
    `[-1]`, nunca `[0]`: se o nó for reexecutado (o retry do Orquestrador é o
    parâmetro nº 4, ainda nulo, e `no_registrar` já o registra como fatia futura),
    `gravar_rodada_decisao` cria uma SEGUNDA linha — não há chave natural para
    deduplicar — e informar a primeira mandaria o dono aprovar a rodada órfã.
    """
    capturado: list[int] = []

    def registrar(estado: EstadoRodada) -> object:
        resultado = estado.get("resultado")
        if resultado is None:
            # Chegar ao nó de registro sem resultado é incoerência de topologia, não
            # rodada vazia: gravar a linha assim mesmo produziria uma "carga vigente"
            # sem decisão, que a segunda mediria como se fosse real.
            raise RuntimeError("rodada chegou ao Registro sem resultado da decisão")
        # As limitações da FIAÇÃO entram no motivo gravado, não só na planilha: sob a
        # D-001 o Registro é a fonte da verdade, e quem auditasse pelo banco — que é
        # como a rodada de segunda enxerga — não veria "histórico de janelas ausente"
        # nem "distrito a 45,9%". Planilha e Registro precisam dizer a mesma coisa.
        degradacoes = [
            *estado.get("degradacoes", []),
            *limitacoes_da_fiacao(parametros, estado.get("penalizaveis", {})),
        ]
        motivo = "; ".join(degradacoes) or None
        if dry_run:
            log.info("[dry-run] rodada NÃO gravada (estado=%s)", estado.get("estado"))
            return None
        try:
            with conectar() as conn, conn.transaction():
                rodada_id = gravar_rodada_decisao(
                    conn,
                    resultado=resultado,
                    estado=str(estado.get("estado")),
                    etapas=estado.get("prontos", {}),
                    parametros=_serializaveis(parametros, hoje, externo),
                    inicio=agora,
                    fim=datetime.now(),
                    motivo_degradacao=motivo,
                )
        except Exception as e:
            # Só o TIPO: a mensagem pode ecoar valor vindo do banco, e a saída do
            # agendador vira e-mail/log capturado.
            avisar(f"FALHA ao gravar a rodada de sexta no Registro: {type(e).__name__}")
            raise SinkFalhou("falha ao gravar no Registro") from e
        capturado.append(rodada_id)
        log.info("rodada de decisão gravada no Registro: id=%s", rodada_id)
        return rodada_id

    return registrar, capturado


def limitacoes_da_fiacao(
    parametros: ParametrosDaRodada, penalizaveis: Mapping[int, ImovelPenalizavel]
) -> list[str]:
    """Limitações que nascem de COMO a rodada foi fiada, não do que o grafo achou.

    A §7.2 quer a limitação visível na planilha, e estas três não apareciam em lugar
    nenhum — quem lesse a lista não teria como saber que existiam:

    1. **Não há histórico de janelas: a penalidade da §6.4 fica inerte.** O Coletor
       Interno devolve `janelas_anteriores=()` para todo imóvel e nada no caminho da
       sexta lê `registro.janela_destaque` (produtor ainda não existe). Uma das três
       penalidades da §6.4 nunca incide e a coluna sai 0,0 para todos —
       indistinguível de "imóvel sem histórico", que o PRD manda identificar como
       tal.

       O predicado é "o produtor entregou ALGUM histórico?", não "algum imóvel foi
       penalizado". A primeira versão perguntava a segunda coisa, e as duas divergem
       no dia em que o produtor existir e todas as janelas tiverem dado resultado:
       ali a planilha declararia "dado ausente" sobre um dado presente — a mesma
       classe de limitação falsa que a degradação incondicional de portal produzia,
       reintroduzida a prazo. Perguntando pelo histórico, a linha some sozinha
       quando o produtor chegar, que é o que o comentário promete.
    2. **Razão 1.0 não decai.** A §6.4 diz que a penalidade decai ao longo dos
       ciclos; a razão 1.0 é aceita, mas a divergência é declarada em vez de o código
       fingir que ela não existe.
    3. **A definição de gestor ativo do distrito** (D-015) cobre 45,9% — a D-016
       manda essa limitação aparecer na aba, e ela não aparecia.
    """
    limitacoes = []
    if not any(p.janelas_anteriores for p in penalizaveis.values()):
        limitacoes.append(
            "HISTÓRICO DE JANELAS ausente para todos os imóveis: a rodada de segunda já "
            "acumula registro.janela_destaque (D-021), mas a SEXTA ainda não lê a tabela — "
            "o Coletor Interno devolve a lista vazia, então a penalidade por janela "
            "anterior sem resultado (Spec §6.4) não pode incidir. A coluna sai 0,0 para "
            "todos — não é 'nenhum imóvel penalizado', é dado ausente"
        )
    if parametros.resultado_esperado is None:
        # A outra metade da D-022: "enquanto nulo... a rodada DECLARA 'limiar de
        # resultado não definido' na planilha. Nunca 0,0 silencioso". Sem esta linha,
        # a ausência de penalidade por falta de limiar seria indistinguível de uma
        # janela que passou no critério.
        limitacoes.append(
            "LIMIAR DE RESULTADO não definido (parâmetro pendente nº 14, D-022): a §6.4 "
            "penaliza a janela que não atingiu 'o resultado esperado para o nível', e os "
            "dois valores seguem nulos. Nenhuma janela é julgada — não é 'todas passaram'"
        )
    if parametros.declarado.get("decaimento_janela", {}).get("razao") == 1.0:
        limitacoes.append(
            "decaimento da penalidade por janela com razão 1.0: a penalidade NÃO "
            "decai ao longo dos ciclos, divergindo da Spec §6.4 — escolha declarada "
            "do dono nesta rodada"
        )
    limitacoes.append(
        f"gestor ativo do distrito = {DEFINICAO_ATIVO.value} (D-015): cobertura de "
        "45,9% da base; imóveis cujo distrito não casa ficam de fora da regra"
    )
    return limitacoes


def notas_da_planilha(
    parametros: ParametrosDaRodada,
    estado: Estado | None,
    degradacoes: Sequence[str],
    *,
    data_referencia: date | None = None,
    vendas_descartadas: int | None = None,
    taxa_amarracao: float | None = None,
    idade_dias: int | None = None,
    posicoes_vazias: int | None = None,
    posicoes_preenchidas: int | None = None,
) -> list[str]:
    """As notas que abrem a aba de parâmetros e limitações.

    O ESTADO e as limitações vêm PRIMEIRO: a §7.2 exige a limitação declarada de
    forma visível, e quem lê a lista precisa saber, antes dos números, se a rodada
    foi completa ou degradada.

    Depois vêm os quatro itens que a §3.1 e o PRD exigem NOMINALMENTE na aba de
    resumo: idade do dado do portal, taxa de amarração, posições não preenchidas e —
    ainda sem produtor — a variação de volume. Cada um que falta é DECLARADO como
    ausente: uma linha faltando é indistinguível de um número que ninguém calculou.
    """
    notas = []
    if data_referencia is not None:
        # A §3.1 pede a DATA no resumo. A subpasta datada não serve: quem abre o CSV
        # solto — que é como ele viaja por e-mail — não vê o nome da pasta.
        notas.append(f"DATA DE REFERÊNCIA DA RODADA: {data_referencia.isoformat()}")
    notas.append(f"ESTADO DA RODADA: {str(estado).upper()}")
    notas += [f"LIMITAÇÃO {i}: {d}" for i, d in enumerate(degradacoes, 1)] or [
        "LIMITAÇÕES: nenhuma"
    ]
    notas.append(
        # Sem afirmar autoria: o runner sabe de qual ARQUIVO os valores vieram, não
        # quem os escreveu. Dizer "declarados pelo dono" viraria mentira no dia em
        # que alguém apontasse `--parametros` para um arquivo de exemplo.
        f"parâmetros da rodada: rótulo {parametros.rotulo}, carregados de "
        f"{parametros.origem} — valores desta rodada, NÃO adotados pelo sistema"
    )
    notas.append(
        f"idade do dado do portal: {idade_dias} dia(s)"
        if idade_dias is not None
        else "idade do dado do portal: AUSENTE (sem coleta externa nesta rodada, ou "
        "coleta sem carimbo de tempo)"
    )
    notas.append(
        f"taxa de amarração anúncio↔imóvel: {taxa_amarracao:.1%}"
        if taxa_amarracao is not None
        else "taxa de amarração anúncio↔imóvel: AUSENTE (sem coleta externa)"
    )
    notas.append(
        f"posições de destaque não preenchidas: {posicoes_vazias}"
        if posicoes_vazias is not None
        else "posições não preenchidas: não apuradas"
    )
    notas.append(
        f"posições preenchidas: {posicoes_preenchidas}"
        if posicoes_preenchidas is not None
        else "posições preenchidas: não apuradas"
    )
    notas.append(
        "variação do estoque elegível em relação à semana anterior: NÃO APURADA — a "
        "comparação exige a rodada anterior no Registro e ainda não tem produtor "
        "(Spec §3.1 a exige; limitação declarada, não omitida)"
    )
    if vendas_descartadas:
        notas.append(
            f"{vendas_descartadas} venda(s) do período descartada(s) por não amarrar "
            "a imóvel — não sustentaram nenhum perfil de conversão"
        )
    return notas


def executar(
    destino: Path,
    parametros: ParametrosDaRodada,
    *,
    externo: Path | None = None,
    hoje: date | None = None,
    dry_run: bool = False,
) -> tuple[dict[str, Any], int | None]:
    """Roda a sexta de ponta a ponta. Devolve o estado final e o `rodada_id`."""
    hoje = hoje or date.today()
    agora = datetime.now()

    # Subpasta por data: sem isto, a sexta seguinte APAGA a planilha da anterior — e a
    # planilha é o artefato contratual, o que foi de fato aprovado e carregado.
    destino_da_rodada = destino / f"{hoje:%Y-%m-%d}"
    avisar = _avisar(destino_da_rodada, dry_run=dry_run)
    fontes, cache_vendas = _fontes(externo)
    registrar, capturado = _registrador(
        parametros, hoje, externo, agora, dry_run=dry_run, avisar=avisar
    )

    grafo = construir_grafo(
        fontes,
        parametros.decisao,
        parametros_externo=parametros.externo if externo else None,
        registrar=registrar,
    )
    final = grafo.invoke(
        {
            "data_referencia": hoje,
            "estado": Estado.EM_ANDAMENTO,
            "prontos": {},
            "degradacoes": [],
        }
    )

    estado = final.get("estado")
    if estado == Estado.ABORTADA:
        # Sem estoque (ou veto do crivo) não há entrega: Spec §7.2, "não há entrega;
        # sem estoque não há decisão possível". A ausência é declarada por log,
        # Registro e aviso — o aviso importa: no disco, uma sexta abortada seria
        # indistinguível de uma máquina desligada.
        avisar(f"rodada de sexta ABORTADA: {final.get('motivo_aborto') or 'motivo não informado'}")
        return final, None

    resultado = final.get("resultado")
    if resultado is None:
        # Estado não-abortado sem resultado é incoerência: o nó de registro já rodou.
        # Sair 0 aqui diria ao agendador que a sexta entregou.
        raise RuntimeError(f"rodada terminou {estado} sem resultado — nada a entregar")

    if not dry_run:
        try:
            caminhos = escrever_planilha(
                final["resultado"],
                parametros.decisao,
                destino_da_rodada,
                notas_coleta=notas_da_planilha(
                    parametros,
                    estado,
                    [
                        *final.get("degradacoes", []),
                        # A MESMA lista que foi para o motivo gravado no Registro.
                        *limitacoes_da_fiacao(parametros, final.get("penalizaveis", {})),
                    ],
                    data_referencia=hoje,
                    vendas_descartadas=cache_vendas[0][1] if cache_vendas else None,
                    taxa_amarracao=final.get("externo_taxa_amarracao"),
                    idade_dias=final.get("externo_idade_dias"),
                    posicoes_vazias=resultado.relaxamento.deficit_restante,
                    posicoes_preenchidas=(
                        len(resultado.alocacao.super_destaque)
                        + len(resultado.alocacao.destaque)
                        + len(resultado.relaxamento.recuperados)
                    ),
                ),
            )
        except Exception as e:
            # A rodada JÁ está no Registro: avisa que a planilha não saiu e propaga.
            # Quem opera precisa saber que existe rodada gravada sem artefato — não
            # é uma sexta que não aconteceu.
            avisar(
                f"Rodada {capturado[-1] if capturado else '?'} gravada, mas a PLANILHA "
                f"não foi escrita: {type(e).__name__}"
            )
            raise SinkFalhou("falha ao escrever a planilha") from e
        log.info("planilha escrita: %s", ", ".join(p.name for p in caminhos))
    else:
        log.info("[dry-run] planilha NÃO escrita")

    return final, capturado[-1] if capturado else None


def construir_parser() -> argparse.ArgumentParser:
    """Público para que o teste leia os DEFAULTS daqui em vez de redigitá-los — um
    teste que reafirma o literal que ele mesmo escreve continua verde com o default
    trocado, e foi o que aconteceu com `--destino`."""
    p = argparse.ArgumentParser(description="Rodada de sexta (decisão)")
    p.add_argument(
        "--parametros",
        type=Path,
        required=True,
        help="TOML com os parâmetros PROVISÓRIOS da rodada, declarados pelo dono da "
        "decisão. Obrigatório e sem default: treze dos quatorze parâmetros são nulos, e "
        "embutir um valor aqui seria inventá-lo. Modelo em docs/.",
    )
    p.add_argument(
        "--externo",
        type=Path,
        help="pasta de saída do raspador (out/). Ausente, o desempenho de portal (F3) "
        "não entra e a rodada sai DEGRADADA nesse fator, com a limitação declarada.",
    )
    p.add_argument("--destino", type=Path, default=Path("saida/sexta"))
    p.add_argument("--dry-run", action="store_true", help="não grava nem escreve nada")
    p.add_argument(
        "--hoje",
        type=date.fromisoformat,
        help="data de referência (AAAA-MM-DD); default é hoje. Governa a regra de "
        "atualização em 90 dias e a idade aceitável da coleta. ATENÇÃO: NÃO retrocede "
        "a rodada inteira — as janelas de 30 dias do gestor e as vendas de 180 dias "
        "saem de NOW() no SQL, então reprocessar uma sexta antiga mistura "
        "elegibilidade datada no passado com produtividade e perfis de hoje.",
    )
    return p


def main(argv: Sequence[str] | None = None) -> int:
    p = construir_parser()
    args = p.parse_args(argv)
    if args.hoje and args.hoje > date.today():
        p.error("--hoje no futuro decidiria sobre um estoque que ainda não existe")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.parametros.resolve() == MODELO_DE_DOCS:
        # O modelo carrega com sucesso e mora no repositório: sem esta recusa, sairia
        # dele uma planilha completa, de aparência normal, construída sobre números
        # que o próprio arquivo declara ilustrativos.
        log.error(
            "%s é o MODELO ilustrativo, não uma declaração de parâmetros. Copie-o para "
            "fora do repositório e substitua os valores antes de rodar.",
            args.parametros,
        )
        return 5

    try:
        parametros = carregar(args.parametros)
    except (ParametroAusente, ParametroInvalido) as e:
        # Código próprio: nada rodou e nada foi tocado. É o arquivo de quem opera,
        # corrigível em segundos — não é incidente, e tratá-lo como falha de fonte
        # mandaria alguém investigar o Newcore por causa de um typo no TOML.
        log.error("parâmetros da rodada: %s", e)
        return 5
    except OSError as e:
        log.error("não foi possível ler %s: %s", args.parametros, e)
        return 5

    try:
        final, rodada_id = executar(
            args.destino,
            parametros,
            externo=args.externo,
            hoje=args.hoje,
            dry_run=args.dry_run,
        )
    except SinkFalhou as e:
        log.error("%s (detalhe no log do servidor)", e)
        log.debug("causa completa", exc_info=True)
        return 1
    except Exception as e:
        # Falha de FONTE (Newcore fora, saída do raspador ilegível) ou incoerência da
        # rodada. Só o tipo para fora: a mensagem pode ecoar dado do banco.
        log.error("falha ao coletar ou decidir: %s (detalhe no log do servidor)", type(e).__name__)
        log.debug("causa completa", exc_info=True)
        return 3

    estado = final.get("estado")
    log.info("ESTADO DA RODADA: %s", str(estado).upper())
    for d in final.get("degradacoes", []):
        log.info("  limitação: %s", d)
    if final.get("motivo_aborto"):
        log.info("  motivo do aborto: %s", final["motivo_aborto"])

    if estado == Estado.ABORTADA:
        # ABORTADA tem duas causas de gravidade OPOSTA e o agendador precisa
        # distingui-las. Estoque vazio é insumo ausente (benigno, código 4). Veto do
        # crivo é a auditoria apanhando violação de cota, de piso ou de relaxamento em
        # super destaque — invariantes 6 e 7 — e sai com código PRÓPRIO: sob um código
        # só, uma violação de invariante chegaria ao monitoramento com a mesma cara de
        # "não havia imóvel para decidir", e ninguém iria olhar.
        return 6 if final.get("prontos", {}).get("crivo") is False else 4
    if rodada_id is not None:
        log.info(
            "rodada %s pendente de APROVAÇÃO (D-001) — o prazo da tácita é o parâmetro "
            "nº 10, nulo; quem o define abre o fluxo de aprovação com este id",
            rodada_id,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
