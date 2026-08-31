"""Testes da leitura de dimensões de perfil do candidato.

A I/O não roda no CI. Cobre linha_para_dimensoes e — o ponto crítico — a FONTE
ÚNICA: candidato e venda com o mesmo valor bruto produzem o mesmo bucket, então
o match do perfil (piloto.semelhanca.casa) casa. Se divergissem, a semelhança
zeraria para todos sem erro.
"""

from decimal import Decimal

from dados.candidatos_perfil import linha_para_dimensoes
from dados.vendas import linha_para_vendido
from dominio.perfil import Dimensao

LINHA_CAND = {
    "imovel_id": 900,
    "regiao": "Centro",
    "faixa_metragem": "60 - 80m2",
    "dormitorios": 2,
    "preco": Decimal("650000.00"),
    "vagas": 1,
}


def test_linha_para_dimensoes_monta_as_cinco():
    dims = linha_para_dimensoes(LINHA_CAND)
    assert dims == {
        Dimensao.REGIAO: "Centro",
        Dimensao.FAIXA_PRECO: "500k–700k",  # 650k
        Dimensao.FAIXA_METRAGEM: "60 - 80m2",
        Dimensao.DORMITORIOS: 2,
        Dimensao.VAGAS: 1,
    }


def test_dimensao_nula_fica_de_fora():
    dims = linha_para_dimensoes({**LINHA_CAND, "dormitorios": None, "vagas": None})
    assert Dimensao.DORMITORIOS not in dims
    assert Dimensao.VAGAS not in dims
    assert Dimensao.REGIAO in dims  # as preenchidas permanecem


def test_preco_ausente_tira_faixa_de_preco():
    dims = linha_para_dimensoes({**LINHA_CAND, "preco": None})
    assert Dimensao.FAIXA_PRECO not in dims


def test_colapso_de_dormitorios_e_vagas():
    dims = linha_para_dimensoes({**LINHA_CAND, "dormitorios": 9, "vagas": 5})
    assert dims[Dimensao.DORMITORIOS] == 5  # teto
    assert dims[Dimensao.VAGAS] == 3  # teto


# --- FONTE ÚNICA: candidato e venda com o mesmo valor casam no mesmo bucket ---


def test_fonte_unica_candidato_e_venda_produzem_o_mesmo_bucket():
    # Mesmos valores brutos nos dois lados → as dimensões preenchidas devem ser
    # IDÊNTICAS. É a prova de que a bucketização compartilhada não diverge.
    brutos = {
        "imovel_id": 1,
        "regiao": "Pinheiros",
        "faixa_metragem": "80 - 100m2",
        "dormitorios": 3,
        "preco": Decimal("1250000.00"),
        "vagas": 2,
    }
    dims_candidato = linha_para_dimensoes(brutos)
    dims_venda = linha_para_vendido(brutos).valores()
    assert dims_candidato == dims_venda


def test_fonte_unica_com_colapso_e_nulos():
    # O acordo vale também nos tetos e ausências.
    brutos = {
        "imovel_id": 2,
        "regiao": "  Moema ",  # espaço aparado nos dois lados
        "faixa_metragem": "acima de 200m2",
        "dormitorios": 8,  # colapsa em 5
        "preco": None,  # sem faixa de preço
        "vagas": None,  # ausente
    }
    assert linha_para_dimensoes(brutos) == linha_para_vendido(brutos).valores()
