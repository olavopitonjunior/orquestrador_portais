"""Testes do esqueleto do grafo (marco F, G1).

Roda o grafo inteiro com FONTES FALSAS (sem MySQL): confere o fluxo, o estado
honesto (degradada com o Coletor Externo stub), o gate do crivo e o caminho de
aborto. `estado_final` tem testes unitários à parte.
"""

from dataclasses import replace
from datetime import date, datetime, timedelta

from langgraph.graph import END

from dados.coletor_externo import (
    ColetaExterna,
    DesempenhoAnuncio,
    ParametrosExterno,
)
from dominio.alocacao import Alocacao, PosicaoAlocada
from dominio.elegibilidade import ImovelCandidato
from dominio.penalidades import ImovelPenalizavel, IntensidadesPenalidade, Penalidade
from dominio.perfil import Dimensao, ImovelVendido, perfis_de_conversao
from dominio.ranking import PesosNivel
from grafo.estado import Estado, Fontes, estado_final
from grafo.fluxo import _rota_pos_crivo, _rota_pos_finalizar, construir_grafo, no_crivo
from piloto.decisao import ParametrosDecisao, decidir
from piloto.semelhanca import ParametrosSemelhanca

HOJE = date(2026, 9, 1)

PARAMS = ParametrosDecisao(
    semelhanca=ParametrosSemelhanca(desconto_fragil=0.5, decaimento=1.0),
    intensidades=IntensidadesPenalidade(
        janela_sem_resultado=0.15, sem_avaliacao_por_categoria=0.10, sem_lead_180d=0.10
    ),
    decaimento_janela=lambda _c: 1.0,
    pesos_super=PesosNivel(
        semelhanca_perfil=45, leads_positivo=30, desempenho_proprio=15, produtividade_gestor=10
    ),
    pesos_destaque=PesosNivel(
        semelhanca_perfil=40, leads_positivo=40, desempenho_proprio=10, produtividade_gestor=10
    ),
)


def _candidato(imovel_id):
    return ImovelCandidato(
        imovel_id=imovel_id,
        publicacao_ativa=True,
        categoria="Apartamento",
        preco=850_000,
        qtd_fotos=20,
        atualizado_em=date(2026, 8, 20),
        notas_por_categoria={"Descrição do imóvel": 10},
        gestor_captou_ou_vendeu_30d=True,
        produtividade_gestor_30d=3,
        corretores_ativos_no_distrito=5,
    )


def _penalizavel(imovel_id, leads=7):
    return ImovelPenalizavel(
        imovel_id=imovel_id,
        janelas_anteriores=(),
        alguma_categoria_avaliada=True,
        leads_180d=leads,
    )


def _dims():
    return {Dimensao.REGIAO: "Centro"}


def _fontes(candidatos):
    ids = [c.imovel_id for c in candidatos]
    return Fontes(
        coletar_interno=lambda: (candidatos, [_penalizavel(i) for i in ids]),
        coletar_dimensoes=lambda: {i: _dims() for i in ids},
        # 3 vendas em "Centro" → perfil robusto (N=3, >= evidência mínima)
        coletar_vendas=lambda: (
            [
                ImovelVendido(
                    imovel_id=900 + k,
                    regiao="Centro",
                    faixa_preco=None,
                    faixa_metragem=None,
                    dormitorios=None,
                    vagas=None,
                )
                for k in range(3)
            ],
            0,
        ),
    )


def _estado_inicial():
    return {
        "data_referencia": HOJE,
        "estado": Estado.EM_ANDAMENTO,
        "prontos": {},
        "degradacoes": [],
    }


# --- fluxo completo com externo stub → DEGRADADA -----------------------------


def test_rodada_com_externo_stub_fica_degradada():
    grafo = construir_grafo(_fontes([_candidato(1), _candidato(2)]), PARAMS)
    final = grafo.invoke(_estado_inicial())
    assert final["estado"] == Estado.DEGRADADA  # nunca completa sem raspagem (honesto)
    assert final["resultado"] is not None
    assert final["veredito"].pronta is True  # crivo aprova o pipeline
    # prontos: tudo pronto menos o externo (stub)
    assert final["prontos"]["coletor_interno"] is True
    assert final["prontos"]["perfil"] is True
    assert final["prontos"]["decisor"] is True
    assert final["prontos"]["crivo"] is True
    assert final["prontos"]["redator"] is True
    assert final["prontos"]["externo"] is False
    # a ausência do externo está declarada nas degradações
    assert any("Coletor Externo" in d for d in final["degradacoes"])


# --- G4: com raspagem fresca e amarrada → COMPLETA ---------------------------

PARAMS_EXT = ParametrosExterno(
    limiar_amarracao=0.5, idade_maxima_dias=8, compor_desempenho=lambda a: a.visualizacoes
)


def _anuncio(imovel_id, views):
    return DesempenhoAnuncio(
        imovel_id=imovel_id,
        id_portal=f"90{imovel_id}",
        nota=8000.0,
        visualizacoes=views,
        cliques={},
        url=None,
    )


def _coleta_ok(views_por_id):
    return ColetaExterna(
        estado="ok",
        coletado_em=datetime(2026, 9, 1, 9, 0),  # mesmo dia de HOJE → fresca
        por_imovel={i: _anuncio(i, v) for i, v in views_por_id.items()},
        total_linhas=len(views_por_id),
        sem_amarracao=0,
    )


def _fontes_com_externo(candidatos, views_por_id):
    fontes = _fontes(candidatos)
    # COMPLETA exige TODAS as fontes, e as janelas entraram na lista (D-023): sem
    # elas a rodada é honestamente degradada.
    return replace(
        fontes,
        coletar_externo=lambda: _coleta_ok(views_por_id),
        coletar_janelas=lambda _ids, _ate: {},
    )


def test_rodada_com_raspagem_fresca_fica_completa():
    fontes = _fontes_com_externo([_candidato(1), _candidato(2)], {1: 300, 2: 50})
    grafo = construir_grafo(fontes, PARAMS, parametros_externo=PARAMS_EXT)
    final = grafo.invoke(_estado_inicial())
    assert final["estado"] == Estado.COMPLETA  # todas as etapas prontas, externo incluso
    assert final["prontos"]["externo"] is True
    assert final["externo_presente"] is True
    # A §3.1 exige idade do dado e taxa de amarração na aba de resumo, e os dois eram
    # descartados justamente no caso de SUCESSO — só existiam embutidos no motivo da
    # rejeição, então a rodada COMPLETA era a única sem os números obrigatórios.
    # Estas duas linhas são o que faz uma renomeação da chave doer: sem elas, trocar o
    # nome só no produtor deixa a suíte verde e a planilha passa a declarar "coleta
    # AUSENTE" numa rodada que teve coleta.
    assert final["externo_taxa_amarracao"] == 1.0  # 2 de 2 candidatos amarrados
    assert final["externo_idade_dias"] == 0  # coletada no mesmo dia de HOJE
    # o desempenho de portal (F3) entrou no cálculo: min-max, o de mais views = 1.0
    assert final["resultado"].detalhes[1].fatores.desempenho_proprio == 1.0
    assert final["resultado"].detalhes[2].fatores.desempenho_proprio == 0.0


def test_coletor_externo_meio_fiado_falha():
    # fornecer parametros_externo SEM coletar_externo (ou vice-versa) é erro de
    # fiação — falha alto em vez de degradar em silêncio (achado do revisor).
    import pytest

    fontes_sem_externo = _fontes([_candidato(1)])  # coletar_externo=None
    with pytest.raises(ValueError, match="meio-fiado"):
        construir_grafo(fontes_sem_externo, PARAMS, parametros_externo=PARAMS_EXT)


def test_raspagem_com_amarracao_baixa_degrada():
    # só 1 dos 2 candidatos amarrado = 50%... abaixo do limiar exige < 50%: uso 1 de 3
    fontes = _fontes_com_externo(
        [_candidato(1), _candidato(2), _candidato(3)], {1: 300}
    )  # 1 de 3 = 33% < 50%
    grafo = construir_grafo(fontes, PARAMS, parametros_externo=PARAMS_EXT)
    final = grafo.invoke(_estado_inicial())
    assert final["estado"] == Estado.DEGRADADA  # performance externa não entra
    assert final["prontos"]["externo"] is False
    assert any("amarração" in d for d in final["degradacoes"])
    # sem F3: desempenho zerado (degradado)
    assert final["resultado"].detalhes[1].fatores.desempenho_proprio == 0.0


def test_decisao_dentro_das_cotas():
    grafo = construir_grafo(_fontes([_candidato(1), _candidato(2)]), PARAMS)
    final = grafo.invoke(_estado_inicial())
    aloc = final["resultado"].alocacao
    # dois elegíveis, ambos ≥700k → super destaque; nada excede cota (invariante 6)
    assert len(aloc.super_destaque) <= 475
    assert len(aloc.destaque) <= 6495
    assert len(aloc.super_destaque) + len(aloc.destaque) == 2


# --- caminho de aborto: coleta interna vazia ---------------------------------


def test_coleta_interna_vazia_aborta():
    grafo = construir_grafo(_fontes([]), PARAMS)
    final = grafo.invoke(_estado_inicial())
    assert final["estado"] == Estado.ABORTADA
    assert final.get("resultado") is None  # decisor nunca rodou
    assert "sem estoque" in final["motivo_aborto"]
    assert final["prontos"]["coletor_interno"] is False


# --- determinismo (invariante 5) ---------------------------------------------


def test_mesma_entrada_mesma_saida():
    fontes = _fontes([_candidato(1), _candidato(2)])
    chaves = set()
    for _ in range(5):
        grafo = construir_grafo(fontes, PARAMS)
        final = grafo.invoke(_estado_inicial())
        aloc = final["resultado"].alocacao
        chaves.add(
            (
                tuple(p.imovel_id for p in aloc.super_destaque),
                tuple(p.imovel_id for p in aloc.destaque),
            )
        )
    assert len(chaves) == 1  # mesma entrada → mesmas listas (super E destaque), sempre


# --- estado_final (unitário) --------------------------------------------------


def _prontos_todos():
    return {
        e: True
        for e in ("coletor_interno", "perfil", "externo", "janelas", "decisor", "crivo", "redator")
    }


def test_estado_final_completa_com_tudo_pronto():
    assert estado_final({"prontos": _prontos_todos()}) == Estado.COMPLETA


def test_estado_final_degradada_sem_externo():
    prontos = _prontos_todos() | {"externo": False}
    assert estado_final({"prontos": prontos}) == Estado.DEGRADADA


def test_estado_final_degradada_sem_o_historico_de_janelas():
    """Decisão do dono: Registro fora DEGRADA e entrega. Sem `janelas` entre as
    etapas exigidas, uma rodada cujo Registro caiu sairia COMPLETA com uma das três
    penalidades da §6.4 silenciosamente inerte."""
    prontos = _prontos_todos() | {"janelas": False}
    assert estado_final({"prontos": prontos}) == Estado.DEGRADADA


def test_estado_final_abortada_prevalece():
    assert estado_final({"estado": Estado.ABORTADA, "prontos": {}}) == Estado.ABORTADA


# --- perfil sem robustez: degrada, não aborta (Spec §7.3) --------------------


def test_perfil_sem_robustez_degrada_sem_abortar():
    fontes = Fontes(
        coletar_interno=lambda: ([_candidato(1)], [_penalizavel(1)]),
        coletar_dimensoes=lambda: {1: _dims()},
        # 1 venda só → perfil frágil (N<3), nenhum robusto
        coletar_vendas=lambda: (
            [
                ImovelVendido(
                    imovel_id=900,
                    regiao="Sul",
                    faixa_preco=None,
                    faixa_metragem=None,
                    dormitorios=None,
                    vagas=None,
                )
            ],
            0,
        ),
    )
    final = construir_grafo(fontes, PARAMS).invoke(_estado_inicial())
    assert final["prontos"]["perfil"] is False
    assert final["estado"] == Estado.DEGRADADA  # degrada, NÃO aborta
    assert final["resultado"] is not None
    assert any("perfil de conversão sem evidência" in d for d in final["degradacoes"])


# --- gate do crivo: veto NÃO entrega (aborta) --------------------------------


def _resultado(cands):
    pen = {c.imovel_id: _penalizavel(c.imovel_id) for c in cands}
    dims = {c.imovel_id: _dims() for c in cands}
    perfis = perfis_de_conversao(
        [
            ImovelVendido(
                imovel_id=900 + k,
                regiao="Centro",
                faixa_preco=None,
                faixa_metragem=None,
                dormitorios=None,
                vagas=None,
            )
            for k in range(3)
        ]
    )
    return decidir(cands, pen, dims, perfis, PARAMS, HOJE)


def test_no_crivo_valido_fica_pronto():
    cands = [_candidato(1), _candidato(2)]
    saida = no_crivo({"resultado": _resultado(cands), "candidatos": cands})
    assert saida["prontos"]["crivo"] is True
    assert saida["veredito"].pronta is True


def test_no_crivo_veto_aborta_sem_entregar():
    cands = [_candidato(1), _candidato(2)]
    # troca a alocação por uma que estoura a cota do super → o crivo veta
    ruim = replace(
        _resultado(cands),
        alocacao=Alocacao(
            super_destaque=tuple(
                PosicaoAlocada(posicao=i, imovel_id=i, nota=1.0) for i in range(1, 477)
            ),
            destaque=(),
        ),
    )
    saida = no_crivo({"resultado": ruim, "candidatos": cands})
    assert saida["prontos"]["crivo"] is False
    assert saida["estado"] == Estado.ABORTADA  # veto não entrega
    assert "cota_super_excedida" in saida["motivo_aborto"]


def test_rota_pos_crivo_desvia_do_redator_no_veto():
    assert _rota_pos_crivo({"estado": Estado.ABORTADA}) == "finalizar"
    assert _rota_pos_crivo({"estado": Estado.EM_ANDAMENTO}) == "redator"


# --- G2a-wire: sink de persistência injetado -----------------------------------


def test_sink_de_persistencia_chamado_em_rodada_valida():
    chamadas = []
    grafo = construir_grafo(
        _fontes([_candidato(1), _candidato(2)]), PARAMS, registrar=chamadas.append
    )
    final = grafo.invoke(_estado_inicial())
    assert final["estado"] == Estado.DEGRADADA
    assert len(chamadas) == 1  # o sink foi chamado uma vez
    assert chamadas[0]["resultado"] is not None  # recebeu o estado com o resultado a gravar


def test_sink_nao_chamado_em_rodada_abortada():
    chamadas = []
    grafo = construir_grafo(
        _fontes([]), PARAMS, registrar=chamadas.append
    )  # estoque vazio → aborta
    final = grafo.invoke(_estado_inicial())
    assert final["estado"] == Estado.ABORTADA
    assert chamadas == []  # rodada abortada não persiste (sem resultado válido)


def test_rota_pos_finalizar_nao_persiste_no_aborto():
    # Roteamento isolado (cobre os dois abortos — estoque vazio e veto do crivo,
    # ambos ABORTADA — sem montar o grafo inteiro): abortada → END, senão → registrar.
    assert _rota_pos_finalizar({"estado": Estado.ABORTADA}) == END
    assert _rota_pos_finalizar({"estado": Estado.DEGRADADA}) == "registrar"
    assert _rota_pos_finalizar({"estado": Estado.COMPLETA}) == "registrar"


# --- consumidor das janelas: a penalidade §6.4 passa a INCIDIR -----------------


def _fontes_com_janelas(candidatos, historico):
    return replace(_fontes(candidatos), coletar_janelas=lambda _ids, _ate: historico)


LIMIAR = {"super_destaque": 5, "destaque": 2}


def test_penalidade_de_janela_INCIDE_quando_ha_historico_e_limiar():
    """O que a fatia inteira existe para fazer. Até aqui a coluna saía 0,0 para todo
    imóvel — não porque ninguém merecesse a penalidade, mas porque nada alimentava o
    cálculo. O imóvel 1 teve uma janela de destaque com 0 lead contra um limiar de 2:
    não atingiu o resultado, e é descontado."""
    fontes = _fontes_com_janelas([_candidato(1)], {1: (("destaque", 0, 0),)})
    final = construir_grafo(fontes, PARAMS, resultado_esperado=LIMIAR).invoke(_estado_inicial())

    detalhe = final["resultado"].detalhes[1]
    assert Penalidade.JANELA_SEM_RESULTADO in detalhe.descontos_por_penalidade
    assert detalhe.descontos_por_penalidade[Penalidade.JANELA_SEM_RESULTADO] > 0
    assert final["janelas_lidas"] == 1


def test_janela_que_ATINGIU_o_resultado_nao_penaliza():
    """A contraprova. Sem ela, o teste acima passaria mesmo se o código penalizasse
    toda janela indistintamente — e a §6.4 penaliza a que NÃO atingiu."""
    fontes = _fontes_com_janelas([_candidato(1)], {1: (("destaque", 9, 0),)})
    final = construir_grafo(fontes, PARAMS, resultado_esperado=LIMIAR).invoke(_estado_inicial())

    detalhe = final["resultado"].detalhes[1]
    assert Penalidade.JANELA_SEM_RESULTADO not in detalhe.descontos_por_penalidade
    assert final["janelas_lidas"] == 1  # leu, e o histórico existe


def test_sem_limiar_a_janela_e_LIDA_mas_nao_julgada():
    """As duas metades separadas: o Registro devolveu histórico (`janelas_lidas` diz
    quanto), mas o parâmetro nº 14 é nulo, então nada é julgado. Sob um sinal só,
    isso sairia idêntico a "não há histórico" — e as duas pedem correções opostas."""
    fontes = _fontes_com_janelas([_candidato(1)], {1: (("destaque", 0, 0),)})
    final = construir_grafo(fontes, PARAMS).invoke(_estado_inicial())  # sem limiar

    assert final["janelas_lidas"] == 1  # o histórico EXISTE
    detalhe = final["resultado"].detalhes[1]
    assert Penalidade.JANELA_SEM_RESULTADO not in detalhe.descontos_por_penalidade


def test_registro_fora_DEGRADA_e_entrega_em_vez_de_abortar(capsys):
    """Decisão do dono. A §7.2 descreve exatamente este caso — "alguma fonte falhou e
    a decisão prosseguiu com dado parcial" — e a §6.4 é uma das TRÊS penalidades: sem
    ela ainda há lista para carregar. Abortar deixaria a semana sem vitrine por causa
    de uma penalidade."""

    def _explode(_ids, _ate):
        raise ConnectionError("postgres fora, com dado sensível na mensagem")

    fontes = replace(_fontes([_candidato(1)]), coletar_janelas=_explode)
    final = construir_grafo(fontes, PARAMS, resultado_esperado=LIMIAR).invoke(_estado_inicial())

    assert final["estado"] == Estado.DEGRADADA
    assert final["resultado"] is not None  # ENTREGOU
    assert final["prontos"]["janelas"] is False
    (motivo,) = [d for d in final["degradacoes"] if "HISTÓRICO DE JANELAS" in d]
    assert "ConnectionError" in motivo  # o TIPO
    assert "dado sensível" not in motivo  # nunca a mensagem


def test_o_REGISTRO_recebe_os_penalizaveis_nao_so_os_elegiveis():
    """O conjunto certo é toda a população penalizável, incluindo reprovados que o
    relaxamento pode recuperar — restringir a elegíveis deixaria recuperado sem a
    penalidade §6.4. Sem esta trava, trocar a lista por `[]` passava na suíte inteira."""
    recebidos = []

    def _capta(ids, _ate):
        recebidos.append(list(ids))
        return {}

    fontes = replace(_fontes([_candidato(1), _candidato(2)]), coletar_janelas=_capta)
    construir_grafo(fontes, PARAMS).invoke(_estado_inicial())

    assert recebidos == [[1, 2]]


def test_o_TETO_da_contagem_de_ciclos_e_a_data_da_RODADA_nao_o_relogio():
    """A data de referência da rodada, não `date.today()`. Trocar uma pela outra é
    dependência do relógio corrente DENTRO do caminho da decisão — a forma de
    não-determinismo que o invariante 5 nomeia — e passava na suíte inteira: o teste
    dos ids descartava este argumento."""
    tetos = []

    def _capta(_ids, ate):
        tetos.append(ate)
        return {}

    ontem = date.today() - timedelta(days=1)  # garante que difere do relógio
    fontes = replace(_fontes([_candidato(1)]), coletar_janelas=_capta)
    construir_grafo(fontes, PARAMS).invoke(_estado_inicial() | {"data_referencia": ontem})

    assert tetos == [ontem]  # a data_referencia do estado, não `date.today()`


def test_sem_fonte_de_janelas_o_contador_e_NONE_nao_zero():
    """`None` = o Registro não foi consultado; `0` = foi consultado e não devolveu
    nada. As duas zeram a penalidade por motivos diferentes, e a limitação da planilha
    afirma o segundo — declarar zero aqui seria afirmar uma consulta que não houve."""
    final = construir_grafo(_fontes([_candidato(1)]), PARAMS).invoke(_estado_inicial())
    assert final["janelas_lidas"] is None


def test_a_ULTIMA_JANELA_CRUA_chega_ao_estado_mesmo_sem_limiar():
    """A fiação que a coluna do PRD precisa, e que era o buraco: sem o limiar do
    nº 14 nada é julgado e `janelas_anteriores` fica vazio — mas a planilha ainda
    tem de poder dizer QUAL foi a última janela. Sem este carregamento ao lado, ela
    afirmaria "sem janela anterior" sobre imóvel que TEM janela, que é exatamente o
    que o critério de aceite do PRD proíbe."""
    fontes = _fontes_com_janelas(
        [_candidato(1)], {1: (("destaque", 9, 5), ("super_destaque", 0, 1))}
    )
    final = construir_grafo(fontes, PARAMS).invoke(_estado_inicial())  # sem limiar

    assert final["janelas_lidas"] == 2
    # o histórico CRU chega inteiro; a eleição da última é do domínio, na entrega
    assert final["historico_janelas"][1] == (("destaque", 9, 5), ("super_destaque", 0, 1))


def test_sem_fonte_de_janelas_o_historico_e_NONE_nao_vazio():
    """Um sinal só: `None` é "não consultado" e dict vazio é "consultado e sem
    janela". Dois sinais (mapa + contador) permitiam a combinação incoerente — mapa
    vazio marcado como consultado —, e era exatamente ela que faria a planilha
    escrever "sem janela anterior" para o estoque inteiro numa rodada degradada."""
    final = construir_grafo(_fontes([_candidato(1)]), PARAMS).invoke(_estado_inicial())
    assert final["janelas_lidas"] is None
    assert final["historico_janelas"] is None


def test_imovel_sem_janela_nao_entra_no_historico():
    """Ausência do mapa é o sinal de "sem janela anterior" — e precisa ser ausência,
    não uma entrada vazia que a planilha teria de interpretar."""
    fontes = _fontes_com_janelas([_candidato(1), _candidato(2)], {1: (("destaque", 0, 1),)})
    final = construir_grafo(fontes, PARAMS).invoke(_estado_inicial())
    # o imóvel 2 PRECISA estar na rodada, senão o teste passa por ausência
    assert 2 in final["resultado"].detalhes
    assert 1 in final["historico_janelas"]
    assert 2 not in final["historico_janelas"]
