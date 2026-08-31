"""Conexão de LEITURA ao MySQL do Newcore.

Invariante 1: o Newcore é somente leitura. A defesa em profundidade tem duas
camadas: (a) a credencial deve ser de um usuário MySQL SEM grant de escrita
(cinto — ver NEWCORE_MYSQL_USER no .env.tmpl, "usuário somente leitura"); e
(b) este módulo só expõe consulta, nunca escrita (suspensória). Se um dia
alguém adicionar um INSERT/UPDATE aqui, a camada (a) ainda o barra no servidor.

O 1045 do U+00A8: a senha do RDS contém U+00A8 (¨), que em UTF-8 são dois bytes
e o hash caching_sha2_password do servidor foi criado sobre a forma UTF-8. O
pymysql força `.encode('latin1')` em senha `str`, mandando o byte errado → 1045
(mistério "só mysql2 autentica" resolvido em 31/08, ver docs/mapa-de-dados.md).
Por isso a senha é passada como `bytes` UTF-8 — NÃO "simplifique" para str, ou
o 1045 volta.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

import pymysql
import pymysql.cursors


def _config() -> dict[str, Any]:
    """Lê a configuração de conexão do ambiente (gerado por op inject)."""
    faltando = [
        v
        for v in (
            "NEWCORE_MYSQL_HOST",
            "NEWCORE_MYSQL_PORT",
            "NEWCORE_MYSQL_USER",
            "NEWCORE_MYSQL_PASSWORD",
        )
        if not os.environ.get(v)
    ]
    if faltando:
        raise RuntimeError(
            f"variáveis de conexão do Newcore ausentes: {', '.join(faltando)} "
            f"(gere o .env com `op inject -i .env.tmpl -o .env`)"
        )
    return {
        "host": os.environ["NEWCORE_MYSQL_HOST"],
        "port": int(os.environ["NEWCORE_MYSQL_PORT"]),
        "user": os.environ["NEWCORE_MYSQL_USER"],
        # bytes UTF-8, NÃO str — ver o docstring do módulo (1045 do U+00A8).
        "password": os.environ["NEWCORE_MYSQL_PASSWORD"].encode("utf-8"),
    }


@contextmanager
def conectar(database: str | None = None) -> Iterator[pymysql.connections.Connection]:
    """Abre uma conexão de leitura ao Newcore e a fecha ao sair.

    `database` seleciona o schema (`newcore` ou `newcore_bi`); None deixa sem
    schema padrão (as queries qualificam a tabela). Cursor devolve dicts.
    """
    cfg = _config()
    conn = pymysql.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=database,
        cursorclass=pymysql.cursors.DictCursor,
        # sem autocommit: irrelevante para leitura, e não é a defesa do
        # invariante 1 (a credencial read-only é). Deixado no default.
        read_timeout=120,
        connect_timeout=30,
    )
    try:
        yield conn
    finally:
        conn.close()


def consultar(
    sql: str, params: Sequence[Any] | None = None, *, database: str | None = None
) -> list[dict[str, Any]]:
    """Executa um SELECT e devolve as linhas como lista de dicts.

    APENAS leitura: o SQL deve ser um SELECT/SHOW. Este módulo não expõe
    execução de escrita; a credencial read-only é a garantia dura.
    """
    inicio = sql.lstrip().upper()
    if not inicio.startswith(("SELECT", "SHOW")):
        verbo = inicio.split()[0] if inicio else "?"
        raise ValueError(f"consultar() só aceita SELECT/SHOW (recebeu: {verbo})")
    # WITH é bloqueado: no MySQL 8 uma CTE pode terminar em DELETE/UPDATE
    # (`WITH x AS (...) DELETE ...`), então "começa com WITH" não garante leitura.
    # A defesa dura continua sendo a credencial read-only; esta guarda não abre
    # essa brecha. Nenhuma query interna usa CTE hoje.
    with conectar(database) as conn, conn.cursor() as cur:
        cur.execute(sql, params or ())
        return list(cur.fetchall())
