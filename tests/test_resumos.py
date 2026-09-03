"""O relatório de cada agente: derivado do estado, JSON puro, sem id de imóvel."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from dominio.elegibilidade import Regra
from dominio.perfil import EVIDENCIA_MINIMA
from executar.resumos import AtribuidorDeDegradacoes, resumo_do_no
from grafo.estado import Estado


def _perfil(num_vendas: int, dims: int = 1):
    return SimpleNamespace(num_vendas=num_vendas, dimensoes=("a", "b")[:dims])


def _resultado():
    return SimpleNamespace(
        n_elegiveis=120,
        n_reprovados=30,
        reprovados_regras={
            101: frozenset({Regra.FOTOS}),
            202: frozenset({Regra.FOTOS, Regra.PRECO_GERAL}),
        },
        alocacao=SimpleNamespace(super_destaque=(1, 2, 3), destaque=tuple(range(50))),
        relaxamento=SimpleNamespace(recuperados=(7, 8), deficit_restante=6440),
    )


ESTADO = {
    "candidatos": [object()] * 150,
    "penalizaveis": {i: object() for i in range(150)},
    "dims": {i: object() for i in range(148)},
    "perfis": (_perfil(5), _perfil(2), _perfil(9, dims=2)),
    "externo_presente": True,
    "externo_taxa_amarracao": 0.83,
    "externo_idade_dias": 1,
    "desempenho_por_imovel": {101: 3.0, 202: 1.0},
    "resultado": _resultado(),
    "veredito": SimpleNamespace(pronta=True, violacoes=()),
    "janelas_lidas": 0,
    "estado": Estado.DEGRADADA,
    "prontos": {"decisor": True},
    "degradacoes": ["a", "b"],
}

NOS = [
    "coletor_interno",
    "analista_perfil",
    "coletor_externo",
    "decisor",
    "crivo",
    "redator",
    "finalizar",
]


@pytest.mark.parametrize("no", NOS)
def test_todo_resumo_e_json_puro(no):
    """O resumo vai para jsonb e para a tela: um objeto de domínio dentro dele
    quebraria a gravação do evento — depois de a etapa já ter acontecido."""
    json.dumps(resumo_do_no(no, ESTADO, degradacoes_novas=["x"]))


def test_coletor_interno_conta_e_declara_o_recorte():
    r = resumo_do_no("coletor_interno", ESTADO, recorte_amostral=200)
    assert (r["candidatos"], r["penalizaveis"], r["com_dimensoes"]) == (150, 150, 148)
    assert r["recorte_amostral"] == 200
    assert resumo_do_no("coletor_interno", ESTADO)["recorte_amostral"] is None


def test_analista_conta_frageis_pela_evidencia_minima():
    r = resumo_do_no("analista_perfil", ESTADO)
    assert r["perfis"] == 3
    assert r["frageis"] == sum(1 for v in (5, 2, 9) if v < EVIDENCIA_MINIMA)
    assert r["evidencia_minima"] == EVIDENCIA_MINIMA
    assert (r["de_uma_dimensao"], r["de_duas_dimensoes"], r["vendas_no_maior_perfil"]) == (2, 1, 9)


def test_coletor_externo_diz_se_entrou_e_com_que_taxa():
    r = resumo_do_no("coletor_externo", ESTADO)
    assert r == {
        "entrou_no_ranking": True,
        "taxa_amarracao": 0.83,
        "idade_dias": 1,
        "imoveis_com_desempenho": 2,
        "degradacoes": [],
    }


def test_decisor_conta_por_regra_e_por_nivel():
    r = resumo_do_no("decisor", ESTADO)
    assert (r["elegiveis"], r["reprovados"]) == (120, 30)
    assert r["reprovados_por_regra"] == {"fotos": 2, "preco_geral": 1}
    assert (r["super_destaque"], r["destaque"]) == (3, 50)
    assert (r["recuperados_por_relaxamento"], r["posicoes_vazias"]) == (2, 6440)
    assert resumo_do_no("decisor", {"resultado": None}) == {"resultado": None, "degradacoes": []}


def test_crivo_reporta_veto_com_os_codigos():
    r = resumo_do_no("crivo", ESTADO)
    assert r["passou"] is True and r["violacoes"] == []
    vetado = {
        **ESTADO,
        "veredito": SimpleNamespace(
            pronta=False, violacoes=(SimpleNamespace(codigo="cota_excedida"),)
        ),
    }
    r = resumo_do_no("crivo", vetado)
    assert r["passou"] is False and r["violacoes"] == ["cota_excedida"]


def test_nenhum_resumo_carrega_id_de_imovel():
    """Os ids 101 e 202 estão no estado (desempenho, reprovados); nenhum sai no resumo —
    só contagens. A mesma disciplina do NDJSON."""
    import re

    for no in NOS:
        texto = json.dumps(resumo_do_no(no, ESTADO))
        assert not re.search(r"\b(101|202)\b", texto), (no, texto)


def test_atribuidor_entrega_so_as_degradacoes_novas_de_cada_passo():
    a = AtribuidorDeDegradacoes()
    assert a.novas({"degradacoes": ["a"]}, "coletor_interno") == ["a"]
    assert a.novas({"degradacoes": ["a", "b", "c"]}, "decisor") == ["b", "c"]
    assert a.novas({"degradacoes": ["a", "b", "c"]}, "crivo") == []
    assert a.novas({}, "redator") == []


def test_no_fan_out_as_degradacoes_do_passo_vao_para_o_PAR_em_qualquer_ordem():
    """A ordem entre perfil e coleta externa é a de conclusão das threads: o relatório
    não pode depender dela. Os dois recebem a mesma lista, e dizem com quem a dividem."""
    for ordem in (("analista_perfil", "coletor_externo"), ("coletor_externo", "analista_perfil")):
        a = AtribuidorDeDegradacoes()
        a.novas({"degradacoes": ["x"]}, "coletor_interno")
        estado = {"degradacoes": ["x", "Coletor Externo: fora"], "nos_do_passo": list(ordem)}
        assert a.novas(estado, ordem[0]) == ["Coletor Externo: fora"]
        assert a.novas(estado, ordem[1]) == ["Coletor Externo: fora"]
        r = resumo_do_no(ordem[1], estado, degradacoes_novas=["Coletor Externo: fora"])
        assert r["degradacoes_compartilhadas_com"] == [ordem[0]]
    assert "degradacoes_compartilhadas_com" not in resumo_do_no(
        "decisor", {"nos_do_passo": ["decisor"]}
    )
