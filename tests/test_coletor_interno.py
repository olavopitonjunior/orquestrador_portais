"""Testes do Coletor Interno: as conversões puras linha→dataclass.

A I/O (conexão real ao Newcore) não roda no CI — precisa de credencial e banco.
O que se testa é a montagem dos contratos do domínio a partir de linhas-fixture
(dicts como o pymysql DictCursor devolve), mais a guarda de leitura e a
interpolação fechada da coluna de distrito.
"""

import re
import sqlite3
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
from dominio.elegibilidade import ORDEM_RELAXAMENTO, Regra, elegivel, regras_reprovadas

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
        sql = _SQL_CANDIDATOS.format(coluna_ativo=d.value, recorte="", login_janela_dias=30)
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


# --- A regra de status passa a VER a fonte transacional (bug do espelho defasado) ---
#
# O espelho `FT_RealtyRelation` atrasa ~13,5 h e dá como Ativo imóvel já removido
# no transacional. Antes desta correção a coluna era `(f.RealtyStatus = 'Ativo')`,
# tautologicamente True sob o WHERE — a regra existia, era testada, e nunca mordia.


def test_status_do_espelho_sozinho_NAO_decide_mais_a_publicacao():
    """A coluna tem de exigir as DUAS fontes. Este teste morre se alguém apagar
    o termo do transacional e voltar a confiar só no espelho — que é exatamente
    o defeito corrigido, e a metade fácil de apagar sem perceber."""
    sql = _SQL_CANDIDATOS
    assert "COALESCE(r.PublishStatus_Id, 0) = 1" in sql
    assert "f.RealtyStatus = 'Ativo'\n     AND COALESCE" in sql
    # E o recorte do WHERE continua no espelho: é ele que traz distrito e gestor.
    assert "WHERE f.RealtyStatus = 'Ativo'" in sql


def test_a_expressao_REAL_de_publicacao_ativa_se_comporta_como_declarado():
    """Teste de COMPORTAMENTO, não de texto — e amarrado ao SQL de verdade.

    A expressão é ANSI padrão, então roda no sqlite sem banco nem credencial.
    O ponto crítico: ela é EXTRAÍDA de `_SQL_CANDIDATOS`, não reescrita aqui.
    Um teste que copiasse a expressão continuaria verde depois de alguém
    reverter o coletor — validaria a própria cópia, não o código."""
    m = re.search(r"\(f\.RealtyStatus.*?\)\s*AS publicacao_ativa", _SQL_CANDIDATOS, re.S)
    assert m, "não achei a expressão de publicacao_ativa no SQL do coletor"
    expr = m.group(0).replace("AS publicacao_ativa", "").replace("f.", "").replace("r.", "")

    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE t (RealtyStatus TEXT, PublishStatus_Id INT)")
    con.executemany(
        "INSERT INTO t VALUES (?,?)",
        [("Ativo", 1), ("Ativo", 3), ("Ativo", None)],
    )
    # O WHERE do coletor entra junto: é ele que garante que o primeiro termo do
    # AND é sempre verdadeiro, e portanto que a expressão nunca devolve NULL.
    obtido = [r[0] for r in con.execute(f"SELECT {expr} FROM t WHERE RealtyStatus = 'Ativo'")]

    assert obtido == [1, 0, 0], "publicado passa; removido reprova; nulo = não publicado"
    assert None not in obtido, "a coluna nunca pode chegar ao Python como None"


def test_imovel_removido_no_transacional_REPROVA_com_motivo_registrado():
    """O ponto da correção: o defasado entra como candidato e é reprovado com
    motivo, em vez de sumir do universo sem deixar linha (critério `:489`)."""
    c = linha_para_candidato({**LINHA, "publicacao_ativa": 0}, {})
    assert c.publicacao_ativa is False

    # `atualizado_em` da fixture é 30/08/2026; a referência mantém o imóvel
    # dentro dos 90 dias, para o teste falar SÓ de status.
    ref = date(2026, 9, 2)
    assert Regra.STATUS_ATIVO in regras_reprovadas(c, ref)
    assert not elegivel(c, ref)


def test_removido_NAO_volta_por_relaxamento():
    """Se status fosse relaxável, a correção teria criado um caminho de volta
    para a vitrine PAGA — pior que o defeito que ela conserta."""
    assert Regra.STATUS_ATIVO not in ORDEM_RELAXAMENTO
    # A ordem nova (D-027) tem seis degraus e começa pelo perfil; status segue fora.
    assert len(ORDEM_RELAXAMENTO) == 6 and ORDEM_RELAXAMENTO[0] is Regra.PERFIL_DE_CONVERSAO


# --- recorte amostral pela raspagem (A2) --------------------------------------


def test_recorte_entra_no_sql_como_IN_de_inteiros_ordenados():
    """Ordenado: o mesmo conjunto produz o mesmo SQL (invariante 5). Antes do ORDER BY."""
    from dados.coletor_interno import _SQL_CANDIDATOS, _clausula_recorte

    sql = _SQL_CANDIDATOS.format(
        coluna_ativo="Brokers", recorte=_clausula_recorte({30, 10, 20}), login_janela_dias=30
    )
    assert "AND f.Realty_Id IN (10, 20, 30)" in sql
    assert sql.index("IN (10, 20, 30)") < sql.index("ORDER BY f.Realty_Id")


def test_sem_recorte_o_sql_e_o_de_sempre():
    from dados.coletor_interno import _SQL_CANDIDATOS, _clausula_recorte

    assert _clausula_recorte(None) == ""
    sql = _SQL_CANDIDATOS.format(coluna_ativo="Brokers", recorte="", login_janela_dias=30)
    assert "Realty_Id IN (" not in sql


# --- a janela do login do gestor (D-029, D-033) ---------------------------------


def test_o_sql_exige_os_TRES_placeholders():
    """`.format` sem `login_janela_dias` falha: a janela é parâmetro da rodada e não
    pode ficar embutida em silêncio no texto."""
    with pytest.raises(KeyError):
        _SQL_CANDIDATOS.format(coluna_ativo="Brokers", recorte="")
    sql = _SQL_CANDIDATOS.format(coluna_ativo="Brokers", recorte="", login_janela_dias=45)
    assert "INTERVAL 45 DAY" in sql
    assert "AS gestor_logou_na_janela" in sql


@pytest.mark.parametrize("janela", [0, -1, True, False, "30", 30.0, None])
def test_coletar_recusa_janela_de_login_invalida_ANTES_de_consultar(monkeypatch, janela):
    """Teste puro: `consultar` é substituído por um que estoura se for chamado. A
    validação vem antes de qualquer I/O — e `True` é recusado porque é subclasse de
    `int` e viraria `INTERVAL 1 DAY` em silêncio."""
    import dados.coletor_interno as ci

    def _nunca(*a, **k):
        raise AssertionError("consultar não pode ser chamado com janela inválida")

    monkeypatch.setattr(ci, "consultar", _nunca)
    with pytest.raises(ValueError, match="login_janela_dias inválido"):
        ci.coletar(DefinicaoAtivoDistrito.TOTAL, login_janela_dias=janela)


def test_coletar_leva_a_janela_declarada_ao_sql(monkeypatch):
    import dados.coletor_interno as ci

    consultas: list[str] = []
    monkeypatch.setattr(ci, "consultar", lambda sql, *a, **k: (consultas.append(sql), [])[1])
    candidatos, penalizaveis = ci.coletar(DefinicaoAtivoDistrito.TOTAL, login_janela_dias=45)
    assert (candidatos, penalizaveis) == ([], [])
    assert "INTERVAL 45 DAY" in consultas[0]
    assert "INTERVAL 30 DAY) AS gestor_logou_na_janela" not in consultas[0]


def test_gestor_logou_na_janela_e_mapeado_e_ausente_vira_None():
    assert (
        linha_para_candidato({**LINHA, "gestor_logou_na_janela": 1}, None).gestor_logou_na_janela
        is True
    )
    assert (
        linha_para_candidato({**LINHA, "gestor_logou_na_janela": 0}, None).gestor_logou_na_janela
        is False
    )
    # linha antiga, sem a coluna: "a coleta não trouxe" — None, não False
    assert linha_para_candidato(LINHA, None).gestor_logou_na_janela is None


def test_login_do_gestor_nao_muda_a_elegibilidade_do_candidato_montado():
    """D-029: trava do relaxamento, não regra. O veredito é o mesmo com e sem login."""
    hoje = date(2026, 9, 3)
    com = linha_para_candidato({**LINHA, "gestor_logou_na_janela": 1}, None)
    sem = linha_para_candidato({**LINHA, "gestor_logou_na_janela": 0}, None)
    assert regras_reprovadas(com, hoje) == regras_reprovadas(sem, hoje) == frozenset()


def test_recorte_vazio_e_recusado_antes_de_consultar():
    from dados.coletor_interno import _clausula_recorte

    with pytest.raises(ValueError, match="VAZIO"):
        _clausula_recorte(set())


def test_recorte_so_aceita_inteiros_e_nao_confunde_bool():
    """Interpolado no SQL (o texto tem `%` em comentário e não pode ir parametrizado),
    então a validação é a única barreira: string é recusada, e `True` também — é
    subclasse de `int` e viraria `1` em silêncio."""
    from dados.coletor_interno import _clausula_recorte

    with pytest.raises(TypeError):
        _clausula_recorte({"101"})
    with pytest.raises(TypeError):
        _clausula_recorte({True, 2})


def test_sql_com_percentual_no_texto_nao_quebra_a_ponte(monkeypatch):
    """Regressão da primeira execução real da sexta.

    `consultar(sql)` sem parâmetros passava `()` ao pymysql, que aplica `query % args`
    sempre que `args` não é None. Uma tupla vazia não escapa disso: qualquer `%` no
    texto do SQL vira especificador de formato e estoura com TypeError. O SQL do
    coletor tem dois percentuais em COMENTÁRIO — números de medição —, então a coleta
    interna falhava contra a base viva enquanto todos os testes ficavam verdes, porque
    nenhum deles atravessava a ponte.

    O teste substitui a conexão e afirma o que a ponte ENTREGA ao driver: com
    parâmetros, dois argumentos; sem, apenas um.
    """
    from dados import newcore

    chamadas: list[tuple] = []

    class _Cursor:
        def execute(self, *args):
            chamadas.append(args)

        def fetchall(self):
            return []

        def __enter__(self):
            return self

        def __exit__(self, *e):
            return False

    class _Conn:
        def cursor(self):
            return _Cursor()

        def __enter__(self):
            return self

        def __exit__(self, *e):
            return False

    monkeypatch.setattr(newcore, "conectar", lambda *a, **k: _Conn())

    newcore.consultar("SELECT 1 -- 94,8% dos ativos")
    assert len(chamadas[-1]) == 1, "sem parâmetros, o SQL não pode passar por formatação"

    newcore.consultar("SELECT %s", (1,))
    assert len(chamadas[-1]) == 2, "com parâmetros, o driver precisa recebê-los"


# --- código do portal (descritivo) ---------------------------------------------


def test_o_select_traz_o_codigo_do_portal_como_coluna_descritiva():
    assert "r.NewIdMarketingRotation" in _SQL_CANDIDATOS
    assert "AS codigo_portal" in _SQL_CANDIDATOS


def test_codigo_portal_e_mapeado_e_ausente_vira_None():
    assert (
        linha_para_candidato({**LINHA, "codigo_portal": "431347A"}, None).codigo_portal == "431347A"
    )
    # linha antiga, sem a coluna: o campo é descritivo e fica nulo, não quebra
    assert linha_para_candidato(LINHA, None).codigo_portal is None
    assert linha_para_candidato({**LINHA, "codigo_portal": "  "}, None).codigo_portal is None
    assert linha_para_candidato({**LINHA, "codigo_portal": None}, None).codigo_portal is None


def test_nenhuma_regra_le_o_codigo_do_portal():
    """Descritivo de verdade: mudar o código não muda o veredito de elegibilidade."""
    com = linha_para_candidato({**LINHA, "codigo_portal": "431347A"}, None)
    sem = linha_para_candidato(LINHA, None)
    hoje = date(2026, 9, 3)
    assert regras_reprovadas(com, hoje) == regras_reprovadas(sem, hoje)


def test_o_default_da_janela_de_login_nao_diverge_do_adotado():
    """Mesma trava do mínimo do distrito: `dados` não importa `config` (seria inverter
    a camada), então o default duplica o adotado e é o teste que os amarra. Nos
    caminhos fiados o valor vem do carregador; o default só vale em chamada direta."""
    import inspect

    from config.adotados import ADOTADOS
    from dados.coletor_interno import coletar

    padrao = inspect.signature(coletar).parameters["login_janela_dias"].default
    assert padrao == ADOTADOS["corretor.login_janela_dias"] == 30
