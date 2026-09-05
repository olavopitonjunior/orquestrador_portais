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
  injetados, lê a saída do raspador e, passando as portas (amarração, idade), a
  nota do portal (D-028) ordena a lista e a rodada pode ser COMPLETA; sem eles, segue
  STUB (DEGRADADA, ausência declarada). A "reserva" da coleta velha (Spec §7.3)
  ainda não é reusada — coleta fora da janela degrada.
- Sem modelo: o Analista de Perfil roda por contagem (o determinístico da Spec
  §6.2) e o Redator não gera resumo por modelo aqui.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from functools import partial

from langgraph.graph import END, START, StateGraph

from dados.coletor_externo import ParametrosExterno, avaliar_coleta
from dominio.auditoria import ItemAuditavel, auditar
from dominio.penalidades import JanelaCrua, com_janelas, julgar_janelas
from dominio.perfil import perfis_de_conversao
from grafo.estado import Estado, EstadoRodada, Fontes, estado_final
from piloto.decisao import ParametrosDecisao, decidir
from piloto.semelhanca import perfis_que_contam


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


def no_analista_perfil(
    estado: EstadoRodada, *, fontes: Fontes, parametros: ParametrosDecisao
) -> dict:
    """Descobre os perfis de conversão por contagem (Spec §6.2, determinístico).
    PRONTO: ao menos um perfil que CONTA para o filtro — robusto E contendo a
    dimensão exigida (D-027), o mesmo critério que `decidir` aplica. Sem isso o
    filtro não incide e a rodada segue degradada (Spec §7.3), não aborta; a
    degradação nomeada é acrescentada pelo decisor."""
    vendas, _descartadas = fontes.coletar_vendas()
    perfis = perfis_de_conversao(vendas)
    robusto = bool(perfis_que_contam(perfis, parametros.exigir_dimensao_no_perfil))
    saida: dict = {"perfis": perfis, "prontos": {"perfil": robusto}}
    if not robusto:
        saida["degradacoes"] = [
            "perfil de conversão sem evidência robusta que conte para o filtro — "
            "o filtro de perfil não incide nesta rodada (Spec §7.3, D-027)"
        ]
    return saida


def no_coletor_externo(
    estado: EstadoRodada,
    *,
    fontes: Fontes,
    parametros_externo: ParametrosExterno | None,
) -> dict:
    """Coletor Externo (G4): lê a saída do raspador e decide se a nota do portal
    ordena a lista (Spec §6.3 e §7.3).

    Sem `coletar_externo`/`parametros_externo` injetados (esqueleto), continua
    STUB: sem raspagem, rodada DEGRADADA nesse fator. Com eles, `avaliar_coleta`
    aplica as portas (estado ok, ao menos um imóvel-alvo amarrado, amarração ≥
    limiar nº 7, idade ≤ máxima nº 5) e,
    passando, entrega os anúncios por imóvel; falhando qualquer porta, a nota do
    portal não entra, a ordem cai para o sinal de banco declarado e a degradação é
    declarada com o motivo — a rodada não é COMPLETA."""
    if fontes.coletar_externo is None or parametros_externo is None:
        return {
            "externo_presente": False,
            "anuncios_por_imovel": {},
            "prontos": {"externo": False},
            "degradacoes": [
                "Coletor Externo não executado (esqueleto, sem raspagem): "
                "desempenho de portal ausente — rodada DEGRADADA nesse fator"
            ],
        }
    coleta = fontes.coletar_externo()
    alvo = [c.imovel_id for c in estado["candidatos"]]
    r = avaliar_coleta(coleta, alvo, parametros_externo, estado["data_referencia"])
    # Os anúncios crus sobem nos DOIS desfechos: o CSV da apuração mostra o que o portal
    # trouxe mesmo quando ele não pesou — `externo_presente` diz se pesou.
    anuncios = dict(coleta.por_imovel)
    if r.entra:
        return {
            "externo_presente": True,
            "anuncios_por_imovel": anuncios,
            # Sobem MESMO no sucesso: a Spec §3.1 exige os dois na aba de resumo, e
            # antes eles só existiam embutidos no motivo da rejeição — a rodada
            # completa era justamente a que não tinha os números obrigatórios.
            "externo_taxa_amarracao": r.taxa_amarracao,
            "externo_idade_dias": r.idade_dias,
            "prontos": {"externo": True},
        }
    return {
        "externo_presente": False,
        "anuncios_por_imovel": anuncios,
        "externo_taxa_amarracao": r.taxa_amarracao,
        "externo_idade_dias": r.idade_dias,
        "prontos": {"externo": False},
        "degradacoes": [f"Coletor Externo: {r.motivo}"],
    }


def no_decisor(
    estado: EstadoRodada,
    *,
    parametros: ParametrosDecisao,
    fontes: Fontes,
    resultado_esperado: Mapping[str, int] | None = None,
) -> dict:
    """Decisor (determinístico, invariante 4): elegibilidade → ranking → cotas →
    relaxamento, via a costura já testada. PRONTO: produziu o resultado.

    É AQUI que o histórico de janelas do Registro entra, e não no Coletor Interno:
    a Spec §5 diz que "o Decisor é o único agente que lê o Registro durante a rodada,
    e o faz para obter o histórico de janelas necessário ao cálculo da penalidade".

    A leitura acontece SEMPRE que a fonte estiver fiada; o JULGAMENTO só quando o
    limiar por nível (parâmetro nº 14, D-022) tiver sido declarado. As duas coisas
    são separadas de propósito: sem limiar, `janelas_lidas` ainda diz quantas janelas
    existem, e a planilha consegue distinguir "o produtor não fechou janela nenhuma"
    de "há histórico, mas nenhuma régua para julgá-lo". Sob um sinal só, as duas
    sairiam como a mesma coisa — e as duas zeram a penalidade por motivos opostos.
    """
    penalizaveis = estado["penalizaveis"]
    janelas_lidas: int | None = None  # None = não consultado
    # O histórico CRU de janelas por imóvel, independente do julgamento, para a
    # entrega poder dizer QUAL foi a última janela mesmo com o limiar do nº 14 nulo.
    # `None` é um SINAL, não vazio: quer dizer histórico não consultado. Um sinal só
    # em vez de dois (mapa + contador) porque a combinação incoerente — mapa vazio
    # com "consultado" — era exprimível e produzia exatamente a afirmação falsa que
    # esta coluna existe para eliminar. Não entra em `decidir`: viaja ao lado.
    historico_janelas: dict[int, tuple[JanelaCrua, ...]] | None = None
    degradacoes: list[str] = []
    pronto_janelas = fontes.coletar_janelas is not None
    if fontes.coletar_janelas is not None:
        try:
            cruas = fontes.coletar_janelas(list(penalizaveis), estado["data_referencia"])
        except Exception as e:
            # Decisão do dono: Registro fora DEGRADA e entrega, não aborta. A Spec
            # §7.2 descreve exatamente este caso — "alguma fonte falhou e a decisão
            # prosseguiu com dado parcial" — e a §6.4 é uma das três penalidades: sem
            # ela ainda há lista para carregar. Abortar deixaria a semana sem vitrine
            # por causa de uma penalidade. Só o TIPO no motivo: a mensagem pode ecoar
            # dado do banco.
            pronto_janelas = False
            degradacoes.append(
                f"HISTÓRICO DE JANELAS indisponível ({type(e).__name__}): a penalidade "
                "por janela anterior sem resultado (Spec §6.4) não incidiu nesta rodada"
            )
        else:
            janelas_lidas = sum(len(js) for js in cruas.values())
            historico_janelas = dict(cruas)
            if resultado_esperado is not None:
                penalizaveis = {
                    imovel_id: com_janelas(
                        p, julgar_janelas(cruas.get(imovel_id, ()), resultado_esperado)
                    )
                    for imovel_id, p in penalizaveis.items()
                }
    resultado = decidir(
        estado["candidatos"],
        penalizaveis,
        estado["dims"],
        estado["perfis"],
        parametros,
        estado["data_referencia"],
        anuncios=estado.get("anuncios_por_imovel"),
        portal_entrou=bool(estado.get("externo_presente")),
    )
    return {
        "resultado": resultado,
        "janelas_lidas": janelas_lidas,
        "historico_janelas": historico_janelas,
        # `penalizaveis` volta ao estado JULGADO: era rebindado só localmente, e o
        # estado guardava a versão sem janelas — divergente da entrada que `decidir`
        # de fato consumiu. Com o checkpointer no Postgres, retomar depois do Decisor
        # leria a entrada errada, em silêncio.
        "penalizaveis": penalizaveis,
        "degradacoes": degradacoes,
        "prontos": {"decisor": True, "janelas": pronto_janelas},
    }


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
    resultado_esperado: Mapping[str, int] | None = None,
    registrar: Callable[[EstadoRodada], object] | None = None,
    checkpointer=None,
):
    """Monta e compila o grafo da rodada de sexta.

    `fontes`, `parametros`, `parametros_externo` e `registrar` são INJETADOS: o
    valor efetivo da semana chega por eles, e nenhum módulo do grafo guarda cópia.
    `parametros_externo` (G4) leva as duas portas da coleta externa — cobertura
    mínima (nº 7) e idade máxima (nº 5), ambas DEFINIDAS pela D-034 e adotadas
    quando a semana não declara outra coisa. Não leva composição nenhuma: desde a
    D-028 a nota é montada na costura, não no coletor. None (com
    `fontes.coletar_externo` None) mantém o
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
    g.add_node("analista_perfil", partial(no_analista_perfil, fontes=fontes, parametros=parametros))
    g.add_node(
        "coletor_externo",
        partial(no_coletor_externo, fontes=fontes, parametros_externo=parametros_externo),
    )
    g.add_node(
        "decisor",
        partial(
            no_decisor,
            parametros=parametros,
            fontes=fontes,
            resultado_esperado=resultado_esperado,
        ),
    )
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
