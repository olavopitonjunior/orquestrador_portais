"""Fluxo de APROVAÇÃO da rodada de decisão (interrupção humana, D-001) — G2b/G3.

Este é um grafo SEPARADO do fluxo de decisão (`src/grafo/fluxo.py`), e a separação
é o ponto. O checkpointer do LangGraph serializa TODO o estado a cada superstep;
o estado do fluxo de decisão carrega objetos de domínio não-serializáveis
(candidatos, ResultadoDecisao). Aqui o estado é DELIBERADAMENTE leve — só o
`rodada_id` (int) e o veredito da aprovação (strings) — então o checkpointer
(Postgres, produção) serializa trivialmente e a pausa sobrevive a reinício de
processo pelas "horas ou dias" que a aprovação pode levar (Ferramentas §2).

A decisão de sexta roda inteira e PERSISTE primeiro (G2a-wire, `no_registrar`),
devolvendo o `rodada_id`. Só então este fluxo abre a interrupção: a decisão
inteira já está no Registro, então a aprovação só precisa carregar a chave da
rodada. É o que torna o checkpointer viável sem escrever serializadores para o
domínio.

Contrato da retomada (`Command(resume=...)`): um dict `{"decisao": ..., "por": ...}`
onde `decisao` ∈ {"aprovada","reprovada"} e `por` identifica quem/como decidiu
("tácita" para a aprovação por decurso de prazo, ou a identificação do dono para a
explícita). Os construtores `aprovar_tacita()`, `aprovar_explicita(por)` e
`reprovar(por)` montam esse dict.

A autoridade de desenho desta fatia é D-001 (aprovação tácita por prazo; o
Registro é a fonte da verdade) + Ferramentas §6 (parâmetro nº 10) — a Spec §7/§8
é silente sobre aprovação humana.

Limites DECLARADOS desta fatia (honestos, não em silêncio):
- O PRAZO da aprovação tácita é o parâmetro nº 10 (NULO): NÃO vive aqui. Este
  módulo entrega só o MECANISMO (pausar → retomar). Quem conta o prazo e dispara
  a retomada tácita é a camada de agendamento (o Orquestrador / o agendador do SO
  / o botão do console) — fora desta fatia. Nenhum valor de prazo é inventado.
- O Registro carimba a APROVAÇÃO com o instante E o `aprovada_por` (via um
  adaptador que chama `marcar_aprovada`): "tácita" para o decurso de prazo ou a
  identificação do dono para a explícita — o "por prazo" de D-001 (migração 004).
- Uma REPROVAÇÃO é representável no estado do fluxo (`decisao="reprovada"`), mas o
  esquema `registro.rodada` não a distingue de "ainda não decidida" (ambas deixam
  `aprovada_em` NULO). Persistir a reprovação exigiria uma coluna de status —
  fatia futura candidata (nota em docs/decisoes.md).
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from functools import partial
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt


class Decisao(StrEnum):
    """Veredito da aprovação humana (D-001)."""

    APROVADA = "aprovada"
    REPROVADA = "reprovada"


class EstadoAprovacao(TypedDict, total=False):
    """Estado LEVE do fluxo de aprovação — só primitivos serializáveis, para o
    checkpointer não tropeçar em objeto de domínio (é o motivo de o fluxo ser
    separado do de decisão)."""

    rodada_id: int
    decisao: str  # Decisao.value (str crua p/ serde); ausente (total=False) = pendente
    aprovada_por: str  # "tácita" | identificação do dono | ""


def aprovar_tacita() -> dict[str, str]:
    """Retomada por decurso de prazo (D-001): silêncio do dono = aprovação. O
    PRAZO (nº 10, nulo) é de quem dispara isto, não deste módulo."""
    return {"decisao": Decisao.APROVADA.value, "por": "tácita"}


def aprovar_explicita(por: str) -> dict[str, str]:
    """Retomada por aprovação EXPLÍCITA do dono (ex.: botão do console)."""
    if not por:
        raise ValueError("aprovar_explicita exige a identificação de quem aprovou")
    return {"decisao": Decisao.APROVADA.value, "por": por}


def reprovar(por: str) -> dict[str, str]:
    """Retomada por REPROVAÇÃO explícita do dono."""
    if not por:
        raise ValueError("reprovar exige a identificação de quem reprovou")
    return {"decisao": Decisao.REPROVADA.value, "por": por}


def no_aguardar(estado: EstadoAprovacao) -> dict:
    """Abre a interrupção de aprovação e PAUSA o grafo (o checkpointer persiste o
    estado leve). Na retomada, `interrupt` devolve o dict de `Command(resume=...)`.

    Fail-closed E recuperável: uma retomada fora do contrato (não montada pelos
    construtores) NÃO aplica nada — reabre a interrupção pedindo uma válida, e a
    retomada válida seguinte prossegue ("o dono corrigiu e reenviou"). Nunca
    carimba decisão malformada, e nunca prende o thread num resume envenenado — o
    que um `raise` deixaria, pois o LangGraph reexecuta o mesmo resume anterior."""
    pergunta = {"rodada_id": estado["rodada_id"], "aguardando": "aprovação do dono (D-001)"}
    while True:
        resposta = interrupt(pergunta)
        if isinstance(resposta, dict) and resposta.get("decisao") in (
            Decisao.APROVADA.value,
            Decisao.REPROVADA.value,
        ):
            # str() explícito: normaliza mesmo se vier o membro StrEnum em vez do
            # .value — garante str pura no estado, à prova de serde em qualquer saver.
            return {
                "decisao": str(resposta["decisao"]),
                "aprovada_por": str(resposta.get("por", "")),
            }
        pergunta = {
            **pergunta,
            "erro": "retomada inválida — use aprovar_tacita/aprovar_explicita/reprovar",
        }


def no_aplicar(estado: EstadoAprovacao, *, aplicar: Callable[[int, str], object]) -> dict:
    """Aplica o veredito. Só a APROVAÇÃO toca o Registro — chama o SINK injetado
    `aplicar(rodada_id, aprovada_por)` (em produção, um adaptador que chama
    `marcar_aprovada`; no teste, um fake). A reprovação não persiste (ver limite
    declarado no cabeçalho). Sink como I/O injetado, igual ao `registrar` do fluxo
    de decisão: mantém o grafo testável sem banco."""
    if estado.get("decisao") == Decisao.APROVADA.value:
        aplicar(estado["rodada_id"], estado.get("aprovada_por", ""))
    return {}


def construir_grafo_aprovacao(
    *,
    aplicar: Callable[[int, str], object],
    checkpointer,
):
    """Monta e compila o fluxo de aprovação (interrupção humana).

    `aplicar` é o SINK que carimba a aprovação no Registro (injetado, como as
    `Fontes`/`registrar` do fluxo de decisão). `checkpointer` é OBRIGATÓRIO — sem
    ele não há pausa que sobreviva ao tempo de espera: em produção um PostgresSaver
    (a pausa dura horas/dias), no teste um MemorySaver (o estado leve é
    serializável nos dois). Invoca-se com `config={"configurable": {"thread_id":
    f"rodada-{rodada_id}"}}`; retoma-se com `Command(resume=aprovar_*(...))` no
    mesmo thread_id.
    """
    if checkpointer is None:
        raise ValueError(
            "construir_grafo_aprovacao exige um checkpointer: a interrupção de "
            "aprovação só é útil se a pausa persistir (PostgresSaver em produção)"
        )
    g = StateGraph(EstadoAprovacao)
    g.add_node("aguardar", no_aguardar)
    g.add_node("aplicar", partial(no_aplicar, aplicar=aplicar))
    g.add_edge(START, "aguardar")
    g.add_edge("aguardar", "aplicar")
    g.add_edge("aplicar", END)
    return g.compile(checkpointer=checkpointer)
