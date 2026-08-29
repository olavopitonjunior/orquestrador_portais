"""Testes do ranking (Spec §6.3, D-008).

Contratos cobertos: os dois conjuntos de pesos exatamente como na Spec,
soma 100 obrigatória, aritmética da soma ponderada, desconto de penalidades
(inclusive integração com dominio.penalidades), validação de finitude e
determinismo (invariantes 4 e 5).
"""

import pytest

from dominio.penalidades import (
    ImovelPenalizavel,
    IntensidadesPenalidade,
    desconto_total,
)
from dominio.ranking import (
    PESOS_DESTAQUE,
    PESOS_SUPER_DESTAQUE,
    FatoresNormalizados,
    PesosNivel,
    nota_bruta,
    nota_final,
)


def fatores(**kwargs) -> FatoresNormalizados:
    base = dict(
        imovel_id=1, semelhanca_perfil=0.5, desempenho_proprio=0.5, produtividade_gestor=0.5
    )
    base.update(kwargs)
    return FatoresNormalizados(**base)


# --- pesos: os dois conjuntos da Spec §6.3 -----------------------------------


def test_pesos_super_destaque_sao_os_da_spec():
    assert (
        PESOS_SUPER_DESTAQUE.semelhanca_perfil,
        PESOS_SUPER_DESTAQUE.desempenho_proprio,
        PESOS_SUPER_DESTAQUE.produtividade_gestor,
    ) == (60, 25, 15)


def test_pesos_destaque_sao_os_da_spec():
    assert (
        PESOS_DESTAQUE.semelhanca_perfil,
        PESOS_DESTAQUE.desempenho_proprio,
        PESOS_DESTAQUE.produtividade_gestor,
    ) == (80, 10, 10)


@pytest.mark.parametrize("pesos", [(60, 25, 16), (100, 0, 1), (0, 0, 0)])  # soma != 100
def test_pesos_que_nao_somam_100_sao_erro(pesos):
    s, d, p = pesos
    with pytest.raises(ValueError, match="pesos devem somar 100"):
        PesosNivel(semelhanca_perfil=s, desempenho_proprio=d, produtividade_gestor=p)


@pytest.mark.parametrize("pesos", [(150, -30, -20), (110, 0, -10)])
def test_peso_negativo_e_erro_mesmo_somando_100(pesos):
    s, d, p = pesos
    with pytest.raises(ValueError, match="peso inválido"):
        PesosNivel(semelhanca_perfil=s, desempenho_proprio=d, produtividade_gestor=p)


def test_peso_nao_inteiro_e_erro():
    with pytest.raises(ValueError, match="peso inválido"):
        PesosNivel(semelhanca_perfil=50.5, desempenho_proprio=49.5, produtividade_gestor=0.0)  # type: ignore[arg-type]


def test_pesos_sem_todos_os_campos_falham():
    with pytest.raises(TypeError):
        PesosNivel(semelhanca_perfil=100)  # type: ignore[call-arg]


# --- soma ponderada -----------------------------------------------------------


def test_nota_bruta_e_a_soma_ponderada_literal():
    f = fatores(semelhanca_perfil=1.0, desempenho_proprio=0.0, produtividade_gestor=0.0)
    assert nota_bruta(f, PESOS_SUPER_DESTAQUE) == 60.0
    assert nota_bruta(f, PESOS_DESTAQUE) == 80.0


def test_nota_bruta_combina_os_tres_fatores():
    f = fatores(semelhanca_perfil=1.0, desempenho_proprio=0.5, produtividade_gestor=0.2)
    assert nota_bruta(f, PESOS_SUPER_DESTAQUE) == 60 * 1.0 + 25 * 0.5 + 15 * 0.2
    assert nota_bruta(f, PESOS_DESTAQUE) == 80 * 1.0 + 10 * 0.5 + 10 * 0.2


def test_mesmos_fatores_notas_diferentes_por_nivel():
    # A diferença deliberada entre níveis (PRD): desempenho próprio pesa 2,5x
    # mais no super destaque.
    f = fatores(semelhanca_perfil=0.0, desempenho_proprio=1.0, produtividade_gestor=0.0)
    assert nota_bruta(f, PESOS_SUPER_DESTAQUE) == 2.5 * nota_bruta(f, PESOS_DESTAQUE)


# --- nota final: desconto de penalidades --------------------------------------


def test_nota_final_desconta_penalidades():
    f = fatores(semelhanca_perfil=1.0, desempenho_proprio=1.0, produtividade_gestor=1.0)
    assert nota_final(f, PESOS_DESTAQUE, 30.0) == 100.0 - 30.0


def test_nota_final_sem_penalidade_e_a_bruta():
    f = fatores()
    assert nota_final(f, PESOS_SUPER_DESTAQUE, 0.0) == nota_bruta(f, PESOS_SUPER_DESTAQUE)


def test_nota_final_pode_ficar_negativa():
    f = fatores(semelhanca_perfil=0.0, desempenho_proprio=0.0, produtividade_gestor=0.0)
    assert nota_final(f, PESOS_DESTAQUE, 5.0) == -5.0


def test_nota_final_sem_desconto_como_argumento_falha():
    with pytest.raises(TypeError):
        nota_final(fatores(), PESOS_DESTAQUE)  # type: ignore[call-arg]


@pytest.mark.parametrize("desconto", [-0.1, float("nan"), float("inf")])
def test_desconto_invalido_e_erro_deterministico(desconto):
    with pytest.raises(ValueError, match="desconto de penalidades inválido"):
        nota_final(fatores(), PESOS_DESTAQUE, desconto)


def test_integracao_com_dominio_penalidades():
    # Fixtures ARBITRÁRIAS — o parâmetro pendente nº 3 (D-004) segue nulo.
    intensidades = IntensidadesPenalidade(
        janela_sem_resultado=10.0, sem_avaliacao_por_categoria=5.0, sem_lead_180d=2.0
    )
    alvo = ImovelPenalizavel(
        imovel_id=7, janelas_anteriores=(), alguma_categoria_avaliada=False, leads_180d=0
    )
    desconto = desconto_total(alvo, intensidades, lambda _: 1.0)
    f = fatores(
        imovel_id=7, semelhanca_perfil=1.0, desempenho_proprio=1.0, produtividade_gestor=1.0
    )
    assert nota_final(f, PESOS_DESTAQUE, desconto) == 100.0 - 7.0


def test_integracao_com_decaimento_atravessando_a_fronteira():
    # Fixtures ARBITRÁRIAS — o parâmetro pendente nº 3 (D-004) segue nulo.
    from dominio.penalidades import JanelaAnterior

    intensidades = IntensidadesPenalidade(
        janela_sem_resultado=10.0, sem_avaliacao_por_categoria=5.0, sem_lead_180d=2.0
    )
    alvo = ImovelPenalizavel(
        imovel_id=8,
        janelas_anteriores=(JanelaAnterior(atingiu_resultado=False, ciclos_desde_encerramento=2),),
        alguma_categoria_avaliada=True,
        leads_180d=1,
    )
    desconto = desconto_total(alvo, intensidades, lambda ciclos: 0.5)
    f = fatores(
        imovel_id=8, semelhanca_perfil=1.0, desempenho_proprio=1.0, produtividade_gestor=1.0
    )
    assert nota_final(f, PESOS_SUPER_DESTAQUE, desconto) == 100.0 - 10.0 * 0.5


# --- validação de finitude -----------------------------------------------------


@pytest.mark.parametrize("invalido", [float("nan"), float("inf"), float("-inf")])
def test_fator_nao_finito_e_erro(invalido):
    with pytest.raises(ValueError, match="fator não finito para desempenho_proprio"):
        fatores(desempenho_proprio=invalido)


def test_fator_negativo_e_aceito():
    # A escala dos fatores é o parâmetro pendente nº 2: este módulo não impõe
    # faixa, só finitude. Se a normalização definida vier a excluir negativos,
    # a validação de faixa nasce com ela.
    assert nota_bruta(fatores(desempenho_proprio=-1.0), PESOS_DESTAQUE) == 80 * 0.5 - 10 + 10 * 0.5


# --- determinismo (invariantes 4 e 5) ------------------------------------------


def test_mesma_entrada_mesma_saida():
    f = fatores(semelhanca_perfil=0.37, desempenho_proprio=0.91, produtividade_gestor=0.12)
    notas = {nota_final(f, PESOS_SUPER_DESTAQUE, 1.25) for _ in range(50)}
    assert len(notas) == 1
