"""Testes das nove regras de elegibilidade e do piso de nível.

Valores-limite conforme Spec §6.1 e PRD (tabela de parâmetros); a nona regra
(perfil de conversão) e a régua declarável de capacidade do distrito vêm das
decisões D-027 e D-033.
"""

from dataclasses import replace
from datetime import date

import pytest

from dominio.elegibilidade import (
    ORDEM_RELAXAMENTO,
    ImovelCandidato,
    Regra,
    candidato_super_destaque,
    elegivel,
    elegivel_com_relaxamento,
    regras_reprovadas,
)

REF = date(2026, 8, 29)

APROVADO = ImovelCandidato(
    imovel_id=1,
    publicacao_ativa=True,
    categoria="Apartamento",
    preco=300_000,
    qtd_fotos=10,
    atualizado_em=date(2026, 8, 1),
    notas_por_categoria={"descricao": 2, "fotos": 2, "atualizacao": 1},
    gestor_captou_ou_vendeu_30d=True,
    produtividade_gestor_30d=3,
    corretores_ativos_no_distrito=2,
)


def test_imovel_aprovado_em_todas_as_regras():
    assert regras_reprovadas(APROVADO, REF) == frozenset()
    assert elegivel(APROVADO, REF)


@pytest.mark.parametrize(
    ("mudanca", "regra"),
    [
        ({"publicacao_ativa": False}, Regra.STATUS_ATIVO),
        ({"categoria": "Terreno"}, Regra.CATEGORIA),
        ({"categoria": "Kitnet"}, Regra.CATEGORIA),
        ({"preco": 299_999}, Regra.PRECO_GERAL),
        ({"qtd_fotos": 9}, Regra.FOTOS),
        ({"atualizado_em": date(2026, 5, 30)}, Regra.ATUALIZACAO_90D),  # 91 dias
        ({"notas_por_categoria": {"descricao": 2, "iptu": 0}}, Regra.CADASTRO_COMPLETO),
        ({"gestor_captou_ou_vendeu_30d": False}, Regra.GESTOR_PRODUTIVO),
        ({"corretores_ativos_no_distrito": 1}, Regra.CAPACIDADE_DISTRITO),
        ({"casa_perfil_de_conversao": False}, Regra.PERFIL_DE_CONVERSAO),
    ],
)
def test_cada_regra_reprova_isoladamente(mudanca, regra):
    imovel = replace(APROVADO, **mudanca)
    assert regras_reprovadas(imovel, REF) == frozenset({regra})
    assert not elegivel(imovel, REF)


@pytest.mark.parametrize(
    ("mudanca", "esperado"),
    [
        ({"preco": 300_000}, True),  # limite exato passa
        ({"qtd_fotos": 10}, True),
        ({"atualizado_em": date(2026, 5, 31)}, True),  # 90 dias exatos passam
        ({"corretores_ativos_no_distrito": 2}, True),
    ],
)
def test_valores_limite(mudanca, esperado):
    assert elegivel(replace(APROVADO, **mudanca), REF) is esperado


def test_sem_avaliacao_por_categoria_passa():
    """Spec §6.1: imóvel sem avaliação não é excluído — passa e recebe
    penalidade no ranking (fora deste módulo)."""
    imovel = replace(APROVADO, notas_por_categoria=None)
    assert elegivel(imovel, REF)


def test_categoria_ausente_nao_reprova_mas_zero_explicito_reprova():
    """Leitura adotada para avaliação parcial (média 4,7 das 7 categorias):
    só zero explícito reprova."""
    assert elegivel(replace(APROVADO, notas_por_categoria={"descricao": 1}), REF)
    assert not elegivel(replace(APROVADO, notas_por_categoria={"descricao": 0}), REF)


def test_piso_de_super_destaque_nao_elimina_do_destaque():
    """D-002: reprovar no piso mantém o imóvel elegível ao destaque."""
    imovel = replace(APROVADO, preco=400_000)
    assert elegivel(imovel, REF)
    assert not candidato_super_destaque(imovel, REF)
    assert candidato_super_destaque(replace(APROVADO, preco=700_000), REF)
    assert not candidato_super_destaque(replace(APROVADO, preco=699_999), REF)


def test_inelegivel_nunca_e_candidato_a_super_destaque():
    imovel = replace(APROVADO, preco=800_000, qtd_fotos=3)
    assert not candidato_super_destaque(imovel, REF)


def test_relaxamento_recupera_apenas_regras_cedidas():
    imovel = replace(APROVADO, qtd_fotos=5, gestor_captou_ou_vendeu_30d=False)
    assert not elegivel(imovel, REF)
    so_fotos = frozenset({Regra.FOTOS})
    ambas = frozenset({Regra.FOTOS, Regra.GESTOR_PRODUTIVO})
    assert not elegivel_com_relaxamento(imovel, REF, so_fotos)
    assert elegivel_com_relaxamento(imovel, REF, ambas)


def test_relaxamento_rejeita_regra_nao_relaxavel():
    with pytest.raises(ValueError, match=r"regras não relaxáveis: \['preco_geral'\]"):
        elegivel_com_relaxamento(APROVADO, REF, frozenset({Regra.PRECO_GERAL}))


def test_mensagem_de_erro_do_relaxamento_e_deterministica():
    """Lista ordenada na mensagem: mesma entrada, mesmo texto, sempre."""
    with pytest.raises(ValueError, match=r"\['categoria', 'preco_geral', 'status_ativo'\]"):
        elegivel_com_relaxamento(
            APROVADO, REF, frozenset({Regra.STATUS_ATIVO, Regra.PRECO_GERAL, Regra.CATEGORIA})
        )


def test_ordem_de_relaxamento_conforme_spec_e_d027():
    # Spec §6.6 + D-027: o perfil de conversão é o PRIMEIRO degrau cedido.
    assert ORDEM_RELAXAMENTO == (
        Regra.PERFIL_DE_CONVERSAO,
        Regra.FOTOS,
        Regra.CADASTRO_COMPLETO,
        Regra.ATUALIZACAO_90D,
        Regra.GESTOR_PRODUTIVO,
        Regra.CAPACIDADE_DISTRITO,
    )
    # status, categoria e preço geral nunca relaxam
    assert not {Regra.STATUS_ATIVO, Regra.CATEGORIA, Regra.PRECO_GERAL} & set(ORDEM_RELAXAMENTO)


# --- a nona regra: perfil de conversão (D-027) ---------------------------------


def test_perfil_de_conversao_so_reprova_com_veredito_FALSO():
    """None = ninguém aplicou o filtro (a medição do funil sem perfis) e NÃO reprova;
    True passa; só False reprova. Reprovar em None seria reprovar em silêncio."""
    assert APROVADO.casa_perfil_de_conversao is None  # o default é "não avaliado"
    assert elegivel(APROVADO, REF)
    assert elegivel(replace(APROVADO, casa_perfil_de_conversao=True), REF)
    assert regras_reprovadas(replace(APROVADO, casa_perfil_de_conversao=False), REF) == frozenset(
        {Regra.PERFIL_DE_CONVERSAO}
    )


def test_perfil_de_conversao_e_relaxavel_e_o_primeiro_degrau():
    fora_do_perfil = replace(APROVADO, casa_perfil_de_conversao=False)
    assert not elegivel(fora_do_perfil, REF)
    assert elegivel_com_relaxamento(fora_do_perfil, REF, frozenset({Regra.PERFIL_DE_CONVERSAO}))
    assert ORDEM_RELAXAMENTO[0] is Regra.PERFIL_DE_CONVERSAO


def test_login_do_gestor_NAO_e_regra_de_elegibilidade():
    """D-029: o login é TRAVA do relaxamento, não regra — medido, excluiria zero
    imóveis a mais. Mudar o campo não muda o veredito."""
    for valor in (True, False, None):
        assert (
            regras_reprovadas(replace(APROVADO, gestor_logou_na_janela=valor), REF) == frozenset()
        )


# --- capacidade do distrito parametrizada (D-033) ------------------------------


@pytest.mark.parametrize(
    ("minimo", "corretores", "reprova"),
    [
        (2, 2, False),  # o adotado, no limite
        (2, 1, True),
        (1, 1, False),  # régua mais frouxa: 1 corretor basta
        (3, 2, True),  # régua mais dura: 2 já não bastam
        (3, 3, False),
    ],
)
def test_minimo_de_corretores_do_distrito_e_parametrizado(minimo, corretores, reprova):
    imovel = replace(APROVADO, corretores_ativos_no_distrito=corretores)
    reprovadas = regras_reprovadas(imovel, REF, minimo_corretores_distrito=minimo)
    assert (Regra.CAPACIDADE_DISTRITO in reprovadas) is reprova


def test_minimo_de_corretores_default_e_o_adotado():
    # Contra o ADOTADO, não contra o literal: o domínio não importa `config` (seria
    # inverter a camada), então o default vive em dois lugares e é este teste que
    # impede os dois de divergirem em silêncio.
    from config.adotados import ADOTADOS
    from dominio.elegibilidade import MINIMO_CORRETORES_ATIVOS_DISTRITO

    assert MINIMO_CORRETORES_ATIVOS_DISTRITO == ADOTADOS["corretor.minimo_no_distrito"] == 2
    imovel = replace(APROVADO, corretores_ativos_no_distrito=1)
    assert regras_reprovadas(imovel, REF) == regras_reprovadas(
        imovel, REF, minimo_corretores_distrito=MINIMO_CORRETORES_ATIVOS_DISTRITO
    )


@pytest.mark.parametrize("minimo", [0, -1])
def test_minimo_de_corretores_abaixo_de_um_e_recusado(minimo):
    with pytest.raises(ValueError, match="mínimo de corretores"):
        regras_reprovadas(APROVADO, REF, minimo_corretores_distrito=minimo)


def test_categoria_e_sensivel_a_caixa_e_acento():
    """Contrato explícito: a comparação é literal (Spec §6.1); normalizar
    grafia é responsabilidade da coleta interna."""
    assert not elegivel(replace(APROVADO, categoria="apartamento"), REF)
    assert not elegivel(replace(APROVADO, categoria="Casa de Condominio"), REF)


def test_data_de_atualizacao_futura_passa():
    """Anomalia de dado não reprova aqui: coleta interna aborta rodada com
    dado inválido (Spec §7.3). Comportamento documentado, não desejado."""
    assert elegivel(replace(APROVADO, atualizado_em=date(2026, 9, 15)), REF)


def test_relaxamento_vazio_equivale_a_elegivel():
    imovel = replace(APROVADO, qtd_fotos=5)
    assert elegivel_com_relaxamento(APROVADO, REF, frozenset()) is elegivel(APROVADO, REF)
    assert elegivel_com_relaxamento(imovel, REF, frozenset()) is elegivel(imovel, REF)


def test_multiplas_regras_reprovadas_de_uma_vez():
    imovel = replace(
        APROVADO, publicacao_ativa=False, preco=100_000, corretores_ativos_no_distrito=0
    )
    assert regras_reprovadas(imovel, REF) == frozenset(
        {Regra.STATUS_ATIVO, Regra.PRECO_GERAL, Regra.CAPACIDADE_DISTRITO}
    )


def test_mapping_externo_nao_vaza_mutacao():
    notas = {"descricao": 2}
    imovel = replace(APROVADO, notas_por_categoria=notas)
    notas["descricao"] = 0  # mutação após a construção
    assert elegivel(imovel, REF)  # a instância guardou cópia imutável


def test_determinismo_mesma_entrada_mesma_saida():
    """Invariante 5, na escala deste módulo."""
    resultados = {regras_reprovadas(APROVADO, REF) for _ in range(50)}
    assert len(resultados) == 1
