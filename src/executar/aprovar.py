"""Ponto de entrada da APROVAÇÃO da rodada de decisão (D-001).

A cadeia semanal do sistema é sexta → carga aplicada → segunda. O elo do meio é um
CARIMBO: `registro.rodada.aprovada_em`. Sem ele nada mais funciona, e o modo de
falhar é silencioso — `registro/acompanhamento.py::ultima_carga_aprovada` filtra por
`aprovada_em IS NOT NULL`, então enquanto ninguém carimba **toda** rodada de segunda
declara ausência de carga e sai pelo código de "insumo ausente", que o agendador
trata como no-op benigno. A rodada de sexta grava e entrega; a de segunda mede. Nada
entre as duas.

O MECANISMO já existia inteiro e testado — `grafo/aprovacao.py` (grafo separado, com
interrupção que sobrevive a reinício de processo num PostgresSaver real) e
`registro/leitura.py::marcar_aprovada`. O que não existia era CHAMADOR: nenhum
arquivo do repo invocava `construir_grafo_aprovacao` fora dos testes. Este módulo é
esse chamador, e só isso — nenhuma regra de decisão vive aqui.

## Por que a sexta não abre a aprovação sozinha

`executar/sexta.py` termina informando o `rodada_id` e para. O que dispara a
aprovação TÁCITA sozinha é o decurso do prazo, que é o parâmetro pendente nº 10 —
**nulo**. Nenhum comando aqui calcula prazo: quem invoca `tacita` está AFIRMANDO que
o prazo decorreu, e o Registro guarda `aprovada_por = "tácita"` justamente para que
essa afirmação fique distinguível de uma aprovação que o dono deu olhando a lista.

## O carimbo é único, e a guarda não é zelo abstrato

Reinvocar o grafo com o mesmo `rodada_id` numa thread JÁ concluída **não é no-op**:
o LangGraph reinicia do começo, reabre a interrupção, e a retomada seguinte chama o
sink outra vez (verificado, não deduzido). O segundo carimbo sobrescreveria
`aprovada_em` — que é ao mesmo tempo o início da janela que a segunda mede
(`janela_da_carga`) e a chave que elege a carga vigente (`ORDER BY aprovada_em
DESC`). Deslocaria a janela em dias e poderia promover uma decisão velha a carga
vigente, sem deixar rastro, porque o esquema não guarda o carimbo anterior.

Por isso a guarda é dupla e nas duas pontas: aqui, lendo o Registro antes de tocar o
grafo; e em `marcar_aprovada`, com `aprovada_em IS NULL` no WHERE — a que vale
quando o chamador for outro.

## `--em`: o instante é o da CARGA, não o do clique

`aprovada_em` é o proxy que o sistema tem para "a carga entrou no ar" (a carga é
manual e o sistema não publica nada — ver o cabeçalho de `registro/janelas.py`).
Aprovar na segunda uma carga aplicada na sexta, carimbando "agora", deslocaria a
janela de medição em três dias sem que nada acusasse. `--em` deixa declarar o
instante real; sem ele, o default é agora. Instante no futuro é recusado, e anterior
ao fim da própria rodada também — a carga não pode ter entrado no ar antes de a
lista existir.

## O que este módulo NÃO faz

**Não reprova.** `grafo/aprovacao.py` sabe representar a reprovação, mas
`registro.rodada` não a distingue de "ainda não decidida" — as duas deixam
`aprovada_em` nulo. Expor o comando daria ao dono a sensação de ter agido: o console
continuaria mostrando "Aprove a rodada N" para sempre, e a thread ficaria queimada.
Sob a D-001 a aprovação é TÁCITA (silêncio = aprovação), então "não aprovar" também
não é o mesmo que reprovar. É buraco de esquema, e está registrado em
`docs/decisoes.md` como pergunta ao dono — não resolvido aqui.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable, Iterator, Sequence
from contextlib import AbstractContextManager, contextmanager
from datetime import datetime
from enum import StrEnum
from typing import Any

import psycopg

from dados.registro.conexao import conectar, url
from dados.registro.leitura import JaAprovada, ler_rodada, marcar_aprovada
from grafo.aprovacao import aprovar_explicita, aprovar_tacita, construir_grafo_aprovacao

log = logging.getLogger("executar.aprovar")

# Códigos de saída. Os significados de 1, 2, 3 e 4 são os MESMOS da sexta e da
# segunda de propósito — o monitoramento lê o código de qualquer runner com o mesmo
# sentido. `5` (parâmetros) e `6` (veto do crivo) ficam RESERVADOS ao que já
# significam na sexta, mesmo não se aplicando aqui: reusá-los com outro sentido faria
# o mesmo número querer dizer duas coisas conforme o programa que saiu.
OK = 0
ESCRITA = 1  # falha ao gravar (Registro ou checkpointer)
# 2 = argparse (reservado, como nos outros runners)
FONTE = 3  # Postgres fora do ar, POSTGRES_URL ausente
NAO_APROVAVEL = 4  # não existe, não é de decisão, ou tem estado inaproveitável
VALOR_INVALIDO = 5  # o operador declarou um `--em` impossível (mesmo sentido do 5 da sexta)
JA_APROVADA = 7  # o carimbo já existe — recusa de RE-carimbo
FORA_DE_ORDEM = 8  # o carimbo poria a carga vigente no lugar errado
# Thread do grafo decidida SEM carimbo no Registro. Código próprio porque o
# monitoramento lê o número, e sob o 7 ("já aprovada") ele leria a causa errada:
# aqui NÃO há aprovação nenhuma no Registro — há um veredito que não chegou lá.
INCONSISTENTE = 9


class Recusa(Exception):
    """Guarda que reprovou, com o código que o monitoramento deve ver. Recusa não é
    incidente: a mensagem diz o que fazer, e o código distingue a causa."""

    def __init__(self, codigo: int, mensagem: str) -> None:
        super().__init__(mensagem)
        self.codigo = codigo


def thread_da_rodada(rodada_id: int) -> dict[str, Any]:
    """Chave da thread de aprovação. Uma por rodada: é o que faz a pausa de uma não
    interferir na de outra, e o que permite retomar num processo diferente do que
    abriu."""
    return {"configurable": {"thread_id": f"rodada-{rodada_id}"}}


def rodada_aprovada_mais_nova(conn: psycopg.Connection, rodada_id: int) -> int | None:
    """Maior id de rodada de decisão JÁ aprovada que seja mais nova que esta.

    Existe por causa de `ultima_carga_aprovada` (`ORDER BY aprovada_em DESC`): aprovar hoje
    uma rodada antiga lhe dá o carimbo mais recente e a promove a carga vigente,
    fazendo a segunda medir contra uma lista que foi substituída. O efeito é
    silencioso — nenhum erro, só o número errado."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT max(id) FROM registro.rodada "
            "WHERE tipo = 'decisao' AND aprovada_em IS NOT NULL AND id > %s",
            (rodada_id,),
        )
        linha = cur.fetchone()
    # `SELECT max(...)` sem GROUP BY sempre devolve uma linha; o que pode vir nulo é
    # a coluna. `int()` para casar com a função irmã, que já convertia.
    assert linha is not None
    return None if linha[0] is None else int(linha[0])


def carga_que_seguiria_vigente(
    conn: psycopg.Connection, rodada_id: int, quando: datetime
) -> int | None:
    """Qual rodada seria a carga vigente se ESTA fosse carimbada em `quando` — None
    se a vigente passaria a ser ela mesma.

    Existe porque a eleição da vigente é por `(aprovada_em, id)` e não por `id`
    (`ultima_carga_aprovada`: `ORDER BY aprovada_em DESC, id DESC`). Comparar ids,
    como a guarda fazia, deixava passar o caso que o `--em` desta mesma fatia tornou
    alcançável em dois comandos comuns: aprovar tarde a rodada 11, e depois aprovar
    a 12 com `--em` anterior ao carimbo da 11. A guarda por id passa (12 > 11), o
    carimbo entra, e a vigente CONTINUA sendo a 11 — a segunda mede a lista
    substituída, que é exatamente o dano que a guarda promete impedir, e sem aviso."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM registro.rodada "
            "WHERE tipo = 'decisao' AND aprovada_em IS NOT NULL "
            "AND (aprovada_em, id) > (%s::timestamptz, %s::bigint) "
            "ORDER BY aprovada_em DESC, id DESC LIMIT 1",
            (quando, rodada_id),
        )
        linha = cur.fetchone()
    return None if linha is None else int(linha[0])


def conferir(
    conn: psycopg.Connection,
    rodada_id: int,
    *,
    em: datetime | None,
    agora: datetime,
    fora_de_ordem: bool,
) -> datetime:
    """Todas as guardas, ANTES de tocar o grafo, e devolve o instante do carimbo.

    A ordem importa: as recusas mais específicas primeiro, para que a mensagem diga a
    causa real. Os estados aceitos são exatamente os que o console usa para montar a
    fila de pendentes hoje — `console/lib/registro.ts::rodadasAguardandoAprovacao`,
    `WHERE tipo = 'decisao' AND aprovada_em IS NULL AND estado IN ('completa',
    'degradada')` — para que ele nunca ofereça um cartão que este comando recusa.

    Nota sobre a recusa de ABORTADA: ela é hoje **inalcançável pelo caminho de
    produção**. O nó de persistência do grafo só grava rodadas não-abortadas, então
    uma rodada abortada não deixa nem o cabeçalho `rodada` — não há id para aprovar
    (`docs/decisoes.md`, consequência de persistência da G2a-wire). A guarda existe
    porque a pendência do dono sobre gravar cabeçalho de abortada segue aberta, e
    porque `estado` é `NULL`-ável no DDL. Declarado em vez de deixar parecer que o
    cenário é corrente."""
    resumo = ler_rodada(conn, rodada_id)
    if resumo is None:
        raise Recusa(NAO_APROVAVEL, f"rodada {rodada_id} não existe no Registro")
    if resumo["tipo"] != "decisao":
        raise Recusa(
            NAO_APROVAVEL,
            f"rodada {rodada_id} é de {resumo['tipo']}: só a rodada de DECISÃO é "
            "aprovada — a de segunda produz relatório, que não passa por aprovação",
        )
    if resumo["aprovada_em"] is not None:
        raise Recusa(
            JA_APROVADA,
            f"rodada {rodada_id} já foi aprovada em {resumo['aprovada_em']} por "
            f"{resumo['aprovada_por']!r}. O carimbo não é sobrescrito: ele é o início "
            "da janela que a segunda mede e a chave que elege a carga vigente",
        )
    if resumo["estado"] not in ("completa", "degradada"):
        raise Recusa(
            NAO_APROVAVEL,
            f"rodada {rodada_id} está {resumo['estado']!r}: não produziu lista para "
            "carregar. Aprová-la criaria uma carga vigente sem imóvel nenhum, e a "
            "segunda mediria contra ela",
        )
    quando = conferir_instante(em, agora=agora, fim=resumo["fim"], rodada_id=rodada_id)
    if fora_de_ordem:
        return quando
    # Duas maneiras opostas de a ordem sair errada, e as duas fazem a segunda medir a
    # lista errada. Precisam das duas guardas: nenhuma implica a outra.
    mais_nova = rodada_aprovada_mais_nova(conn, rodada_id)
    if mais_nova is not None:
        raise Recusa(
            FORA_DE_ORDEM,
            f"a rodada {mais_nova}, mais nova que a {rodada_id}, já está aprovada. "
            f"Aprovar a {rodada_id} agora lhe daria o carimbo mais recente e a "
            "promoveria a carga vigente — a segunda passaria a medir uma lista que já "
            "foi substituída. Se é mesmo o que você quer, repita com --fora-de-ordem",
        )
    seguiria = carga_que_seguiria_vigente(conn, rodada_id, quando)
    if seguiria is not None:
        raise Recusa(
            FORA_DE_ORDEM,
            f"carimbar a rodada {rodada_id} em {quando.isoformat()} NÃO a tornaria a "
            f"carga vigente: a rodada {seguiria} continuaria vigente, porque a eleição "
            "é pelo instante do carimbo, não pelo id. Você aprovaria esta lista e a "
            "segunda seguiria medindo a outra. Confira o --em; se é mesmo o que você "
            "quer, repita com --fora-de-ordem",
        )
    return quando


def conferir_instante(
    em: datetime | None, *, agora: datetime, fim: datetime | None, rodada_id: int
) -> datetime:
    """O instante do carimbo, normalizado ao fuso local e conferido.

    Naive vira aware pelo fuso LOCAL — a coluna é `timestamptz` e `janela_da_carga`
    normaliza ao fuso local antes de recortar; deixar naive faria o Postgres
    interpretar pelo fuso da SESSÃO, e a janela mudaria conforme quem conectou."""
    quando = agora if em is None else em
    if quando.tzinfo is None:
        quando = quando.astimezone()
    if quando > agora:
        raise Recusa(
            VALOR_INVALIDO,
            f"--em {quando.isoformat()} está no futuro: a carga não entrou no ar ainda, "
            "e a janela que a segunda mede começaria depois dos dias que ela vai medir",
        )
    if fim is not None and quando < fim:
        raise Recusa(
            VALOR_INVALIDO,
            f"--em {quando.isoformat()} é anterior ao fim da rodada {rodada_id} ({fim}): "
            "a carga não pode ter entrado no ar antes de a lista existir",
        )
    return quando


def sink(conn: psycopg.Connection, quando: datetime) -> Callable[[int, str], object]:
    """O SINK que o grafo chama ao aplicar o veredito: carimba no Registro.

    Usa a MESMA conexão que conferiu as guardas, e de propósito: entre ler
    `aprovada_em IS NULL` e carimbar existe uma janela em que outro processo poderia
    carimbar, e com duas conexões ela ficaria aberta. Numa só, a leitura e a escrita
    caem na mesma transação — e a guarda `aprovada_em IS NULL` do próprio UPDATE
    fecha o resto."""

    def aplicar(rodada_id: int, por: str) -> None:
        marcar_aprovada(conn, rodada_id, quando, por or None)
        log.info("rodada %s APROVADA em %s por %r", rodada_id, quando.isoformat(), por)

    return aplicar


class EstadoDaThread(StrEnum):
    """Em que ponto está a thread de aprovação, do ponto de vista de QUEM FALTA."""

    INEXISTENTE = "inexistente"  # ninguém abriu ainda
    AGUARDANDO = "aguardando"  # a interrupção está aberta: falta o dono decidir
    DECIDIDA = "decidida"  # o veredito já foi consumido — concluída OU travada no sink


def _estado_da_thread(grafo: Any, rodada_id: int) -> EstadoDaThread:
    """Classifica a thread pela PENDÊNCIA DE INTERRUPÇÃO, não por ter próximo nó.

    A distinção é correção, e a versão anterior errava. O LangGraph tem QUATRO
    estados aqui, e `bool(next)` colapsa dois deles que exigem tratamento oposto:

    | estado                     | values | next          | interrupts |
    |----------------------------|--------|---------------|------------|
    | inexistente                | {}     | ()            | 0          |
    | aguardando o dono          | parcial| ('aguardar',) | 1          |
    | TRAVADA no `aplicar`       | cheio  | ('aplicar',)  | 0          |
    | concluída                  | cheio  | ()            | 0          |

    A terceira acontece sempre que o sink levanta — a falha que este módulo diz
    temer. Sob `bool(next)` ela passava por "aguardando", o `Command(resume=...)` NÃO
    era consumido (não há interrupção pendente), e o nó `aplicar` rodava de novo com
    o veredito ANTERIOR. Efeito medido: `tacita` falha no sink, o dono roda
    `aprovar --por olavo`, e o Registro grava `aprovada_por = "tácita"`, com saída 0.
    Na direção oposta é pior — atribui a uma PESSOA uma aprovação que ela não deu.
    Justo o campo que a D-001 criou para distinguir tácita de explícita.

    `interrupts` responde a pergunta certa: "a interrupção está aberta esperando o
    dono?". Se não está e a thread existe, o veredito já foi consumido e o digitado
    seria ignorado — recusa, nunca aplicação silenciosa do antigo."""
    estado = grafo.get_state(thread_da_rodada(rodada_id))
    if estado.interrupts:
        return EstadoDaThread.AGUARDANDO
    if estado.values:
        return EstadoDaThread.DECIDIDA
    return EstadoDaThread.INEXISTENTE


def executar(
    rodada_id: int,
    *,
    retomada: dict[str, str] | None,
    em: datetime | None,
    agora: datetime,
    fora_de_ordem: bool,
    dry_run: bool,
    refazer: bool = False,
    conectar_registro: Callable[[], AbstractContextManager[psycopg.Connection]] = conectar,
    checkpointer_de: Callable[[str], Any] | None = None,
) -> int:
    """Confere, abre a pausa se preciso e (com `retomada`) carimba.

    `retomada` None é o comando `abrir`: deixa a rodada pendente com a pausa criada,
    sem decidir nada. As fontes são injetadas (`conectar_registro`, `checkpointer_de`)
    pelo mesmo motivo das outras rodadas — o runner é testável sem banco."""
    try:
        dsn = url()
    except RuntimeError as e:
        # Fail-fast de `conexao.url`, traduzido aqui e NÃO num `except RuntimeError`
        # ao redor de tudo: `RuntimeError` é a base genérica em uso corrente, e um
        # erro do sink ou do LangGraph sairia pelo código de "Postgres fora do ar",
        # que o monitoramento lê com esse sentido herdado da sexta e da segunda.
        log.error("%s", e)
        return FONTE
    try:
        if dry_run:
            with conectar_registro() as conn:
                quando = conferir(conn, rodada_id, em=em, agora=agora, fora_de_ordem=fora_de_ordem)
            log.info(
                "[dry-run] rodada %s APROVÁVEL; carimbo seria %s. Nada gravado.",
                rodada_id,
                quando.isoformat(),
            )
            return OK
        # O checkpointer PRIMEIRO, e por fora da conexão do Registro. Não é estilo:
        # `PostgresSaver.setup()` roda `CREATE INDEX CONCURRENTLY`, que espera TODA
        # transação concorrente do banco terminar — e o Registro e o checkpointer
        # dividem o mesmo Postgres por desenho. Com a conexão do Registro já aberta,
        # o índice espera por ela, a conexão espera o grafo, e o comando trava para
        # sempre. Travou de verdade (`idle in transaction` de um lado, `CREATE INDEX
        # CONCURRENTLY` do outro), e só apareceu ao simular o passo de CI.
        fabrica = checkpointer_de or _checkpointer_postgres
        with fabrica(dsn) as checkpointer, conectar_registro() as conn:
            quando = conferir(conn, rodada_id, em=em, agora=agora, fora_de_ordem=fora_de_ordem)
            grafo = construir_grafo_aprovacao(aplicar=sink(conn, quando), checkpointer=checkpointer)
            _decidir(grafo, checkpointer, rodada_id, retomada=retomada, refazer=refazer)
    except Recusa as e:
        # Recusa não é incidente: sai pelo código da causa, com a mensagem dizendo o
        # que fazer. Sair do `with` por exceção também desfaz a transação, então uma
        # recusa nunca deixa carimbo pela metade.
        log.error("%s", e)
        return e.codigo
    return OK


def _decidir(
    grafo: Any,
    checkpointer: Any,
    rodada_id: int,
    *,
    retomada: dict[str, str] | None,
    refazer: bool,
) -> None:
    """Abre a pausa se preciso e, havendo `retomada`, aplica o veredito."""
    estado = _estado_da_thread(grafo, rodada_id)
    if estado is EstadoDaThread.DECIDIDA:
        # O Registro já disse que não há carimbo (a guarda de `conferir` roda antes),
        # então o veredito não chegou ao Registro: ou o sink falhou, ou foi uma
        # reprovação, que o esquema não representa. Retomar aqui NÃO aplicaria o que
        # o dono digitou — aplicaria de novo o veredito antigo. Recusa, com saída.
        if not refazer:
            raise Recusa(
                INCONSISTENTE,
                f"a thread de aprovação da rodada {rodada_id} já foi decidida, mas o "
                "Registro não tem carimbo: o veredito não chegou lá (sink que falhou, "
                "ou reprovação, que o esquema não representa). Retomar agora aplicaria "
                "o veredito ANTIGO, não o que você digitou. Para descartar a thread e "
                "decidir de novo, repita com --refazer",
            )
        checkpointer.delete_thread(thread_da_rodada(rodada_id)["configurable"]["thread_id"])
        log.warning("thread de aprovação da rodada %s DESCARTADA (--refazer)", rodada_id)
        estado = EstadoDaThread.INEXISTENTE
    if estado is EstadoDaThread.INEXISTENTE:
        grafo.invoke({"rodada_id": rodada_id}, thread_da_rodada(rodada_id))
        log.info("aprovação da rodada %s ABERTA (aguardando decisão)", rodada_id)
    if retomada is not None:
        grafo.invoke(_comando(retomada), thread_da_rodada(rodada_id))


def _comando(retomada: dict[str, str]) -> Any:
    from langgraph.types import Command

    return Command(resume=retomada)


@contextmanager
def _checkpointer_postgres(dsn: str) -> Iterator[Any]:
    """PostgresSaver com `setup()` — o DDL do checkpointer é idempotente e vive no
    Postgres PRÓPRIO (invariante 2).

    Onde exatamente: as tabelas `checkpoints`, `checkpoint_writes`, `checkpoint_blobs`
    e `checkpoint_migrations` nascem em **`public`**, não num esquema dedicado — é o
    default da biblioteca, e é o que "esquemas separados" significa na prática aqui:
    `public` do checkpointer contra `registro` nosso. Verificado no banco, não
    suposto; o comentário anterior prometia uma separação mais forte do que existe."""
    from langgraph.checkpoint.postgres import PostgresSaver

    with PostgresSaver.from_conn_string(dsn) as saver:
        # A ordem (checkpointer antes do Registro) mata o auto-impasse, mas não a
        # CLASSE dele: `CREATE INDEX CONCURRENTLY` espera toda transação concorrente
        # do banco, inclusive de outro processo — uma sexta rodando, ou um `psql`
        # esquecido em `idle in transaction`. Sem teto, isso volta a travar sem erro e
        # sem fim. Com teto, vira exceção e o comando sai por um código.
        conexao = saver.conn
        if isinstance(conexao, psycopg.Connection):  # `from_conn_string` dá conexão, não pool
            with conexao.cursor() as cur:
                cur.execute("SET lock_timeout = '30s'")
                cur.execute("SET statement_timeout = '120s'")
        saver.setup()
        yield saver


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Aprovação da rodada de decisão (D-001): carimba `aprovada_em`."
    )
    sub = p.add_subparsers(dest="comando", required=True)

    def comum(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("rodada_id", type=int, help="id da rodada de decisão no Registro")
        sp.add_argument("--dry-run", action="store_true", help="confere as guardas e para")
        sp.add_argument(
            "--fora-de-ordem",
            action="store_true",
            help="permite aprovar mesmo havendo rodada MAIS NOVA já aprovada (a rodada "
            "aprovada agora vira a carga vigente)",
        )
        sp.add_argument(
            "--em",
            type=datetime.fromisoformat,
            help="instante em que a carga entrou no ar (AAAA-MM-DDTHH:MM). Default: "
            "agora. É o que a segunda usa como início da janela de medição. No "
            "subcomando `abrir` ele só participa da validação — abrir não carimba.",
        )

    def refazivel(sp: argparse.ArgumentParser) -> None:
        sp.add_argument(
            "--refazer",
            action="store_true",
            help="descarta a thread de aprovação já decidida e decide de novo. É a "
            "saída do código 9 (veredito que não chegou ao Registro). Só age quando o "
            "Registro NÃO tem carimbo — nunca produz carimbo duplo.",
        )

    comum(sub.add_parser("abrir", help="abre a pausa de aprovação, sem decidir"))
    ap = sub.add_parser("aprovar", help="aprovação EXPLÍCITA do dono")
    comum(ap)
    refazivel(ap)
    ap.add_argument("--por", required=True, help="quem aprovou (vai para `aprovada_por`)")
    tc = sub.add_parser(
        "tacita",
        help="aprovação TÁCITA por decurso de prazo (D-001). Quem invoca AFIRMA "
        "que o prazo decorreu: o prazo é o parâmetro nº 10, nulo, e nada aqui o calcula",
    )
    comum(tc)
    refazivel(tc)

    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    retomada: dict[str, str] | None = None
    if args.comando == "aprovar":
        retomada = aprovar_explicita(args.por)
    elif args.comando == "tacita":
        retomada = aprovar_tacita()

    try:
        return executar(
            args.rodada_id,
            retomada=retomada,
            em=args.em,
            agora=datetime.now().astimezone(),
            fora_de_ordem=args.fora_de_ordem,
            dry_run=args.dry_run,
            refazer=getattr(args, "refazer", False),
        )
    except JaAprovada as e:
        # A guarda de `marcar_aprovada`. Chegar aqui significa que o carimbo nasceu
        # ENTRE a conferência e o sink — corrida real, não erro de uso.
        log.error("%s", e)
        return JA_APROVADA
    except psycopg.OperationalError as e:
        log.error("Postgres próprio indisponível: %s", type(e).__name__)
        log.debug("causa completa", exc_info=True)
        return FONTE
    except Exception as e:
        # Só o TIPO para fora: a mensagem pode ecoar valor vindo do banco, e a saída
        # do agendador vira log capturado. Sai por ESCRITA mesmo quando a falha foi
        # na fase de LEITURA e nada chegou a ser gravado — as falhas de leitura
        # esperadas já saem por FONTE acima, e o que cai aqui é defeito, para o qual
        # "não confie que o carimbo aconteceu" é a leitura segura.
        log.error("falha ao carimbar a aprovação: %s", type(e).__name__)
        log.debug("causa completa", exc_info=True)
        return ESCRITA


if __name__ == "__main__":
    sys.exit(main())
