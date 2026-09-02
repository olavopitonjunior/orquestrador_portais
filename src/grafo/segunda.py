"""Fluxo da rodada de SEGUNDA (acompanhamento) como grafo LangGraph — Spec §1/§4.

  carga aprovada → medir (leads → apurar → registrar → entregar) → END
                 ↘ (sem carga, ou falha de FONTE) → declarar ausência + avisar → END

Fluxo SEPARADO do de sexta: a segunda não raspa nada, não decide nada e não tem
aprovação — só mede o que a carga produziu. Nenhuma regra vive aqui; os nós chamam
`dominio.acompanhamento` (puro) e as fontes/sinks injetados.

## Por que `no_medir` faz quatro coisas num nó só

A precondição de PII registrada em `docs/decisoes.md` (achado do auditor na M2) diz:
`ResultadoAcompanhamento` e `LeadDoPeriodo` carregam identidade de pessoa (Spec
§4.2), e o checkpointer do LangGraph **serializa o estado no Postgres** — pôr esses
objetos no estado reintroduziria no banco exatamente a PII que a M2 deliberadamente
não grava, e em silêncio.

A consequência de desenho é esta: os leads entram, são apurados e saem para os
sinks **dentro do mesmo nó**. A PII nunca toca o estado do grafo — não porque hoje
não há checkpointer (não há), mas para que ligar um amanhã não vaze nada. O estado
carrega só `PayloadModelo` (agregados, sem identidade), ids e contadores.

Não é a ÚNICA saída possível: dava para separar em nós e guardar o resultado num
cofre fora do estado (dict no closure do builder, chaveado por `thread_id`), com o
estado carregando só a chave — o mesmo movimento que `aprovacao.py` faz com o
`rodada_id`. Optou-se pelo nó único porque a segunda não tem pausa, então nada se
perde, e a garantia fica por construção em vez de por convenção. A parte decisória
foi extraída em funções puras (`monitor_pronto`, `degradacoes_da_rodada`,
`estado_terminal`) para o nó ficar fiação legível e testável sem grafo.

## Sinks injetados (I/O fora do domínio)

- `registrar(resultado, estado, motivo, prontos)` — o Registro, que guarda só a
  contagem por imóvel. Chamado ANTES da planilha (ver `no_medir`).
- `entregar(resultado, estado, degradacoes)` — a planilha (Spec §4.1), que É onde a
  lista nominal deve viver, lida por gente; recebe a limitação para declará-la.
- `declarar_ausencia(motivo)` e `avisar(mensagem)` — as duas metades da §7.3 quando
  não há carga aprovada: registrar a rodada abortada E avisar o gestor da vitrine.

## Limitações DECLARADAS (não em silêncio)

1. **A janela não é derivada da carga.** `inicio_periodo`/`fim_periodo` vêm de quem
   invoca, independentes de quando a carga medida foi aprovada. A Spec §1 chama o
   recorte de três dias de deliberado ("mede o efeito da carga nova sem misturar com
   a anterior"); aqui nada garante isso. Derivar a janela de `aprovada_em` é fatia de
   wiring — e nenhum prazo foi inventado no código (parâmetros nº 8/nº 11 seguem nulos).
2. **A D-020 tem produtor, com duas limitações declaradas.** `gravar_acompanhamento`
   acumula `registro.janela_destaque` na mesma transação (D-021) e devolve o
   histórico, que `com_historico` põe nas duas colunas da Spec §4.3. As limitações
   que sobram vêm em `acumulo.limitacoes` e vão à planilha E ao motivo gravado: os leads da
   janela são AMOSTRA (a segunda mede três dias de um ciclo de sete) e a contagem de
   semanas COMEÇA AGORA, sem o histórico anterior ao produtor. O consumidor da
   sexta já lê a tabela: a penalidade §6.4 incide sobre as janelas ENCERRADAS,
   desde que o limiar por nível (parâmetro nº 14) tenha sido declarado.
3. **ABORTADA é reusada para "não há carga aprovada".** A Spec §7.2 define abortada
   como "a coleta interna não ficou pronta" — a CONSEQUÊNCIA casa (não há entrega),
   o gatilho não está previsto para a segunda. Mesmo reuso declarado que a G1 fez
   para o veto do crivo; pendência do dono para uma revisão da §7.2.
4. **O "pronto" olha só o corretor gestor.** `sem_tratamento_sem_responsavel` conta
   ausência de `corretor_gestor`; o PRD fala em "corretor e gestor de distrito". Um
   lead com corretor e sem embaixador conta como pronto. Pendência do dono (é a mesma
   família da D-019: quem é o responsável cobrável).
5. **O estado é seguro quanto a PII, NÃO quanto a serde.** Medido: ele serializa
   hoje (msgpack) e a sentinela não aparece nos bytes — mas o LangGraph avisa
   "Deserializing unregistered type" para `Estado`, `Nivel`, `PosicaoPaga` e o
   `PayloadModelo`, e sob `LANGGRAPH_STRICT_MSGPACK=true` (anunciado como padrão
   futuro) eles voltam como **dict cru**, o que quebraria `apurar` numa retomada.
   Quando o checkpointer entrar: ou o estado vira primitivo (o padrão que
   `aprovacao.py` já adota de propósito), ou registram-se os módulos permitidos.
6. **O `except` cobre as LEITURAS, não as escritas.** Se `registrar` ou `entregar`
   levantar, a exceção escapa por `invoke()` — o gestor não é avisado, e a mensagem
   (que pode ter PII) escapa junto. ARMADILHA para quem for fechar isso: NÃO basta
   esticar o `try` até os sinks, porque `_rota_pos_medir` manda toda ABORTADA para
   `declarar_ausencia`, que insere rodada incondicionalmente — `registrar` OK seguido
   de `entregar` falho gravaria DUAS rodadas para a mesma segunda, corrompendo a
   auditoria que a §7.3 quer proteger. O tratamento certo é por sink: `registrar`
   falho → `avisar` (canal diferente do Postgres que caiu) e propagar; `entregar`
   falho com rodada já gravada → `avisar` que a planilha não saiu, e NUNCA
   `declarar_ausencia`, porque a rodada existe.
7. **Sem idempotência e sem higienização de traceback.** Com retomada, `no_medir`
   reexecuta inteiro e reentregaria a planilha. O motivo de falha já carrega só o
   TIPO da exceção (a mensagem pode ecoar payload de lead, e o LangGraph persiste
   `repr(exc)` nos writes de erro) — mas o log do servidor ainda vê tudo.
"""

from __future__ import annotations

import operator
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from functools import partial
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from dados.registro.acompanhamento import AcumuloDaJanela
from dominio.acompanhamento import (
    LeadDoPeriodo,
    PayloadModelo,
    PosicaoPaga,
    ResultadoAcompanhamento,
    apurar,
    com_historico,
    payload_para_modelo,
)
from grafo.estado import Estado, _merge_dict


class EstadoSegunda(TypedDict, total=False):
    """Estado do fluxo de segunda. SEM PII, por desenho (ver cabeçalho): nem
    `LeadDoPeriodo` nem `ResultadoAcompanhamento` entram aqui — só o recorte
    agregado `PayloadModelo`, ids e contagens."""

    inicio_periodo: date
    fim_periodo: date
    # produtos dos nós
    rodada_decisao_id: int | None  # a carga aprovada de referência
    posicoes: list[PosicaoPaga]  # imóvel + nível: sem identidade de pessoa
    payload: PayloadModelo | None  # agregados — o que pode ir a modelo
    rodada_id: int | None  # a rodada de acompanhamento gravada
    leads_descartados_sem_imovel: int
    # controle
    estado: Estado
    motivo: str | None
    prontos: Annotated[dict[str, bool], _merge_dict]
    degradacoes: Annotated[list[str], operator.add]


@dataclass(frozen=True)
class FontesSegunda:
    """Leituras injetadas: Registro (carga aprovada) e Newcore (leads)."""

    carga_aprovada: Callable[[], int | None]
    posicoes_da_carga: Callable[[int], Sequence[PosicaoPaga]]
    # devolve (leads, descartados_sem_imovel) — o descarte é contado, não sumido
    coletar_leads: Callable[[date, date], tuple[Sequence[LeadDoPeriodo], int]]


@dataclass(frozen=True)
class SinksSegunda:
    """Escritas/entregas injetadas. `entregar` e `registrar` recebem o resultado
    COM PII e são chamados de dentro de `no_medir` — nunca via estado.

    `entregar` recebe TAMBÉM o estado e as degradações: a Spec §7.2 exige que a
    rodada degradada entregue "com a limitação declarada de forma visível NA
    PLANILHA" — mandar isso só ao Registro deixaria quem lê a planilha sem saber
    que a rodada foi degradada e por quê.
    """

    entregar: Callable[[ResultadoAcompanhamento, str, Sequence[str]], object]
    # `registrar` devolve (rodada_id, histórico de janelas). O histórico vem de lá, e
    # não de uma leitura à parte, porque ele só existe DEPOIS de a mesma transação
    # atualizar a janela com os leads desta semana (D-021) — uma leitura separada
    # veria o estado anterior e o relatório diria "2 semanas" na terceira.
    registrar: Callable[
        [ResultadoAcompanhamento, str, str | None, Mapping[str, bool]],
        tuple[int, AcumuloDaJanela],
    ]
    declarar_ausencia: Callable[[str, Mapping[str, bool]], int]
    avisar: Callable[[str], object]


def monitor_pronto(resultado: ResultadoAcompanhamento) -> bool:
    """PRD: o pronto do Monitor exige as listas produzidas COM responsável nomeado.
    Pura e testável fora do grafo. NOTA declarada: olha só o corretor gestor; o PRD
    fala em "corretor e gestor de distrito" — pendência do dono (ver cabeçalho)."""
    return resultado.resumo.sem_tratamento_sem_responsavel == 0


def degradacoes_da_rodada(
    resultado: ResultadoAcompanhamento, descartados_sem_imovel: int
) -> list[str]:
    """As limitações da rodada, em texto, para a planilha e para o Registro. Pura:
    a mesma entrada dá a mesma lista, NA MESMA ORDEM (o motivo gravado depende
    dela — invariante 5)."""
    r = resultado.resumo
    degradacoes: list[str] = []
    if r.sem_tratamento_sem_responsavel:
        degradacoes.append(
            f"{r.sem_tratamento_sem_responsavel} lead(s) sem tratamento SEM responsável "
            "nomeado — pronto do Monitor não cumprido (PRD)"
        )
    if descartados_sem_imovel:
        degradacoes.append(
            f"{descartados_sem_imovel} lead(s) do período descartados por não terem "
            "imóvel de origem — fora do recorte de posição paga"
        )
    if r.sem_tratamento_sem_distribuicao:
        degradacoes.append(
            f"{r.sem_tratamento_sem_distribuicao} lead(s) sem data de distribuição na "
            "origem: a coluna 'tempo desde a distribuição' fica vazia"
        )
    return degradacoes


def estado_terminal(degradacoes: Sequence[str]) -> Estado:
    """COMPLETA só sem nenhuma limitação; qualquer uma degrada (Spec §7.2). Note que
    "monitor pronto" NÃO basta: a rodada pode ter o pronto e ainda degradar por
    descarte ou por distribuição ausente — foi o caso na primeira execução real."""
    return Estado.DEGRADADA if degradacoes else Estado.COMPLETA


def _aborto_declarado(motivo: str) -> dict:
    """Aborto que NÃO termina calado: o roteamento leva a `declarar_ausencia`, que
    registra a rodada e avisa o gestor (Spec §7.3). `carga` fica pronta porque a
    carga foi de fato encontrada — o que falhou foi medir."""
    return {"estado": Estado.ABORTADA, "prontos": {"monitor": False}, "motivo": motivo}


def no_carga_aprovada(estado: EstadoSegunda, *, fontes: FontesSegunda) -> dict:
    """Qual carga medir: a última rodada de decisão APROVADA (D-001). Sem ela, a
    rodada ABORTA — e a ausência será declarada pelo nó seguinte (Spec §7.3)."""
    rodada_decisao_id = fontes.carga_aprovada()
    if rodada_decisao_id is None:
        return {
            "estado": Estado.ABORTADA,
            "prontos": {"carga": False},
            "motivo": (
                "nenhuma rodada de decisão aprovada — não há planilha aprovada "
                "vigente para medir (Spec §7.3, D-001)"
            ),
        }
    posicoes = list(fontes.posicoes_da_carga(rodada_decisao_id))
    if not posicoes:
        return {
            "estado": Estado.ABORTADA,
            "rodada_decisao_id": rodada_decisao_id,
            "prontos": {"carga": False},
            "motivo": (
                f"a carga aprovada (rodada {rodada_decisao_id}) não tem posições "
                "registradas — sem imóvel em posição paga não há o que medir"
            ),
        }
    return {
        "rodada_decisao_id": rodada_decisao_id,
        "posicoes": posicoes,
        "prontos": {"carga": True},
    }


def no_medir(estado: EstadoSegunda, *, fontes: FontesSegunda, sinks: SinksSegunda) -> dict:
    """Lê os leads, apura, entrega a planilha e registra — TUDO neste nó.

    Os quatro passos moram juntos de propósito: os leads e o resultado carregam PII
    e não podem atravessar o estado do grafo (ver cabeçalho). Aqui eles nascem, são
    usados e saem para os sinks; ao estado volta só o recorte agregado.
    """
    posicoes = estado["posicoes"]
    inicio, fim = estado["inicio_periodo"], estado["fim_periodo"]
    rodada_decisao_id = estado["rodada_decisao_id"]
    # Invariante topológico (mesmo padrão de `fluxo.py`): o roteamento garante os
    # dois. Estreita o tipo sem `assert` (que evapora sob -O) e sem `type: ignore`.
    if rodada_decisao_id is None or not posicoes:
        raise RuntimeError(
            "no_medir sem carga: o roteamento deveria ter desviado para declarar_ausencia"
        )

    try:
        # Leitura de fonte: a mensagem pode ecoar payload de lead — só o TIPO sai.
        leads, descartados = fontes.coletar_leads(inicio, fim)
    except Exception as e:
        return _aborto_declarado(
            f"falha ao ler os leads da carga {rodada_decisao_id}: {type(e).__name__} "
            "(detalhe no log do servidor — a mensagem pode conter dado de lead)"
        )
    try:
        resultado = apurar(
            rodada_decisao_id=rodada_decisao_id,
            posicoes=list(posicoes),
            leads=list(leads),
            inicio_periodo=inicio,
            fim_periodo=fim,
        )
    except Exception as e:
        # Exceção do DOMÍNIO (`apurar`): as mensagens são estruturais por
        # construção — "imovel_id repetido na carga", "nível fora do vocabulário" —
        # sem PII. Aqui a mensagem PASSA, porque a §2.1 quer saber o porquê.
        return _aborto_declarado(f"falha ao apurar a carga {rodada_decisao_id}: {e}")

    pronto = monitor_pronto(resultado)
    novas = degradacoes_da_rodada(resultado, descartados)
    # As limitações que já vieram no estado (ex.: janela truncada, posta pelo runner)
    # contam TANTO para o estado terminal quanto para o que a planilha declara — a
    # §7.2 fala da rodada inteira, não só do que este nó descobriu. Ao estado volta
    # só `novas`, porque o reducer soma; aos sinks vai a lista COMPLETA.
    todas = [*estado.get("degradacoes", []), *novas]
    estado_final = estado_terminal(todas)
    motivo = "; ".join(todas) or None

    # `prontos` é derivado UMA vez, aqui, e viaja para o Registro junto — para não
    # existirem duas derivações independentes da mesma regra (a do grafo e a da
    # camada de escrita) que hoje coincidem só por coincidência de fórmula.
    # `redator` NÃO é afirmado: o sink não ter levantado exceção não prova que a
    # entrega saiu, e "pronto" é condição verificável (glossário).
    prontos = {**estado.get("prontos", {}), "monitor": pronto}

    # A PII sai daqui direto para os sinks. REGISTRO PRIMEIRO, planilha depois — e a
    # ordem é deliberada: as duas escritas não podem ser atômicas (a planilha vai
    # para o Drive), então a pergunta é QUAL metade solta é a silenciosa. Registrar
    # antes torna a falha VISÍVEL (rodada registrada, planilha ausente) em vez de
    # muda (planilha no Drive, nenhum rastro no Registro, e um rerun duplicando a
    # entrega). A planilha recebe estado e degradações porque a §7.2 exige a
    # limitação visível NELA, não só no Registro.
    rodada_id, acumulo = sinks.registrar(resultado, str(estado_final), motivo, prontos)
    # As duas colunas da §4.3 (semanas consecutivas, leads acumulados na janela) são
    # preenchidas AQUI, entre registrar e entregar: antes de registrar elas não
    # existem (a janela ainda não acumulou esta semana) e depois de entregar seria
    # tarde. `com_historico` é pura e não recomputa medição nenhuma — só preenche o
    # que estava declarado ausente.
    resultado = com_historico(resultado, acumulo.historico)
    # As limitações do ACÚMULO vão para a planilha, não para `todas`: elas não são
    # falha de fonte, são o que o produtor de janelas ainda não sabe (amostra de três
    # dias num ciclo de sete; contagem que começa agora). Somá-las ao estado tornaria
    # TODA segunda degradada enquanto durarem, e um estado que nunca varia deixa de
    # informar — mesma razão declarada para as limitações de fiação da sexta, e a
    # mesma pergunta aberta ao dono em docs/decisoes.md.
    sinks.entregar(resultado, str(estado_final), (*todas, *acumulo.limitacoes))

    return {
        "payload": payload_para_modelo(resultado),  # agregados: o que pode ir a modelo
        "rodada_id": rodada_id,
        "leads_descartados_sem_imovel": descartados,
        "estado": estado_final,
        "motivo": motivo,
        "prontos": prontos,
        "degradacoes": novas,  # só as novas: o reducer soma às que já estavam
    }


def no_declarar_ausencia(estado: EstadoSegunda, *, sinks: SinksSegunda) -> dict:
    """Spec §7.3, as DUAS metades: o relatório não é emitido **e a ausência é
    declarada** — registra a rodada abortada e avisa o gestor da vitrine. Sem isto,
    a segunda simplesmente não apareceria, que é o silêncio que a §7.3 proíbe."""
    motivo = estado.get("motivo") or "carga aprovada ausente"
    # Passa os `prontos` que o fluxo já derivou, em vez de o sink recompor um fixo:
    # a mesma derivação única do caminho feliz, agora também no de aborto.
    prontos = dict(estado.get("prontos") or {"monitor": False})
    rodada_id = sinks.declarar_ausencia(motivo, prontos)
    sinks.avisar(f"Relatório de segunda NÃO emitido: {motivo}")
    return {"rodada_id": rodada_id, "prontos": {"ausencia_declarada": True}}


def _rota_pos_carga(estado: EstadoSegunda) -> str:
    """Sem carga aprovada, a rodada não mede: vai declarar a ausência."""
    if estado.get("estado") == Estado.ABORTADA:
        return "declarar_ausencia"
    return "medir"


def _rota_pos_medir(estado: EstadoSegunda) -> str:
    """Se `medir` abortou (defesa), a ausência ainda tem de ser declarada — a §7.3
    não admite terminar calado."""
    if estado.get("estado") == Estado.ABORTADA:
        return "declarar_ausencia"
    return END


def construir_grafo_segunda(fontes: FontesSegunda, sinks: SinksSegunda, *, checkpointer=None):
    """Monta e compila o fluxo da rodada de segunda.

    `checkpointer` default None: a segunda não tem interrupção humana (não há
    aprovação a esperar), então roda de um fôlego. Se um dia ganhar checkpointer, o
    estado é seguro quanto a PII (ela nunca entra nele, por desenho) — mas NÃO quanto
    a serde: ver limitação 5 no cabeçalho antes de ligar um.
    """
    g = StateGraph(EstadoSegunda)
    g.add_node("carga", partial(no_carga_aprovada, fontes=fontes))
    g.add_node("medir", partial(no_medir, fontes=fontes, sinks=sinks))
    g.add_node("declarar_ausencia", partial(no_declarar_ausencia, sinks=sinks))

    g.add_edge(START, "carga")
    g.add_conditional_edges("carga", _rota_pos_carga, ["medir", "declarar_ausencia"])
    g.add_conditional_edges("medir", _rota_pos_medir, ["declarar_ausencia", END])
    g.add_edge("declarar_ausencia", END)
    return g.compile(checkpointer=checkpointer)
