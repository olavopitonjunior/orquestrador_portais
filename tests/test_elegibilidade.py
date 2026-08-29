"""Testes das oito regras de elegibilidade e do piso de nível.

Valores-limite conforme Spec §6.1 e PRD (tabela de parâmetros).
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


def test_ordem_de_relaxamento_conforme_spec():
    assert ORDEM_RELAXAMENTO == (
        Regra.FOTOS,
        Regra.CADASTRO_COMPLETO,
        Regra.ATUALIZACAO_90D,
        Regra.GESTOR_PRODUTIVO,
        Regra.CAPACIDADE_DISTRITO,
    )


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
