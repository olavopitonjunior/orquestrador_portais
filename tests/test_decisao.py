"""Testes da costura da decisão (piloto) — "o banco manda, o portal classifica".

Módulo puro — roda no CI. Verifica a FIAÇÃO das etapas (D-027 a D-030): o filtro de
perfil como regra, a separação elegível/reprovado, a nota do portal (ou o desempate
de banco declarado quando o portal não entra), o tratamento do imóvel sem anúncio,
o desempate por leads antes do cadastro mais novo, a trava do login no relaxamento e
o determinismo. Os módulos do domínio já são testados isoladamente.
"""

import random
from dataclasses import replace
from datetime import date

import pytest

from dados.coletor_externo import DesempenhoAnuncio
from dominio.elegibilidade import ImovelCandidato, Regra
from dominio.penalidades import ImovelPenalizavel, IntensidadesPenalidade, Penalidade
from dominio.perfil import Dimensao, PerfilConversao
from dominio.ranking import PesosPortal, nota_portal
from piloto.decisao import (
    DEGRADACOES,
    FORMAS_DE_ORDEM_SEM_PORTAL,
    FORMAS_SEM_ANUNCIO,
    ParametrosDecisao,
    decidir,
    degradacao_sem_portal,
)

HOJE = date(2026, 8, 31)

PESOS = PesosPortal(nota_anuncio=70, cliques=30, visualizacoes=0)
INTENSIDADES = IntensidadesPenalidade(
    janela_sem_resultado=20.0, sem_avaliacao_por_categoria=5.0, sem_lead_180d=10.0
)


def _params(**mudancas):
    base = dict(
        pesos_portal=PESOS,
        sem_anuncio="fim_da_fila",
        ordem_sem_portal="leads_180d",
        intensidades=INTENSIDADES,
        decaimento_janela=lambda _c: 1.0,
        minimo_corretores_distrito=2,
        # None: qualquer perfil robusto conta — o teste do FAIXA_PRECO é próprio.
        exigir_dimensao_no_perfil=None,
    )
    return ParametrosDecisao(**{**base, **mudancas})


PARAMS = _params()


def _candidato(
    imovel_id,
    *,
    elegivel=True,
    preco=850_000,
    gestor=True,
    produtividade=1,
    logou=None,
    corretores=5,
):
    """Um ImovelCandidato elegível por padrão; `elegivel=False` reprova em fotos."""
    return ImovelCandidato(
        imovel_id=imovel_id,
        publicacao_ativa=True,
        categoria="Apartamento",
        preco=preco,
        qtd_fotos=20 if elegivel else 3,  # < 10 reprova (regra relaxável FOTOS)
        atualizado_em=date(2026, 8, 30),
        notas_por_categoria={"Descrição do imóvel": 10},
        gestor_captou_ou_vendeu_30d=gestor,
        produtividade_gestor_30d=produtividade,
        corretores_ativos_no_distrito=corretores,
        gestor_logou_na_janela=logou,
    )


def _penalizavel(imovel_id, leads=7):
    return ImovelPenalizavel(
        imovel_id=imovel_id,
        janelas_anteriores=(),
        alguma_categoria_avaliada=True,
        leads_180d=leads,
    )


def _dims(regiao="Centro", dorm=2):
    return {Dimensao.REGIAO: regiao, Dimensao.DORMITORIOS: dorm}


def _anuncio(imovel_id, nota=8000.0, views=0, cliques=None):
    return DesempenhoAnuncio(
        imovel_id=imovel_id,
        id_portal=f"90{imovel_id}",
        nota=nota,
        visualizacoes=views,
        cliques=cliques or {},
        url=None,
    )


PERFIS = (PerfilConversao(dimensoes=(Dimensao.REGIAO,), valores=("Centro",), num_vendas=10),)


def _rodar(candidatos, dims_por_imovel, *, params=PARAMS, leads=None, anuncios=None, portal=False):
    leads = leads or {}
    penalizaveis = {
        c.imovel_id: _penalizavel(c.imovel_id, leads.get(c.imovel_id, 7)) for c in candidatos
    }
    return decidir(
        candidatos,
        penalizaveis,
        dims_por_imovel,
        PERFIS,
        params,
        HOJE,
        anuncios=anuncios,
        portal_entrou=portal,
    )


def _ordem_super(r):
    return [p.imovel_id for p in r.alocacao.super_destaque]


# --- fiação básica ----------------------------------------------------------------


def test_separa_elegiveis_de_reprovados():
    cands = [_candidato(1), _candidato(2, elegivel=False)]
    r = _rodar(cands, {1: _dims(), 2: _dims()})
    assert r.n_elegiveis == 1
    assert r.n_reprovados == 1
    assert r.reprovados_regras == {2: frozenset({Regra.FOTOS})}


def test_elegiveis_recebem_posicao():
    cands = [_candidato(i) for i in range(1, 4)]
    r = _rodar(cands, {i: _dims() for i in range(1, 4)})
    # Todos elegíveis, preço ≥ 700k → todos aptos ao super destaque; cabem nas cotas.
    assert set(_ordem_super(r)) == {1, 2, 3}
    assert r.alocacao.destaque == ()


def test_abaixo_do_piso_vai_para_destaque_nao_super():
    cands = [_candidato(1, preco=400_000)]  # < 700k: não entra no super
    r = _rodar(cands, {1: _dims()})
    assert r.alocacao.super_destaque == ()
    assert {p.imovel_id for p in r.alocacao.destaque} == {1}


def test_relaxamento_dispara_com_deficit_e_reprovado_relaxavel():
    cands = [_candidato(1, preco=400_000), _candidato(2, preco=400_000, elegivel=False)]
    r = _rodar(cands, {1: _dims(), 2: _dims()})
    assert r.n_reprovados == 1
    assert {rec.imovel_id for rec in r.relaxamento.recuperados} == {2}


def test_sem_candidatos_nao_quebra():
    r = _rodar([], {})
    assert r.n_elegiveis == 0
    assert r.alocacao.super_destaque == ()
    assert r.relaxamento.recuperados == ()


def test_imovel_id_duplicado_no_lote_e_erro():
    cands = [_candidato(1), _candidato(1, elegivel=False)]
    with pytest.raises(ValueError, match="imovel_id duplicado"):
        _rodar(cands, {1: _dims()})


def test_penalizavel_ausente_falha_alto():
    with pytest.raises(ValueError, match="coleta desalinhada"):
        decidir([_candidato(1)], {}, {1: _dims()}, PERFIS, PARAMS, HOJE)


# --- o filtro de perfil é REGRA (D-027) ----------------------------------------------


def test_quem_nao_casa_perfil_reprova_em_PERFIL_DE_CONVERSAO():
    cands = [_candidato(1), _candidato(2), _candidato(3)]
    dims = {1: _dims("Centro"), 2: _dims("Sul"), 3: {}}  # 3: sem dimensão nenhuma
    r = _rodar(cands, dims)
    assert r.n_elegiveis == 1
    assert r.reprovados_regras[2] == frozenset({Regra.PERFIL_DE_CONVERSAO})
    assert r.reprovados_regras[3] == frozenset({Regra.PERFIL_DE_CONVERSAO})
    # dimensões PRESENTES mas vazias = "não casa" (3, acima); candidato FORA do mapa
    # = não avaliado: não reprova, é contado e declarado (revisão de 04/09/2026)
    r2 = _rodar([_candidato(4)], {})
    assert 4 not in r2.reprovados_regras
    assert r2.detalhes[4].fatores.casa_perfil is None
    assert any("1 candidato(s) sem dimensões" in d for d in r2.degradacoes)


def test_o_veredito_e_preenchido_em_TODO_candidato_pela_costura():
    """Os candidatos entram com `casa_perfil_de_conversao=None` (a coleta não o
    conhece) e a costura calcula o veredito para cada um: elegível carrega
    `casa_perfil=True` no detalhe, reprovado carrega `False` — nenhum fica sem."""
    cands = [_candidato(1, preco=400_000), _candidato(2, preco=400_000)]
    assert all(c.casa_perfil_de_conversao is None for c in cands)
    r = _rodar(cands, {1: _dims("Centro"), 2: _dims("Sul")})
    assert r.detalhes[1].fatores.casa_perfil is True
    assert r.detalhes[2].fatores.casa_perfil is False  # pontuado para o relaxamento
    assert set(r.detalhes) == {1, 2}


def test_a_costura_RECALCULA_o_veredito_e_nao_confia_no_que_veio():
    """Um veredito pré-carregado no candidato é sobrescrito pelo cálculo contra os
    perfis — só a costura conhece os perfis, e é ela que responde pela regra."""
    dentro_marcado_fora = replace(_candidato(1), casa_perfil_de_conversao=False)
    fora_marcado_dentro = replace(_candidato(2), casa_perfil_de_conversao=True)
    r = _rodar([dentro_marcado_fora, fora_marcado_dentro], {1: _dims("Centro"), 2: _dims("Sul")})
    assert r.n_elegiveis == 1 and 1 in {p.imovel_id for p in r.alocacao.super_destaque}
    assert r.reprovados_regras[2] == frozenset({Regra.PERFIL_DE_CONVERSAO})


def test_perfil_fragil_NAO_conta_para_o_filtro():
    """D-014/D-027: perfil com N < 3 não conta. Sem NENHUM perfil que conte, a regra
    não é avaliada (veredito None), ninguém reprova por perfil e a rodada declara a
    degradação (Spec §7.3: "sem robustez opera sem o fator") — em vez de reprovar
    100 % do estoque em silêncio."""
    frageis = (PerfilConversao(dimensoes=(Dimensao.REGIAO,), valores=("Centro",), num_vendas=2),)
    pen = {1: _penalizavel(1)}
    r = decidir([_candidato(1)], pen, {1: _dims("Centro")}, frageis, PARAMS, HOJE)
    assert 1 not in r.reprovados_regras
    assert r.detalhes[1].fatores.casa_perfil is None
    assert any("sem evidência robusta" in d and "NÃO incidiu" in d for d in r.degradacoes)


def test_candidato_sem_dimensoes_nao_reprova_por_dado_ausente():
    """Coleta de perfil desalinhada da de candidatos: o imóvel sem dimensões fica com
    veredito None (não avaliado), é contado e declarado — não reprova por ausência."""
    perfis = (PerfilConversao(dimensoes=(Dimensao.REGIAO,), valores=("Centro",), num_vendas=5),)
    pen = {1: _penalizavel(1), 2: _penalizavel(2)}
    r = decidir([_candidato(1), _candidato(2)], pen, {1: _dims("Centro")}, perfis, PARAMS, HOJE)
    assert 2 not in r.reprovados_regras
    assert r.detalhes[2].fatores.casa_perfil is None
    assert r.detalhes[1].fatores.casa_perfil is True
    assert any("1 candidato(s) sem dimensões" in d for d in r.degradacoes)


def test_exigir_dimensao_no_perfil_descarta_perfil_sem_a_dimensao():
    """D-027: o perfil precisa CONTER a dimensão exigida (faixa de preço em
    produção) para contar. O perfil só de região, robusto, deixa de valer."""
    perfis = (
        PerfilConversao(dimensoes=(Dimensao.REGIAO,), valores=("Centro",), num_vendas=10),
        PerfilConversao(
            dimensoes=(Dimensao.REGIAO, Dimensao.FAIXA_PRECO),
            valores=("Centro", "700k–1M"),
            num_vendas=5,
        ),
    )
    params = _params(exigir_dimensao_no_perfil=Dimensao.FAIXA_PRECO)
    cands = [_candidato(1), _candidato(2)]
    pen = {c.imovel_id: _penalizavel(c.imovel_id) for c in cands}
    dims = {
        1: {Dimensao.REGIAO: "Centro", Dimensao.FAIXA_PRECO: "700k–1M"},
        2: {Dimensao.REGIAO: "Centro"},  # casa só o perfil de região, que não conta
    }
    r = decidir(cands, pen, dims, perfis, params, HOJE)
    assert r.n_elegiveis == 1
    assert r.reprovados_regras[2] == frozenset({Regra.PERFIL_DE_CONVERSAO})
    # o rótulo é o perfil que CONTOU, não o de mais vendas entre todos
    assert r.detalhes[1].perfil_que_puxou == perfis[1]
    # sem a exigência, o de região volta a contar e o 2 passa
    assert decidir(cands, pen, dims, perfis, PARAMS, HOJE).n_elegiveis == 2


def test_detalhe_carrega_o_perfil_que_puxou_o_de_MAIS_vendas():
    perfis = (
        *PERFIS,
        PerfilConversao(
            dimensoes=(Dimensao.REGIAO, Dimensao.DORMITORIOS), valores=("Centro", 2), num_vendas=4
        ),
    )
    pen = {1: _penalizavel(1)}
    r = decidir([_candidato(1)], pen, {1: _dims("Centro", 2)}, perfis, PARAMS, HOJE)
    pqp = r.detalhes[1].perfil_que_puxou
    assert pqp is not None and pqp.valores == ("Centro",) and pqp.num_vendas == 10


def test_reprovado_sem_perfil_casado_tem_perfil_que_puxou_None():
    r = _rodar([_candidato(1, preco=400_000)], {1: _dims(regiao="RegiaoSemPerfil")})
    assert 1 in r.detalhes  # pontuado para o relaxamento
    assert r.detalhes[1].perfil_que_puxou is None
    assert r.detalhes[1].nota_super_destaque is None  # reprovado só disputa destaque


# --- a NOTA: o portal classifica (D-028) ----------------------------------------------


def test_com_portal_a_nota_bruta_e_a_nota_portal():
    cands = [_candidato(1), _candidato(2)]
    an = {1: _anuncio(1, nota=9000.0), 2: _anuncio(2, nota=6000.0)}
    r = _rodar(cands, {1: _dims(), 2: _dims()}, anuncios=an, portal=True)
    d1, d2 = r.detalhes[1], r.detalhes[2]
    assert (d1.fatores.nota_anuncio, d2.fatores.nota_anuncio) == (1.0, 0.0)  # min-max
    assert d1.nota_bruta == nota_portal(d1.fatores, PESOS) == 70.0
    assert d2.nota_bruta == nota_portal(d2.fatores, PESOS) == 0.0
    assert d1.nota_destaque == d1.nota_bruta - d1.desconto_total
    assert _ordem_super(r) == [1, 2]
    # o portal entrou: nenhuma degradação de "desempate de banco"
    assert r.degradacoes == DEGRADACOES


def test_cliques_sao_SOMADOS_entre_tipos_na_nota_do_portal():
    cands = [_candidato(1), _candidato(2)]
    an = {
        1: _anuncio(1, cliques={"cliqueContato": 2, "cliqueWhatsapp": 3}),
        2: _anuncio(2, cliques={"cliqueContato": 4}),
    }
    r = _rodar(cands, {1: _dims(), 2: _dims()}, anuncios=an, portal=True)
    assert r.detalhes[1].fatores.cliques == 1.0  # 5 > 4
    assert r.detalhes[2].fatores.cliques == 0.0
    assert r.detalhes[1].nota_bruta == 30.0  # notas iguais → 0; só os cliques pesam


def test_sem_portal_a_nota_vem_do_desempate_de_banco_e_a_rodada_declara():
    cands = [_candidato(1), _candidato(2)]
    r = _rodar(cands, {1: _dims(), 2: _dims()}, leads={1: 100, 2: 0})
    assert r.detalhes[1].nota_bruta == 100.0 * r.detalhes[1].fatores.leads == 100.0
    assert r.detalhes[2].nota_bruta == 0.0
    assert degradacao_sem_portal("leads_180d") in r.degradacoes
    assert any("DEGRADADA" in d for d in r.degradacoes)
    assert any("PROVIS" in d for d in r.degradacoes)  # a normalização min-max é provisória
    assert r.detalhes[1].fatores.nota_anuncio == 0.0  # sem anúncio nenhum, sinal zero


def test_anuncios_presentes_mas_portal_NAO_entrou_nao_pesam_mas_aparecem():
    """As portas do Coletor Externo fecharam: os sinais do portal são calculados (a
    apuração os mostra), mas a nota vem do banco e a degradação é declarada."""
    cands = [_candidato(1), _candidato(2)]
    an = {1: _anuncio(1, nota=9000.0), 2: _anuncio(2, nota=6000.0)}
    r = _rodar(cands, {1: _dims(), 2: _dims()}, leads={1: 0, 2: 50}, anuncios=an, portal=False)
    assert r.detalhes[1].fatores.nota_anuncio == 1.0  # descritivo
    assert r.detalhes[1].nota_bruta == 0.0  # mas não pesou: leads mandam
    assert r.detalhes[2].nota_bruta == 100.0
    assert degradacao_sem_portal("leads_180d") in r.degradacoes


def test_portal_entrou_sem_anuncio_nenhum_e_tratado_como_nao_entrou():
    r = _rodar([_candidato(1)], {1: _dims()}, anuncios={}, portal=True)
    assert degradacao_sem_portal("leads_180d") in r.degradacoes


def test_ordem_sem_portal_produtividade_gestor():
    params = _params(ordem_sem_portal="produtividade_gestor")
    cands = [_candidato(1, produtividade=0), _candidato(2, produtividade=12)]
    r = _rodar(cands, {1: _dims(), 2: _dims()}, params=params)
    assert r.detalhes[2].nota_bruta == 100.0 and r.detalhes[1].nota_bruta == 0.0
    assert _ordem_super(r) == [2, 1]
    assert degradacao_sem_portal("produtividade_gestor") in r.degradacoes


def test_ordem_sem_portal_cadastro_mais_novo_empata_todos_e_o_id_decide():
    params = _params(ordem_sem_portal="cadastro_mais_novo")
    cands = [_candidato(1), _candidato(2), _candidato(3)]
    r = _rodar(cands, {i: _dims() for i in (1, 2, 3)}, params=params)
    assert {d.nota_bruta for d in r.detalhes.values()} == {0.0}
    assert _ordem_super(r) == [3, 2, 1]  # leads iguais → imovel_id decrescente (D-009)


# --- imóvel sem anúncio: o tratamento declarado --------------------------------------


def _quatro_com_um_sem_anuncio(sem_anuncio):
    cands = [_candidato(i) for i in (1, 2, 3, 4)]
    an = {1: _anuncio(1, nota=6000.0), 2: _anuncio(2, nota=8000.0), 3: _anuncio(3, nota=10000.0)}
    return _rodar(
        cands,
        {i: _dims() for i in (1, 2, 3, 4)},
        params=_params(sem_anuncio=sem_anuncio),
        anuncios=an,
        portal=True,
    )


def test_sem_anuncio_fim_da_fila_recebe_o_MINIMO():
    r = _quatro_com_um_sem_anuncio("fim_da_fila")
    assert r.detalhes[4].fatores.nota_anuncio == 0.0 == r.detalhes[1].fatores.nota_anuncio
    assert _ordem_super(r)[0] == 3
    assert _ordem_super(r)[-2:] == [4, 1]  # empatados no fim; id maior primeiro


def test_sem_anuncio_mediana_recebe_a_MEDIANA_de_quem_tem():
    r = _quatro_com_um_sem_anuncio("mediana")
    assert r.detalhes[4].fatores.nota_anuncio == 0.5 == r.detalhes[2].fatores.nota_anuncio
    assert _ordem_super(r)[0] == 3 and _ordem_super(r)[-1] == 1


# --- o DESEMPATE é o banco: leads antes do cadastro mais novo ----------------------


def test_empate_de_nota_e_decidido_por_leads_antes_do_imovel_id():
    cands = [_candidato(1), _candidato(2)]
    an = {1: _anuncio(1), 2: _anuncio(2)}  # anúncios idênticos → nota igual
    # leads 100 vs 1 (não 0: zero lead dispara a penalidade e desempataria pela nota)
    r = _rodar(cands, {1: _dims(), 2: _dims()}, leads={1: 100, 2: 1}, anuncios=an, portal=True)
    assert r.detalhes[1].nota_destaque == r.detalhes[2].nota_destaque
    assert _ordem_super(r) == [1, 2]  # mais leads vence, apesar do id menor
    # leads iguais: cai no cadastro mais novo (D-009, id decrescente)
    r2 = _rodar(cands, {1: _dims(), 2: _dims()}, leads={1: 5, 2: 5}, anuncios=an, portal=True)
    assert _ordem_super(r2) == [2, 1]


# --- descontos --------------------------------------------------------------------


def test_detalhe_do_elegivel_carrega_fatores_e_notas():
    r = _rodar([_candidato(1)], {1: _dims()})
    det = r.detalhes[1]
    assert det.fatores.imovel_id == 1
    assert det.nota_super_destaque is not None and det.nota_destaque is not None
    assert det.desconto_total == sum(det.descontos_por_penalidade.values())
    assert det.nota_destaque == det.nota_bruta - det.desconto_total


def test_detalhe_reflete_penalidade_aplicada_em_pontos_de_100():
    r = _rodar([_candidato(1)], {1: _dims()}, leads={1: 0})
    det = r.detalhes[1]
    assert det.descontos_por_penalidade[Penalidade.SEM_LEAD_180D] == 10.0
    assert det.nota_destaque == det.nota_bruta - 10.0


# --- a trava do login chega ao relaxamento (D-029) -----------------------------------


def _com_gestor_improdutivo(logou):
    cands = [
        _candidato(1, preco=400_000),
        _candidato(2, preco=400_000, gestor=False, logou=logou),
    ]
    return _rodar(cands, {1: _dims(), 2: _dims()})


def test_gestor_sem_login_reprovado_em_gestor_produtivo_nao_e_recuperado():
    r = _com_gestor_improdutivo(logou=False)
    assert r.reprovados_regras[2] == frozenset({Regra.GESTOR_PRODUTIVO})
    assert r.relaxamento.recuperados == ()
    assert r.relaxamento.bloqueados_por_login == 1


@pytest.mark.parametrize("logou", [True, None])
def test_com_login_ou_sem_informacao_o_degrau_gestor_produtivo_recupera(logou):
    r = _com_gestor_improdutivo(logou=logou)
    assert [rec.imovel_id for rec in r.relaxamento.recuperados] == [2]
    assert r.relaxamento.recuperados[0].degrau is Regra.GESTOR_PRODUTIVO
    assert r.relaxamento.bloqueados_por_login == 0


# --- parâmetros -------------------------------------------------------------------


def test_minimo_de_corretores_do_distrito_chega_a_elegibilidade():
    cands = [_candidato(1, corretores=2)]
    assert _rodar(cands, {1: _dims()}).n_elegiveis == 1
    r = _rodar(cands, {1: _dims()}, params=_params(minimo_corretores_distrito=3))
    assert r.reprovados_regras[1] == frozenset({Regra.CAPACIDADE_DISTRITO})


def test_parametros_recusam_formas_desconhecidas_e_minimo_abaixo_de_um():
    assert set(FORMAS_SEM_ANUNCIO) == {"fim_da_fila", "mediana"}
    assert set(FORMAS_DE_ORDEM_SEM_PORTAL) == {
        "leads_180d",
        "produtividade_gestor",
        "cadastro_mais_novo",
    }
    with pytest.raises(ValueError, match="sem_anuncio desconhecido"):
        _params(sem_anuncio="zero")
    with pytest.raises(ValueError, match="ordem_sem_portal desconhecida"):
        _params(ordem_sem_portal="aleatoria")
    with pytest.raises(ValueError, match="minimo_corretores_distrito inválido"):
        _params(minimo_corretores_distrito=0)


# --- determinismo (invariante 5) ---------------------------------------------------


def test_mesma_entrada_mesma_saida():
    cands = [_candidato(1), _candidato(2), _candidato(3, elegivel=False)]
    dims = {1: _dims("Centro"), 2: _dims("Sul"), 3: _dims("Centro")}
    an = {1: _anuncio(1, nota=9000.0), 3: _anuncio(3, nota=7000.0)}
    a = _rodar(cands, dims, anuncios=an, portal=True)
    b = _rodar(cands, dims, anuncios=an, portal=True)
    assert a == b


def test_ordem_dos_candidatos_embaralhada_nao_muda_nada():
    cands = [
        _candidato(i, preco=400_000 if i % 3 else 850_000, elegivel=(i % 4 != 0))
        for i in range(1, 25)
    ]
    dims = {c.imovel_id: _dims("Centro" if c.imovel_id % 5 else "Sul") for c in cands}
    leads = {c.imovel_id: (c.imovel_id * 7) % 11 for c in cands}
    an = {
        c.imovel_id: _anuncio(c.imovel_id, nota=6000.0 + (c.imovel_id * 37) % 900)
        for c in cands
        if c.imovel_id % 6
    }
    referencia = _rodar(cands, dims, leads=leads, anuncios=an, portal=True)
    rng = random.Random(7)
    for _ in range(5):
        embaralhados = list(cands)
        rng.shuffle(embaralhados)
        r = _rodar(embaralhados, dims, leads=leads, anuncios=an, portal=True)
        assert r.alocacao == referencia.alocacao
        assert r.relaxamento == referencia.relaxamento
        assert r.detalhes == referencia.detalhes
        assert r.reprovados_regras == referencia.reprovados_regras
