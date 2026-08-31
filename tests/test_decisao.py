"""Testes da costura da decisão (piloto) — o encadeamento das seis etapas.

Módulo puro — roda no CI. Verifica a separação elegível/reprovado, a montagem
dos fatores (desempenho zerado, produtividade binária), a alocação nas cotas, o
disparo do relaxamento sobre reprovados e o determinismo. Os módulos do domínio
já são testados isoladamente; aqui prova-se a FIAÇÃO.
"""

from datetime import date

from dominio.elegibilidade import ImovelCandidato
from dominio.penalidades import ImovelPenalizavel, IntensidadesPenalidade
from dominio.perfil import Dimensao, PerfilConversao
from piloto.decisao import ParametrosDecisao, decidir
from piloto.semelhanca import ParametrosSemelhanca

HOJE = date(2026, 8, 31)

PARAMS = ParametrosDecisao(
    semelhanca=ParametrosSemelhanca(desconto_fragil=0.5),
    intensidades=IntensidadesPenalidade(
        janela_sem_resultado=0.15, sem_avaliacao_por_categoria=0.10, sem_lead_180d=0.10
    ),
    decaimento_janela=lambda ciclos: 1.0,
)


def _candidato(imovel_id, *, elegivel=True, preco=850_000, gestor=True):
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
        corretores_ativos_no_distrito=5,
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


PERFIS = (PerfilConversao(dimensoes=(Dimensao.REGIAO,), valores=("Centro",), num_vendas=10),)


def _rodar(candidatos, dims_por_imovel):
    penalizaveis = {c.imovel_id: _penalizavel(c.imovel_id) for c in candidatos}
    return decidir(candidatos, penalizaveis, dims_por_imovel, PERFIS, PARAMS, HOJE)


def test_separa_elegiveis_de_reprovados():
    cands = [_candidato(1), _candidato(2, elegivel=False)]
    r = _rodar(cands, {1: _dims(), 2: _dims()})
    assert r.n_elegiveis == 1
    assert r.n_reprovados == 1


def test_elegiveis_recebem_posicao():
    cands = [_candidato(i) for i in range(1, 4)]
    r = _rodar(cands, {i: _dims() for i in range(1, 4)})
    # Todos elegíveis, preço ≥ 700k → todos aptos ao super destaque; cabem nas cotas.
    ids_super = {p.imovel_id for p in r.alocacao.super_destaque}
    assert ids_super == {1, 2, 3}
    # Nenhum sobra para destaque (todos foram para super).
    assert r.alocacao.destaque == ()


def test_abaixo_do_piso_vai_para_destaque_nao_super():
    cands = [_candidato(1, preco=400_000)]  # < 700k: não entra no super
    r = _rodar(cands, {1: _dims()})
    assert r.alocacao.super_destaque == ()
    assert {p.imovel_id for p in r.alocacao.destaque} == {1}


def test_relaxamento_dispara_com_deficit_e_reprovado_relaxavel():
    # 1 elegível (destaque) + 1 reprovado só por FOTOS (regra relaxável): com
    # déficit gigante (cota 6.495), o relaxamento recupera o reprovado.
    cands = [_candidato(1, preco=400_000), _candidato(2, preco=400_000, elegivel=False)]
    r = _rodar(cands, {1: _dims(), 2: _dims()})
    assert r.n_reprovados == 1
    recuperados = {rec.imovel_id for rec in r.relaxamento.recuperados}
    assert 2 in recuperados  # reprovado por FOTOS é recuperável


def test_degradacoes_declaradas():
    r = _rodar([_candidato(1)], {1: _dims()})
    assert any("degradada" in d.lower() for d in r.degradacoes)
    assert any("provis" in d.lower() for d in r.degradacoes)


def test_deterministico():
    cands = [_candidato(1), _candidato(2), _candidato(3, elegivel=False)]
    dims = {1: _dims("Centro"), 2: _dims("Sul"), 3: _dims("Centro")}
    a = _rodar(cands, dims)
    b = _rodar(list(reversed(cands)), dims)
    assert a.alocacao == b.alocacao
    assert a.relaxamento == b.relaxamento


def test_sem_candidatos_nao_quebra():
    r = _rodar([], {})
    assert r.n_elegiveis == 0
    assert r.alocacao.super_destaque == ()
    assert r.relaxamento.recuperados == ()
