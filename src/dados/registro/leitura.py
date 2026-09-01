"""Leitura do Registro (Spec §2). O Registro é a fonte da verdade (D-001): a
rodada de segunda mede contra a decisão registrada, nunca contra a planilha.

G2a expõe o mínimo para provar o round-trip e sustentar a rodada de segunda:
resumo da rodada e a contagem por nível. As leituras ricas (imóveis por posição,
janelas para a penalidade) crescem com o Monitor e o Decisor de produção.
"""

from __future__ import annotations

import psycopg


def ler_rodada(conn: psycopg.Connection, rodada_id: int) -> dict | None:
    """Resumo da rodada: tipo, estado, etapas, aprovação. None se não existe."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT tipo, estado, etapas, motivo_degradacao, aprovada_em, posicoes_vazias_destaque "
            "FROM registro.rodada WHERE id = %s",
            (rodada_id,),
        )
        linha = cur.fetchone()
    if linha is None:
        return None
    tipo, estado, etapas, motivo, aprovada_em, vazias = linha
    return {
        "tipo": tipo,
        "estado": estado,
        "etapas": etapas,
        "motivo_degradacao": motivo,
        "aprovada_em": aprovada_em,
        "posicoes_vazias_destaque": vazias,
    }


def contagem_por_nivel(conn: psycopg.Connection, rodada_id: int) -> dict[str, int]:
    """Quantas posições cada nível recebeu na rodada (para conferir cotas)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT nivel, COUNT(*) FROM registro.decisao_imovel "
            "WHERE rodada_id = %s GROUP BY nivel",
            (rodada_id,),
        )
        return {nivel: n for nivel, n in cur.fetchall()}


def marcar_aprovada(conn: psycopg.Connection, rodada_id: int, aprovada_em) -> None:
    """Carimba a aprovação tácita por prazo na rodada (D-001) — sem verificação
    de conteúdo, só o estado. O prazo (parâmetro nº 10) é do chamador; aqui só
    se grava o instante que ele decidiu. Não commita."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE registro.rodada SET aprovada_em = %s WHERE id = %s AND tipo = 'decisao'",
            (aprovada_em, rodada_id),
        )
        if cur.rowcount != 1:
            raise ValueError(
                f"marcar_aprovada: nenhuma rodada de decisão com id={rodada_id} "
                f"(afetou {cur.rowcount} linhas) — aprovação é estado sensível (D-001)"
            )
