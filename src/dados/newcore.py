"""Conexão de LEITURA ao MySQL do Newcore.

Invariante 1: o Newcore é somente leitura. A defesa em profundidade tem duas
camadas: (a) a credencial deve ser de um usuário MySQL SEM grant de escrita
(cinto — ver NEWCORE_MYSQL_USER no .env.tmpl, "usuário somente leitura"); e
(b) este módulo só expõe consulta, nunca escrita (suspensória). Se um dia
alguém adicionar um INSERT/UPDATE aqui, a camada (a) ainda o barra no servidor.

O 1045 "só o mysql2 autentica": **senha não-ASCII quebra o pymysql**. Ele força
`.encode('latin1')` em senha `str`, ignorando o `charset`; como o hash
caching_sha2_password do servidor é formado sobre a forma UTF-8, o byte que chega
não é o esperado e o servidor devolve 1045 — indistinguível de credencial errada
(resolvido em 31/08, ver docs/mapa-de-dados.md). Por isso a senha vai como
`bytes` UTF-8 — NÃO "simplifique" para str, ou o 1045 volta.

A regra acima vale para QUALQUER senha, e está escrita assim de propósito: este
repositório é público (D-012) e descrever o conteúdo da senha vigente é vazar
credencial em prosa — o que nenhum gitleaks pega, porque prosa não casa com padrão
de segredo. Guarda que executa: `tests/test_sem_vazamento_de_credencial.py`.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any

import pymysql
import pymysql.cursors

# Prazos de operação isolada (`docs/prazos.md`), constantes de módulo para um teste
# poder afirmá-los. `read_timeout` é por leitura do socket — na prática, por consulta
# (SELECT com ORDER BY materializa antes de enviar). A sexta faz ≥4 consultas: o pior
# caso com a fonte viva-mas-travada é N × LEITURA_MYSQL_S antes do código 3, com o
# batimento do trabalhador vivo o tempo todo (thread própria) — sem alarme falso.
LEITURA_MYSQL_S = 600
CONEXAO_MYSQL_S = 30


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
        # bytes UTF-8, NÃO str — ver o docstring do módulo (o 1045 do pymysql).
        "password": os.environ["NEWCORE_MYSQL_PASSWORD"].encode("utf-8"),
    }


@contextmanager
def conectar(database: str | None = None) -> Iterator[pymysql.connections.Connection]:
    """Abre uma conexão de leitura ao Newcore e a fecha ao sair.

    `database` seleciona o schema (`newcore` ou `newcore_bi`); None deixa sem
    schema padrão (as queries qualificam a tabela). Cursor devolve dicts.

    NÃO passe `client_flag` aqui. A guarda de prefixo de `consultar()` só barra
    `SELECT 1; DELETE ...` porque o pymysql NÃO habilita `MULTI_STATEMENTS` por
    padrão; ligar essa flag derrubaria a suspensória e deixaria só o cinto (a
    credencial read-only) segurando o invariante 1.
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
        # Por CONSULTA, não por rodada. Medido em 03/09/2026 à noite: a consulta de
        # candidatos levou 109 s numa base carregada (62 s a rodada inteira de manhã),
        # e duas execuções pelo trabalhador caíram em `OperationalError` neste teto —
        # a rodada abortava por prazo de driver, com a fonte viva. 600 s é teto de
        # operação isolada (`docs/prazos.md`): estourar continua sendo falha ruidosa
        # de fonte; só deixa de ser falha por variância normal da base.
        read_timeout=LEITURA_MYSQL_S,
        connect_timeout=CONEXAO_MYSQL_S,
    )
    try:
        yield conn
    finally:
        conn.close()


def consultar(
    sql: str,
    # `Mapping` também: o pymysql aceita dict para placeholders NOMEADOS
    # (`%(nome)s`), que é como a consulta da rodada de segunda parametriza.
    params: Sequence[Any] | Mapping[str, Any] | None = None,
    *,
    database: str | None = None,
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
        # Sem parâmetros, `execute` é chamado com UM argumento — nunca com `()`.
        # O pymysql aplica `query % args` sempre que `args` não é None, e uma tupla
        # vazia não escapa disso: qualquer `%` no texto do SQL vira especificador de
        # formato e estoura com TypeError. Não é hipótese — a primeira execução real
        # da sexta morreu assim, por causa de dois percentuais escritos em COMENTÁRIO
        # do próprio SQL ("94,8%", "0,176%"). O defeito é silencioso na revisão porque
        # o SQL está certo; quem erra é a ponte.
        if params:
            cur.execute(sql, params)
        else:
            cur.execute(sql)
        return list(cur.fetchall())
