"""Testes da leitura de vendas: a montagem de ImovelVendido a partir de linhas.

A I/O (conexão real ao Newcore) não roda no CI. O que se testa aqui é
`linha_para_vendido` — a bucketização em si vive em test_bucketizacao.py (fonte
única).
"""

from decimal import Decimal

import pytest

from dados.vendas import _vendas_ancoraveis, linha_para_vendido

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


# --- Realty_Id nulo: descarte contado, nunca silencioso (fix da rodada real) ---


def test_vendas_ancoraveis_separa_e_conta_os_sem_imovel():
    # Duas ofertas assinadas têm Realty_Id nulo (patologia real, ~2 de 177):
    # ficam de fora e são CONTADAS.
    rows = [
        {**LINHA, "imovel_id": 1},
        {**LINHA, "imovel_id": None},
        {**LINHA, "imovel_id": 2},
        {**LINHA, "imovel_id": None},
    ]
    ancoraveis, descartadas = _vendas_ancoraveis(rows)
    assert [r["imovel_id"] for r in ancoraveis] == [1, 2]
    assert descartadas == 2


def test_vendas_ancoraveis_sem_nulos_nao_descarta():
    rows = [{**LINHA, "imovel_id": 1}, {**LINHA, "imovel_id": 2}]
    ancoraveis, descartadas = _vendas_ancoraveis(rows)
    assert len(ancoraveis) == 2
    assert descartadas == 0


def test_vendas_ancoraveis_vazio():
    assert _vendas_ancoraveis([]) == ([], 0)


def test_linha_para_vendido_falha_alto_com_imovel_id_nulo():
    # Tripwire: após o filtro de _vendas_ancoraveis, um nulo aqui é regressão —
    # falha alto em vez de mascarar (era o int(None) que quebrava a rodada real).
    with pytest.raises(ValueError, match="Realty_Id.*nulo|imovel_id.*nulo"):
        linha_para_vendido({**LINHA, "imovel_id": None})
