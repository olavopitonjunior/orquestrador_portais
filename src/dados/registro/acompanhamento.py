"""Registro na rodada de SEGUNDA: lê a carga APROVADA vigente e grava o apurado.

Entrega o MECANISMO das duas metades que o domínio puro
(`src/dominio/acompanhamento.py`) declarou faltar (Spec §7.3) — quem as LIGA é o nó
da rodada de segunda (fatia seguinte); mecanismo pronto ainda não é §7.3 cumprida:

1. **Qual carga medir**: não é "a última rodada de decisão", é a última rodada de
   decisão **APROVADA** (D-001: a planilha aprovada vigente). Rodada sem
   `aprovada_em` não é carga vigente — medir contra ela seria cobrar por uma
   seleção que ninguém autorizou a aplicar.
2. **Declarar a ausência**: quando não há carga aprovada, a rodada de segunda é
   REGISTRADA assim mesmo (tipo 'acompanhamento', estado 'abortada', com o motivo),
   em vez de sumir. "O relatório não é emitido **e a ausência é declarada**" — a
   §7.3 tem duas metades, e a segunda é esta.

Escrita SÓ no Postgres próprio (invariante 2); nada aqui toca o Newcore.

3. **Acumular o histórico de janelas**: `gravar_acompanhamento` atualiza
   `registro.janela_destaque` na MESMA transação (PRD, passo 5 do ciclo de segunda:
   "Registro | Resultado da carga | Acumulação do resultado por janela de destaque")
   e devolve o histórico resultante. É o que fecha a D-020 de fato: as duas colunas
   da Spec §4.3 sem fonte no Newcore ("semanas consecutivas em destaque" e "leads
   acumulados na janela atual") ficavam `None` INDEFINIDAMENTE, não "nas primeiras
   semanas" como a decisão previa, porque ninguém escrevia a tabela. A regra de
   abertura e fechamento é a D-021; ver `janelas.py`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

import psycopg
from psycopg.types.json import Json

from dados.registro.janelas import atualizar_janelas, limitacoes_do_acumulo
from dominio.acompanhamento import Nivel, PosicaoPaga, ResultadoAcompanhamento


@dataclass(frozen=True)
class AcumuloDaJanela:
    """O que a atualização das janelas produziu nesta rodada.

    `historico` preenche as duas colunas da §4.3 no relatório desta mesma segunda;
    `limitacoes` são o que o acúmulo ainda não sabe, e vão para a planilha E para o
    motivo gravado — as duas, porque planilha e Registro têm de dizer o mesmo.
    """

    historico: Mapping[int, tuple[int, int]]
    limitacoes: tuple[str, ...]


def _exigir_transacao(conn: psycopg.Connection) -> None:
    """A gravação é tudo-ou-nada; com autocommit a rodada poderia ficar
    meio-gravada (cabeçalho sem `resultado_carga`). `raise`, não `assert`:
    `assert` evapora sob `python -O` justamente onde a garantia importa."""
    if conn.autocommit:
        raise ValueError(
            "conexão em autocommit: a gravação da rodada precisa ser atômica "
            "(o chamador controla a transação)"
        )


def ultima_carga_aprovada(conn: psycopg.Connection) -> int | None:
    """Id da rodada de decisão APROVADA mais recente (a carga vigente, D-001), ou
    None se nenhuma foi aprovada. Só aprovação conta: `aprovada_em IS NOT NULL`."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM registro.rodada "
            "WHERE tipo = 'decisao' AND aprovada_em IS NOT NULL "
            "ORDER BY aprovada_em DESC, id DESC LIMIT 1"
        )
        linha = cur.fetchone()
    return int(linha[0]) if linha else None


def posicoes_da_carga(conn: psycopg.Connection, rodada_decisao_id: int) -> list[PosicaoPaga]:
    """As posições pagas que a carga colocou no ar, do Registro (fonte da verdade,
    D-001 — nunca da planilha). Ordem estável por (nível, imóvel)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT imovel_id, nivel FROM registro.decisao_imovel "
            "WHERE rodada_id = %s ORDER BY nivel, imovel_id",
            (rodada_decisao_id,),
        )
        return [PosicaoPaga(imovel_id=int(i), nivel=Nivel(n)) for i, n in cur.fetchall()]


def _abrir_rodada(
    conn: psycopg.Connection,
    *,
    inicio: datetime,
    fim: datetime | None,
    estado: str,
    etapas: dict[str, bool],
    motivo: str | None,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO registro.rodada (tipo, inicio, fim, estado, etapas, motivo_degradacao) "
            "VALUES ('acompanhamento', %s, %s, %s, %s, %s) RETURNING id",
            (inicio, fim, estado, Json(etapas), motivo),
        )
        linha = cur.fetchone()
        if linha is None:
            raise RuntimeError("INSERT ... RETURNING id não devolveu linha")
        return int(linha[0])


def declarar_ausencia_de_carga(
    conn: psycopg.Connection,
    *,
    inicio: datetime,
    fim: datetime,
    motivo: str,
    etapas: Mapping[str, bool] | None = None,
) -> int:
    """Segunda metade da §7.3: sem carga aprovada, o relatório não é emitido — mas a
    rodada FICA REGISTRADA (estado 'abortada', com o motivo), para que a ausência
    seja visível ao gestor e à auditoria em vez de silenciosa. Não commita."""
    return _abrir_rodada(
        conn,
        inicio=inicio,
        fim=fim,
        estado="abortada",
        etapas=dict(etapas if etapas is not None else {"monitor": False}),
        motivo=motivo,
    )


def gravar_acompanhamento(
    conn: psycopg.Connection,
    *,
    resultado: ResultadoAcompanhamento,
    inicio: datetime,
    fim: datetime,
    estado: str = "completa",
    motivo_degradacao: str | None = None,
    etapas: Mapping[str, bool] | None = None,
) -> tuple[int, AcumuloDaJanela]:
    """Grava a rodada de acompanhamento e o `resultado_carga` por imóvel (Spec §2.1).

    Uma transação só (o chamador controla o commit). Devolve o id da rodada de
    acompanhamento — a chave que o domínio puro deliberadamente não carrega, porque
    é esta camada que a conhece — e o HISTÓRICO de janelas resultante,
    `{imovel_id: (semanas_consecutivas, leads_acumulados)}`, que preenche as duas
    colunas da §4.3 no relatório desta mesma segunda (D-020/D-021). Devolver o
    histórico daqui, e não de uma leitura à parte, é o que garante que ele reflita a
    atualização que acabou de acontecer nesta transação.

    NÃO grava a lista de leads sem tratamento: ela carrega PII (Spec §4.2) e vive na
    planilha, lida por gente. O Registro guarda a CONTAGEM por imóvel, que é o que a
    §2.1 pede em `resultado_carga` — menos dado pessoal parado no banco, mesma
    capacidade de auditoria.
    """
    _exigir_transacao(conn)
    # O "pronto" do Monitor é DERIVADO, nunca afirmado: o PRD exige as listas "com
    # responsável nomeado", e o próprio domínio diz que `sem_tratamento_sem_
    # responsavel > 0` significa pronto NÃO cumprido. Gravar True incondicionalmente
    # faria o Registro afirmar pronto onde o PRD diz que não está — e `Gestor` está
    # 96,4% preenchido, então rodada real TEM lead sem responsável.
    # `redator` não é afirmado aqui: quem sabe se a entrega saiu é a fatia do Redator.
    #
    # O chamador PODE passar `etapas` (é o que o nó do grafo faz, com o pronto que
    # ele já derivou): assim existe UMA derivação da regra, não duas que coincidem
    # por coincidência de fórmula. Sem ele, deriva-se aqui — mesmo resultado.
    etapas = dict(
        etapas
        if etapas is not None
        else {"monitor": resultado.resumo.sem_tratamento_sem_responsavel == 0}
    )
    # "Completa" é definida no glossário como TODAS as etapas prontas. Com `monitor`
    # agora derivado, gravar `completa` sobre etapa não-pronta escreveria uma linha
    # que se contradiz — e o Registro é a fonte da verdade da auditoria.
    if estado == "completa" and not all(etapas.values()):
        raise ValueError(
            "rodada 'completa' exige todas as etapas prontas (monitor não está); "
            "use estado='degradada' e declare o motivo"
        )
    rodada_id = _abrir_rodada(
        conn,
        inicio=inicio,
        fim=fim,
        estado=estado,
        etapas=etapas,
        motivo=motivo_degradacao,
    )
    linhas = [
        (
            rodada_id,
            resultado.resumo.rodada_decisao_id,
            d.imovel_id,
            d.leads_gerados,
            d.leads_sem_tratamento,
        )
        for d in resultado.desempenho
    ]
    if linhas:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO registro.resultado_carga "
                "(rodada_acompanhamento_id, rodada_decisao_id, imovel_id, "
                " leads_gerados, leads_sem_tratamento) VALUES (%s, %s, %s, %s, %s)",
                linhas,
            )
    # O histórico de janelas é atualizado na MESMA transação (PRD, passo 5 do ciclo
    # de segunda: "Registro | Resultado da carga | Acumulação do resultado por janela
    # de destaque"). Transação única de propósito: uma rodada gravada cuja janela não
    # acumulou faria o relatório da semana seguinte contar uma permanência a menos, e
    # a §6.4 julgar a janela por um acumulado incompleto.
    acumulo = atualizar_janelas(
        conn,
        rodada_decisao_id=resultado.resumo.rodada_decisao_id,
        rodada_acompanhamento_id=rodada_id,
        desempenho=resultado.desempenho,
        # A data da CARGA, não o relógio da execução. `inicio_periodo` é derivado de
        # `aprovada_em` (Spec §1), então é quando a carga entrou no ar; `fim` aqui é
        # `datetime.now()`, e usá-lo deslocaria toda janela em alguns dias e
        # carimbaria um reprocessamento com a data de hoje.
        data_da_carga=resultado.resumo.inicio_periodo,
    )
    # As limitações do acúmulo entram no MOTIVO gravado, não só na planilha: sob a
    # D-001 o Registro é a fonte da verdade, e quem auditasse pelo banco não veria
    # que os leads da janela são amostra nem que a contagem começou agora. É a mesma
    # regra que a rodada de sexta já aplica às limitações de fiação. O UPDATE vem
    # depois do acúmulo de propósito: a limitação de história rasa é DERIVADA do
    # estado resultante, e computá-la antes descreveria a rodada anterior.
    limitacoes = limitacoes_do_acumulo(conn)
    motivos = [*([motivo_degradacao] if motivo_degradacao else []), *limitacoes]
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE registro.rodada SET motivo_degradacao = %s WHERE id = %s",
            ("; ".join(motivos) or None, rodada_id),
        )
    return rodada_id, AcumuloDaJanela(historico=acumulo, limitacoes=limitacoes)


def ler_resultado_carga(
    conn: psycopg.Connection, rodada_acompanhamento_id: int
) -> dict[int, tuple[int, int]]:
    """Por imóvel: (leads_gerados, leads_sem_tratamento) — para conferência."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT imovel_id, leads_gerados, leads_sem_tratamento "
            "FROM registro.resultado_carga WHERE rodada_acompanhamento_id = %s",
            (rodada_acompanhamento_id,),
        )
        return {int(i): (int(g), int(s)) for i, g, s in cur.fetchall()}
