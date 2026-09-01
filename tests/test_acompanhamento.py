"""Testes da apuração da rodada de segunda (Spec §4).

Módulo puro — roda no CI sem banco. Cobre o critério conservador de "lead sem
tratamento" (§4.2), a listagem COMPLETA das posições inclusive zero-lead (§4.3),
o gate de ausência de carga aprovada (§7.3), o determinismo e a fronteira de PII
(o resumo agregado não carrega identidade).
"""

from dataclasses import fields
from datetime import date

import pytest

from dominio.acompanhamento import (
    DesempenhoImovel,
    LeadDoPeriodo,
    PosicaoPaga,
    ResumoAcompanhamento,
    SemCargaAprovada,
    apurar,
    payload_para_modelo,
    sem_tratamento,
)

INICIO = date(2026, 8, 28)  # sexta (carga)
FIM = date(2026, 8, 31)  # segunda (apuração)


def _lead(lead_id, imovel_id, *, atendido=False, contatado=False, entrada=INICIO, **extra):
    return LeadDoPeriodo(
        lead_id=lead_id,
        imovel_id=imovel_id,
        entrada=entrada,
        atendimento_registrado=atendido,
        contato_registrado=contatado,
        **extra,
    )


def _apurar(posicoes, leads, **kw):
    return apurar(
        rodada_decisao_id=7,
        posicoes=posicoes,
        leads=leads,
        inicio_periodo=INICIO,
        fim_periodo=FIM,
        **kw,
    )


# --- §4.2: sem tratamento exige as DUAS ausências ----------------------------


def test_sem_tratamento_exige_as_duas_ausencias():
    assert sem_tratamento(_lead(1, 1)) is True  # sem atendimento e sem contato
    assert sem_tratamento(_lead(1, 1, atendido=True)) is False  # teve atendimento
    assert sem_tratamento(_lead(1, 1, contatado=True)) is False  # teve contato
    assert sem_tratamento(_lead(1, 1, atendido=True, contatado=True)) is False


def test_conta_apenas_o_abandono_indiscutivel():
    pos = [PosicaoPaga(1, "destaque")]
    r = _apurar(pos, [_lead(10, 1), _lead(11, 1, contatado=True), _lead(12, 1, atendido=True)])
    assert r.resumo.leads_gerados == 3
    assert r.resumo.leads_sem_tratamento == 1  # só o que não teve nem um nem outro
    assert [x.lead_id for x in r.leads_sem_tratamento] == [10]


# --- §4.3: lista TODAS as posições, inclusive zero lead ----------------------


def test_lista_completa_inclui_imovel_sem_lead():
    pos = [PosicaoPaga(1, "super_destaque"), PosicaoPaga(2, "destaque")]
    r = _apurar(pos, [_lead(10, 1)])  # o imóvel 2 não gerou nada
    assert [d.imovel_id for d in r.desempenho] == [1, 2]  # os dois aparecem
    assert r.desempenho[1].leads_gerados == 0
    assert r.resumo.imoveis_sem_lead == 1


def test_super_destaque_vem_primeiro_e_ordem_e_estavel():
    pos = [PosicaoPaga(9, "destaque"), PosicaoPaga(5, "super_destaque"), PosicaoPaga(3, "destaque")]
    r = _apurar(pos, [])
    assert [(d.nivel, d.imovel_id) for d in r.desempenho] == [
        ("super_destaque", 5),
        ("destaque", 3),
        ("destaque", 9),
    ]


def test_historico_ausente_fica_none_nao_zero():
    pos = [PosicaoPaga(1, "destaque"), PosicaoPaga(2, "destaque")]
    r = _apurar(pos, [], historico={1: (3, 12)})
    assert (r.desempenho[0].semanas_consecutivas, r.desempenho[0].leads_acumulados_janela) == (
        3,
        12,
    )
    # imóvel sem histórico: declarado ausente (None), não inventado como 0
    assert r.desempenho[1].semanas_consecutivas is None
    assert r.desempenho[1].leads_acumulados_janela is None


# --- §7.3: sem carga aprovada, não emite -------------------------------------


def test_sem_carga_aprovada_nao_emite():
    with pytest.raises(SemCargaAprovada):
        _apurar([], [_lead(10, 1)])


# --- higiene da entrada -------------------------------------------------------


def test_lead_de_imovel_fora_da_carga_e_descartado_e_contado():
    pos = [PosicaoPaga(1, "destaque")]
    r = _apurar(pos, [_lead(10, 1), _lead(11, 999)])  # 999 não está na carga
    assert r.resumo.leads_gerados == 1
    assert all(x.imovel_id == 1 for x in r.leads_sem_tratamento)
    assert r.resumo.leads_fora_da_carga == 1  # descarte contado, não silencioso


def test_colapso_prefere_o_valor_conhecido_e_nao_fabrica_ausencia():
    """Um LEFT JOIN parcial traz o mesmo lead em duas linhas — uma com responsável e
    distribuição, outra sem. O colapso não pode escolher a linha VAZIA: isso criaria
    uma ausência sobre dado que a origem tem, esvaziando colunas da §4.2."""
    pos = [PosicaoPaga(1, "destaque")]
    cheia = _lead(
        10, 1, distribuicao=date(2026, 8, 29), corretor_gestor="Corretor X", distrito="Centro"
    )
    vazia = _lead(10, 1)  # mesma chave, sem os dados
    for ordem in ([cheia, vazia], [vazia, cheia]):
        r = _apurar(pos, ordem)
        linha = r.leads_sem_tratamento[0]
        assert linha.corretor_gestor == "Corretor X"  # o valor conhecido vence
        assert linha.distrito == "Centro"
        assert linha.tempo_desde_distribuicao == (FIM - date(2026, 8, 29)).days
        assert r.resumo.sem_tratamento_sem_responsavel == 0  # não infla a ausência
        assert r.resumo.sem_tratamento_sem_distribuicao == 0


def test_lead_duplicado_conta_uma_vez():
    pos = [PosicaoPaga(1, "destaque")]
    r = _apurar(pos, [_lead(10, 1), _lead(10, 1)])  # mesmo lead_id repetido no join
    assert r.resumo.leads_gerados == 1


def test_duplicata_divergente_colapsa_por_or_e_independe_da_ordem():
    """O join por atendimento pode trazer o MESMO lead com sinais diferentes. O
    colapso é por OR (§4.2: se qualquer linha registrou tratamento, houve
    tratamento) — e o resultado não pode depender da ordem de chegada (inv. 5)."""
    pos = [PosicaoPaga(1, "destaque")]
    a = _lead(10, 1, atendido=False)
    b = _lead(10, 1, atendido=True)  # mesma chave, sinal divergente
    r1 = _apurar(pos, [a, b])
    r2 = _apurar(pos, [b, a])
    assert r1 == r2  # ordem do banco não muda a apuração
    assert r1.resumo.leads_gerados == 1
    assert r1.resumo.leads_sem_tratamento == 0  # teve atendimento em alguma linha


def test_nivel_fora_do_vocabulario_falha():
    with pytest.raises(ValueError, match="vocabulário fechado"):
        PosicaoPaga(1, "superdestaque")  # grafia errada não pode passar em silêncio


def test_contagens_do_resumo_fecham_com_as_posicoes():
    pos = [PosicaoPaga(1, "super_destaque"), PosicaoPaga(2, "destaque"), PosicaoPaga(3, "destaque")]
    r = _apurar(pos, [])
    assert r.resumo.posicoes_super + r.resumo.posicoes_destaque == len(pos) == len(r.desempenho)


def test_lead_fora_do_periodo_e_descartado_e_contado():
    pos = [PosicaoPaga(1, "destaque")]
    r = _apurar(
        pos,
        [
            _lead(10, 1, entrada=date(2026, 8, 29)),  # dentro
            _lead(11, 1, entrada=date(2026, 1, 1)),  # antes da carga
            _lead(12, 1, entrada=date(2026, 9, 10)),  # depois do fim
        ],
    )
    assert r.resumo.leads_gerados == 1
    assert r.resumo.leads_fora_do_periodo == 2  # descarte declarado, não silencioso


def test_tempo_desde_distribuicao_usa_a_distribuicao_nao_a_entrada():
    """Spec §4.2 pede DUAS grandezas: data de entrada E tempo desde a distribuição.
    Uma nunca substitui a outra."""
    pos = [PosicaoPaga(1, "destaque")]
    r = _apurar(
        pos,
        [_lead(10, 1, entrada=date(2026, 8, 28), distribuicao=date(2026, 8, 30))],
    )
    linha = r.leads_sem_tratamento[0]
    assert linha.entrada == date(2026, 8, 28)  # a coluna "data de entrada"
    assert linha.tempo_desde_distribuicao == (FIM - date(2026, 8, 30)).days == 1  # ≠ 3


def test_sem_distribuicao_declara_ausencia_em_vez_de_usar_a_entrada():
    pos = [PosicaoPaga(1, "destaque")]
    r = _apurar(pos, [_lead(10, 1, entrada=date(2026, 8, 28))])  # sem distribuição
    assert r.leads_sem_tratamento[0].tempo_desde_distribuicao is None  # nunca 3
    assert r.resumo.sem_tratamento_sem_distribuicao == 1


def test_resumo_conta_leads_sem_responsavel_nomeado():
    """O 'pronto' da rodada de segunda exige responsável nomeado (PRD): a ausência
    precisa ser contável, não silenciosa."""
    pos = [PosicaoPaga(1, "destaque")]
    r = _apurar(pos, [_lead(10, 1), _lead(11, 1, corretor_gestor="Corretor X")])
    assert r.resumo.sem_tratamento_sem_responsavel == 1


def test_imovel_repetido_na_carga_falha():
    with pytest.raises(ValueError, match="repetido"):
        _apurar([PosicaoPaga(1, "destaque"), PosicaoPaga(1, "super_destaque")], [])


def test_periodo_invertido_falha():
    with pytest.raises(ValueError):
        apurar(
            rodada_decisao_id=7,
            posicoes=[PosicaoPaga(1, "destaque")],
            leads=[],
            inicio_periodo=FIM,
            fim_periodo=INICIO,
        )


# --- determinismo -------------------------------------------------------------


def test_mesma_entrada_mesma_saida_em_qualquer_ordem():
    pos = [PosicaoPaga(1, "destaque"), PosicaoPaga(2, "super_destaque")]
    leads = [_lead(10, 1), _lead(11, 2, entrada=date(2026, 8, 29)), _lead(12, 1)]
    a = _apurar(pos, leads)
    b = _apurar(list(reversed(pos)), list(reversed(leads)))
    assert a == b


def test_leads_sem_tratamento_ordenados_por_entrada():
    pos = [PosicaoPaga(1, "destaque")]
    leads = [
        _lead(10, 1, entrada=date(2026, 8, 30)),
        _lead(11, 1, entrada=date(2026, 8, 28)),
    ]
    r = _apurar(pos, leads)
    assert [x.lead_id for x in r.leads_sem_tratamento] == [11, 10]  # mais antigo primeiro


def test_tempo_sai_do_periodo_nao_do_relogio():
    """O tempo decorrido sai de `fim_periodo` (input), nunca de date.today()."""
    pos = [PosicaoPaga(1, "destaque")]
    r = _apurar(pos, [_lead(10, 1, distribuicao=date(2026, 8, 28))])
    assert r.leads_sem_tratamento[0].tempo_desde_distribuicao == (FIM - date(2026, 8, 28)).days


# --- fronteira de PII (invariante 3) -----------------------------------------


# Identidade de PESSOA. `imovel_id` NÃO entra aqui: o invariante 3 permite
# explicitamente características de imóvel — o que ele proíbe é identidade de lead,
# comprador ou corretor.
PII_DE_PESSOA = {"lead_id", "corretor_gestor", "gestor_distrito"}


def test_tipos_que_podem_ir_a_modelo_nao_carregam_identidade():
    """Cadeado dos DOIS tipos model-eligible: se alguém enriquecer o resumo ou o
    desempenho com identidade de pessoa, este teste falha antes do vazamento."""
    for tipo in (ResumoAcompanhamento, DesempenhoImovel):
        nomes = {f.name for f in fields(tipo)}
        assert nomes & PII_DE_PESSOA == set(), f"{tipo.__name__} ganhou identidade de pessoa"


def test_payload_para_modelo_descarta_a_pii():
    """A projeção é a única porta para modelo: o recorte não pode conter a PII —
    nem no tipo, nem no valor serializado."""
    pos = [PosicaoPaga(1, "destaque")]
    r = _apurar(pos, [_lead(10, 1, corretor_gestor="Corretor X", gestor_distrito="Gestor Y")])
    assert r.leads_sem_tratamento  # o resultado completo TEM a PII
    payload = payload_para_modelo(r)
    assert not hasattr(payload, "leads_sem_tratamento")  # o recorte, não
    # sentinela: a identidade não sobrevive à serialização do que iria ao modelo
    serializado = repr(payload)
    assert "Corretor X" not in serializado
    assert "Gestor Y" not in serializado
    # e o que importa para o resumo continua lá
    assert payload.resumo.leads_sem_tratamento == 1
    assert payload.desempenho[0].imovel_id == 1  # característica de imóvel: permitida


def test_pii_do_lead_viaja_para_a_planilha():
    """A linha de lead sem tratamento SIM carrega os campos da Spec §4.2 (é para a
    planilha, lida por gente — nunca para modelo)."""
    pos = [PosicaoPaga(1, "destaque")]
    r = _apurar(
        pos,
        [_lead(10, 1, corretor_gestor="Corretor X", gestor_distrito="Gestor Y", distrito="Centro")],
    )
    linha = r.leads_sem_tratamento[0]
    assert linha.corretor_gestor == "Corretor X"
    assert linha.gestor_distrito == "Gestor Y"
    assert linha.distrito == "Centro"
