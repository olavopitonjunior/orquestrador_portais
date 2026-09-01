"""Testes do esqueleto do grafo (marco F, G1).

Roda o grafo inteiro com FONTES FALSAS (sem MySQL): confere o fluxo, o estado
honesto (degradada com o Coletor Externo stub), o gate do crivo e o caminho de
aborto. `estado_final` tem testes unitários à parte.
"""

from dataclasses import replace
from datetime import date

from langgraph.graph import END

from dominio.alocacao import Alocacao, PosicaoAlocada
from dominio.elegibilidade import ImovelCandidato
from dominio.penalidades import ImovelPenalizavel, IntensidadesPenalidade
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
        e: True for e in ("coletor_interno", "perfil", "externo", "decisor", "crivo", "redator")
    }


def test_estado_final_completa_com_tudo_pronto():
    assert estado_final({"prontos": _prontos_todos()}) == Estado.COMPLETA


def test_estado_final_degradada_sem_externo():
    prontos = _prontos_todos() | {"externo": False}
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
