"""Testes da bucketização — a FONTE ÚNICA compartilhada por vendas e candidatos.

Asserções idênticas às que viviam em test_vendas.py antes do refactor (agora com
os nomes públicos de dados.bucketizacao): a prova de que mover a lógica não mudou
o comportamento. O teste de que candidato e venda com o mesmo valor casam no
mesmo bucket entra junto com a leitura do candidato.
"""

from dados.bucketizacao import (
    bucketiza_contagem,
    faixa_de_preco,
    para_int_reais,
    texto_ou_none,
)


def test_faixa_de_preco_nos_limites():
    assert faixa_de_preco(299_999) == "< 300k"
    assert faixa_de_preco(300_000) == "300k–500k"  # limite inferior inclusivo
    assert faixa_de_preco(700_000) == "700k–1M"  # piso do super destaque
    assert faixa_de_preco(3_000_000) == "≥ 3M"
    assert faixa_de_preco(None) is None


def test_faixa_de_preco_limites_internos():
    # Cada limite interno é inferior-inclusivo, superior-exclusivo (sem furo).
    assert faixa_de_preco(499_999) == "300k–500k"
    assert faixa_de_preco(500_000) == "500k–700k"
    assert faixa_de_preco(999_999) == "700k–1M"
    assert faixa_de_preco(1_000_000) == "1M–1,5M"
    assert faixa_de_preco(1_499_999) == "1M–1,5M"
    assert faixa_de_preco(1_500_000) == "1,5M–3M"
    assert faixa_de_preco(2_999_999) == "1,5M–3M"


def test_colapso_de_dormitorios_e_vagas():
    # ≥ teto colapsa no teto ("N ou mais"); abaixo mantém o valor.
    assert bucketiza_contagem(7, 5) == 5
    assert bucketiza_contagem(5, 5) == 5
    assert bucketiza_contagem(3, 5) == 3
    assert bucketiza_contagem(4, 3) == 3  # vagas colapsa em 3
    assert bucketiza_contagem(0, 3) == 0


def test_nulos_e_negativo_viram_none():
    # Nulo é ausência; negativo é anomalia — nenhum vira bucket 0.
    assert bucketiza_contagem(None, 5) is None
    assert bucketiza_contagem(-1, 5) is None


def test_texto_ou_none_apara_e_anula_vazio():
    assert texto_ou_none("  Centro ") == "Centro"
    assert texto_ou_none("   ") is None
    assert texto_ou_none("") is None
    assert texto_ou_none(None) is None


def test_para_int_reais_trunca_e_trata_none():
    from decimal import Decimal

    assert para_int_reais(Decimal("650000.99")) == 650_000
    assert para_int_reais(300000.5) == 300_000
    assert para_int_reais(None) is None
