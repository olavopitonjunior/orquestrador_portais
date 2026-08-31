"""Testes da descoberta de perfis de conversão (Spec §6.2, D-014).

Módulo puro — roda inteiro no CI, sem banco. Cobre a contagem de 1 e 2
dimensões, o rótulo de fragilidade (N ≥ 3), o tratamento de dimensão nula,
a proibição de combinações de 3+ dimensões e o determinismo da ordem.
"""

import pytest

from dominio.perfil import (
    EVIDENCIA_MINIMA,
    Dimensao,
    ImovelVendido,
    PerfilConversao,
    perfis_de_conversao,
)


def _vendido(
    imovel_id, regiao=None, faixa_preco=None, faixa_metragem=None, dormitorios=None, vagas=None
):
    return ImovelVendido(
        imovel_id=imovel_id,
        regiao=regiao,
        faixa_preco=faixa_preco,
        faixa_metragem=faixa_metragem,
        dormitorios=dormitorios,
        vagas=vagas,
    )


def test_valores_exclui_none():
    v = _vendido(1, regiao="Centro", dormitorios=2)
    assert v.valores() == {Dimensao.REGIAO: "Centro", Dimensao.DORMITORIOS: 2}


def test_conta_uma_dimensao():
    vendas = [_vendido(1, regiao="Centro"), _vendido(2, regiao="Centro"), _vendido(3, regiao="Sul")]
    perfis = perfis_de_conversao(vendas)
    por_regiao = {p.valores: p.num_vendas for p in perfis if p.dimensoes == (Dimensao.REGIAO,)}
    assert por_regiao == {("Centro",): 2, ("Sul",): 1}


def test_conta_duas_dimensoes():
    vendas = [
        _vendido(1, regiao="Centro", dormitorios=2),
        _vendido(2, regiao="Centro", dormitorios=2),
        _vendido(3, regiao="Centro", dormitorios=3),
    ]
    par = [
        p
        for p in perfis_de_conversao(vendas)
        if p.dimensoes == (Dimensao.REGIAO, Dimensao.DORMITORIOS)
    ]
    contagem = {p.valores: p.num_vendas for p in par}
    assert contagem == {("Centro", 2): 2, ("Centro", 3): 1}


def test_nunca_tres_dimensoes():
    # Spec §6.2: nunca as cinco (nem três) simultaneamente. Só 1 e 2 dims saem.
    vendas = [_vendido(1, regiao="C", faixa_preco="A", faixa_metragem="M", dormitorios=2, vagas=1)]
    assert all(1 <= len(p.dimensoes) <= 2 for p in perfis_de_conversao(vendas))


def test_dimensao_nula_nao_entra_em_combinacao():
    # Imóvel sem dormitórios não conta para nenhum perfil que inclua dormitórios.
    vendas = [
        _vendido(1, regiao="Centro", dormitorios=2),
        _vendido(2, regiao="Centro", dormitorios=None),  # sem dormitórios
    ]
    perfis = perfis_de_conversao(vendas)
    regiao_so = next(p for p in perfis if p.dimensoes == (Dimensao.REGIAO,))
    assert regiao_so.num_vendas == 2  # ambos contam para região
    par = [p for p in perfis if p.dimensoes == (Dimensao.REGIAO, Dimensao.DORMITORIOS)]
    assert {p.valores: p.num_vendas for p in par} == {("Centro", 2): 1}  # só o imóvel 1


def test_fragilidade_no_limiar():
    # N == EVIDENCIA_MINIMA (3) é robusto; N < 3 é frágil. Ambos permanecem.
    vendas = [_vendido(i, regiao="Robusto") for i in range(EVIDENCIA_MINIMA)] + [
        _vendido(99, regiao="Fragil")
    ]
    perfis = {
        p.valores[0]: p for p in perfis_de_conversao(vendas) if p.dimensoes == (Dimensao.REGIAO,)
    }
    assert perfis["Robusto"].num_vendas == 3
    assert perfis["Robusto"].fragil is False
    assert perfis["Fragil"].num_vendas == 1
    assert perfis["Fragil"].fragil is True


def test_fragilidade_vizinho_do_limiar():
    # N=2 (logo abaixo de 3) é frágil; N=3 é robusto. Cobre a borda exata.
    vendas = [_vendido(1, regiao="Dois"), _vendido(2, regiao="Dois")]
    perfil = next(p for p in perfis_de_conversao(vendas) if p.dimensoes == (Dimensao.REGIAO,))
    assert perfil.num_vendas == 2
    assert perfil.fragil is True


def test_fragil_nao_e_excluido():
    # Uma única venda gera um perfil frágil, presente no resultado.
    perfis = perfis_de_conversao([_vendido(1, regiao="Unico")])
    assert any(p.valores == ("Unico",) and p.fragil for p in perfis)


def test_venda_de_duas_dimensoes_gera_os_tres_perfis():
    # Um imóvel com 2 dimensões preenchidas conta para os dois perfis de 1-dim
    # E para o de 2-dim (contagem cruzada completa).
    perfis = perfis_de_conversao([_vendido(1, regiao="Centro", dormitorios=2)])
    combos = {p.dimensoes: p.valores for p in perfis}
    assert combos[(Dimensao.REGIAO,)] == ("Centro",)
    assert combos[(Dimensao.DORMITORIOS,)] == (2,)
    assert combos[(Dimensao.REGIAO, Dimensao.DORMITORIOS)] == ("Centro", 2)
    assert len(perfis) == 3


def test_ordem_estavel_com_valores_int_e_str_na_mesma_dimensao():
    # Contrato do invariante 5: valores opacos de tipos diferentes na MESMA
    # dimensão (int 2 e str "2") não colapsam num empate nem quebram a
    # ordenação. A chave de ordenação tagueada por tipo é a rede (achado do
    # revisor). O valor é declarado opaco, então o teste força os dois tipos.
    a = [_vendido(1, dormitorios=2), _vendido(2, dormitorios="2")]
    b = list(reversed(a))
    r_a = perfis_de_conversao(a)
    assert r_a == perfis_de_conversao(b)  # determinístico, independe da entrada
    # int 2 e str "2" produzem DOIS perfis distintos (não colapsam).
    dorm = [p for p in r_a if p.dimensoes == (Dimensao.DORMITORIOS,)]
    assert {p.valores for p in dorm} == {(2,), ("2",)}


def test_ordem_canonica_e_deterministica():
    # Mesma entrada em ordens diferentes ⇒ mesma saída (invariante 5).
    a = [_vendido(1, regiao="B", dormitorios=1), _vendido(2, regiao="A", dormitorios=2)]
    b = list(reversed(a))
    assert perfis_de_conversao(a) == perfis_de_conversao(b)


def test_ordem_por_dimensao_depois_valor():
    vendas = [_vendido(1, regiao="Sul", dormitorios=1), _vendido(2, regiao="Centro", dormitorios=1)]
    perfis = perfis_de_conversao(vendas)
    # Perfis de 1 dimensão de REGIAO vêm antes dos de DORMITORIOS (ordem do enum),
    # e dentro de REGIAO, "Centro" antes de "Sul".
    de_uma = [p for p in perfis if len(p.dimensoes) == 1]
    seq = [(p.dimensoes[0].value, str(p.valores[0])) for p in de_uma]
    assert seq == sorted(seq)


def test_perfil_rejeita_tres_dimensoes():
    with pytest.raises(ValueError, match="1 ou 2 dimensões"):
        PerfilConversao(
            dimensoes=(Dimensao.REGIAO, Dimensao.DORMITORIOS, Dimensao.VAGAS),
            valores=("C", 2, 1),
            num_vendas=5,
        )


def test_perfil_rejeita_valores_desalinhados():
    with pytest.raises(ValueError, match="mesmo comprimento"):
        PerfilConversao(dimensoes=(Dimensao.REGIAO,), valores=("C", 2), num_vendas=1)


def test_perfil_rejeita_num_vendas_zero():
    with pytest.raises(ValueError, match="num_vendas"):
        PerfilConversao(dimensoes=(Dimensao.REGIAO,), valores=("C",), num_vendas=0)


def test_vazio_nao_gera_perfis():
    assert perfis_de_conversao([]) == ()
