"""Testes do perfil de conversão como FILTRO (D-027): casa ou não casa.

Módulo puro — roda inteiro no CI. Cobre a regra de match, quais perfis CONTAM
(robustos; contendo a dimensão exigida), o "perfil que puxou" como rótulo
explicativo (mais vendas; empate → mais específico → ordem canônica), o veredito
binário `casa_algum` e uma MEDIÇÃO em miniatura do fato que motivou a exigência de
dimensão: sem ela, o perfil de metragem sozinho casa o estoque inteiro.
"""

from dominio.perfil import Dimensao, ImovelVendido, PerfilConversao, perfis_de_conversao
from piloto.semelhanca import casa, casa_algum, perfil_que_puxou, perfis_que_contam


def _perfil(dims, vals, n):
    return PerfilConversao(dimensoes=dims, valores=vals, num_vendas=n)


REGIAO_CENTRO = _perfil((Dimensao.REGIAO,), ("Centro",), 10)  # robusto
CENTRO_2D = _perfil((Dimensao.REGIAO, Dimensao.DORMITORIOS), ("Centro", 2), 4)  # robusto
FRAGIL = _perfil((Dimensao.REGIAO,), ("Sul",), 1)  # frágil (N<3)
PRECO_700K = _perfil((Dimensao.FAIXA_PRECO,), ("700k-1M",), 5)  # robusto, contém preço
PRECO_CENTRO = _perfil((Dimensao.REGIAO, Dimensao.FAIXA_PRECO), ("Centro", "700k-1M"), 3)
PRECO_FRAGIL = _perfil((Dimensao.FAIXA_PRECO,), ("1M+",), 2)  # contém preço, mas frágil


# --- casa: match exato de todas as dimensões do perfil ------------------------


def test_casa_match_exato_de_todas_as_dimensoes():
    dims = {Dimensao.REGIAO: "Centro", Dimensao.DORMITORIOS: 2}
    assert casa(dims, REGIAO_CENTRO) is True
    assert casa(dims, CENTRO_2D) is True


def test_nao_casa_se_alguma_dimensao_difere():
    dims = {Dimensao.REGIAO: "Centro", Dimensao.DORMITORIOS: 3}
    assert casa(dims, CENTRO_2D) is False  # dormitórios diferem


def test_nao_casa_se_candidato_nao_tem_a_dimensao():
    """Dimensão ausente no candidato (a fonte não preenche) não é coringa."""
    dims = {Dimensao.REGIAO: "Centro"}  # sem dormitórios
    assert casa(dims, CENTRO_2D) is False


def test_casa_nao_confunde_tipos():
    """`2` (int) e `"2"` (str) são valores distintos: a bucketização mantém tipo fixo
    por dimensão, e o match não pode colapsar os dois."""
    dims = {Dimensao.REGIAO: "Centro", Dimensao.DORMITORIOS: "2"}
    assert casa(dims, CENTRO_2D) is False


# --- perfis_que_contam: robustos, contendo a dimensão exigida -----------------


def test_fragil_nao_conta():
    """Perfil frágil (N < 3, D-014) não recebe "peso pleno" — e como o perfil agora
    filtra, não há peso parcial: ele simplesmente não conta."""
    assert perfis_que_contam((REGIAO_CENTRO, FRAGIL, PRECO_FRAGIL), None) == (REGIAO_CENTRO,)


def test_sem_exigencia_todos_os_robustos_contam():
    perfis = (REGIAO_CENTRO, CENTRO_2D, FRAGIL, PRECO_700K, PRECO_CENTRO)
    assert perfis_que_contam(perfis, None) == (REGIAO_CENTRO, CENTRO_2D, PRECO_700K, PRECO_CENTRO)


def test_exigir_dimensao_mantem_so_quem_a_contem():
    """D-027: o perfil precisa CONTER a faixa de preço — em uma ou em duas dimensões."""
    perfis = (REGIAO_CENTRO, CENTRO_2D, FRAGIL, PRECO_700K, PRECO_CENTRO, PRECO_FRAGIL)
    assert perfis_que_contam(perfis, Dimensao.FAIXA_PRECO) == (PRECO_700K, PRECO_CENTRO)


def test_exigir_dimensao_e_robustez_sao_cumulativos():
    """Conter a dimensão não salva o frágil; ser robusto não salva quem não a contém."""
    assert perfis_que_contam((PRECO_FRAGIL, REGIAO_CENTRO), Dimensao.FAIXA_PRECO) == ()


def test_perfis_que_contam_preserva_a_ordem_de_entrada():
    """A ordem canônica vem de `perfis_de_conversao`; aqui ela só é filtrada, nunca
    reordenada (invariante 5)."""
    perfis = (PRECO_CENTRO, PRECO_700K, REGIAO_CENTRO)
    assert perfis_que_contam(perfis, None) == perfis
    assert perfis_que_contam(perfis, Dimensao.FAIXA_PRECO) == (PRECO_CENTRO, PRECO_700K)


def test_perfis_que_contam_vazio():
    assert perfis_que_contam((), None) == ()
    assert perfis_que_contam((), Dimensao.FAIXA_PRECO) == ()


# --- perfil que puxou: o rótulo da justificativa -----------------------------


def test_perfil_que_puxou_none_sem_match():
    dims = {Dimensao.REGIAO: "Norte"}
    assert perfil_que_puxou(dims, (REGIAO_CENTRO, CENTRO_2D)) is None


def test_perfil_que_puxou_none_sem_perfis():
    assert perfil_que_puxou({Dimensao.REGIAO: "Centro"}, ()) is None


def test_perfil_que_puxou_e_o_de_mais_vendas():
    """Casa REGIAO_CENTRO (N=10) e CENTRO_2D (N=4): puxa o de mais vendas — a
    evidência que a planilha mostra ao lado do identificador (Spec §2.1)."""
    dims = {Dimensao.REGIAO: "Centro", Dimensao.DORMITORIOS: 2}
    assert perfil_que_puxou(dims, (REGIAO_CENTRO, CENTRO_2D)) is REGIAO_CENTRO


def test_perfil_que_puxou_ignora_o_que_nao_casa_mesmo_com_mais_vendas():
    grande = _perfil((Dimensao.REGIAO,), ("Norte",), 100)
    dims = {Dimensao.REGIAO: "Centro", Dimensao.DORMITORIOS: 2}
    assert perfil_que_puxou(dims, (grande, CENTRO_2D)) is CENTRO_2D


def test_empate_de_vendas_o_mais_especifico_ganha():
    """Dois perfis com o MESMO N: o de 2 dimensões (mais específico) é o exibido —
    diz mais sobre POR QUE o imóvel entrou."""
    p1d = _perfil((Dimensao.REGIAO,), ("X",), 5)
    p2d = _perfil((Dimensao.REGIAO, Dimensao.DORMITORIOS), ("X", 2), 5)
    dims = {Dimensao.REGIAO: "X", Dimensao.DORMITORIOS: 2}
    assert perfil_que_puxou(dims, (p1d, p2d)) is p2d
    assert perfil_que_puxou(dims, (p2d, p1d)) is p2d


def test_empate_total_decide_pela_ordem_canonica():
    """Mesmo N, mesma especificidade: a ordem canônica (dimensões, depois valores)
    decide — e NÃO a ordem de entrada, senão o rótulo mudaria entre rodadas iguais
    (invariante 5)."""
    preco = _perfil((Dimensao.FAIXA_PRECO,), ("700k-1M",), 5)
    vagas = _perfil((Dimensao.VAGAS,), (2,), 5)
    dims = {Dimensao.FAIXA_PRECO: "700k-1M", Dimensao.VAGAS: 2}
    assert perfil_que_puxou(dims, (preco, vagas)) is preco  # "faixa_preco" < "vagas"
    assert perfil_que_puxou(dims, (vagas, preco)) is preco


def test_perfil_que_puxou_nao_reconsidera_os_que_nao_contam():
    """`perfil_que_puxou` recebe os perfis JÁ filtrados: o rótulo nunca aponta para um
    perfil que o filtro não usou. A responsabilidade de filtrar é de quem chama."""
    dims = {Dimensao.REGIAO: "Sul"}
    assert perfil_que_puxou(dims, perfis_que_contam((FRAGIL,), None)) is None


# --- casa_algum: o veredito do filtro -----------------------------------------


def test_casa_algum_verdadeiro_com_um_match():
    dims = {Dimensao.REGIAO: "Centro"}
    assert casa_algum(dims, (FRAGIL, REGIAO_CENTRO)) is True


def test_casa_algum_falso_sem_match_e_sem_perfis():
    assert casa_algum({Dimensao.REGIAO: "Norte"}, (REGIAO_CENTRO, CENTRO_2D)) is False
    assert casa_algum({Dimensao.REGIAO: "Centro"}, ()) is False


def test_casa_algum_concorda_com_perfil_que_puxou():
    """Fonte única: há rótulo se e só se há veredito positivo."""
    perfis = (REGIAO_CENTRO, CENTRO_2D, PRECO_700K)
    for dims in (
        {Dimensao.REGIAO: "Centro"},
        {Dimensao.FAIXA_PRECO: "700k-1M"},
        {Dimensao.REGIAO: "Norte"},
        {},
    ):
        assert casa_algum(dims, perfis) is (perfil_que_puxou(dims, perfis) is not None)


# --- MEDIÇÃO em miniatura: por que a dimensão é exigida (D-027) ---------------

# Quatro vendas, todas na mesma faixa de metragem; só UMA faixa de preço chega a N ≥ 3.
VENDAS = (
    ImovelVendido(1, None, "300-500k", "50-80", None, None),
    ImovelVendido(2, None, "300-500k", "50-80", None, None),
    ImovelVendido(3, None, "300-500k", "50-80", None, None),
    ImovelVendido(4, None, "700k-1M", "50-80", None, None),
)
CANDIDATOS = {
    "A": {Dimensao.FAIXA_PRECO: "300-500k", Dimensao.FAIXA_METRAGEM: "50-80"},
    "B": {Dimensao.FAIXA_PRECO: "700k-1M", Dimensao.FAIXA_METRAGEM: "50-80"},  # preço frágil
    "C": {Dimensao.FAIXA_PRECO: "1M+", Dimensao.FAIXA_METRAGEM: "50-80"},  # preço sem venda
    "D": {Dimensao.FAIXA_METRAGEM: "50-80"},  # sem preço
}


def test_sem_exigir_dimensao_a_metragem_sozinha_casa_todo_mundo():
    """O fato medido em 04/09/2026: com perfis de uma dimensão em N ≥ 3, a faixa de
    metragem sozinha cobre o estoque, e o filtro deixa passar 100%."""
    que_contam = perfis_que_contam(perfis_de_conversao(VENDAS), None)
    assert all(casa_algum(dims, que_contam) for dims in CANDIDATOS.values())


def test_exigindo_faixa_de_preco_so_quem_tem_a_faixa_certa_casa():
    """Com a exigência (D-027), só passa quem se parece com o que vendeu NA FAIXA DE
    PREÇO: B cai porque a faixa dele tem uma venda só; C e D porque não têm faixa
    com venda."""
    que_contam = perfis_que_contam(perfis_de_conversao(VENDAS), Dimensao.FAIXA_PRECO)
    veredito = {nome: casa_algum(dims, que_contam) for nome, dims in CANDIDATOS.items()}
    assert veredito == {"A": True, "B": False, "C": False, "D": False}


def test_na_medicao_o_perfil_que_puxou_e_o_mais_especifico_com_mesma_evidencia():
    """A casa o perfil de preço (N=3) e o de preço+metragem (N=3): o rótulo é o de
    duas dimensões, e a evidência exibida é 3."""
    que_contam = perfis_que_contam(perfis_de_conversao(VENDAS), Dimensao.FAIXA_PRECO)
    puxou = perfil_que_puxou(CANDIDATOS["A"], que_contam)
    assert puxou is not None
    assert puxou.dimensoes == (Dimensao.FAIXA_PRECO, Dimensao.FAIXA_METRAGEM)
    assert puxou.num_vendas == 3
    assert puxou.fragil is False


def test_medicao_e_deterministica():
    """Mesmas vendas, mesmos candidatos ⇒ mesmos vereditos e rótulos (invariante 5)."""
    perfis = perfis_de_conversao(VENDAS)
    que_contam = perfis_que_contam(perfis, Dimensao.FAIXA_PRECO)
    resultados = {
        tuple(
            (nome, casa_algum(dims, que_contam), perfil_que_puxou(dims, que_contam))
            for nome, dims in CANDIDATOS.items()
        )
        for _ in range(20)
    }
    assert len(resultados) == 1
