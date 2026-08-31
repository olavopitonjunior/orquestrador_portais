"""Testes da leitura de vendas: a montagem de ImovelVendido a partir de linhas.

A I/O (conexão real ao Newcore) não roda no CI. O que se testa aqui é
`linha_para_vendido` — a bucketização em si vive em test_bucketizacao.py (fonte
única).
"""

from decimal import Decimal

from dados.vendas import linha_para_vendido

LINHA = {
    "imovel_id": 501,
    "regiao": "Centro",
    "faixa_metragem": "60 a 80 m²",
    "dormitorios": 2,
    "preco": Decimal("650000.00"),
    "vagas": 1,
}


def test_linha_para_vendido_monta_dimensoes():
    v = linha_para_vendido(LINHA)
    assert v.imovel_id == 501
    assert v.regiao == "Centro"
    assert v.faixa_metragem == "60 a 80 m²"
    assert v.dormitorios == 2
    assert v.vagas == 1
    assert v.faixa_preco == "500k–700k"  # 650k cai em [500k, 700k)


def test_valores_nulos_viram_none():
    v = linha_para_vendido({**LINHA, "dormitorios": None, "vagas": None, "preco": None})
    assert v.dormitorios is None
    assert v.vagas is None
    assert v.faixa_preco is None


def test_string_vazia_de_regiao_ou_metragem_vira_none():
    v = linha_para_vendido({**LINHA, "regiao": "", "faixa_metragem": ""})
    assert v.regiao is None
    assert v.faixa_metragem is None


def test_string_so_espaco_vira_none_e_bordas_sao_aparadas():
    v = linha_para_vendido({**LINHA, "regiao": "   ", "faixa_metragem": " 60 a 80 m² "})
    assert v.regiao is None
    assert v.faixa_metragem == "60 a 80 m²"


def test_preco_decimal_vira_faixa():
    v = linha_para_vendido({**LINHA, "preco": Decimal("1250000.50")})
    assert v.faixa_preco == "1M–1,5M"
