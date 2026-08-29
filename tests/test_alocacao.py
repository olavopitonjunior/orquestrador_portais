"""Testes da alocação (Spec §6.5, D-008, invariante 6).

Contratos cobertos: amarração das cotas Python ↔ DDL do Registro, as duas
fases com suas notas próprias, piso de nível, cotas nos dois sentidos
(nunca excede; déficit legítimo sem preenchimento), exclusividade entre
listas, posições 1-indexadas, desempate determinístico declarado e
determinismo sob permutação da entrada (invariantes 5 e 6).
"""

import re
from pathlib import Path

import pytest

from dominio.alocacao import (
    COTA_DESTAQUE,
    COTA_SUPER_DESTAQUE,
    Alocacao,
    CandidatoAlocacao,
    alocar,
)
from dominio.elegibilidade import PRECO_MINIMO_SUPER_DESTAQUE

RAIZ = Path(__file__).parents[1]
DDL = RAIZ / "src" / "dados" / "registro" / "001_registro.sql"


def candidato(
    imovel_id: int,
    preco: int = 1_000_000,
    nota_super: float = 50.0,
    nota_destaque: float = 50.0,
) -> CandidatoAlocacao:
    return CandidatoAlocacao(
        imovel_id=imovel_id,
        preco=preco,
        nota_super_destaque=nota_super,
        nota_destaque=nota_destaque,
    )


# --- amarração das cotas Python ↔ DDL (invariante 6) -------------------------


def _cota_no_ddl(texto_sem_comentarios: str, nivel: str) -> int | None:
    padrao = rf"nivel\s*=\s*'{nivel}'\s+AND\s+posicao_ranking\s+BETWEEN\s+1\s+AND\s+(\d+)"
    m = re.search(padrao, texto_sem_comentarios)
    return int(m.group(1)) if m else None


def test_cotas_do_modulo_batem_com_o_check_do_ddl():
    # A cota vive em dois lugares sem runtime comum: aqui e no CHECK
    # posicao_dentro_da_cota do Registro. Este teste é o elo que quebra
    # ruidosamente se um lado mudar sozinho. Comentários SQL removidos antes
    # de casar (constraint comentada não conta) e espaços colapsados, para
    # sobreviver a reformatação; a extração por regex tolera formatadores e
    # permite dizer o valor que o DDL efetivamente contém.
    texto = re.sub(r"--[^\n]*", "", DDL.read_text(encoding="utf-8"))
    texto = re.sub(r"\s+", " ", texto)
    no_ddl_super = _cota_no_ddl(texto, "super_destaque")
    no_ddl_destaque = _cota_no_ddl(texto, "destaque")
    assert no_ddl_super == COTA_SUPER_DESTAQUE, (
        f"cota do super destaque divergiu: src/dominio/alocacao.py diz "
        f"{COTA_SUPER_DESTAQUE}, {DDL} diz {no_ddl_super} — "
        f"os dois lados do contrato OLX devem mudar juntos"
    )
    assert no_ddl_destaque == COTA_DESTAQUE, (
        f"cota do destaque divergiu: src/dominio/alocacao.py diz "
        f"{COTA_DESTAQUE}, {DDL} diz {no_ddl_destaque} — "
        f"os dois lados do contrato OLX devem mudar juntos"
    )


def test_cotas_sao_as_do_contrato():
    assert COTA_SUPER_DESTAQUE == 475
    assert COTA_DESTAQUE == 6_495


# --- as duas fases e o piso de nível ------------------------------------------


def test_piso_no_limite_entra_no_super_destaque():
    resultado = alocar([candidato(1, preco=PRECO_MINIMO_SUPER_DESTAQUE)])
    assert [p.imovel_id for p in resultado.super_destaque] == [1]
    assert resultado.destaque == ()


def test_abaixo_do_piso_vai_para_o_destaque():
    resultado = alocar([candidato(1, preco=PRECO_MINIMO_SUPER_DESTAQUE - 1, nota_super=999.0)])
    # A nota de super destaque alta é ignorada: abaixo do piso o candidato
    # nunca entra na fase 1.
    assert resultado.super_destaque == ()
    assert [p.imovel_id for p in resultado.destaque] == [1]


def test_cada_fase_ordena_pela_nota_do_proprio_nivel():
    lote = [
        candidato(1, nota_super=90.0, nota_destaque=10.0),
        candidato(2, nota_super=80.0, nota_destaque=99.0),
        candidato(3, preco=400_000, nota_super=999.0, nota_destaque=50.0),
        candidato(4, preco=400_000, nota_super=0.0, nota_destaque=70.0),
    ]
    resultado = alocar(lote)
    assert [p.imovel_id for p in resultado.super_destaque] == [1, 2]
    # Fase 2 ordena por nota_destaque (70 > 50), nunca pela nota_super (999).
    assert [p.imovel_id for p in resultado.destaque] == [4, 3]


def test_quem_nao_coube_no_super_compete_no_destaque():
    lote = [
        candidato(i, nota_super=float(1000 - i), nota_destaque=float(i))
        for i in range(1, COTA_SUPER_DESTAQUE + 2)  # 476 aptos ao super
    ]
    resultado = alocar(lote)
    assert len(resultado.super_destaque) == COTA_SUPER_DESTAQUE
    # O 476º no ranking do super (imovel_id 476, menor nota_super) cai para
    # o destaque, onde sua nota_destaque vale.
    assert [p.imovel_id for p in resultado.destaque] == [476]


# --- invariante 6 nos dois sentidos --------------------------------------------


def test_lote_maior_que_as_cotas_produz_exatamente_as_cotas():
    lote = [
        candidato(i, preco=800_000 if i <= 500 else 400_000)
        for i in range(1, COTA_SUPER_DESTAQUE + COTA_DESTAQUE + 100)
    ]
    resultado = alocar(lote)
    assert len(resultado.super_destaque) == COTA_SUPER_DESTAQUE
    assert len(resultado.destaque) == COTA_DESTAQUE
    ids_super = {p.imovel_id for p in resultado.super_destaque}
    ids_destaque = {p.imovel_id for p in resultado.destaque}
    assert ids_super.isdisjoint(ids_destaque)


def test_lote_menor_produz_deficit_sem_preenchimento_artificial():
    resultado = alocar([candidato(1), candidato(2, preco=400_000)])
    assert len(resultado.super_destaque) == 1
    assert len(resultado.destaque) == 1


def test_lote_vazio_produz_listas_vazias():
    assert alocar([]) == Alocacao(super_destaque=(), destaque=())


# --- exclusividade e posições ---------------------------------------------------


def test_nenhum_imovel_aparece_nas_duas_listas():
    lote = [candidato(i) for i in range(1, 600)]
    resultado = alocar(lote)
    ids_super = {p.imovel_id for p in resultado.super_destaque}
    ids_destaque = {p.imovel_id for p in resultado.destaque}
    assert ids_super.isdisjoint(ids_destaque)


def test_posicoes_comecam_em_1_e_sao_consecutivas():
    lote = [candidato(i) for i in range(1, 6)] + [
        candidato(i, preco=400_000) for i in range(10, 14)
    ]
    resultado = alocar(lote)
    assert [p.posicao for p in resultado.super_destaque] == [1, 2, 3, 4, 5]
    assert [p.posicao for p in resultado.destaque] == [1, 2, 3, 4]


def test_posicao_carrega_a_nota_do_nivel_alocado():
    resultado = alocar([candidato(1, nota_super=77.0, nota_destaque=11.0)])
    assert resultado.super_destaque[0].nota == 77.0


# --- desempate e determinismo (invariante 5) -------------------------------------


def test_desempate_por_imovel_id_crescente():
    # Leitura estrutural declarada: em empate de nota, ganha o imovel_id
    # menor — viés a favor de cadastros mais antigos, apontado ao dono.
    lote = [
        candidato(9, nota_super=50.0),
        candidato(3, nota_super=50.0),
        candidato(7, nota_super=50.0),
    ]
    resultado = alocar(lote)
    assert [p.imovel_id for p in resultado.super_destaque] == [3, 7, 9]


def test_permutacoes_da_entrada_produzem_saida_identica():
    lote = [
        candidato(
            i,
            preco=800_000 if i % 3 else 400_000,
            nota_super=float(i % 5),
            nota_destaque=float(i % 7),
        )
        for i in range(1, 200)
    ]
    invertido = list(reversed(lote))
    rotacionado = lote[37:] + lote[:37]
    assert alocar(lote) == alocar(invertido) == alocar(rotacionado)


def test_mesma_entrada_mesma_saida():
    lote = [candidato(i, nota_super=float(i % 4), nota_destaque=float(i % 6)) for i in range(1, 50)]
    resultados = {alocar(lote) for _ in range(20)}
    assert len(resultados) == 1


# --- validação de entrada ----------------------------------------------------------


def test_imovel_id_duplicado_e_erro_deterministico():
    with pytest.raises(ValueError, match=r"imovel_id duplicado no lote: \[2, 5\]"):
        alocar([candidato(2), candidato(5), candidato(2), candidato(5), candidato(1)])


def test_preco_negativo_e_erro():
    with pytest.raises(ValueError, match="preco negativo"):
        candidato(1, preco=-1)


@pytest.mark.parametrize("invalida", [float("nan"), float("inf")])
def test_nota_nao_finita_e_erro(invalida):
    with pytest.raises(ValueError, match="nota não finita para nota_destaque"):
        candidato(1, nota_destaque=invalida)
