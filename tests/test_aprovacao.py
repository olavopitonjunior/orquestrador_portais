"""Testes do fluxo de aprovação (interrupção humana, D-001) — G2b/G3.

O núcleo do mecanismo (pausa → retoma → aplica) é provado com MemorySaver, sem
banco: o estado é leve e serializável, então o checkpointer em memória basta para
exercer interrupt/resume, o veredito e o sink. Um teste de integração à parte roda
com o PostgresSaver REAL e prova o que só o Postgres entrega: a pausa sobrevive a
um "reinício de processo" (uma segunda instância do grafo retoma o mesmo
thread_id). Pulado onde não há banco (CI), como os demais testes de I/O.

O sink de aprovação recebe `(rodada_id, aprovada_por)` — o "por prazo" de D-001;
os fakes abaixo registram a tupla para conferir o que chegou à borda de
persistência.
"""

from __future__ import annotations

import uuid

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from grafo.aprovacao import (
    Decisao,
    aprovar_explicita,
    aprovar_tacita,
    construir_grafo_aprovacao,
    reprovar,
)

CONF = {"configurable": {"thread_id": "rodada-42"}}
ESTADO = {"rodada_id": 42}


def _grafo(chamadas):
    """Grafo com um sink fake que registra `(rodada_id, aprovada_por)`."""
    return construir_grafo_aprovacao(
        aplicar=lambda rid, por: chamadas.append((rid, por)), checkpointer=MemorySaver()
    )


# --- construtores da retomada (unitário) -------------------------------------


def test_construtores_montam_o_contrato():
    assert aprovar_tacita() == {"decisao": "aprovada", "por": "tácita"}
    assert aprovar_explicita("dono") == {"decisao": "aprovada", "por": "dono"}
    assert reprovar("dono") == {"decisao": "reprovada", "por": "dono"}


def test_construtores_exigem_identificacao():
    with pytest.raises(ValueError):
        aprovar_explicita("")
    with pytest.raises(ValueError):
        reprovar("")


# --- a interrupção PAUSA e não aplica nada ------------------------------------


def test_invocar_pausa_na_interrupcao_sem_aplicar():
    chamadas = []
    saida = _grafo(chamadas).invoke(ESTADO, CONF)
    assert "__interrupt__" in saida  # pausou aguardando o dono
    assert chamadas == []  # nada tocou o Registro antes da aprovação
    # a interrupção carrega a chave da rodada para quem for decidir
    assert saida["__interrupt__"][0].value["rodada_id"] == 42


# --- retomada: aprovação tácita, explícita, reprovação ------------------------


def test_retomada_tacita_aplica_no_registro():
    chamadas = []
    grafo = _grafo(chamadas)
    grafo.invoke(ESTADO, CONF)  # pausa
    final = grafo.invoke(Command(resume=aprovar_tacita()), CONF)  # retoma
    assert final["decisao"] == Decisao.APROVADA
    assert final["aprovada_por"] == "tácita"
    assert chamadas == [(42, "tácita")]  # o sink carimbou a rodada 42, por prazo


def test_retomada_explicita_registra_quem_aprovou():
    chamadas = []
    grafo = _grafo(chamadas)
    grafo.invoke(ESTADO, CONF)
    final = grafo.invoke(Command(resume=aprovar_explicita("gestor.vitrine")), CONF)
    assert final["decisao"] == Decisao.APROVADA
    assert final["aprovada_por"] == "gestor.vitrine"
    assert chamadas == [(42, "gestor.vitrine")]  # tácita vs. explícita distinguíveis


def test_reprovacao_nao_toca_o_registro():
    chamadas = []
    grafo = _grafo(chamadas)
    grafo.invoke(ESTADO, CONF)
    final = grafo.invoke(Command(resume=reprovar("gestor.vitrine")), CONF)
    assert final["decisao"] == Decisao.REPROVADA
    assert chamadas == []  # reprovada NÃO persiste aprovação (limite declarado)


# --- validação do contrato da retomada + recuperação (fail-closed) ------------


def test_retomada_invalida_repausa_sem_aplicar():
    """Retomada fora do contrato NÃO aplica — reabre a interrupção (fail-closed),
    com o erro no payload, em vez de carimbar decisão malformada ou prender o
    thread."""
    chamadas = []
    grafo = _grafo(chamadas)
    grafo.invoke(ESTADO, CONF)
    saida = grafo.invoke(Command(resume={"decisao": "talvez"}), CONF)
    assert "__interrupt__" in saida  # repausou pedindo uma retomada válida
    assert "erro" in saida["__interrupt__"][0].value
    assert chamadas == []  # nada aplicado


def test_recupera_de_retomada_invalida():
    """Depois de uma retomada inválida (que só repausa), um resume VÁLIDO no mesmo
    thread retoma e aplica — 'o dono corrigiu e reenviou'."""
    chamadas = []
    grafo = _grafo(chamadas)
    grafo.invoke(ESTADO, CONF)
    grafo.invoke(Command(resume={"decisao": "talvez"}), CONF)  # inválida → repausa
    final = grafo.invoke(Command(resume=aprovar_tacita()), CONF)  # reenvio válido
    assert final["decisao"] == Decisao.APROVADA
    assert chamadas == [(42, "tácita")]  # recuperou e aplicou


# --- checkpointer é obrigatório ----------------------------------------------


def test_checkpointer_obrigatorio():
    with pytest.raises(ValueError, match="checkpointer"):
        construir_grafo_aprovacao(aplicar=lambda _r, _p: None, checkpointer=None)


# --- isolamento por thread_id (uma rodada não interfere na outra) -------------


def test_threads_independentes():
    chamadas = []
    grafo = _grafo(chamadas)
    c1 = {"configurable": {"thread_id": "rodada-1"}}
    c2 = {"configurable": {"thread_id": "rodada-2"}}
    grafo.invoke({"rodada_id": 1}, c1)  # pausa a rodada 1
    grafo.invoke({"rodada_id": 2}, c2)  # pausa a rodada 2
    grafo.invoke(Command(resume=aprovar_tacita()), c2)  # retoma só a 2
    assert chamadas == [(2, "tácita")]
    grafo.invoke(Command(resume=reprovar("dono")), c1)  # a 1 seguiu esperando
    assert chamadas == [(2, "tácita")]  # reprovada não aplica


# --- integração: a pausa sobrevive a "reinício" (PostgresSaver real) ----------


def test_pausa_persiste_no_postgres_e_retoma_apos_reinicio():
    from langgraph.checkpoint.postgres import PostgresSaver

    from dados.registro.conexao import url

    try:
        dsn = url()
    except Exception as e:  # POSTGRES_URL ausente → pula (CI)
        pytest.skip(f"POSTGRES_URL ausente: {e}")

    thread_id = f"teste-aprovacao-{uuid.uuid4()}"
    conf = {"configurable": {"thread_id": thread_id}}
    chamadas_2: list[tuple[int, str]] = []
    criou = False  # só limpa se o checkpoint chegou a ser criado (guarda o skip)
    try:
        # 1ª "vida do processo": constrói o grafo, invoca, PAUSA — nada aplicado.
        with PostgresSaver.from_conn_string(dsn) as cp1:
            try:
                cp1.setup()
            except Exception as e:  # sem banco/rede → pula (sem limpeza pendente)
                pytest.skip(f"Postgres próprio indisponível: {e}")
            criou = True
            g1 = construir_grafo_aprovacao(aplicar=lambda rid, por: None, checkpointer=cp1)
            saida = g1.invoke({"rodada_id": 7}, conf)
            assert "__interrupt__" in saida
        # 2ª "vida do processo": saver e grafo NOVOS, mesmo thread_id → a pausa
        # persistida no Postgres é retomada (é o que só o checkpointer durável dá).
        with PostgresSaver.from_conn_string(dsn) as cp2:
            g2 = construir_grafo_aprovacao(
                aplicar=lambda rid, por: chamadas_2.append((rid, por)), checkpointer=cp2
            )
            final = g2.invoke(Command(resume=aprovar_tacita()), conf)
            assert final["decisao"] == Decisao.APROVADA
            assert chamadas_2 == [(7, "tácita")]  # retomou no processo novo e aplicou
    finally:
        if criou:  # não tenta reconectar num banco que o skip já declarou fora
            with PostgresSaver.from_conn_string(dsn) as cpc:
                cpc.delete_thread(thread_id)  # não deixa checkpoint de teste no banco
