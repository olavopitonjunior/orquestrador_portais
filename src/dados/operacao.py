"""A fila de operação: o console insere, o trabalhador reivindica e executa.

Separado de `dados/registro/` de propósito. Aquele pacote é o trilho de auditoria
da DECISÃO — sob a D-001 é a fonte da verdade sobre o que a rodada decidiu, e a
segunda mede contra ele. Isto aqui é quem clicou, quando, e o que o processo
imprimiu: operação, não decisão.

**Nenhuma função commita.** O chamador é dono da transação, como em
`registro/escrita.py` — é o que permite ao trabalhador criar o trabalho e o
primeiro evento no mesmo commit, sem uma janela em que um exista sem o outro.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import psycopg

TIPOS = ("sexta", "segunda", "canario", "full", "aprovar", "publicar")
EM_VOO = ("pendente", "executando")


class TrabalhoEmVoo(RuntimeError):
    """Já existe um trabalho deste tipo pendente ou executando.

    Não é erro de programação nem condição rara: é o duplo-clique no botão, e o
    caminho normal é a UI dizer "já está rodando" em vez de criar a segunda rodada.
    """


@dataclass(frozen=True)
class Trabalho:
    id: int
    tipo: str
    estado: str
    pedido_em: datetime
    pedido_por: str | None
    argumentos: Mapping[str, Any]
    iniciado_em: datetime | None = None
    terminado_em: datetime | None = None
    codigo_saida: int | None = None
    rodada_id: int | None = None
    pid: int | None = None


_NOMES = (
    "id",
    "tipo",
    "estado",
    "pedido_em",
    "pedido_por",
    "argumentos",
    "iniciado_em",
    "terminado_em",
    "codigo_saida",
    "rodada_id",
    "pid",
)
_COLUNAS = ", ".join(_NOMES)
# Qualificada, para o RETURNING do `reivindicar`: ali o UPDATE tem duas relações em
# escopo (a tabela e a CTE), as duas com `id`, e o Postgres recusa por ambiguidade.
_COLUNAS_T = ", ".join(f"t.{nome}" for nome in _NOMES)


def _para_trabalho(linha: Sequence[Any]) -> Trabalho:
    return Trabalho(
        id=linha[0],
        tipo=linha[1],
        estado=linha[2],
        pedido_em=linha[3],
        pedido_por=linha[4],
        argumentos=linha[5],
        iniciado_em=linha[6],
        terminado_em=linha[7],
        codigo_saida=linha[8],
        rodada_id=linha[9],
        pid=linha[10],
    )


def criar(
    conn: psycopg.Connection,
    tipo: str,
    *,
    pedido_por: str | None = None,
    argumentos: Mapping[str, Any] | None = None,
) -> int:
    """Enfileira um trabalho. Levanta `TrabalhoEmVoo` se já houver um do mesmo tipo.

    A guarda é do BANCO (índice parcial único), não deste código: duas requisições
    simultâneas do console passariam por qualquer verificação feita em Python antes
    do INSERT. Aqui a segunda simplesmente falha, e a falha é traduzida.
    """
    if tipo not in TIPOS:
        raise ValueError(f"tipo de trabalho desconhecido: {tipo!r}. Conhecidos: {list(TIPOS)}")
    # SAVEPOINT explícito, e só fora de autocommit.
    #
    # Uma violação de unicidade ABORTA a transação do Postgres, e traduzir a exceção
    # não desfaz isso: sem savepoint, a conexão fica envenenada e o próximo comando
    # estoura com `InFailedSqlTransaction`. Quebrava justamente o caminho que o
    # docstring acima chama de normal — o console captura `TrabalhoEmVoo` e então LÊ a
    # fila para dizer "já está rodando"; é a leitura que falhava.
    #
    # Por que SQL na mão e não `conn.transaction()`: no psycopg3 aquele gerenciador,
    # quando é o mais externo, faz COMMIT ao sair. Sob o fixture de teste (que isola
    # por transação e desfaz no fim) ele commitava as linhas no banco VIGENTE — e como
    # nascem `pendente`, seguravam o índice parcial e TRAVAVAM a fila daquele tipo.
    # Aconteceu: seis linhas vazaram e precisaram ser removidas à mão. É exatamente a
    # armadilha registrada em `tests/README.md`.
    #
    # Em autocommit não há savepoint a fazer — cada comando é sua própria transação, e
    # a violação não envenena nada. É o modo do trabalhador.
    #
    # Fronteira deliberadamente estreita: só `UniqueViolation` é desfeita. Qualquer
    # outra exceção do INSERT (queda de conexão, outro CHECK) propaga com a transação
    # do chamador abortada, como ficaria sem savepoint nenhum. Não é regressão — é que
    # essas são falhas de verdade, e engoli-las daria ao chamador uma conexão de
    # aparência sã sobre um erro que ninguém tratou.
    marcador = "criar_trabalho"
    with conn.cursor() as cur:
        if not conn.autocommit:
            cur.execute(f"SAVEPOINT {marcador}")
        try:
            cur.execute(
                "INSERT INTO operacao.trabalho (tipo, pedido_por, argumentos) "
                "VALUES (%s, %s, %s) RETURNING id",
                (tipo, pedido_por, json.dumps(dict(argumentos or {}))),
            )
            linha = cur.fetchone()
        except psycopg.errors.UniqueViolation as e:
            if not conn.autocommit:
                cur.execute(f"ROLLBACK TO SAVEPOINT {marcador}")
            raise TrabalhoEmVoo(
                f"já existe um trabalho '{tipo}' pendente ou executando. Um segundo "
                "criaria uma rodada duplicada: a gravação no Registro não tem chave "
                "natural de deduplicação, então duas execuções produzem duas rodadas "
                "indistinguíveis."
            ) from e
        if not conn.autocommit:
            cur.execute(f"RELEASE SAVEPOINT {marcador}")
    assert linha is not None
    return int(linha[0])


def reivindicar(conn: psycopg.Connection, tipos: Sequence[str] = TIPOS) -> Trabalho | None:
    """Toma UM trabalho pendente para si, atomicamente. None se não houver.

    `FOR UPDATE SKIP LOCKED` para que dois trabalhadores nunca peguem o mesmo — hoje
    só há um, mas a alternativa (ler e depois atualizar) seria uma corrida esperando
    o dia em que houver dois, e o sintoma seria uma rodada duplicada.

    `pid` é gravado aqui: é o que permite a uma tela dizer "está rodando no processo
    N" e a um humano decidir se o processo morreu.
    """
    with conn.cursor() as cur:
        cur.execute(
            "WITH proximo AS ("
            "  SELECT id FROM operacao.trabalho "
            "  WHERE estado = 'pendente' AND tipo = ANY(%s) "
            "  ORDER BY pedido_em, id LIMIT 1 FOR UPDATE SKIP LOCKED"
            ") "
            "UPDATE operacao.trabalho t SET estado = 'executando', iniciado_em = now(), pid = %s "
            "FROM proximo WHERE t.id = proximo.id "
            f"RETURNING {_COLUNAS_T}",
            (list(tipos), os.getpid()),
        )
        linha = cur.fetchone()
    return _para_trabalho(linha) if linha is not None else None


def concluir(
    conn: psycopg.Connection,
    trabalho_id: int,
    *,
    codigo_saida: int,
    rodada_id: int | None = None,
) -> None:
    """Fecha o trabalho. `codigo_saida` 0 é `ok`; qualquer outro é `falhou`.

    `rodada_id` fica nulo quando não houve rodada — em `--dry-run`, e sobretudo numa
    rodada ABORTADA, que não deixa NENHUMA linha no Registro. É por isso que o
    trabalho existe como entidade própria: sem ele, um aborto não teria onde ser
    contado.
    """
    estado = "ok" if codigo_saida == 0 else "falhou"
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE operacao.trabalho SET estado = %s, codigo_saida = %s, "
            "terminado_em = now(), rodada_id = COALESCE(%s, rodada_id) "
            "WHERE id = %s AND estado = 'executando'",
            (estado, codigo_saida, rodada_id, trabalho_id),
        )
        if cur.rowcount != 1:
            raise ValueError(
                f"trabalho {trabalho_id} não estava 'executando' — concluir duas vezes, ou "
                "concluir o que ninguém reivindicou, esconderia uma execução perdida"
            )


def evento(
    conn: psycopg.Connection,
    trabalho_id: int,
    texto: str,
    *,
    nivel: str = "info",
    no_grafo: str | None = None,
) -> None:
    """Uma linha do log da execução. É o que a tela de acompanhamento mostra."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO operacao.trabalho_evento (trabalho_id, nivel, no_grafo, texto) "
            "VALUES (%s, %s, %s, %s)",
            (trabalho_id, nivel, no_grafo, texto),
        )


def bater_ponto(conn: psycopg.Connection, nome: str = "principal") -> None:
    """Marca que o trabalhador está vivo. A UI compara com o relógio e avisa quando
    envelhece — sem isso, clicar em "rodar" com o processo fora do ar não produz
    nada nem explicação."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO operacao.trabalhador (nome, visto_em, pid) VALUES (%s, now(), %s) "
            "ON CONFLICT (nome) DO UPDATE SET visto_em = now(), pid = EXCLUDED.pid",
            (nome, os.getpid()),
        )


def ler_parametros(conn: psycopg.Connection, declaracao_id: int) -> str | None:
    """O TOML declarado, verbatim. None se a declaração não existe.

    O console guarda TEXTO, não caminho: o arquivo é materializado pelo trabalhador
    na hora de rodar. Assim a `origem` que viaja para a planilha e para o Registro
    carrega o id do trabalho, e o texto sobrevive mesmo se o arquivo sumir — o que
    importa num caso concreto, porque **rodada abortada não persiste nada**, nem
    cabeçalho, e sem esta tabela os parâmetros de um aborto se perderiam por completo.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT toml FROM operacao.parametros_declarados WHERE id = %s", (declaracao_id,)
        )
        linha = cur.fetchone()
    return str(linha[0]) if linha is not None else None


def ligar_declaracao(conn: psycopg.Connection, declaracao_id: int, trabalho_id: int) -> None:
    """Marca o ÚLTIMO trabalho que usou esta declaração. Rastreabilidade, não guarda.

    Último, e não "o" trabalho: o fluxo normal — declarar uma vez, rodar seco, rodar
    real — reusa a mesma declaração e esta escrita sobrepõe a anterior. Não há perda,
    porque a direção autoritativa é a outra: `trabalho.argumentos` guarda de qual
    declaração cada rodada saiu, e é ela que sustenta a `origem` que viaja para a
    planilha e para o Registro. Esta coluna é atalho de leitura, não fonte."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE operacao.parametros_declarados SET trabalho_id = %s WHERE id = %s",
            (trabalho_id, declaracao_id),
        )


def ler_trabalho(conn: psycopg.Connection, trabalho_id: int) -> Trabalho | None:
    with conn.cursor() as cur:
        cur.execute(f"SELECT {_COLUNAS} FROM operacao.trabalho WHERE id = %s", (trabalho_id,))
        linha = cur.fetchone()
    return _para_trabalho(linha) if linha is not None else None


def listar_trabalhos(conn: psycopg.Connection, limite: int = 50) -> list[Trabalho]:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {_COLUNAS} FROM operacao.trabalho ORDER BY pedido_em DESC, id DESC LIMIT %s",
            (limite,),
        )
        return [_para_trabalho(linha) for linha in cur.fetchall()]


def guardar_parametros(conn: psycopg.Connection, toml: str, *, por: str | None = None) -> int:
    """Guarda o TOML declarado pelo dono, verbatim. Append-only: é o versionamento.

    O TEXTO fica aqui, e o arquivo é materializado pelo trabalhador na hora de rodar.
    Assim os parâmetros sobrevivem mesmo quando a rodada aborta e não deixa linha no
    Registro — e é justamente na rodada abortada que saber com que números ela foi
    tentada tem mais valor.
    """
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO operacao.parametros_declarados (toml, por) VALUES (%s, %s) RETURNING id",
            (toml, por),
        )
        linha = cur.fetchone()
    assert linha is not None
    return int(linha[0])
