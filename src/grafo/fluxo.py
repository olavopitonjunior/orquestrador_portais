"""Fluxo da rodada de decisão (sexta) como grafo LangGraph.

Liga o caminho DETERMINÍSTICO já pronto como nós (Spec §5, ordem da sexta):

  Coletor Interno → (Analista de Perfil ∥ Coletor Externo) → Decisor
  → crivo (gate de "pronto" da decisão, D-017) → Redator → finalizar
  → registrar (persiste no Registro; só rodada não-abortada, sink injetado — G2a-wire)

Cada nó chama um módulo já testado e escreve seu produto e seu "pronto" no
estado; nenhuma regra de decisão vive aqui (invariante 4 — o domínio é puro e
não importa langgraph; este módulo é a única casa da orquestração). A G1 compila
SEM checkpointer e roda o caminho uma vez: o checkpointer (Postgres) exige uma
estratégia de serialização dos objetos de domínio no estado — fica na G2, junto
do Registro. A aprovação humana (interrupção, que depende do checkpointer) e o
retry do Orquestrador (parâmetro nº 4, nulo) são fatias próprias.

Limitações declaradas (honestas quanto ao estado, Spec §7.2):
- Coletor Externo (G4): quando `fontes.coletar_externo`/`parametros_externo` são
  injetados, lê a saída do raspador e, passando as portas (amarração, idade), o
  desempenho de portal (F3) entra e a rodada pode ser COMPLETA; sem eles, segue
  STUB (DEGRADADA, ausência declarada). A "reserva" da coleta velha (Spec §7.3)
  ainda não é reusada — coleta fora da janela degrada.
- Sem modelo: o Analista de Perfil roda por contagem (o determinístico da Spec
  §6.2) e o Redator não gera resumo por modelo aqui.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial

from langgraph.graph import END, START, StateGraph

from dados.coletor_externo import ParametrosExterno, avaliar_coleta
from dominio.auditoria import ItemAuditavel, auditar
from dominio.perfil import perfis_de_conversao
from grafo.estado import Estado, EstadoRodada, Fontes, estado_final
from piloto.decisao import ParametrosDecisao, decidir


def no_coletor_interno(estado: EstadoRodada, *, fontes: Fontes) -> dict:
    """Lê o estoque elegível e as dimensões. PRONTO: há estoque. Sem estoque a
    rodada ABORTA (Spec §7.2: sem estoque não há decisão)."""
    candidatos, penalizaveis = fontes.coletar_interno()
    dims = fontes.coletar_dimensoes()
    if not candidatos:
        return {
            "estado": Estado.ABORTADA,
            "prontos": {"coletor_interno": False},
            "motivo_aborto": "coleta interna vazia — sem estoque, sem decisão (Spec §7.2)",
        }
    return {
        "candidatos": list(candidatos),
        "penalizaveis": {p.imovel_id: p for p in penalizaveis},
        "dims": dict(dims),
        "prontos": {"coletor_interno": True},
    }


def no_analista_perfil(estado: EstadoRodada, *, fontes: Fontes) -> dict:
    """Descobre os perfis de conversão por contagem (Spec §6.2, determinístico).
    PRONTO: ao menos um perfil robusto. Sem robustez a priorização opera sem o
    fator, registrado como degradação (Spec §7.3), não aborta."""
    vendas, _descartadas = fontes.coletar_vendas()
    perfis = perfis_de_conversao(vendas)
    robusto = any(not p.fragil for p in perfis)
    saida: dict = {"perfis": perfis, "prontos": {"perfil": robusto}}
    if not robusto:
        saida["degradacoes"] = [
            "perfil de conversão sem evidência robusta — priorização sem o fator (Spec §7.3)"
        ]
    return saida


def no_coletor_externo(
    estado: EstadoRodada,
    *,
    fontes: Fontes,
    parametros_externo: ParametrosExterno | None,
) -> dict:
    """Coletor Externo (G4): lê a saída do raspador e decide se a performance de
    portal entra no ranking (F3, Spec §7.3).

    Sem `coletar_externo`/`parametros_externo` injetados (esqueleto), continua
    STUB: sem raspagem, rodada DEGRADADA nesse fator. Com eles, `avaliar_coleta`
    aplica as portas (estado ok, amarração ≥ limiar nº 7, idade ≤ máxima nº 5) e,
    passando, compõe o sinal F3 por imóvel; falhando qualquer porta, o desempenho
    não entra e a degradação é declarada com o motivo — a rodada não é COMPLETA."""
    if fontes.coletar_externo is None or parametros_externo is None:
        return {
            "externo_presente": False,
            "prontos": {"externo": False},
            "degradacoes": [
                "Coletor Externo não executado (esqueleto, sem raspagem): "
                "desempenho de portal ausente — rodada DEGRADADA nesse fator"
            ],
        }
    coleta = fontes.coletar_externo()
    alvo = [c.imovel_id for c in estado["candidatos"]]
    r = avaliar_coleta(coleta, alvo, parametros_externo, estado["data_referencia"])
    if r.entra:
        return {
            "externo_presente": True,
            "desempenho_por_imovel": dict(r.desempenho_por_imovel),
            # Sobem MESMO no sucesso: a Spec §3.1 exige os dois na aba de resumo, e
            # antes eles só existiam embutidos no motivo da rejeição — a rodada
            # completa era justamente a que não tinha os números obrigatórios.
            "externo_taxa_amarracao": r.taxa_amarracao,
            "externo_idade_dias": r.idade_dias,
            "prontos": {"externo": True},
        }
    return {
        "externo_presente": False,
        "externo_taxa_amarracao": r.taxa_amarracao,
        "externo_idade_dias": r.idade_dias,
        "prontos": {"externo": False},
        "degradacoes": [f"Coletor Externo: {r.motivo}"],
    }


def no_decisor(estado: EstadoRodada, *, parametros: ParametrosDecisao) -> dict:
    """Decisor (determinístico, invariante 4): elegibilidade → ranking → cotas →
    relaxamento, via a costura já testada. PRONTO: produziu o resultado."""
    resultado = decidir(
        estado["candidatos"],
        estado["penalizaveis"],
        estado["dims"],
        estado["perfis"],
        parametros,
        estado["data_referencia"],
        desempenho_por_imovel=estado.get("desempenho_por_imovel"),
    )
    return {"resultado": resultado, "prontos": {"decisor": True}}


def no_crivo(estado: EstadoRodada) -> dict:
    """Crivo de auditoria camada 1 (D-017): gate de PRONTO da decisão.

    Se veta, a decisão NÃO fica pronta e a rodada é ABORTADA — não se entrega
    uma seleção que viola critério objetivo (cota, piso, relaxamento em super):
    "etapa que não cumpre pronto não entrega para a seguinte" (glossário). O
    roteamento pós-crivo (`_rota_pos_crivo`) desvia do Redator nesse caso.
    NOTA para o dono (lacuna da Spec §7.2, revisão da G1): a §7.2 só prevê
    ABORTADA para coleta interna vazia; aqui reusamos ABORTADA pela CONSEQUÊNCIA
    (sem entrega), com o motivo distinguindo veto-de-integridade de estoque-vazio
    — a §7.2 pode ganhar um estado próprio numa revisão.
    """
    resultado = estado["resultado"]
    if resultado is None:  # invariante topológico: crivo só roda após o decisor
        raise RuntimeError("no_crivo sem resultado: o decisor deveria ter rodado antes")
    precos = {c.imovel_id: c.preco for c in estado["candidatos"]}
    recuperados = {rec.imovel_id for rec in resultado.relaxamento.recuperados}
    # `elegivel` é derivado do proxy `nota_super_destaque is not None`: em
    # `decisao.py` todo elegível recebe nota_super (float) e só o reprovado
    # recuperado recebe None. Acoplamento declarado ao contrato de DetalheImovel;
    # se um dia um elegível abaixo do piso vier com nota_super None, este proxy
    # precisa virar um campo explícito de elegibilidade (registrado como dívida).
    itens = {
        iid: ItemAuditavel(
            imovel_id=iid,
            preco=precos.get(iid, 0),
            nota_super=det.nota_super_destaque,
            nota_destaque=det.nota_destaque,
            elegivel=det.nota_super_destaque is not None,
            veio_de_relaxamento=iid in recuperados,
        )
        for iid, det in resultado.detalhes.items()
    }
    veredito = auditar(resultado.alocacao, itens)
    saida: dict = {"veredito": veredito, "prontos": {"crivo": veredito.pronta}}
    if not veredito.pronta:
        codigos = ", ".join(sorted({v.codigo for v in veredito.violacoes}))
        saida["estado"] = Estado.ABORTADA
        saida["motivo_aborto"] = (
            f"crivo VETOU a decisão ({len(veredito.violacoes)} violações: {codigos}) — "
            "seleção viola critério objetivo, sem entrega (não é estoque vazio)"
        )
        saida["degradacoes"] = [f"crivo vetou a decisão: {codigos}"]
    return saida


def no_redator(estado: EstadoRodada) -> dict:
    """Redator — PRONTO: há resultado a serializar. Na G1 não gera resumo por
    modelo; a planilha é serializada pelo runner (entrega.planilha_piloto), já
    testada. Aqui só se registra o pronto da entrega."""
    return {"prontos": {"redator": estado.get("resultado") is not None}}


def no_finalizar(estado: EstadoRodada) -> dict:
    """Deriva o estado terminal da rodada (completa/degradada/abortada)."""
    return {"estado": estado_final(estado)}


def no_registrar(estado: EstadoRodada, *, registrar: Callable[[EstadoRodada], object]) -> dict:
    """Persiste a rodada no Registro chamando o SINK injetado (G2a-wire). Só roda
    em rodada não-abortada (pelo roteamento) — que tem `resultado` válido; não se
    registra seleção abortada por veto nem rodada sem estoque.

    O sink é injetado como as `Fontes`: em produção grava no Postgres (carimba os
    timestamps e serializa os parâmetros — I/O, fora do estado determinístico, e
    controla a transação); no teste, um fake que só registra a chamada. Assim o
    grafo segue testável sem banco e o domínio permanece puro. O contrato do sink:
    o `estado` recebido NÃO carrega parâmetros nem timestamps — o closure de
    produção fecha sobre os provisórios e carimba inicio/fim (é o que mantém isso
    fora do caminho determinístico). O retorno do sink (o `rodada.id`) é
    descartado aqui; se um nó futuro precisar dele, exporá no estado.

    CONSEQUÊNCIA DECLARADA do corte (não em silêncio, ligada à divergência aberta
    de 2026-09-01 em docs/decisoes.md): uma rodada ABORTADA NÃO deixa NENHUMA linha
    no Registro — nem o cabeçalho `rodada`. Logo o valor `estado='abortada'` da
    Spec §2.1 e os campos `motivo`/`tentativas_por_etapa` nunca são populados para
    abortos, e o Monitor de segunda / a auditoria não enxergam a execução que
    abortou. Registrar o cabeçalho da rodada abortada (sem `decisao_imovel`) é
    fatia futura candidata.
    """
    registrar(estado)
    return {}


def _rota_pos_coleta(estado: EstadoRodada) -> list[str] | str:
    """Após a coleta interna: aborta (vai direto finalizar) ou segue para o
    fan-out perfil ∥ externo."""
    if estado.get("estado") == Estado.ABORTADA:
        return "finalizar"
    return ["analista_perfil", "coletor_externo"]


def _rota_pos_crivo(estado: EstadoRodada) -> str:
    """Após o crivo: se vetou (estado ABORTADA), NÃO entrega — pula o Redator e
    vai a finalizar; senão segue para o Redator."""
    if estado.get("estado") == Estado.ABORTADA:
        return "finalizar"
    return "redator"


def _rota_pos_finalizar(estado: EstadoRodada) -> str:
    """Após finalizar: rodada ABORTADA não persiste (sem resultado válido) — vai
    a END; senão passa pelo nó de registro."""
    if estado.get("estado") == Estado.ABORTADA:
        return END
    return "registrar"


def construir_grafo(
    fontes: Fontes,
    parametros: ParametrosDecisao,
    *,
    parametros_externo: ParametrosExterno | None = None,
    registrar: Callable[[EstadoRodada], object] | None = None,
    checkpointer=None,
):
    """Monta e compila o grafo da rodada de sexta.

    `fontes`, `parametros`, `parametros_externo` e `registrar` são INJETADOS
    (run-local; provisórios, nunca adotados). `parametros_externo` (G4) leva os
    limiares nulos da coleta externa (amarração nº 7, idade nº 5) e a composição
    do sinal F3 — provisórios; None (com `fontes.coletar_externo` None) mantém o
    Coletor Externo em STUB e a rodada DEGRADADA nesse fator. `registrar` é o SINK
    de persistência (G2a-wire): se fornecido, a rodada NÃO-abortada passa por um
    nó que grava no Registro; se None, o grafo termina sem persistir. `checkpointer`
    default = None (sem persistência de ESTADO do grafo): o estado carrega objetos
    de domínio não-serializáveis; o checkpointer Postgres da aprovação é a G2b/G3.
    """
    if (fontes.coletar_externo is None) != (parametros_externo is None):
        raise ValueError(
            "Coletor Externo meio-fiado: forneça `fontes.coletar_externo` E "
            "`parametros_externo` juntos (raspagem viva), ou nenhum (stub). Um só "
            "dos dois degradaria a rodada em silêncio em vez de sinalizar a fiação."
        )
    g = StateGraph(EstadoRodada)
    g.add_node("coletor_interno", partial(no_coletor_interno, fontes=fontes))
    g.add_node("analista_perfil", partial(no_analista_perfil, fontes=fontes))
    g.add_node(
        "coletor_externo",
        partial(no_coletor_externo, fontes=fontes, parametros_externo=parametros_externo),
    )
    g.add_node("decisor", partial(no_decisor, parametros=parametros))
    g.add_node("crivo", no_crivo)
    g.add_node("redator", no_redator)
    g.add_node("finalizar", no_finalizar)

    g.add_edge(START, "coletor_interno")
    g.add_conditional_edges(
        "coletor_interno", _rota_pos_coleta, ["analista_perfil", "coletor_externo", "finalizar"]
    )
    g.add_edge("analista_perfil", "decisor")
    g.add_edge("coletor_externo", "decisor")
    g.add_edge("decisor", "crivo")
    g.add_conditional_edges("crivo", _rota_pos_crivo, ["redator", "finalizar"])
    g.add_edge("redator", "finalizar")

    if registrar is not None:
        g.add_node("registrar", partial(no_registrar, registrar=registrar))
        g.add_conditional_edges("finalizar", _rota_pos_finalizar, ["registrar", END])
        g.add_edge("registrar", END)
    else:
        g.add_edge("finalizar", END)

    return g.compile(checkpointer=checkpointer)
