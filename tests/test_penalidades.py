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
    com_janelas,
    desconto_total,
    descontos_por_penalidade,
    julgar_janelas,
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


# --- julgar_janelas: o limiar por nível vira booleano, e é INJETADO ------------


def test_julga_cada_janela_pela_regua_do_SEU_nivel():
    """A §6.4 penaliza a janela que "não atingiu o resultado esperado PARA O NÍVEL".
    Duas janelas com os MESMOS leads podem ter vereditos opostos — é o ponto."""
    julgadas = julgar_janelas(
        [("super_destaque", 2, 0), ("destaque", 2, 1)],
        {"super_destaque": 5, "destaque": 1},
    )
    assert [j.atingiu_resultado for j in julgadas] == [False, True]
    assert [j.ciclos_desde_encerramento for j in julgadas] == [0, 1]


def test_limiar_ausente_para_um_nivel_e_ERRO_nao_default():
    """Cair na régua de outro nível é exatamente o que a §6.4 proíbe ao dizer "para o
    nível" — e um default aqui seria invisível na planilha."""
    with pytest.raises(ValueError, match="POR NÍVEL"):
        julgar_janelas([("super_destaque", 9, 0)], {"destaque": 1})


def test_atingir_o_limiar_EXATO_conta_como_resultado():
    """`>=`, não `>`: o limiar é "o resultado esperado", e alcançá-lo é atingi-lo."""
    (j,) = julgar_janelas([("destaque", 3, 0)], {"destaque": 3})
    assert j.atingiu_resultado is True


def test_sem_janela_nenhuma_o_resultado_e_vazio():
    assert julgar_janelas([], {"destaque": 1}) == ()


def test_com_janelas_acopla_sem_tocar_o_resto():
    """O Coletor Interno lê só o Newcore e devolve a lista vazia; o histórico vem do
    Registro. `com_janelas` é a costura, e não pode mexer em mais nada."""
    base = imovel(leads_180d=7, alguma_categoria_avaliada=False)
    j = janela(atingiu=False, ciclos=2)
    novo = com_janelas(base, [j])

    assert novo.janelas_anteriores == (j,)
    assert (novo.imovel_id, novo.leads_180d, novo.alguma_categoria_avaliada) == (
        base.imovel_id,
        base.leads_180d,
        base.alguma_categoria_avaliada,
    )
    assert base.janelas_anteriores == ()  # o original não é mutado


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


def test_a_ULTIMA_janela_sem_resultado_penaliza_ainda_que_haja_anterior_boa():
    """Sob a regra revogada (`any`), este caso passava por outro motivo — bastava uma
    falha em qualquer lugar. Agora passa porque a MAIS RECENTE (ciclos=2) falhou."""
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


# --- SÓ a última janela é julgada (D-023) ------------------------------------


def test_janela_recente_COM_resultado_limpa_o_historico_ruim():
    """A decisão do dono: a §6.4 julga a ÚLTIMA exposição, não o histórico inteiro.
    Sob a regra anterior (`any`), estas duas janelas antigas sem resultado
    penalizariam para sempre — e com decaimento de razão 1.0, sem nunca esmaecer."""
    alvo = imovel(
        janelas_anteriores=(
            janela(atingiu=False, ciclos=7),
            janela(atingiu=False, ciclos=3),
            janela(atingiu=True, ciclos=1),  # a mais recente ATINGIU
        )
    )
    assert Penalidade.JANELA_SEM_RESULTADO not in penalidades_aplicaveis(alvo)
    assert ciclos_desde_janela_sem_resultado(alvo) is None


def test_janela_recente_SEM_resultado_penaliza_mesmo_com_passado_bom():
    """A contraprova: o que manda é a última, para os dois lados."""
    alvo = imovel(
        janelas_anteriores=(
            janela(atingiu=True, ciclos=9),
            janela(atingiu=False, ciclos=2),  # a mais recente FALHOU
        )
    )
    assert Penalidade.JANELA_SEM_RESULTADO in penalidades_aplicaveis(alvo)
    assert ciclos_desde_janela_sem_resultado(alvo) == 2


def test_a_ordem_da_lista_nao_governa_qual_janela_e_a_ultima():
    """ "Mais recente" é o MENOR `ciclos_desde_encerramento`, não a posição na tupla —
    a ordem vem do chamador e não pode decidir a regra (invariante 5)."""
    recentes_primeiro = imovel(
        janelas_anteriores=(janela(atingiu=True, ciclos=1), janela(atingiu=False, ciclos=5))
    )
    antigas_primeiro = imovel(
        janelas_anteriores=(janela(atingiu=False, ciclos=5), janela(atingiu=True, ciclos=1))
    )
    assert penalidades_aplicaveis(recentes_primeiro) == penalidades_aplicaveis(antigas_primeiro)
    assert Penalidade.JANELA_SEM_RESULTADO not in penalidades_aplicaveis(antigas_primeiro)


def test_empate_de_ciclos_a_janela_que_FALHOU_vence():
    """Duas janelas encerradas no mesmo ciclo é o que a mudança de nível produz
    (D-021). O desempate é determinístico e conservador: entre duas exposições
    simultâneas, a §6.4 penaliza a que falhou."""
    alvo = imovel(
        janelas_anteriores=(janela(atingiu=True, ciclos=2), janela(atingiu=False, ciclos=2))
    )
    assert Penalidade.JANELA_SEM_RESULTADO in penalidades_aplicaveis(alvo)
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


# --- detalhamento por penalidade (Spec §2.1/§6.4): breakdown e soma ---------


def test_descontos_por_penalidade_soma_bate_com_total():
    # As três penalidades ligadas: o breakdown por penalidade soma exatamente o
    # desconto_total (o total deriva do breakdown — sem divergência possível).
    alvo = imovel(
        janelas_anteriores=(janela(atingiu=False),),
        alguma_categoria_avaliada=False,
        leads_180d=0,
    )
    breakdown = descontos_por_penalidade(alvo, INTENSIDADES, sem_decaimento)
    assert breakdown == {
        Penalidade.JANELA_SEM_RESULTADO: 10.0,
        Penalidade.SEM_AVALIACAO_POR_CATEGORIA: 5.0,
        Penalidade.SEM_LEAD_180D: 2.0,
    }
    assert sum(breakdown.values()) == desconto_total(alvo, INTENSIDADES, sem_decaimento)


def test_descontos_por_penalidade_so_lista_aplicadas():
    # Imóvel sem nenhuma penalidade: dict vazio (ausência = não aplicada).
    assert descontos_por_penalidade(imovel(), INTENSIDADES, sem_decaimento) == {}


def test_descontos_por_penalidade_aplica_decaimento_na_janela():
    alvo = imovel(janelas_anteriores=(janela(atingiu=False),))
    breakdown = descontos_por_penalidade(alvo, INTENSIDADES, lambda _: 0.5)
    assert breakdown[Penalidade.JANELA_SEM_RESULTADO] == 5.0  # 10.0 × 0.5
