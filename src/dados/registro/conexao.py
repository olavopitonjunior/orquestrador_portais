"""Conexão com o PostgreSQL PRÓPRIO (o Registro, Spec §2).

Um único Postgres serve o Registro (esquema `registro`) e o checkpointer do
grafo (esquema separado, gerenciado pela biblioteca) — a mesma `POSTGRES_URL`.
Diferente do Newcore (somente leitura, `src/dados/newcore.py`), aqui a escrita
é o ponto: é a ÚNICA escrita do sistema (invariante 2), e acontece exclusivamente
neste banco, no esquema `registro`.

Fail-fast como o Newcore: `POSTGRES_URL` vem do ambiente (gerada de
`op://Personal/orquestrador_portais/POSTGRES_URL`); ausência é erro claro, nunca
um default com host/credencial embutido no repo.
"""

from __future__ import annotations

import os

import psycopg


def url() -> str:
    """A `POSTGRES_URL` do ambiente. Erro claro se ausente (fail-fast)."""
    valor = os.environ.get("POSTGRES_URL")
    if not valor:
        raise RuntimeError(
            "POSTGRES_URL ausente no ambiente. Gere o .env "
            "(op inject -i .env.tmpl -o .env) ou exporte a URL do Postgres próprio."
        )
    return valor


def conectar() -> psycopg.Connection:
    """Abre uma conexão com o Postgres próprio. O chamador é dono do ciclo de
    vida (use como context manager para o commit/rollback automático)."""
    return psycopg.connect(url())
