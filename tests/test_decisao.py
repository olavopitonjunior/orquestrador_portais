"""Testes da costura da decisão (piloto) — o encadeamento das seis etapas.

Módulo puro — roda no CI. Verifica a separação elegível/reprovado, a montagem
dos fatores (desempenho zerado, produtividade binária), a alocação nas cotas, o
disparo do relaxamento sobre reprovados e o determinismo. Os módulos do domínio
já são testados isoladamente; aqui prova-se a FIAÇÃO.
"""

from datetime import date

import pytest

from dominio.elegibilidade import ImovelCandidato
from dominio.penalidades import ImovelPenalizavel, IntensidadesPenalidade, Penalidade
from dominio.perfil import Dimensao, PerfilConversao
from dominio.ranking import PesosNivel
from piloto.decisao import ParametrosDecisao, decidir
from piloto.semelhanca import ParametrosSemelhanca

HOJE = date(2026, 8, 31)

# Pesos-ponte DORMENTES (leads_positivo=0) + decaimento=1.0 (ponderação por
# dimensão = identidade): mantêm estes testes de fiação equivalentes ao esquema
# pré-D-017, então as asserções de nota seguem válidas. O comportamento vivo
# (leads positivo, de-saturação) tem testes próprios.
PARAMS = ParametrosDecisao(
    semelhanca=ParametrosSemelhanca(desconto_fragil=0.5, decaimento=1.0),
    intensidades=IntensidadesPenalidade(
        janela_sem_resultado=0.15, sem_avaliacao_por_categoria=0.10, sem_lead_180d=0.10
    ),
    decaimento_janela=lambda ciclos: 1.0,
    pesos_super=PesosNivel(
        semelhanca_perfil=60, leads_positivo=0, desempenho_proprio=25, produtividade_gestor=15
    ),
    pesos_destaque=PesosNivel(
        semelhanca_perfil=80, leads_positivo=0, desempenho_proprio=10, produtividade_gestor=10
    ),
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
    assert a.detalhes == b.detalhes


def test_sem_candidatos_nao_quebra():
    r = _rodar([], {})
    assert r.n_elegiveis == 0
    assert r.alocacao.super_destaque == ()
    assert r.relaxamento.recuperados == ()


# --- detalhamento por imóvel (justificativa carregada, não recomputada) ------


def test_detalhe_do_elegivel_carrega_fatores_e_notas():
    cands = [_candidato(1)]
    r = _rodar(cands, {1: _dims()})
    det = r.detalhes[1]
    assert det.fatores.imovel_id == 1
    assert det.nota_super_destaque is not None  # elegível disputa super
    assert det.nota_destaque is not None
    # o total é a soma do breakdown por penalidade (sem divergência)
    assert det.desconto_total == sum(det.descontos_por_penalidade.values())


def test_detalhe_carrega_o_perfil_que_puxou():
    # O imóvel casa o perfil (Centro): o detalhe carrega o perfil casado como
    # justificativa (Spec §2.1).
    r = _rodar([_candidato(1)], {1: _dims(regiao="Centro")})
    pqp = r.detalhes[1].perfil_que_puxou
    assert pqp is not None
    assert pqp.valores == ("Centro",)
    assert pqp.num_vendas == 10  # a evidência viaja junto


def test_detalhe_sem_perfil_casado_e_none():
    # Imóvel numa região sem perfil: perfil_que_puxou é None (não inventa).
    r = _rodar([_candidato(1)], {1: _dims(regiao="RegiaoSemPerfil")})
    assert r.detalhes[1].perfil_que_puxou is None


def test_detalhe_do_reprovado_recuperado_tem_nota_super_none():
    cands = [_candidato(1, preco=400_000), _candidato(2, preco=400_000, elegivel=False)]
    r = _rodar(cands, {1: _dims(), 2: _dims()})
    assert r.detalhes[2].nota_super_destaque is None  # reprovado só disputa destaque
    assert r.detalhes[2].nota_destaque is not None


def test_detalhe_reflete_penalidade_aplicada():
    # Imóvel elegível mas sem lead em 180d recebe a penalidade SEM_LEAD_180D,
    # visível no breakdown.
    cands = [_candidato(1)]
    penalizaveis = {1: _penalizavel(1, leads=0)}
    r = decidir(cands, penalizaveis, {1: _dims()}, PERFIS, PARAMS, HOJE)
    assert Penalidade.SEM_LEAD_180D in r.detalhes[1].descontos_por_penalidade
    assert r.detalhes[1].descontos_por_penalidade[Penalidade.SEM_LEAD_180D] == 0.10


def test_imovel_id_duplicado_no_lote_e_erro():
    # A guarda de unicidade fecha o buraco: id repetido atravessando
    # elegível↔reprovado sobrescreveria detalhes em silêncio.
    cands = [_candidato(1), _candidato(1, elegivel=False)]
    with pytest.raises(ValueError, match="imovel_id duplicado"):
        _rodar(cands, {1: _dims()})


def test_leads_e_fator_positivo_vivo():
    # F2 (D-017): dois elegíveis idênticos exceto Leads180D; com peso de leads > 0,
    # quem tem mais leads recebe fator de leads maior (min-max sobre os elegíveis)
    # e nota maior. Prova que lead virou sinal POSITIVO, não só penalidade.
    params = ParametrosDecisao(
        semelhanca=ParametrosSemelhanca(desconto_fragil=0.5, decaimento=1.0),
        intensidades=IntensidadesPenalidade(
            janela_sem_resultado=0.0, sem_avaliacao_por_categoria=0.0, sem_lead_180d=0.0
        ),
        decaimento_janela=lambda _c: 1.0,
        pesos_super=PesosNivel(
            semelhanca_perfil=50, leads_positivo=30, desempenho_proprio=10, produtividade_gestor=10
        ),
        pesos_destaque=PesosNivel(
            semelhanca_perfil=40, leads_positivo=40, desempenho_proprio=10, produtividade_gestor=10
        ),
    )
    cands = [_candidato(1), _candidato(2)]
    dims = {1: _dims(), 2: _dims()}
    penalizaveis = {1: _penalizavel(1, leads=100), 2: _penalizavel(2, leads=0)}
    r = decidir(cands, penalizaveis, dims, PERFIS, params, HOJE)
    # min-max sobre os dois elegíveis: mais leads → 1.0, menos → 0.0.
    assert r.detalhes[1].fatores.leads == 1.0
    assert r.detalhes[2].fatores.leads == 0.0
    # semelhança/produtividade são iguais nos dois (min-max degenera em 0.0);
    # só o fator de leads difere, então a nota do de mais leads é maior.
    assert r.detalhes[1].nota_destaque > r.detalhes[2].nota_destaque


def test_penalizavel_ausente_falha_alto():
    # _leads_do falha alto se um elegível não tem ImovelPenalizavel — protege
    # contra coleta desalinhada (mesmo contrato de _descontos), agora disparado
    # ao montar o fator de leads.
    with pytest.raises(ValueError, match="coleta desalinhada"):
        decidir([_candidato(1)], {}, {1: _dims()}, PERFIS, PARAMS, HOJE)
