"""Leitura do Registro (Spec §2). O Registro é a fonte da verdade (D-001): a
rodada de segunda mede contra a decisão registrada, nunca contra a planilha.

G2a expõe o mínimo para provar o round-trip e sustentar a rodada de segunda:
resumo da rodada e a contagem por nível. As leituras ricas (imóveis por posição,
janelas para a penalidade) crescem com o Monitor e o Decisor de produção.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, TypedDict

import psycopg


class ResumoDaRodada(TypedDict):
    """Resumo tipado da rodada. Tipado porque as guardas mais sensíveis do sistema
    leem daqui (`executar/aprovar.py` decide carimbar ou recusar): sob `dict` cru,
    `resumo["estdao"]` passaria pelo `mypy --strict` e a guarda sumiria em silêncio."""

    tipo: str
    estado: str | None
    etapas: dict[str, Any]
    motivo_degradacao: str | None
    aprovada_em: datetime | None
    aprovada_por: str | None
    posicoes_vazias_destaque: int | None
    fim: datetime | None


def ler_rodada(conn: psycopg.Connection, rodada_id: int) -> ResumoDaRodada | None:
    """Resumo da rodada: tipo, estado, etapas, aprovação. None se não existe."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT tipo, estado, etapas, motivo_degradacao, aprovada_em, aprovada_por, "
            "posicoes_vazias_destaque, fim FROM registro.rodada WHERE id = %s",
            (rodada_id,),
        )
        linha = cur.fetchone()
    if linha is None:
        return None
    tipo, estado, etapas, motivo, aprovada_em, aprovada_por, vazias, fim = linha
    return {
        "tipo": tipo,
        "estado": estado,
        "etapas": etapas,
        "motivo_degradacao": motivo,
        "aprovada_em": aprovada_em,
        "aprovada_por": aprovada_por,
        "posicoes_vazias_destaque": vazias,
        # `fim` sustenta a guarda de `executar/aprovar.py`: a carga não pode ter
        # entrado no ar antes de a lista existir. `inicio` NÃO entra: ninguém o lê, e
        # campo sem consumidor é peso que finge utilidade.
        "fim": fim,
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


class JaAprovada(ValueError):
    """Tentativa de RE-carimbar uma rodada que já tem `aprovada_em`."""


def marcar_aprovada(
    conn: psycopg.Connection, rodada_id: int, aprovada_em, aprovada_por: str | None = None
) -> None:
    """Carimba a aprovação na rodada (D-001) — sem verificação de conteúdo, só o
    estado. O prazo (parâmetro nº 10) é do chamador; aqui só se grava o instante
    que ele decidiu e `aprovada_por`, que distingue a aprovação tácita ("por
    prazo") da explícita (identificação do dono) — o "por prazo" de D-001. Não
    commita.

    **Carimba UMA vez.** `aprovada_em IS NULL` está no WHERE, e a segunda tentativa
    levanta `JaAprovada` em vez de sobrescrever. Não é zelo abstrato: `aprovada_em`
    é o início da janela que a rodada de segunda mede (`executar/segunda.py::
    janela_da_carga`) E a chave que elege a carga vigente (`registro/
    acompanhamento.py::ultima_carga_aprovada`, `ORDER BY aprovada_em DESC`). Sobrescrever
    desloca a janela em dias e pode promover uma decisão velha a carga vigente — em
    silêncio, porque nada no esquema guarda o carimbo anterior.

    O caminho que produz o re-carimbo é concreto, não hipotético: reinvocar o grafo
    de aprovação com o mesmo `rodada_id` numa thread JÁ concluída não é no-op — o
    LangGraph reinicia do começo, reabre a interrupção, e a retomada seguinte chama
    o sink outra vez (verificado). O ponto de entrada recusa antes de chegar aqui;
    esta guarda é a que vale quando o chamador for outro."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE registro.rodada SET aprovada_em = %s, aprovada_por = %s "
            "WHERE id = %s AND tipo = 'decisao' AND aprovada_em IS NULL",
            (aprovada_em, aprovada_por, rodada_id),
        )
        if cur.rowcount == 1:
            return
        # Não afetou linha: distinguir "já aprovada" de "não existe / não é decisão"
        # — as duas exigem ação oposta de quem opera, e uma mensagem só as esconderia.
        cur.execute(
            "SELECT aprovada_em, aprovada_por FROM registro.rodada "
            "WHERE id = %s AND tipo = 'decisao'",
            (rodada_id,),
        )
        linha = cur.fetchone()
    if linha is not None and linha[0] is not None:
        raise JaAprovada(
            f"rodada {rodada_id} JÁ aprovada em {linha[0]} por {linha[1]!r}: o carimbo "
            "não é sobrescrito — ele é o início da janela que a segunda mede e a chave "
            "que elege a carga vigente (D-001)"
        )
    raise ValueError(
        f"marcar_aprovada: nenhuma rodada de decisão com id={rodada_id} "
        "— aprovação é estado sensível (D-001)"
    )
