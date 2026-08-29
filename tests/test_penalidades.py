"""Testes das penalidades (Spec §6.4).

Contratos cobertos: os três predicados isolados, o caso explícito da Spec
(sem histórico não penaliza), parâmetros pendentes obrigatórios (ausência
falha, nunca produz nota), contrato do decaimento em [0, 1], imutabilidade
da entrada e determinismo (invariantes 4 e 5).
"""

import pytest

from dominio.penalidades import (
    ImovelPenalizavel,
    IntensidadesPenalidade,
    JanelaAnterior,
    Penalidade,
    ciclos_desde_janela_sem_resultado,
    desconto_total,
    penalidades_aplicaveis,
)


def imovel(**kwargs) -> ImovelPenalizavel:
    """Imóvel que não recebe nenhuma penalidade; cada teste liga uma."""
    base = dict(
        imovel_id=1,
        janelas_anteriores=(),
        alguma_categoria_avaliada=True,
        leads_180d=3,
    )
    base.update(kwargs)
    return ImovelPenalizavel(**base)


def janela(atingiu: bool, ciclos: int = 1) -> JanelaAnterior:
    return JanelaAnterior(atingiu_resultado=atingiu, ciclos_desde_encerramento=ciclos)


# Fixtures ARBITRÁRIAS de teste — o parâmetro pendente nº 3 (D-004) segue nulo;
# estes números não são calibração e não devem ser citados como tal.
INTENSIDADES = IntensidadesPenalidade(
    janela_sem_resultado=10.0,
    sem_avaliacao_por_categoria=5.0,
    sem_lead_180d=2.0,
)


def sem_decaimento(_ciclos: int) -> float:
    return 1.0


# --- caso explícito da Spec §6.4 -------------------------------------------


def test_sem_historico_de_destaque_nao_e_penalizado_por_ausencia_de_historico():
    assert Penalidade.JANELA_SEM_RESULTADO not in penalidades_aplicaveis(
        imovel(janelas_anteriores=())
    )


# --- predicados isolados ----------------------------------------------------


def test_imovel_sem_nenhuma_penalidade():
    assert penalidades_aplicaveis(imovel()) == frozenset()


def test_janela_anterior_sem_resultado_penaliza():
    alvo = imovel(janelas_anteriores=(janela(atingiu=False),))
    assert penalidades_aplicaveis(alvo) == {Penalidade.JANELA_SEM_RESULTADO}


def test_janela_anterior_com_resultado_nao_penaliza():
    alvo = imovel(janelas_anteriores=(janela(atingiu=True),))
    assert penalidades_aplicaveis(alvo) == frozenset()


def test_uma_janela_sem_resultado_entre_varias_basta():
    alvo = imovel(
        janelas_anteriores=(janela(atingiu=True, ciclos=5), janela(atingiu=False, ciclos=2))
    )
    assert Penalidade.JANELA_SEM_RESULTADO in penalidades_aplicaveis(alvo)


def test_sem_avaliacao_por_categoria_penaliza():
    alvo = imovel(alguma_categoria_avaliada=False)
    assert penalidades_aplicaveis(alvo) == {Penalidade.SEM_AVALIACAO_POR_CATEGORIA}


def test_sem_lead_em_180_dias_penaliza():
    alvo = imovel(leads_180d=0)
    assert penalidades_aplicaveis(alvo) == {Penalidade.SEM_LEAD_180D}


def test_um_unico_lead_em_180_dias_escapa_da_penalidade():
    assert Penalidade.SEM_LEAD_180D not in penalidades_aplicaveis(imovel(leads_180d=1))


def test_as_tres_penalidades_acumulam():
    alvo = imovel(
        janelas_anteriores=(janela(atingiu=False),),
        alguma_categoria_avaliada=False,
        leads_180d=0,
    )
    assert penalidades_aplicaveis(alvo) == {
        Penalidade.JANELA_SEM_RESULTADO,
        Penalidade.SEM_AVALIACAO_POR_CATEGORIA,
        Penalidade.SEM_LEAD_180D,
    }


# --- janela mais recente dirige o decaimento --------------------------------


def test_ciclos_vem_da_janela_sem_resultado_mais_recente():
    alvo = imovel(
        janelas_anteriores=(
            janela(atingiu=False, ciclos=7),
            janela(atingiu=False, ciclos=3),
            janela(atingiu=True, ciclos=1),  # com resultado não dirige o decaimento
        )
    )
    assert ciclos_desde_janela_sem_resultado(alvo) == 3


def test_empate_de_ciclos_entre_janelas_sem_resultado():
    alvo = imovel(
        janelas_anteriores=(janela(atingiu=False, ciclos=2), janela(atingiu=False, ciclos=2))
    )
    assert ciclos_desde_janela_sem_resultado(alvo) == 2


def test_ciclos_e_none_sem_janela_sem_resultado():
    assert ciclos_desde_janela_sem_resultado(imovel()) is None
    assert ciclos_desde_janela_sem_resultado(imovel(janelas_anteriores=(janela(True),))) is None


# --- desconto: parâmetros pendentes são obrigatórios (D-004, nº 3) -----------


def test_intensidades_sem_todos_os_campos_falham():
    with pytest.raises(TypeError):
        IntensidadesPenalidade(janela_sem_resultado=10.0)  # type: ignore[call-arg]


def test_desconto_sem_decaimento_falha():
    with pytest.raises(TypeError):
        desconto_total(imovel(), INTENSIDADES)  # type: ignore[call-arg]


@pytest.mark.parametrize("invalida", [-1.0, float("nan"), float("inf")])
def test_intensidade_negativa_ou_nao_finita_e_erro(invalida):
    with pytest.raises(ValueError, match="intensidade inválida para sem_lead_180d"):
        IntensidadesPenalidade(
            janela_sem_resultado=1.0, sem_avaliacao_por_categoria=1.0, sem_lead_180d=invalida
        )


def test_desconto_soma_apenas_as_aplicaveis():
    alvo = imovel(alguma_categoria_avaliada=False, leads_180d=0)
    assert desconto_total(alvo, INTENSIDADES, sem_decaimento) == 5.0 + 2.0


def test_desconto_zero_sem_penalidade():
    assert desconto_total(imovel(), INTENSIDADES, sem_decaimento) == 0.0


def test_decaimento_multiplica_apenas_a_penalidade_por_janela():
    alvo = imovel(janelas_anteriores=(janela(atingiu=False, ciclos=2),), leads_180d=0)
    metade = desconto_total(alvo, INTENSIDADES, lambda ciclos: 0.5)
    assert metade == 10.0 * 0.5 + 2.0


def test_decaimento_recebe_os_ciclos_da_janela_mais_recente():
    recebidos: list[int] = []

    def espiao(ciclos: int) -> float:
        recebidos.append(ciclos)
        return 1.0

    alvo = imovel(
        janelas_anteriores=(janela(atingiu=False, ciclos=9), janela(atingiu=False, ciclos=4))
    )
    desconto_total(alvo, INTENSIDADES, espiao)
    assert recebidos == [4]


def test_decaimento_total_zera_o_desconto_mas_a_penalidade_segue_visivel():
    alvo = imovel(janelas_anteriores=(janela(atingiu=False, ciclos=10),))
    assert Penalidade.JANELA_SEM_RESULTADO in penalidades_aplicaveis(alvo)
    assert desconto_total(alvo, INTENSIDADES, lambda _: 0.0) == 0.0


@pytest.mark.parametrize("fator", [-0.1, 1.1])
def test_decaimento_fora_da_faixa_e_erro_deterministico(fator):
    alvo = imovel(janelas_anteriores=(janela(atingiu=False, ciclos=2),))
    with pytest.raises(ValueError, match=r"decaimento fora de \[0, 1\]"):
        desconto_total(alvo, INTENSIDADES, lambda _: fator)


# --- validação de entrada ----------------------------------------------------


def test_leads_negativos_sao_erro():
    with pytest.raises(ValueError, match="leads_180d negativo"):
        imovel(leads_180d=-1)


def test_ciclos_negativos_sao_erro():
    with pytest.raises(ValueError, match="ciclos_desde_encerramento negativo"):
        janela(atingiu=False, ciclos=-1)


def test_janela_encerrada_no_ciclo_corrente_e_valida():
    assert (
        ciclos_desde_janela_sem_resultado(
            imovel(janelas_anteriores=(janela(atingiu=False, ciclos=0),))
        )
        == 0
    )


# --- imutabilidade e determinismo (invariantes 4 e 5) ------------------------


def test_generator_como_janelas_anteriores_e_congelado_na_construcao():
    alvo = imovel(janelas_anteriores=(j for j in [janela(atingiu=False, ciclos=3)]))
    # O generator foi consumido uma única vez na construção; leituras repetidas
    # enxergam a mesma tupla.
    assert penalidades_aplicaveis(alvo) == {Penalidade.JANELA_SEM_RESULTADO}
    assert ciclos_desde_janela_sem_resultado(alvo) == 3


def test_mutacao_da_lista_original_nao_vaza():
    janelas = [janela(atingiu=True)]
    alvo = imovel(janelas_anteriores=janelas)
    janelas.append(janela(atingiu=False))
    assert penalidades_aplicaveis(alvo) == frozenset()


def test_mesma_entrada_mesma_saida():
    alvo = imovel(
        janelas_anteriores=(janela(atingiu=False, ciclos=3), janela(atingiu=True, ciclos=1)),
        alguma_categoria_avaliada=False,
        leads_180d=0,
    )
    resultados = {
        (
            tuple(sorted(p.value for p in penalidades_aplicaveis(alvo))),
            desconto_total(alvo, INTENSIDADES, sem_decaimento),
        )
        for _ in range(50)
    }
    assert len(resultados) == 1
