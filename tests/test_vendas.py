"""Testes da leitura de vendas: as conversões e a bucketização puras.

A I/O (conexão real ao Newcore) não roda no CI. O que se testa é a montagem de
ImovelVendido a partir de linhas-fixture e as faixas/colapsos de dimensão.
"""

from decimal import Decimal

from dados.vendas import (
    _bucketiza_contagem,
    _faixa_de_preco,
    linha_para_vendido,
)

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


def test_faixa_de_preco_nos_limites():
    assert _faixa_de_preco(299_999) == "< 300k"
    assert _faixa_de_preco(300_000) == "300k–500k"  # limite inferior inclusivo
    assert _faixa_de_preco(700_000) == "700k–1M"    # piso do super destaque
    assert _faixa_de_preco(3_000_000) == "≥ 3M"
    assert _faixa_de_preco(None) is None


def test_faixa_de_preco_limites_internos():
    # Cada limite interno é inferior-inclusivo, superior-exclusivo (sem furo).
    assert _faixa_de_preco(499_999) == "300k–500k"
    assert _faixa_de_preco(500_000) == "500k–700k"
    assert _faixa_de_preco(999_999) == "700k–1M"
    assert _faixa_de_preco(1_000_000) == "1M–1,5M"
    assert _faixa_de_preco(1_499_999) == "1M–1,5M"
    assert _faixa_de_preco(1_500_000) == "1,5M–3M"
    assert _faixa_de_preco(2_999_999) == "1,5M–3M"


def test_colapso_de_dormitorios_e_vagas():
    # ≥ teto colapsa no teto ("N ou mais"); abaixo mantém o valor.
    assert _bucketiza_contagem(7, 5) == 5
    assert _bucketiza_contagem(5, 5) == 5
    assert _bucketiza_contagem(3, 5) == 3
    assert _bucketiza_contagem(4, 3) == 3  # vagas colapsa em 3
    assert _bucketiza_contagem(0, 3) == 0


def test_valores_nulos_viram_none():
    assert _bucketiza_contagem(None, 5) is None
    v = linha_para_vendido({**LINHA, "dormitorios": None, "vagas": None, "preco": None})
    assert v.dormitorios is None
    assert v.vagas is None
    assert v.faixa_preco is None


def test_negativo_vira_none():
    # Anomalia de dado não vira bucket 0; a coleta aborta rodada com dado inválido.
    assert _bucketiza_contagem(-1, 5) is None


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
