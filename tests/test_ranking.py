"""Testes do ranking (D-028: "o banco manda, o portal classifica").

Contratos cobertos: `PesosPortal` em pontos de 100 (soma 100 obrigatória, inteiros,
negativo e booleano recusados, zero legítimo), `FatoresNormalizados` (finitude), a
nota do portal como soma ponderada literal em [0, 100], `nota_final` como bruta
menos desconto (inclusive integração com dominio.penalidades) e determinismo
(invariantes 4 e 5).
"""

import pytest

from dominio.penalidades import (
    ImovelPenalizavel,
    IntensidadesPenalidade,
    JanelaAnterior,
    desconto_total,
)
from dominio.ranking import (
    FatoresNormalizados,
    PesosPortal,
    nota_final,
    nota_portal,
)

# Fixture LOCAL: os pesos são parâmetro da rodada (adotados por D-034, injetados),
# nunca constante do domínio. Aqui servem só à aritmética.
PESOS = PesosPortal(nota_anuncio=70, cliques=30, visualizacoes=0)
PESOS_TRES = PesosPortal(nota_anuncio=50, cliques=30, visualizacoes=20)


def fatores(**kwargs) -> FatoresNormalizados:
    base = dict(
        imovel_id=1,
        nota_anuncio=0.5,
        cliques=0.5,
        visualizacoes=0.5,
        leads=0.5,
        produtividade_gestor=0.5,
        casa_perfil=True,
    )
    base.update(kwargs)
    return FatoresNormalizados(**base)


# --- pesos: validação de PesosPortal -------------------------------------------


@pytest.mark.parametrize("pesos", [(70, 30, 1), (100, 0, 1), (0, 0, 0), (50, 49, 0)])
def test_pesos_que_nao_somam_100_sao_erro(pesos):
    n, c, v = pesos
    with pytest.raises(ValueError, match="somar 100"):
        PesosPortal(nota_anuncio=n, cliques=c, visualizacoes=v)


@pytest.mark.parametrize("pesos", [(130, -30, 0), (110, 0, -10), (-5, 100, 5)])
def test_peso_negativo_e_erro_mesmo_somando_100(pesos):
    """Peso negativo inverteria o sinal: anúncio melhor cairia na ordem."""
    n, c, v = pesos
    with pytest.raises(ValueError, match="peso inválido"):
        PesosPortal(nota_anuncio=n, cliques=c, visualizacoes=v)


def test_peso_nao_inteiro_e_erro():
    """Pontos de 100 são inteiros: meio ponto não é uma unidade que o dono lê."""
    with pytest.raises(ValueError, match="peso inválido"):
        PesosPortal(nota_anuncio=50.5, cliques=49.5, visualizacoes=0.0)  # type: ignore[arg-type]


def test_peso_booleano_e_erro_mesmo_somando_100():
    """`True` é `int` em Python e somaria como 1: sem a guarda, (True, 99, 0) passaria."""
    with pytest.raises(ValueError, match="peso inválido"):
        PesosPortal(nota_anuncio=True, cliques=99, visualizacoes=0)  # type: ignore[arg-type]


@pytest.mark.parametrize("pesos", [(70, 30, 0), (100, 0, 0), (0, 0, 100), (0, 100, 0)])
def test_peso_zero_e_legitimo(pesos):
    """Visualizações mediram zero em 300/300 anúncios (03/09/2026): o peso zero é
    declarado, não omitido — e uma rodada só de nota também é expressável."""
    n, c, v = pesos
    p = PesosPortal(nota_anuncio=n, cliques=c, visualizacoes=v)
    assert (p.nota_anuncio, p.cliques, p.visualizacoes) == pesos


def test_pesos_sem_todos_os_campos_falham():
    with pytest.raises(TypeError):
        PesosPortal(nota_anuncio=100)  # type: ignore[call-arg]


# --- nota do portal: soma ponderada ------------------------------------------


def test_nota_portal_e_a_soma_ponderada_literal():
    f = fatores(nota_anuncio=1.0, cliques=0.0, visualizacoes=0.0)
    assert nota_portal(f, PESOS) == 70.0
    f = fatores(nota_anuncio=0.0, cliques=1.0, visualizacoes=0.0)
    assert nota_portal(f, PESOS) == 30.0


def test_nota_portal_combina_os_tres_sinais():
    f = fatores(nota_anuncio=1.0, cliques=0.5, visualizacoes=0.2)
    assert nota_portal(f, PESOS_TRES) == 50 * 1.0 + 30 * 0.5 + 20 * 0.2


def test_peso_zero_apaga_o_sinal():
    """Com peso zero, o sinal pode variar à vontade sem mover a nota — é o que
    "peso zero declarado" significa na prática."""
    com = fatores(nota_anuncio=0.4, cliques=0.6, visualizacoes=1.0)
    sem = fatores(nota_anuncio=0.4, cliques=0.6, visualizacoes=0.0)
    assert nota_portal(com, PESOS) == nota_portal(sem, PESOS)


def test_fatores_de_banco_nao_pesam_na_nota_do_portal():
    """Leads, produtividade e perfil viajam no `FatoresNormalizados` para o Registro,
    a planilha e o desempate — não para a nota (D-028: o banco manda, o portal
    classifica)."""
    a = fatores(leads=0.0, produtividade_gestor=0.0, casa_perfil=False)
    b = fatores(leads=1.0, produtividade_gestor=1.0, casa_perfil=True)
    assert nota_portal(a, PESOS_TRES) == nota_portal(b, PESOS_TRES)


@pytest.mark.parametrize("pesos", [PESOS, PESOS_TRES, PesosPortal(0, 0, 100)])
@pytest.mark.parametrize(
    "sinais",
    [(0.0, 0.0, 0.0), (1.0, 1.0, 1.0), (1.0, 0.0, 1.0), (0.25, 0.75, 0.5), (0.999, 0.001, 0.5)],
)
def test_nota_portal_fica_em_0_a_100_para_sinais_normalizados(pesos, sinais):
    """Pesos somam 100 e sinais vivem em [0, 1] (min-max a montante): a nota bruta
    vive em [0, 100] por construção, que é a escala dos descontos."""
    n, c, v = sinais
    nota = nota_portal(fatores(nota_anuncio=n, cliques=c, visualizacoes=v), pesos)
    assert 0.0 <= nota <= 100.0


def test_todos_os_sinais_no_maximo_dao_100_e_no_minimo_dao_0():
    assert nota_portal(fatores(nota_anuncio=1.0, cliques=1.0, visualizacoes=1.0), PESOS) == 100.0
    assert nota_portal(fatores(nota_anuncio=0.0, cliques=0.0, visualizacoes=0.0), PESOS) == 0.0


def test_os_dois_niveis_usam_a_mesma_nota():
    """Não há `PesosNivel`: a alocação separa o super destaque pelo piso de preço, não
    por nota diferente. Um único `PesosPortal` serve aos dois."""
    f = fatores(nota_anuncio=0.8, cliques=0.2, visualizacoes=0.0)
    assert nota_portal(f, PESOS) == nota_portal(f, PESOS)
    assert not hasattr(PESOS, "super_destaque")


# --- nota final: desconto de penalidades --------------------------------------


def test_nota_final_desconta_penalidades():
    assert nota_final(100.0, 30.0) == 70.0


def test_nota_final_sem_penalidade_e_a_bruta():
    bruta = nota_portal(fatores(), PESOS)
    assert nota_final(bruta, 0.0) == bruta


def test_nota_final_pode_ficar_negativa():
    """A ordenação só compara: nota negativa é legal e mantém o imóvel no fim."""
    assert nota_final(0.0, 5.0) == -5.0


def test_nota_final_sem_desconto_como_argumento_falha():
    with pytest.raises(TypeError):
        nota_final(50.0)  # type: ignore[call-arg]


@pytest.mark.parametrize("desconto", [-0.1, float("nan"), float("inf")])
def test_desconto_invalido_e_erro_deterministico(desconto):
    """Desconto negativo viraria bônus; nan/inf quebraria a ordem total. O valor pode
    vir reidratado do Registro, por isso a revalidação aqui."""
    with pytest.raises(ValueError, match="desconto de penalidades inválido"):
        nota_final(50.0, desconto)


@pytest.mark.parametrize("bruta", [float("nan"), float("inf"), float("-inf")])
def test_nota_bruta_nao_finita_e_erro(bruta):
    with pytest.raises(ValueError, match="nota bruta não finita"):
        nota_final(bruta, 0.0)


def test_integracao_com_dominio_penalidades():
    # Intensidades em pontos de 100 (adotadas por D-034; aqui fixture local).
    intensidades = IntensidadesPenalidade(
        janela_sem_resultado=20.0, sem_avaliacao_por_categoria=5.0, sem_lead_180d=10.0
    )
    alvo = ImovelPenalizavel(
        imovel_id=7, janelas_anteriores=(), alguma_categoria_avaliada=False, leads_180d=0
    )
    desconto = desconto_total(alvo, intensidades, lambda _: 1.0)
    bruta = nota_portal(fatores(nota_anuncio=1.0, cliques=1.0, visualizacoes=1.0), PESOS)
    assert nota_final(bruta, desconto) == 100.0 - 15.0


def test_integracao_com_decaimento_atravessando_a_fronteira():
    intensidades = IntensidadesPenalidade(
        janela_sem_resultado=20.0, sem_avaliacao_por_categoria=5.0, sem_lead_180d=10.0
    )
    alvo = ImovelPenalizavel(
        imovel_id=8,
        janelas_anteriores=(JanelaAnterior(atingiu_resultado=False, ciclos_desde_encerramento=1),),
        alguma_categoria_avaliada=True,
        leads_180d=1,
    )
    desconto = desconto_total(alvo, intensidades, lambda ciclos: 0.5**ciclos)
    assert nota_final(100.0, desconto) == 100.0 - 20.0 * 0.5


# --- validação de finitude -----------------------------------------------------


@pytest.mark.parametrize(
    "campo", ["nota_anuncio", "cliques", "visualizacoes", "leads", "produtividade_gestor"]
)
@pytest.mark.parametrize("invalido", [float("nan"), float("inf"), float("-inf")])
def test_fator_nao_finito_e_erro(campo, invalido):
    with pytest.raises(ValueError, match=f"fator não finito para {campo}"):
        fatores(**{campo: invalido})


def test_fator_fora_de_0_a_1_e_aceito_pelo_dominio():
    """A escala é responsabilidade da normalização a montante (parâmetro nº 2, min-max
    provisório): este módulo só impõe finitude. Se a normalização vier a garantir a
    faixa, a validação nasce com ela."""
    assert nota_portal(fatores(nota_anuncio=-1.0, cliques=0.0, visualizacoes=0.0), PESOS) == -70.0


def test_fatores_sem_todos_os_campos_falham():
    with pytest.raises(TypeError):
        FatoresNormalizados(imovel_id=1, nota_anuncio=0.5)  # type: ignore[call-arg]


# --- determinismo (invariantes 4 e 5) ------------------------------------------


def test_mesma_entrada_mesma_saida():
    f = fatores(nota_anuncio=0.37, cliques=0.91, visualizacoes=0.12)
    notas = {nota_final(nota_portal(f, PESOS_TRES), 1.25) for _ in range(50)}
    assert len(notas) == 1
