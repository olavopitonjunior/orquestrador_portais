"""Testes do relaxamento (Spec §6.6, PRD Estágio 5, D-005, D-009, invariante 7).

Contratos cobertos: cedência progressiva e mínima, ordem importada de
elegibilidade (nunca própria), relatório apenas dos graus cedidos (com zero
quando cabível), regra não relaxável nunca entra, déficit residual legítimo,
consequência distributiva declarada, desempate D-009 dentro do grau,
resultado sem nível (invariante 7), determinismo sob permutação, o perfil de
conversão como PRIMEIRO degrau (D-027) e a trava do login (D-029).
Nenhum teste usa os ganhos medidos (+133/+569/+1.680/+1.747/+5.686) como
valor exato — D-005: ordem de grandeza medida com outro parâmetro.
"""

import dataclasses

import pytest

from dominio import elegibilidade, relaxamento
from dominio.alocacao import COTA_DESTAQUE
from dominio.elegibilidade import ORDEM_RELAXAMENTO, Regra
from dominio.relaxamento import (
    CandidatoRelaxamento,
    LinhaRelatorio,
    ResultadoRelaxamento,
    relaxar,
)


def candidato(
    imovel_id: int,
    regras: frozenset[Regra] | set[Regra],
    nota: float = 50.0,
    *,
    sem_login: bool = False,
) -> CandidatoRelaxamento:
    return CandidatoRelaxamento(
        imovel_id=imovel_id,
        nota_destaque=nota,
        regras_reprovadas=frozenset(regras),
        gestor_sem_login=sem_login,
    )


SO_PERFIL = {Regra.PERFIL_DE_CONVERSAO}
SO_FOTOS = {Regra.FOTOS}
SO_CADASTRO = {Regra.CADASTRO_COMPLETO}
SO_GESTOR = {Regra.GESTOR_PRODUTIVO}
SO_DISTRITO = {Regra.CAPACIDADE_DISTRITO}
PERFIL_0 = LinhaRelatorio(regra=Regra.PERFIL_DE_CONVERSAO, posicoes_dependentes=0)


# --- ordem de cedência: fonte única -------------------------------------------


def test_modulo_nao_tem_ordem_propria():
    # Condição do orquestrador: se um dia o módulo ganhar ordem própria,
    # este teste quebra. Hoje ele nem re-exporta a tupla.
    propria = getattr(relaxamento, "ORDEM_RELAXAMENTO", elegibilidade.ORDEM_RELAXAMENTO)
    assert propria is elegibilidade.ORDEM_RELAXAMENTO


# --- cedência progressiva e mínima ---------------------------------------------


def test_deficit_zero_nao_cede_nada():
    resultado = relaxar(0, [candidato(1, SO_FOTOS)])
    assert resultado == ResultadoRelaxamento(recuperados=(), relatorio=(), deficit_restante=0)


def test_grau_um_suficiente_nao_cede_o_segundo():
    # Minimalidade: há candidato do grau 1 (perfil) e do grau 2 (fotos), mas o
    # déficit fecha no grau 1 — fotos NÃO é cedida e não aparece no relatório.
    resultado = relaxar(1, [candidato(1, SO_PERFIL), candidato(2, SO_FOTOS)])
    assert [r.imovel_id for r in resultado.recuperados] == [1]
    assert resultado.relatorio == (
        LinhaRelatorio(regra=Regra.PERFIL_DE_CONVERSAO, posicoes_dependentes=1),
    )
    assert resultado.deficit_restante == 0


def test_o_perfil_e_o_PRIMEIRO_degrau_cedido():
    """D-027, palavras do dono: "preferir um imóvel com cadastro impecável fora do
    perfil a um dentro do perfil com nove fotos". Quem só reprova no perfil entra
    antes de quem só reprova em fotos, mesmo com nota menor."""
    fora_do_perfil = candidato(1, SO_PERFIL, nota=1.0)
    poucas_fotos = candidato(2, SO_FOTOS, nota=99.0)
    resultado = relaxar(1, [poucas_fotos, fora_do_perfil])
    assert [r.imovel_id for r in resultado.recuperados] == [1]
    assert resultado.recuperados[0].degrau is Regra.PERFIL_DE_CONVERSAO
    assert resultado.relatorio == (
        LinhaRelatorio(regra=Regra.PERFIL_DE_CONVERSAO, posicoes_dependentes=1),
    )


def test_grau_cedido_sem_recuperados_gera_linha_zero():
    # Perfil e fotos são cedidos (o déficit exige descer), não recuperam ninguém,
    # e as linhas com zero registram a cedência efetivada.
    resultado = relaxar(1, [candidato(2, SO_CADASTRO)])
    assert resultado.relatorio == (
        PERFIL_0,
        LinhaRelatorio(regra=Regra.FOTOS, posicoes_dependentes=0),
        LinhaRelatorio(regra=Regra.CADASTRO_COMPLETO, posicoes_dependentes=1),
    )
    assert resultado.deficit_restante == 0


def test_degrau_minimo_e_o_maior_indice_das_regras_reprovadas():
    # FOTOS + ATUALIZACAO_90D exige ceder até o grau 4 (índice 3, com o perfil na frente).
    alvo = candidato(1, {Regra.FOTOS, Regra.ATUALIZACAO_90D})
    resultado = relaxar(1, [alvo])
    assert [linha.regra for linha in resultado.relatorio] == [
        Regra.PERFIL_DE_CONVERSAO,
        Regra.FOTOS,
        Regra.CADASTRO_COMPLETO,
        Regra.ATUALIZACAO_90D,
    ]
    assert resultado.recuperados[0].degrau == Regra.ATUALIZACAO_90D


def test_consequencia_distributiva_grau_prevalece_sobre_nota():
    # Declarada no docstring e no CHANGELOG: nota ALTA que exige grau 3
    # perde para nota BAIXA que exige grau 1 — a ordem da Spec manda.
    alto_grau3 = candidato(1, {Regra.ATUALIZACAO_90D}, nota=99.0)
    baixo_grau1 = candidato(2, SO_FOTOS, nota=1.0)
    resultado = relaxar(1, [alto_grau3, baixo_grau1])
    assert [r.imovel_id for r in resultado.recuperados] == [2]


def test_regra_nao_relaxavel_nunca_entra():
    # Reprova em PRECO_GERAL junto com FOTOS: nem no grau 5, nem nunca.
    inadmissivel = candidato(1, {Regra.FOTOS, Regra.PRECO_GERAL})
    resultado = relaxar(3, [inadmissivel, candidato(2, SO_DISTRITO)])
    assert [r.imovel_id for r in resultado.recuperados] == [2]
    assert resultado.deficit_restante == 2


def test_deficit_residual_quando_os_seis_graus_nao_bastam():
    resultado = relaxar(4, [candidato(1, SO_FOTOS), candidato(2, SO_DISTRITO)])
    assert len(resultado.recuperados) == 2
    assert len(resultado.relatorio) == len(ORDEM_RELAXAMENTO) == 6  # todos os graus cedidos
    assert resultado.deficit_restante == 2


def test_selecao_dentro_do_grau_por_nota_com_desempate_d009():
    lote = [
        candidato(3, SO_FOTOS, nota=50.0),
        candidato(9, SO_FOTOS, nota=50.0),
        candidato(7, SO_FOTOS, nota=80.0),
    ]
    resultado = relaxar(2, lote)
    # Nota maior primeiro; empate resolvido por imovel_id decrescente (D-009).
    assert [r.imovel_id for r in resultado.recuperados] == [7, 9]


# --- a trava do login (D-029) ------------------------------------------------------


@pytest.mark.parametrize(
    "regras",
    [
        SO_GESTOR,
        {Regra.GESTOR_PRODUTIVO, Regra.FOTOS},
        {Regra.GESTOR_PRODUTIVO, Regra.CAPACIDADE_DISTRITO},  # degrau depois do gestor
        {Regra.PERFIL_DE_CONVERSAO, Regra.GESTOR_PRODUTIVO},
    ],
)
def test_gestor_sem_login_reprovado_em_gestor_produtivo_e_irrecuperavel(regras):
    """Quem não entra no sistema não vai atender o lead que a posição paga gerar. O
    imóvel não entra em degrau NENHUM — nem no `capacidade_distrito`, que vem depois
    de `gestor_produtivo` — e o resultado conta o bloqueio."""
    travado = candidato(1, regras, nota=99.0, sem_login=True)
    resultado = relaxar(3, [travado])
    assert resultado.recuperados == ()
    assert len(resultado.relatorio) == len(ORDEM_RELAXAMENTO)  # desceu tudo, sem achar
    assert resultado.deficit_restante == 3
    assert resultado.bloqueados_por_login == 1


def test_a_trava_nao_muda_quem_mais_entra():
    # O travado some do pool; os outros seguem a cedência normal.
    lote = [
        candidato(1, SO_GESTOR, nota=99.0, sem_login=True),
        candidato(2, SO_GESTOR, nota=10.0),  # mesmo degrau, com login: entra
        candidato(3, SO_FOTOS, nota=5.0),
    ]
    resultado = relaxar(2, lote)
    assert [r.imovel_id for r in resultado.recuperados] == [3, 2]
    assert resultado.bloqueados_por_login == 1


def test_bloqueados_por_login_e_contado_MESMO_sem_deficit():
    """A trava é fato sobre os candidatos, não sobre a cedência: a planilha declara
    "N travados" ainda que ninguém tenha sido cedido."""
    lote = [candidato(1, SO_GESTOR, sem_login=True), candidato(2, SO_FOTOS, sem_login=True)]
    resultado = relaxar(0, lote)
    assert resultado.recuperados == () and resultado.relatorio == ()
    assert resultado.bloqueados_por_login == 1  # só o de gestor_produtivo


def test_gestor_sem_login_SEM_gestor_produtivo_nas_reprovadas_nao_trava():
    """A trava só morde no degrau `gestor_produtivo`: reprovado só em fotos, o imóvel
    de gestor sem login é recuperado normalmente e não é contado."""
    resultado = relaxar(1, [candidato(1, SO_FOTOS, sem_login=True)])
    assert [r.imovel_id for r in resultado.recuperados] == [1]
    assert resultado.bloqueados_por_login == 0


def test_com_login_o_degrau_gestor_produtivo_recupera():
    resultado = relaxar(1, [candidato(1, SO_GESTOR, sem_login=False)])
    assert [r.imovel_id for r in resultado.recuperados] == [1]
    assert resultado.recuperados[0].degrau is Regra.GESTOR_PRODUTIVO
    assert resultado.bloqueados_por_login == 0


def test_travado_com_regra_nao_relaxavel_nao_e_contado_como_bloqueado_pelo_login():
    """Quem reprova em regra que nunca relaxa jamais entraria; o login não é o que o
    barrou, e a contagem declarada é só dos que a trava barrou."""
    resultado = relaxar(
        1, [candidato(1, {Regra.GESTOR_PRODUTIVO, Regra.PRECO_GERAL}, sem_login=True)]
    )
    assert resultado.recuperados == ()
    assert resultado.bloqueados_por_login == 0


def test_o_default_de_gestor_sem_login_e_falso():
    assert candidato(1, SO_GESTOR).gestor_sem_login is False
    assert (
        ResultadoRelaxamento(recuperados=(), relatorio=(), deficit_restante=0).bloqueados_por_login
        == 0
    )


# --- invariante 7: sem nível no resultado ---------------------------------------


def test_resultado_nao_carrega_nivel():
    campos = {f.name for f in dataclasses.fields(relaxamento.ImovelRecuperado)}
    assert campos == {"imovel_id", "nota_destaque", "degrau"}
    assert "nivel" not in {f.name for f in dataclasses.fields(ResultadoRelaxamento)}


# --- validação de entrada --------------------------------------------------------


def test_deficit_negativo_e_erro():
    with pytest.raises(ValueError, match="deficit negativo"):
        relaxar(-1, [])


def test_deficit_igual_a_cota_e_aceito():
    resultado = relaxar(COTA_DESTAQUE, [])
    assert resultado.deficit_restante == COTA_DESTAQUE


def test_deficit_acima_da_cota_e_erro():
    with pytest.raises(ValueError, match="deficit maior que a cota de destaque"):
        relaxar(COTA_DESTAQUE + 1, [])


def test_candidato_sem_regra_reprovada_e_erro():
    with pytest.raises(ValueError, match="sem regra reprovada"):
        candidato(1, set())


def test_regra_que_nao_e_regra_e_erro():
    with pytest.raises(ValueError, match="não é Regra"):
        CandidatoRelaxamento(
            imovel_id=1,
            nota_destaque=1.0,
            regras_reprovadas=frozenset({"fotos"}),  # type: ignore[arg-type]
        )


def test_nota_nao_finita_e_erro():
    with pytest.raises(ValueError, match="nota não finita"):
        candidato(1, SO_FOTOS, nota=float("nan"))


def test_imovel_id_duplicado_e_erro():
    with pytest.raises(ValueError, match=r"imovel_id duplicado no lote: \[1\]"):
        relaxar(1, [candidato(1, SO_FOTOS), candidato(1, SO_CADASTRO)])


# --- determinismo (invariantes 4 e 5) --------------------------------------------


def test_permutacoes_da_entrada_produzem_saida_identica():
    lote = [
        candidato(
            i,
            {ORDEM_RELAXAMENTO[i % len(ORDEM_RELAXAMENTO)]},
            nota=float(i % 4),
        )
        for i in range(1, 60)
    ]
    invertido = list(reversed(lote))
    rotacionado = lote[23:] + lote[:23]
    assert relaxar(10, lote) == relaxar(10, invertido) == relaxar(10, rotacionado)


def test_mesma_entrada_mesma_saida():
    lote = [candidato(i, {ORDEM_RELAXAMENTO[i % 3]}, nota=float(i % 5)) for i in range(1, 30)]
    resultados = {relaxar(7, lote) for _ in range(20)}
    assert len(resultados) == 1


# --- a UNIÃO contra a cota (invariante 6) ---------------------------------------


def test_relaxar_NUNCA_devolve_mais_recuperados_que_o_deficit():
    """O invariante 6 no destaque vale por CONSTRUÇÃO — `pool[:restante]` corta —, mas
    até aqui nada o amarrava: nenhum teste comparava o total de recuperados com o
    déficit pedido, em nenhum arquivo.

    Isso importa porque a lista de destaque ENTREGUE não é `alocacao.destaque`: a
    planilha emite o ranking mais os recuperados, numerando em continuação
    (`entrega/planilha_piloto.py`). E o crivo de auditoria confere só
    `alocacao.destaque` — a união, que é o que vai ao portal, não passa por veto
    nenhum. Achado do `orchestrator` ao conferir o critério de aceite das cotas: sem
    esta trava, a evidência do critério é leitura de código, não prova."""
    for deficit in (0, 1, 3, 7):
        candidatos = [candidato(i, SO_FOTOS, nota=100.0 - i) for i in range(1, 20)]
        resultado = relaxar(deficit, candidatos)
        assert len(resultado.recuperados) == min(deficit, len(candidatos))
        assert len(resultado.recuperados) <= deficit


def test_a_UNIAO_ranking_mais_recuperados_cabe_na_cota():
    """A propriedade que o critério de aceite das cotas afirma, e que ninguém provava:
    o que a planilha entrega no destaque é ranking + recuperados, e a soma não pode
    passar de COTA_DESTAQUE.

    O caso aqui é o do ranking QUASE cheio — cinco vagas de déficit e mais candidatos
    que vagas —, que é onde o corte precisa morder. O déficit igual à cota inteira,
    limite superior aceito por `relaxar`, já tem teste próprio acima. *(A versão
    anterior desta docstring dizia ser o caso da cota inteira; era falso, e o portão
    o apanhou — o corpo usa déficit 5.)*"""
    candidatos = [candidato(i, SO_FOTOS) for i in range(1, 12)]
    ja_no_ranking = COTA_DESTAQUE - 5  # sobra 5 de déficit
    resultado = relaxar(COTA_DESTAQUE - ja_no_ranking, candidatos)
    assert ja_no_ranking + len(resultado.recuperados) <= COTA_DESTAQUE
    assert len(resultado.recuperados) == 5  # encheu o déficit, não passou dele
