"""Testes da conversão linha-do-banco → LeadDoPeriodo (rodada de segunda).

Puros: exercitam `_para_lead` com linhas no formato exato que o MySQL devolve, sem
tocar o banco. O que importa provar aqui é a D-018 — um lead cujo `AttendedAt` foi
APAGADO na remoção não pode ser acusado de abandono se passou por atendimento.
"""

from datetime import date, datetime

import pytest

from dados.acompanhamento import _para_lead, coletar_leads


def _linha(**extra):
    base = {
        "lead_id": 1001,
        "imovel_id": 55,
        "entrada": datetime(2026, 8, 29, 10, 30),
        "distribuicao": datetime(2026, 8, 29, 10, 31),
        "atendido_em": None,
        "qtde_contatos": 0,
        "corretor_gestor": "Corretor X",
        "gestor_distrito": "Embaixador Y",
        "distrito": "Centro",
        "atendeu_algum_dia": 0,
    }
    base.update(extra)
    return base


# --- D-018: o histórico resgata o lead cujo carimbo foi apagado ---------------


def test_atendimento_pelo_estado_atual():
    lead = _para_lead(_linha(atendido_em=datetime(2026, 8, 30, 9, 0)))
    assert lead.atendimento_registrado is True


def test_atendimento_pelo_historico_mesmo_sem_carimbo():
    """O caso que a D-018 existe para cobrir: AttendedAt nulo (lead removido do
    atendimento) mas passagem por 'Atendimento' no histórico. NÃO é abandono."""
    lead = _para_lead(_linha(atendido_em=None, atendeu_algum_dia=1))
    assert lead.atendimento_registrado is True


def test_sem_atendimento_em_nenhuma_das_duas_fontes():
    lead = _para_lead(_linha(atendido_em=None, atendeu_algum_dia=0))
    assert lead.atendimento_registrado is False


def test_contato_vem_da_contagem():
    assert _para_lead(_linha(qtde_contatos=3)).contato_registrado is True
    assert _para_lead(_linha(qtde_contatos=0)).contato_registrado is False
    assert _para_lead(_linha(qtde_contatos=None)).contato_registrado is False


# --- conversão de tipos e colunas ---------------------------------------------


def test_datetime_vira_date():
    lead = _para_lead(_linha())
    assert lead.entrada == date(2026, 8, 29)
    assert lead.distribuicao == date(2026, 8, 29)


def test_distribuicao_ausente_fica_none():
    """6,4% dos leads não têm distribuição: ausência declarada, nunca a entrada."""
    lead = _para_lead(_linha(distribuicao=None))
    assert lead.distribuicao is None
    assert lead.entrada == date(2026, 8, 29)  # a entrada continua lá


def test_responsaveis_e_distrito():
    lead = _para_lead(_linha())
    assert lead.corretor_gestor == "Corretor X"
    assert lead.gestor_distrito == "Embaixador Y"  # D-019: o embaixador
    assert lead.distrito == "Centro"


def test_string_vazia_vira_none():
    lead = _para_lead(_linha(corretor_gestor="", gestor_distrito="", distrito=""))
    assert lead.corretor_gestor is None
    assert lead.gestor_distrito is None
    assert lead.distrito is None


def test_lead_id_e_o_facid():
    """O grão é FacId (par lead↔imóvel); LeadID duplicaria linhas."""
    assert _para_lead(_linha(lead_id=987)).lead_id == 987


# --- guarda de período --------------------------------------------------------


def test_periodo_invertido_falha_antes_de_consultar():
    with pytest.raises(ValueError):
        coletar_leads(date(2026, 8, 31), date(2026, 8, 28))


def test_entrada_nula_falha_alto_em_vez_de_passar():
    """`CreatedAt` é NOT NULL na origem; se vier nulo, a origem mudou — falha alto
    em vez de deixar passar um lead sem data para o domínio."""
    with pytest.raises(ValueError, match="CreatedAt"):
        _para_lead(_linha(entrada=None))


def test_atendeu_algum_dia_como_string_zero_nao_esvazia_a_lista():
    """Modo de falha caro: se o driver devolvesse "0", um `bool()` diria True e a
    aba de cobrança esvaziaria em silêncio. `int()` mantém o lead na lista."""
    lead = _para_lead(_linha(atendido_em=None, atendeu_algum_dia="0"))
    assert lead.atendimento_registrado is False


def test_sql_nao_tem_interpolacao():
    """Trava a regressão: a consulta é 100% parametrizada, sem f-string/format."""
    from dados.acompanhamento import _SQL_LEADS

    assert "{" not in _SQL_LEADS and "}" not in _SQL_LEADS
