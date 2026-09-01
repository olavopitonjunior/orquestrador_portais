"""Registro na rodada de SEGUNDA: lê a carga APROVADA vigente e grava o apurado.

Fecha as duas metades que o domínio puro (`src/dominio/acompanhamento.py`) declarou
faltar (Spec §7.3):

1. **Qual carga medir**: não é "a última rodada de decisão", é a última rodada de
   decisão **APROVADA** (D-001: a planilha aprovada vigente). Rodada sem
   `aprovada_em` não é carga vigente — medir contra ela seria cobrar por uma
   seleção que ninguém autorizou a aplicar.
2. **Declarar a ausência**: quando não há carga aprovada, a rodada de segunda é
   REGISTRADA assim mesmo (tipo 'acompanhamento', estado 'abortada', com o motivo),
   em vez de sumir. "O relatório não é emitido **e a ausência é declarada**" — a
   §7.3 tem duas metades, e a segunda é esta.

Escrita SÓ no Postgres próprio (invariante 2); nada aqui toca o Newcore.
"""

from __future__ import annotations

from datetime import datetime

import psycopg
from psycopg.types.json import Json

from dominio.acompanhamento import Nivel, PosicaoPaga, ResultadoAcompanhamento


class SemCargaAprovadaVigente(Exception):
    """Não há rodada de decisão aprovada para servir de carga de referência."""


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
        assert linha is not None
        return int(linha[0])


def declarar_ausencia_de_carga(
    conn: psycopg.Connection, *, inicio: datetime, fim: datetime, motivo: str
) -> int:
    """Segunda metade da §7.3: sem carga aprovada, o relatório não é emitido — mas a
    rodada FICA REGISTRADA (estado 'abortada', com o motivo), para que a ausência
    seja visível ao gestor e à auditoria em vez de silenciosa. Não commita."""
    return _abrir_rodada(
        conn,
        inicio=inicio,
        fim=fim,
        estado="abortada",
        etapas={"monitor": False},
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
) -> int:
    """Grava a rodada de acompanhamento e o `resultado_carga` por imóvel (Spec §2.1).

    Uma transação só (o chamador controla o commit). Devolve o id da rodada de
    acompanhamento — a chave que o domínio puro deliberadamente não carrega, porque
    é esta camada que a conhece.

    NÃO grava a lista de leads sem tratamento: ela carrega PII (Spec §4.2) e vive na
    planilha, lida por gente. O Registro guarda a CONTAGEM por imóvel, que é o que a
    §2.1 pede em `resultado_carga` — menos dado pessoal parado no banco, mesma
    capacidade de auditoria.
    """
    assert not conn.autocommit, "o chamador controla a transação"
    etapas = {"monitor": True, "redator": True}
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
    return rodada_id


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
