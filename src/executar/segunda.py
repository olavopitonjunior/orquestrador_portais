"""Ponto de entrada da rodada de SEGUNDA (acompanhamento) — Spec §1.

É o que faltava para o sistema ser executável por alguém além de quem o escreveu:
até aqui o fluxo existia e passava nos testes, mas só rodava por script solto e não
versionado. Aqui a fiação é commitada, reproduzível e auditável.

    uv run python -m executar.segunda [--destino DIR] [--dry-run] [--hoje AAAA-MM-DD]

## A janela é DERIVADA da carga, não recebida

A Spec §1 diz que o intervalo entre a aplicação da carga e o relatório é de três dias
corridos, e chama o recorte de deliberado: "mede o efeito da carga nova sem misturar
com a anterior". Aceitar a janela de quem chama deixaria esse recorte à mercê do
chamador — por isso ela sai de `aprovada_em` da carga medida. Os três dias são TEXTO
DA SPEC, não parâmetro pendente: o nº 8 é "horários exatos de execução", coisa
diferente, e segue nulo (não há horário embutido aqui; quem agenda é o SO).

## Fiação dos sinks — leia a limitação 6 de `grafo/segunda.py` antes de mexer

Falha de sink NÃO pode virar `declarar_ausencia`: o roteamento do grafo manda toda
ABORTADA para lá, e `declarar_ausencia` insere rodada incondicionalmente — logo
`registrar` bem-sucedido seguido de `entregar` falho gravaria DUAS rodadas para a
mesma segunda, corrompendo a auditoria que a §7.3 quer proteger. Por isso o
tratamento é por sink, aqui na borda:

- `registrar` falha → avisa (canal diferente do Postgres que caiu) e propaga.
- `entregar` falha com a rodada já gravada → avisa que a planilha não saiu, e
  propaga; a rodada EXISTE, então nada de declarar ausência.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta
from pathlib import Path

from dados.acompanhamento import coletar_leads
from dados.registro.acompanhamento import (
    declarar_ausencia_de_carga,
    gravar_acompanhamento,
    posicoes_da_carga,
    ultima_carga_aprovada,
)
from dados.registro.conexao import conectar
from dados.registro.leitura import ler_rodada
from dominio.acompanhamento import ResultadoAcompanhamento
from entrega.relatorio_segunda import escrever_relatorio
from grafo.estado import Estado
from grafo.segunda import FontesSegunda, SinksSegunda, construir_grafo_segunda

# Spec §1: três dias corridos entre a carga e o relatório. Texto da Spec, não
# parâmetro pendente — por isso é constante nomeada e não valor injetado.
#
# ATENÇÃO à contagem: são três dias de INTERVALO (sexta → segunda), o que em dias de
# calendário INCLUSIVOS dá quatro (sex, sáb, dom, seg). A janela é [D, D+3] e o filtro
# de leads é inclusivo nas duas pontas de propósito: o lead de segunda de manhã chegou
# DEPOIS da carga e ANTES do relatório, então é efeito dela. Cortar em D+2 perderia a
# manhã de segunda; contar até D+4 invadiria a carga seguinte. A imprecisão residual é
# a granularidade de DIA (a carga entra no ar numa hora), já declarada em
# `dados/acompanhamento.py`.
DIAS_DO_PERIODO = 3

log = logging.getLogger("rodada.segunda")


class SinkFalhou(RuntimeError):
    """Falha de ESCRITA (Registro ou planilha). Distinta de falha de fonte, que o
    grafo converte em aborto declarado — ver limitação 6 de `grafo/segunda.py`."""


def janela_da_carga(aprovada_em: datetime | None, hoje: date) -> tuple[date, date]:
    """Deriva [inicio, fim] da aprovação da carga (Spec §1).

    O fim nunca passa de `hoje`: medir dias que ainda não aconteceram inflaria o
    denominador com período inexistente. Se a carga for antiga, a janela continua
    sendo os três dias seguintes à aprovação — é o efeito DAQUELA carga que se mede.

    FUSO: `aprovada_em` vem como `timestamptz` e é normalizado ao fuso LOCAL antes de
    virar data, porque `hoje` também é local. Sem isso, a mesma carga daria janelas
    diferentes em máquinas com fusos diferentes, e uma carga aprovada de noite podia
    cair no dia seguinte — produzindo `fim < inicio` e transformando o relatório numa
    rodada abortada, sem ninguém perceber.
    """
    if aprovada_em is None:
        raise ValueError("carga sem `aprovada_em`: não é carga aprovada vigente (D-001)")
    if aprovada_em.tzinfo is not None:
        aprovada_em = aprovada_em.astimezone()  # ao fuso local, o mesmo de `hoje`
    inicio = aprovada_em.date()
    fim = min(inicio + timedelta(days=DIAS_DO_PERIODO), hoje)
    # Carga aprovada HOJE mais tarde do que o relógio de `hoje` sugere (ou relógio
    # atrasado): a janela degenera para o próprio dia em vez de inverter.
    return inicio, max(fim, inicio)


def _fontes() -> FontesSegunda:
    """Fontes injetadas. `carga_aprovada` MEMOIZA de propósito: o runner a consulta
    para derivar a janela e o grafo a consulta de novo para escolher a carga. Sem o
    cache, uma aprovação que caísse entre as duas leituras faria a janela sair da
    carga A e a medição rodar contra a carga B — a janela derivada da §1 perderia
    justamente a garantia que esta fatia existe para dar."""
    lido: list[int | None] = []

    def carga_aprovada() -> int | None:
        if not lido:
            with conectar() as conn:
                lido.append(ultima_carga_aprovada(conn))
        return lido[0]

    def posicoes(rodada_id: int):
        with conectar() as conn:
            return posicoes_da_carga(conn, rodada_id)

    return FontesSegunda(
        carga_aprovada=carga_aprovada,
        posicoes_da_carga=posicoes,
        coletar_leads=coletar_leads,
    )


def limitacao_de_janela(inicio: date, fim: date) -> list[str]:
    """Janela mais curta que os três dias da §1 é DADO PARCIAL — a rodada mediu menos
    do que o recorte manda, e a §7.2 exige a limitação visível na planilha. Sem isto,
    uma rodada que mediu zero dia decorrido sairia com o mesmo vocabulário de uma
    janela completa."""
    dias = (fim - inicio).days
    if dias >= DIAS_DO_PERIODO:
        return []
    return [
        f"janela TRUNCADA: {dias} de {DIAS_DO_PERIODO} dias corridos decorridos desde a "
        f"aprovação da carga ({inicio}); o relatório mede um período incompleto"
    ]


def _sinks(destino: Path, agora: datetime, *, dry_run: bool) -> SinksSegunda:
    def registrar(
        resultado: ResultadoAcompanhamento,
        estado: str,
        motivo: str | None,
        prontos: Mapping[str, bool],
    ) -> int:
        if dry_run:
            log.info("[dry-run] rodada NÃO gravada (estado=%s)", estado)
            return -1
        try:
            with conectar() as conn, conn.transaction():
                return gravar_acompanhamento(
                    conn,
                    resultado=resultado,
                    inicio=agora,
                    fim=datetime.now(),
                    estado=estado,
                    motivo_degradacao=motivo,
                    etapas=prontos,
                )
        except Exception as e:
            # NÃO declarar ausência: tentaria o mesmo banco que acabou de cair, e o
            # roteamento gravaria uma segunda rodada. Avisa por outro canal e propaga.
            avisar(f"FALHA ao gravar a rodada de segunda no Registro: {type(e).__name__}")
            raise SinkFalhou("falha ao gravar no Registro") from e

    def entregar(
        resultado: ResultadoAcompanhamento, estado: str, degradacoes: Sequence[str]
    ) -> object:
        if dry_run:
            log.info("[dry-run] relatório NÃO escrito (%d posições)", len(resultado.desempenho))
            return None
        try:
            caminhos = escrever_relatorio(resultado, estado, degradacoes, destino)
        except Exception as e:
            # A rodada JÁ está gravada aqui: declarar ausência seria mentir sobre uma
            # rodada que existe. Avisa que a planilha não saiu e propaga.
            avisar(f"Rodada gravada, mas o RELATÓRIO não foi escrito: {type(e).__name__}")
            raise SinkFalhou("falha ao escrever o relatório") from e
        log.info("relatório escrito: %s", ", ".join(p.name for p in caminhos))
        return caminhos

    def declarar_ausencia(motivo: str, prontos: Mapping[str, bool]) -> int:
        if dry_run:
            log.info("[dry-run] ausência NÃO registrada: %s", motivo)
            return -1
        try:
            with conectar() as conn, conn.transaction():
                return declarar_ausencia_de_carga(
                    conn, inicio=agora, fim=datetime.now(), motivo=motivo, etapas=prontos
                )
        except Exception as e:
            # Sem isto a §7.3 falharia nas DUAS metades de uma vez: o grafo chama
            # `avisar` DEPOIS de `declarar_ausencia`, então a exceção subiria antes
            # do aviso — nem registra, nem avisa, só um traceback.
            avisar(
                f"FALHA ao registrar a ausência de carga ({type(e).__name__}). "
                f"Motivo original: {motivo}"
            )
            raise SinkFalhou("falha ao declarar a ausência no Registro") from e

    def avisar(mensagem: str) -> None:
        """Aviso ao gestor da vitrine (Spec §7.3). Nesta fatia é o log e o arquivo
        `aviso.txt`; e-mail/console é fatia do Redator."""
        log.warning(mensagem)  # o log sai SEMPRE, primeiro
        if dry_run:
            return
        try:
            destino.mkdir(parents=True, exist_ok=True)
            with (destino / "aviso.txt").open("a", encoding="utf-8") as f:
                f.write(f"{datetime.now().isoformat()} {mensagem}\n")
        except OSError as e:
            # `avisar` é chamado de dentro de handlers de falha: se ele mesmo
            # levantar, troca a exceção original por outra e esconde a causa.
            log.error("não foi possível gravar aviso.txt (%s); o aviso está no log", e)

    return SinksSegunda(
        entregar=entregar,
        registrar=registrar,
        declarar_ausencia=declarar_ausencia,
        avisar=avisar,
    )


def executar(destino: Path, *, hoje: date | None = None, dry_run: bool = False) -> dict:
    """Roda a segunda de ponta a ponta e devolve o estado final do fluxo."""
    hoje = hoje or date.today()
    agora = datetime.now()
    fontes = _fontes()

    # A janela precisa da carga ANTES de o grafo rodar (o fluxo a recebe pronta).
    # Se não há carga aprovada, o próprio grafo declara a ausência — aqui só se
    # escolhe uma janela qualquer, que ele não vai usar.
    rodada_decisao_id = fontes.carga_aprovada()
    if rodada_decisao_id is None:
        inicio, fim = hoje, hoje
        log.warning("nenhuma carga aprovada: o grafo vai declarar a ausência (Spec §7.3)")
    else:
        with conectar() as conn:
            resumo = ler_rodada(conn, rodada_decisao_id)
        inicio, fim = janela_da_carga(resumo["aprovada_em"] if resumo else None, hoje)
        if inicio > hoje:
            # Truncamento é normal (carga recente); aprovação no FUTURO é relógio ou
            # fuso torto, e sairia rotulada como truncamento sem esta linha.
            log.warning(
                "carga aprovada em %s, à frente da data de referência %s — verifique o "
                "relógio/fuso da máquina; a janela sai degenerada",
                inicio,
                hoje,
            )
        log.info("carga aprovada %s; janela derivada %s → %s", rodada_decisao_id, inicio, fim)

    # A limitação de janela entra pelo estado inicial: o reducer de `degradacoes` a
    # soma às que o grafo descobrir, e `no_medir` a leva à planilha e ao Registro.
    degradacoes = limitacao_de_janela(inicio, fim) if rodada_decisao_id is not None else []
    for d in degradacoes:
        log.warning(d)

    # Subpasta por data: sem isto, a segunda seguinte APAGA o relatório da anterior —
    # o Registro guarda uma linha por rodada, mas a planilha (que é o artefato lido
    # por gente e o que a §7.2 quer auditável) guardaria só a última.
    destino_da_rodada = destino / f"{hoje:%Y-%m-%d}"
    grafo = construir_grafo_segunda(fontes, _sinks(destino_da_rodada, agora, dry_run=dry_run))
    return grafo.invoke(
        {
            "inicio_periodo": inicio,
            "fim_periodo": fim,
            "estado": Estado.EM_ANDAMENTO,
            "prontos": {},
            "degradacoes": degradacoes,
        }
    )


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Rodada de segunda (acompanhamento)")
    p.add_argument("--destino", type=Path, default=Path("saida/segunda"))
    p.add_argument("--dry-run", action="store_true", help="não grava nem escreve nada")
    p.add_argument(
        "--hoje",
        type=date.fromisoformat,
        help="data de referência (AAAA-MM-DD); default é hoje. Fixa a janela, "
        "tornando a rodada reproduzível.",
    )
    args = p.parse_args(argv)
    if args.hoje and args.hoje > date.today():
        # Reprocessar o PASSADO é legítimo; o futuro não — mediria dias que ainda
        # não aconteceram, desfazendo a guarda que `janela_da_carga` aplica.
        p.error("--hoje no futuro mediria dias que não aconteceram")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    try:
        final = executar(args.destino, hoje=args.hoje, dry_run=args.dry_run)
    except SinkFalhou as e:
        # O traceback encadeado carrega a exceção ORIGINAL, que pode ecoar valor de
        # lead — e a saída do agendador vira e-mail/log capturado. A causa completa
        # fica no log do servidor; para fora vai só a mensagem sanitizada.
        log.error("%s (detalhe no log do servidor)", e)
        log.debug("causa completa", exc_info=True)
        return 1

    estado = final.get("estado")
    log.info("ESTADO DA RODADA: %s", str(estado).upper())
    for d in final.get("degradacoes", []):
        log.info("  limitação: %s", d)
    if final.get("motivo"):
        log.info("  motivo: %s", final["motivo"])

    if estado != Estado.ABORTADA:
        return 0
    # Aborto tem DUAS causas com gravidades opostas, e o agendador precisa
    # distinguir: sem carga aprovada é insumo ausente (benigno); falha ao coletar ou
    # apurar é incidente — tratá-los igual faria uma queda do Newcore passar por
    # no-op. O código 2 fica RESERVADO ao argparse (`p.error` sai com 2): sem essa
    # reserva, um `--destinno` digitado errado no agendador sairia com o mesmo código
    # de "não havia carga" e o monitoramento registraria um no-op benigno.
    return 4 if final.get("prontos", {}).get("carga") is False else 3


if __name__ == "__main__":
    sys.exit(main())
