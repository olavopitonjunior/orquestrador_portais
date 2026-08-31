"""Testes do mapeamento candidato → semelhanca_perfil (o coração de regra do B3).

Módulo puro — roda inteiro no CI. Cobre a regra de match, o sinal bruto
(robusto vs frágil, seleção do máximo, sem match), a normalização min-max
(inclusive o caso degenerado) e o determinismo.
"""

import pytest

from dominio.perfil import Dimensao, PerfilConversao
from piloto.semelhanca import (
    ParametrosSemelhanca,
    casa,
    perfil_que_puxou,
    semelhanca_por_imovel,
    sinal_bruto,
)

PARAMS = ParametrosSemelhanca(desconto_fragil=0.5)


def _perfil(dims, vals, n):
    return PerfilConversao(dimensoes=dims, valores=vals, num_vendas=n)


REGIAO_CENTRO = _perfil((Dimensao.REGIAO,), ("Centro",), 10)  # robusto
CENTRO_2D = _perfil((Dimensao.REGIAO, Dimensao.DORMITORIOS), ("Centro", 2), 4)  # robusto
FRAGIL = _perfil((Dimensao.REGIAO,), ("Sul",), 1)  # frágil (N<3)


def test_casa_match_exato_de_todas_as_dimensoes():
    dims = {Dimensao.REGIAO: "Centro", Dimensao.DORMITORIOS: 2}
    assert casa(dims, REGIAO_CENTRO) is True
    assert casa(dims, CENTRO_2D) is True


def test_nao_casa_se_alguma_dimensao_difere():
    dims = {Dimensao.REGIAO: "Centro", Dimensao.DORMITORIOS: 3}
    assert casa(dims, CENTRO_2D) is False  # dormitórios diferem


def test_nao_casa_se_candidato_nao_tem_a_dimensao():
    dims = {Dimensao.REGIAO: "Centro"}  # sem dormitórios
    assert casa(dims, CENTRO_2D) is False


def test_sinal_bruto_pega_o_maior():
    # Casa REGIAO_CENTRO (10) e CENTRO_2D (4): o sinal é o maior, 10.
    dims = {Dimensao.REGIAO: "Centro", Dimensao.DORMITORIOS: 2}
    assert sinal_bruto(dims, (REGIAO_CENTRO, CENTRO_2D), PARAMS) == 10.0


def test_sinal_bruto_desconta_fragil():
    # Só casa o perfil frágil (Sul, N=1): 1 × 0.5 = 0.5.
    dims = {Dimensao.REGIAO: "Sul"}
    assert sinal_bruto(dims, (REGIAO_CENTRO, FRAGIL), PARAMS) == 0.5


def test_sinal_bruto_zero_sem_match():
    dims = {Dimensao.REGIAO: "Norte"}
    assert sinal_bruto(dims, (REGIAO_CENTRO, CENTRO_2D), PARAMS) == 0.0


def test_fragil_perde_para_robusto_quando_ambos_casam():
    # Robusto (N=2 seria frágil; aqui N=10) domina o frágil descontado.
    dims = {Dimensao.REGIAO: "X"}
    robusto = _perfil((Dimensao.REGIAO,), ("X",), 10)
    fragil = _perfil((Dimensao.REGIAO,), ("X",), 2)  # 2 × 0.5 = 1.0 < 10
    assert sinal_bruto(dims, (robusto, fragil), PARAMS) == 10.0


def test_normalizacao_minmax():
    perfis = (
        _perfil((Dimensao.REGIAO,), ("A",), 10),
        _perfil((Dimensao.REGIAO,), ("B",), 5),
    )
    dims = {
        1: {Dimensao.REGIAO: "A"},  # sinal 10 → 1.0
        2: {Dimensao.REGIAO: "B"},  # sinal 5  → 0.0
        3: {Dimensao.REGIAO: "Z"},  # sinal 0  → ... menor é 0
    }
    r = semelhanca_por_imovel(dims, perfis, PARAMS)
    assert r[1] == 1.0  # maior
    assert r[3] == 0.0  # menor
    assert 0.0 < r[2] < 1.0  # meio (5 entre 0 e 10 = 0.5)
    assert r[2] == 0.5


def test_normalizacao_degenerada_todos_iguais_viram_zero():
    # Ninguém casa nenhum perfil (todos sinal 0) → todos 0.0, ninguém favorecido.
    perfis = (_perfil((Dimensao.REGIAO,), ("A",), 10),)
    dims = {1: {Dimensao.REGIAO: "X"}, 2: {Dimensao.REGIAO: "Y"}}
    r = semelhanca_por_imovel(dims, perfis, PARAMS)
    assert r == {1: 0.0, 2: 0.0}


def test_deterministico_independe_da_ordem():
    perfis = (_perfil((Dimensao.REGIAO,), ("A",), 10), _perfil((Dimensao.REGIAO,), ("B",), 5))
    dims1 = {1: {Dimensao.REGIAO: "A"}, 2: {Dimensao.REGIAO: "B"}}
    dims2 = {2: {Dimensao.REGIAO: "B"}, 1: {Dimensao.REGIAO: "A"}}
    assert semelhanca_por_imovel(dims1, perfis, PARAMS) == semelhanca_por_imovel(
        dims2, perfis, PARAMS
    )


def test_vazio():
    assert semelhanca_por_imovel({}, (REGIAO_CENTRO,), PARAMS) == {}


def test_parametros_rejeita_desconto_fora_da_faixa():
    with pytest.raises(ValueError, match="desconto_fragil"):
        ParametrosSemelhanca(desconto_fragil=1.5)
    with pytest.raises(ValueError, match="desconto_fragil"):
        ParametrosSemelhanca(desconto_fragil=-0.1)


# --- perfil que puxou (argmax) e a concordância com o sinal (fonte única) -----


def test_perfil_que_puxou_none_sem_match():
    dims = {Dimensao.REGIAO: "Norte"}
    assert perfil_que_puxou(dims, (REGIAO_CENTRO, CENTRO_2D), PARAMS) is None


def test_perfil_que_puxou_e_o_de_maior_contribuicao():
    dims = {Dimensao.REGIAO: "Centro", Dimensao.DORMITORIOS: 2}
    assert perfil_que_puxou(dims, (REGIAO_CENTRO, CENTRO_2D), PARAMS) is REGIAO_CENTRO


def test_empate_de_contribuicao_o_mais_especifico_ganha():
    # Dois perfis com a MESMA contribuição (N=5): o de 2 dimensões (mais
    # específico) é o exibido.
    p1d = _perfil((Dimensao.REGIAO,), ("X",), 5)
    p2d = _perfil((Dimensao.REGIAO, Dimensao.DORMITORIOS), ("X", 2), 5)
    dims = {Dimensao.REGIAO: "X", Dimensao.DORMITORIOS: 2}
    assert perfil_que_puxou(dims, (p1d, p2d), PARAMS) is p2d


def test_concordancia_perfil_que_puxou_bate_com_sinal_bruto():
    # A CONDIÇÃO da fonte única: a contribuição do perfil que puxou == o sinal
    # bruto, para a mesma entrada. O rótulo nunca diverge do número.
    dims = {Dimensao.REGIAO: "Centro", Dimensao.DORMITORIOS: 2}
    perfis = (REGIAO_CENTRO, CENTRO_2D, FRAGIL)
    sinal = sinal_bruto(dims, perfis, PARAMS)
    pqp = perfil_que_puxou(dims, perfis, PARAMS)
    contrib_do_pqp = pqp.num_vendas * (PARAMS.desconto_fragil if pqp.fragil else 1.0)
    assert contrib_do_pqp == sinal


def test_concordancia_com_fragil_descontado():
    dims = {Dimensao.REGIAO: "Sul"}
    perfis = (REGIAO_CENTRO, FRAGIL)  # só FRAGIL (Sul) casa
    sinal = sinal_bruto(dims, perfis, PARAMS)
    pqp = perfil_que_puxou(dims, perfis, PARAMS)
    assert pqp is FRAGIL
    assert pqp.num_vendas * PARAMS.desconto_fragil == sinal
