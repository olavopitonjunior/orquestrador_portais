"""Testes do relaxamento (Spec §6.6, PRD Estágio 5, D-005, D-009, invariante 7).

Contratos cobertos: cedência progressiva e mínima, ordem importada de
elegibilidade (nunca própria), relatório apenas dos graus cedidos (com zero
quando cabível), regra não relaxável nunca entra, déficit residual legítimo,
consequência distributiva declarada, desempate D-009 dentro do grau,
resultado sem nível (invariante 7) e determinismo sob permutação.
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
) -> CandidatoRelaxamento:
    return CandidatoRelaxamento(
        imovel_id=imovel_id, nota_destaque=nota, regras_reprovadas=frozenset(regras)
    )


SO_FOTOS = {Regra.FOTOS}
SO_CADASTRO = {Regra.CADASTRO_COMPLETO}
SO_DISTRITO = {Regra.CAPACIDADE_DISTRITO}


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
    # Minimalidade: há candidato do grau 2 disponível, mas o déficit fecha
    # no grau 1 — cadastro completo NÃO é cedido e não aparece no relatório.
    resultado = relaxar(1, [candidato(1, SO_FOTOS), candidato(2, SO_CADASTRO)])
    assert [r.imovel_id for r in resultado.recuperados] == [1]
    assert resultado.relatorio == (LinhaRelatorio(regra=Regra.FOTOS, posicoes_dependentes=1),)
    assert resultado.deficit_restante == 0


def test_grau_cedido_sem_recuperados_gera_linha_zero():
    # Fotos é cedida (o déficit exige descer), não recupera ninguém, e a
    # linha com zero registra a cedência efetivada.
    resultado = relaxar(1, [candidato(2, SO_CADASTRO)])
    assert resultado.relatorio == (
        LinhaRelatorio(regra=Regra.FOTOS, posicoes_dependentes=0),
        LinhaRelatorio(regra=Regra.CADASTRO_COMPLETO, posicoes_dependentes=1),
    )
    assert resultado.deficit_restante == 0


def test_degrau_minimo_e_o_maior_indice_das_regras_reprovadas():
    # FOTOS + ATUALIZACAO_90D exige ceder até o grau 3 (índice 2).
    alvo = candidato(1, {Regra.FOTOS, Regra.ATUALIZACAO_90D})
    resultado = relaxar(1, [alvo])
    assert [linha.regra for linha in resultado.relatorio] == [
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


def test_deficit_residual_quando_os_cinco_graus_nao_bastam():
    resultado = relaxar(4, [candidato(1, SO_FOTOS), candidato(2, SO_DISTRITO)])
    assert len(resultado.recuperados) == 2
    assert len(resultado.relatorio) == 5  # todos os graus foram cedidos
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
            {ORDEM_RELAXAMENTO[i % 5]},
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
