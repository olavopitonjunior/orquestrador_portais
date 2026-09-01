"""Testes do Coletor Interno: as conversões puras linha→dataclass.

A I/O (conexão real ao Newcore) não roda no CI — precisa de credencial e banco.
O que se testa é a montagem dos contratos do domínio a partir de linhas-fixture
(dicts como o pymysql DictCursor devolve), mais a guarda de leitura e a
interpolação fechada da coluna de distrito.
"""

from datetime import date, datetime
from decimal import Decimal

import pytest

from dados import newcore
from dados.coletor_interno import (
    _SQL_CANDIDATOS,
    DefinicaoAtivoDistrito,
    _agrupar_notas,
    _dedup_por_imovel,
    linha_para_candidato,
    linha_para_penalizavel,
)
from dominio.elegibilidade import elegivel

LINHA = {
    "imovel_id": 101,
    "publicacao_ativa": 1,
    "categoria": "Apartamento",
    "preco": Decimal("850000.00"),
    "qtd_fotos": 28,
    "atualizado_em": datetime(2026, 8, 30, 12, 0, 0),
    "gestor_ativo_30d": 1,
    "produtividade_gestor_30d": 4,
    "ativos_no_distrito": 5,
    "alguma_categoria_avaliada": 1,
    "leads_180d": 7,
}


def test_linha_para_candidato_monta_o_contrato_do_dominio():
    c = linha_para_candidato(LINHA, {"Quantidade de fotos": 8, "Descrição do imóvel": 10})
    assert c.imovel_id == 101
    assert c.publicacao_ativa is True
    assert c.categoria == "Apartamento"
    assert c.preco == 850000  # int, reais (centavos truncados)
    assert isinstance(c.preco, int)
    assert c.qtd_fotos == 28
    assert c.atualizado_em == date(2026, 8, 30)  # datetime → date
    assert c.gestor_captou_ou_vendeu_30d is True
    assert c.produtividade_gestor_30d == 4  # F4 contínuo (D-017), separado do binário
    assert c.corretores_ativos_no_distrito == 5
    assert c.notas_por_categoria == {"Quantidade de fotos": 8, "Descrição do imóvel": 10}


def test_preco_decimal_com_centavos_vira_int_reais():
    assert linha_para_candidato({**LINHA, "preco": Decimal("299999.99")}, None).preco == 299999


def test_produtividade_nula_vira_zero():
    # LEFT JOIN sem linha em productivityrating → coluna None; o mapeamento
    # (int(... or 0)) e o COALESCE do SQL degeneram para 0, sem quebrar.
    c = linha_para_candidato({**LINHA, "produtividade_gestor_30d": None}, None)
    assert c.produtividade_gestor_30d == 0


def test_sem_avaliacao_notas_e_None_nao_dict_vazio():
    # None (sem nenhuma categoria) é distinto de {} para a regra cadastro completo (D-007).
    c = linha_para_candidato(LINHA, None)
    assert c.notas_por_categoria is None


def test_candidato_montado_passa_pela_elegibilidade_real():
    # A linha-fixture representa um imóvel elegível; o contrato tem de casar com
    # o domínio em main sem drift (a montagem produz um ImovelCandidato válido).
    c = linha_para_candidato(LINHA, {"Descrição do imóvel": 10})
    assert elegivel(c, date(2026, 8, 31)) is True


def test_categoria_fora_das_aceitas_reprova_na_elegibilidade():
    c = linha_para_candidato({**LINHA, "categoria": "Casa de Vila"}, None)
    assert elegivel(c, date(2026, 8, 31)) is False


def test_mutacao_das_notas_originais_nao_vaza():
    notas = {"Descrição do imóvel": 10}
    c = linha_para_candidato(LINHA, notas)
    notas["Descrição do imóvel"] = 0
    assert c.notas_por_categoria["Descrição do imóvel"] == 10


def test_linha_para_penalizavel_sem_janelas_do_registro():
    p = linha_para_penalizavel(LINHA)
    assert p.imovel_id == 101
    assert p.janelas_anteriores == ()  # histórico vem do Registro, não do Newcore
    assert p.alguma_categoria_avaliada is True
    assert p.leads_180d == 7


def test_leads_nulo_vira_zero():
    assert linha_para_penalizavel({**LINHA, "leads_180d": None}).leads_180d == 0


def test_dedup_por_imovel_mantem_primeira_e_ordem():
    linhas = [{"imovel_id": 3}, {"imovel_id": 1}, {"imovel_id": 3}, {"imovel_id": 2}]
    assert [r["imovel_id"] for r in _dedup_por_imovel(linhas)] == [3, 1, 2]


def test_agrupar_notas_por_imovel():
    linhas = [
        {"imovel_id": 1, "categoria": "A", "score": 5},
        {"imovel_id": 1, "categoria": "B", "score": 0},
        {"imovel_id": 2, "categoria": "A", "score": 9},
    ]
    assert _agrupar_notas(linhas) == {1: {"A": 5, "B": 0}, 2: {"A": 9}}


# --- segurança da interpolação e da leitura ---


def test_coluna_de_distrito_e_conjunto_fechado():
    # A coluna interpolada vem do enum (valor fixo), nunca de entrada livre.
    for d in DefinicaoAtivoDistrito:
        sql = _SQL_CANDIDATOS.format(coluna_ativo=d.value)
        assert d.value in sql
        assert d.value in {
            "Brokers",
            "BrokersProductivity",
            "Brokers_logged30d",
            "BrokersEnabledLeads",
        }


def test_consultar_recusa_escrita():
    # A guarda de leitura (suspensória do invariante 1): nada além de SELECT/SHOW.
    # WITH é bloqueado de propósito — no MySQL 8 uma CTE pode terminar em DELETE.
    for sql in (
        "UPDATE realties SET x=1",
        "DELETE FROM t",
        "INSERT INTO t VALUES (1)",
        "DROP TABLE t",
        "WITH x AS (SELECT 1) DELETE FROM t WHERE t.id IN (SELECT * FROM x)",
    ):
        with pytest.raises(ValueError, match="só aceita SELECT"):
            newcore.consultar(sql)
