"""Testes da camada 1 do crivo de auditoria (D-017).

Módulo puro — roda inteiro no CI. Cobre o cenário pronto (sem violações) e cada
verificação disparando SEU veto isoladamente, além do determinismo (invariante
5: mesmo resultado ⇒ mesmo veredito).
"""

from dominio.alocacao import Alocacao, PosicaoAlocada
from dominio.auditoria import (
    AgregadosParaParecer,
    ItemAuditavel,
    auditar,
)


def _item(
    imovel_id, *, preco=800_000, nota_super=90.0, nota_destaque=50.0, elegivel=True, relax=False
):
    return ItemAuditavel(
        imovel_id=imovel_id,
        preco=preco,
        nota_super=nota_super,
        nota_destaque=nota_destaque,
        elegivel=elegivel,
        veio_de_relaxamento=relax,
    )


def _super(*pares):
    return tuple(
        PosicaoAlocada(posicao=i, imovel_id=iid, nota=nota)
        for i, (iid, nota) in enumerate(pares, 1)
    )


def _dest(*pares):
    return tuple(
        PosicaoAlocada(posicao=i, imovel_id=iid, nota=nota)
        for i, (iid, nota) in enumerate(pares, 1)
    )


def _cenario_valido():
    """Super {1:90, 2:80}, destaque {3:50, 4:40}, + 1 elegível excluído abaixo do corte."""
    alocacao = Alocacao(
        super_destaque=_super((1, 90.0), (2, 80.0)), destaque=_dest((3, 50.0), (4, 40.0))
    )
    itens = {
        1: _item(1, nota_super=90.0),
        2: _item(2, nota_super=80.0),
        3: _item(3, preco=400_000, nota_super=None, nota_destaque=50.0),
        4: _item(4, preco=400_000, nota_super=None, nota_destaque=40.0),
        5: _item(
            5, preco=400_000, nota_super=None, nota_destaque=30.0
        ),  # excluído, abaixo do corte
    }
    return alocacao, itens


def _codigos(resultado):
    return {v.codigo for v in resultado.violacoes}


def test_cenario_valido_fica_pronta():
    alocacao, itens = _cenario_valido()
    r = auditar(alocacao, itens)
    assert r.pronta is True
    assert r.violacoes == ()


def test_piso_super_violado():
    alocacao, itens = _cenario_valido()
    itens[2] = _item(2, preco=699_999, nota_super=80.0)  # super abaixo de 700k
    r = auditar(alocacao, itens)
    assert r.pronta is False
    assert "piso_super_violado" in _codigos(r)


def test_super_com_relaxamento_violado():
    alocacao, itens = _cenario_valido()
    itens[2] = _item(2, nota_super=80.0, relax=True)  # super nunca relaxa (inv. 7)
    r = auditar(alocacao, itens)
    assert "super_com_relaxamento" in _codigos(r)


def test_imovel_em_dois_niveis_violado():
    itens = _cenario_valido()[1]
    alocacao = Alocacao(
        super_destaque=_super((1, 90.0)), destaque=_dest((1, 50.0))
    )  # id 1 nos dois
    r = auditar(alocacao, itens)
    assert "imovel_em_dois_niveis" in _codigos(r)


def test_sem_justificativa_violado():
    alocacao, itens = _cenario_valido()
    del itens[2]  # super sem item auditável
    r = auditar(alocacao, itens)
    assert "sem_justificativa" in _codigos(r)


def test_corte_super_violado():
    alocacao, itens = _cenario_valido()
    # elegível apto (preço ≥ 700k) fora do super com nota_super acima do menor dentro (80).
    itens[6] = _item(6, preco=800_000, nota_super=85.0)
    r = auditar(alocacao, itens)
    assert "corte_super_violado" in _codigos(r)


def test_corte_destaque_violado():
    alocacao, itens = _cenario_valido()
    # elegível excluído com nota_destaque acima do menor do destaque de ranking (40).
    itens[7] = _item(7, preco=400_000, nota_super=None, nota_destaque=45.0)
    r = auditar(alocacao, itens)
    assert "corte_destaque_violado" in _codigos(r)


def test_recuperado_por_relaxamento_nao_conta_no_corte_destaque():
    # Um recuperado (veio_de_relaxamento) no destaque NÃO baixa o corte do ranking,
    # e um reprovado (não elegível) fora não dispara corte.
    alocacao = Alocacao(
        super_destaque=_super((1, 90.0)),
        destaque=_dest((3, 50.0), (8, 5.0)),  # id 8 recuperado, nota baixa
    )
    itens = {
        1: _item(1, nota_super=90.0),
        3: _item(3, preco=400_000, nota_super=None, nota_destaque=50.0),
        8: _item(8, preco=400_000, nota_super=None, nota_destaque=5.0, elegivel=False, relax=True),
        9: _item(
            9, preco=400_000, nota_super=None, nota_destaque=20.0, elegivel=False
        ),  # reprovado fora
    }
    r = auditar(alocacao, itens)
    # o corte do ranking é 50 (só a posição 3 é ranking); o reprovado (não elegível)
    # não entra no corte, então nada viola.
    assert r.pronta is True


def test_cota_super_excedida():
    # 476 super estoura a cota (invariante 6).
    alocacao = Alocacao(
        super_destaque=_super(*[(i, 100.0 - i * 0.001) for i in range(1, 477)]),
        destaque=(),
    )
    itens = {i: _item(i) for i in range(1, 477)}
    r = auditar(alocacao, itens)
    assert "cota_super_excedida" in _codigos(r)


def test_deterministico():
    alocacao, itens = _cenario_valido()
    itens[2] = _item(2, preco=1, nota_super=80.0)  # força uma violação
    vereditos = {tuple(sorted(_codigos(auditar(alocacao, itens)))) for _ in range(30)}
    assert len(vereditos) == 1


def test_contrato_camada2_so_agregados():
    # A camada 2 é declarada, não implementada: o contrato de agregados existe e
    # não carrega identidade de pessoa (invariante 3 / D-006).
    ag = AgregadosParaParecer(
        n_super=475,
        n_destaque=6495,
        n_recuperados_relaxamento=0,
        distribuicao_perfis_super={"faixa_preco=700k-1M": 468},
        distribuicao_perfis_destaque={"faixa_preco=300k-500k": 2696},
        degradacoes=("desempenho zerado",),
        camada1_pronta=True,
    )
    campos = set(ag.__dataclass_fields__)
    # nenhum campo de identidade de pessoa
    assert not campos & {"lead", "comprador", "corretor", "gestor", "nome", "email", "telefone"}


def test_cota_destaque_excedida():
    # 6496 destaque estoura a cota (invariante 6), espelho do super.
    alocacao = Alocacao(
        super_destaque=(),
        destaque=_dest(*[(i, 100.0 - i * 0.0001) for i in range(1, 6497)]),
    )
    itens = {i: _item(i, preco=400_000, nota_super=None) for i in range(1, 6497)}
    r = auditar(alocacao, itens)
    assert "cota_destaque_excedida" in _codigos(r)


def test_empate_no_corte_nao_viola():
    # Nota IGUAL ao menor do corte NÃO viola (só estritamente maior) — contrato
    # do desempate (D-009). Trava a regra contra uma troca futura de > por >=.
    alocacao, itens = _cenario_valido()
    # == menor super (80) e nota_destaque abaixo do corte (40): empate no super, não viola.
    itens[6] = _item(6, preco=800_000, nota_super=80.0, nota_destaque=30.0)
    itens[7] = _item(7, preco=400_000, nota_super=None, nota_destaque=40.0)  # == menor destaque
    r = auditar(alocacao, itens)
    assert r.pronta is True


def test_varias_violacoes_coexistem():
    # O laço de agregação acumula vetos simultâneos (piso + corte super).
    alocacao, itens = _cenario_valido()
    itens[2] = _item(2, preco=1, nota_super=80.0)  # piso violado (super id 2)
    itens[6] = _item(6, preco=800_000, nota_super=85.0)  # corte super violado
    r = auditar(alocacao, itens)
    assert {"piso_super_violado", "corte_super_violado"} <= _codigos(r)


def test_ambos_niveis_vazios_fica_pronta():
    # Sem posições, nada a conferir — pronta vacuamente.
    r = auditar(Alocacao(super_destaque=(), destaque=()), {})
    assert r.pronta is True
    assert r.violacoes == ()


def test_super_inelegivel_violado():
    # Super não elegível e não recuperado vazou por bug (super nunca relaxa).
    alocacao, itens = _cenario_valido()
    itens[2] = _item(2, nota_super=80.0, elegivel=False)
    r = auditar(alocacao, itens)
    assert "super_inelegivel" in _codigos(r)


def test_destaque_inelegivel_sem_relaxamento_violado():
    # Destaque nem elegível nem recuperado por relaxamento — via ilegítima.
    alocacao, itens = _cenario_valido()
    itens[3] = _item(3, preco=400_000, nota_super=None, nota_destaque=50.0, elegivel=False)
    r = auditar(alocacao, itens)
    assert "destaque_inelegivel_sem_relaxamento" in _codigos(r)
