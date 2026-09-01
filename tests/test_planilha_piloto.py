"""Testes da serialização da planilha-piloto.

As funções de linha são puras (testadas sem arquivo): provam que o CSV
SERIALIZA o ResultadoDecisao campo a campo, sem recomputar. Um teste do writer
usa tmp_path (fora do repo) só para confirmar que os quatro arquivos saem.
"""

import csv
from datetime import date

from dominio.elegibilidade import ImovelCandidato
from dominio.penalidades import ImovelPenalizavel, IntensidadesPenalidade, Penalidade
from dominio.perfil import Dimensao, PerfilConversao
from entrega.planilha_piloto import (
    escrever_planilha,
    linhas_destaque,
    linhas_excluidos_por_regra,
    linhas_parametros_e_limitacoes,
    linhas_super_destaque,
)
from piloto.decisao import ParametrosDecisao, decidir
from piloto.semelhanca import ParametrosSemelhanca

HOJE = date(2026, 8, 31)
PARAMS = ParametrosDecisao(
    semelhanca=ParametrosSemelhanca(desconto_fragil=0.5),
    intensidades=IntensidadesPenalidade(
        janela_sem_resultado=0.15, sem_avaliacao_por_categoria=0.10, sem_lead_180d=0.10
    ),
    decaimento_janela=lambda _c: 1.0,
)
PERFIS = (PerfilConversao(dimensoes=(Dimensao.REGIAO,), valores=("Centro",), num_vendas=10),)


def _cand(imovel_id, *, preco=850_000, fotos=20, categoria="Apartamento"):
    return ImovelCandidato(
        imovel_id=imovel_id,
        publicacao_ativa=True,
        categoria=categoria,
        preco=preco,
        qtd_fotos=fotos,
        atualizado_em=date(2026, 8, 30),
        notas_por_categoria={"Descrição do imóvel": 10},
        gestor_captou_ou_vendeu_30d=True,
        corretores_ativos_no_distrito=5,
    )


def _pen(imovel_id):
    return ImovelPenalizavel(
        imovel_id=imovel_id, janelas_anteriores=(), alguma_categoria_avaliada=True, leads_180d=7
    )


def _resultado():
    # c0: super destaque (≥700k); c1: destaque (ranking); c2: reprovado por FOTOS
    # (relaxável → recuperado); c3: reprovado por CATEGORIA (não relaxável → excluído).
    cands = [
        _cand(10),
        _cand(11, preco=400_000),
        _cand(12, preco=400_000, fotos=3),
        _cand(13, preco=400_000, categoria="Casa de Vila"),
    ]
    pen = {c.imovel_id: _pen(c.imovel_id) for c in cands}
    dims = {c.imovel_id: {Dimensao.REGIAO: "Centro"} for c in cands}
    return decidir(cands, pen, dims, PERFIS, PARAMS, HOJE)


def test_super_destaque_serializa_a_nota_e_a_justificativa():
    r = _resultado()
    linhas = linhas_super_destaque(r)
    assert [ln["imovel_id"] for ln in linhas] == [10]
    ln = linhas[0]
    # a nota do CSV é a mesma do ResultadoDecisao (serializa, não recomputa)
    assert ln["nota"] == r.alocacao.super_destaque[0].nota
    assert ln["semelhanca_perfil"] == r.detalhes[10].fatores.semelhanca_perfil
    assert ln["perfil_que_puxou"] == "regiao=Centro"
    assert ln["perfil_num_vendas"] == 10
    # paridade de colunas com destaque (Spec §3.2): super tem origem/degrau vazios
    assert ln["origem"] == "ranking"
    assert ln["degrau_cedido"] == ""
    assert set(ln.keys()) == set(linhas_destaque(r)[0].keys())


def test_destaque_inclui_recuperado_com_degrau():
    r = _resultado()
    linhas = linhas_destaque(r)
    por_id = {ln["imovel_id"]: ln for ln in linhas}
    assert por_id[11]["origem"] == "ranking"
    assert por_id[11]["degrau_cedido"] == ""
    # c2 (fotos) foi recuperado pelo relaxamento, com o degrau "fotos"
    assert por_id[12]["origem"] == "relaxamento"
    assert por_id[12]["degrau_cedido"] == "fotos"
    # posições contínuas: recuperado vem depois do ranking
    assert por_id[12]["posicao"] > por_id[11]["posicao"]


def test_destaque_nota_bate_com_o_resultado():
    r = _resultado()
    linhas = {ln["imovel_id"]: ln for ln in linhas_destaque(r)}
    # ranking: nota == pos.nota; recuperado: nota == rec.nota_destaque
    assert linhas[11]["nota"] == r.alocacao.destaque[0].nota
    rec = next(x for x in r.relaxamento.recuperados if x.imovel_id == 12)
    assert linhas[12]["nota"] == rec.nota_destaque


def test_excluidos_lista_so_os_nao_recuperados_com_as_regras():
    r = _resultado()
    linhas = linhas_excluidos_por_regra(r)
    ids = [ln["imovel_id"] for ln in linhas]
    assert ids == [13]  # c2 (fotos) foi recuperado; c3 (categoria) não
    assert "categoria" in linhas[0]["regras_reprovadas"]


def test_parametros_e_limitacoes_rotula_provisorios_e_limitacoes():
    r = _resultado()
    linhas = linhas_parametros_e_limitacoes(r, PARAMS)
    tipos = {ln["tipo"] for ln in linhas}
    assert tipos == {"PROVISÓRIO", "LIMITAÇÃO", "NOTA"}
    provisorios = [ln for ln in linhas if ln["tipo"] == "PROVISÓRIO"]
    # o desconto de frágil injetado aparece com seu valor
    assert any(ln["valor"] == 0.5 for ln in provisorios)
    limitacoes = [ln for ln in linhas if ln["tipo"] == "LIMITAÇÃO"]
    assert len(limitacoes) == len(r.degradacoes)


def test_notas_de_coleta_entram_como_limitacao():
    # A contagem de vendas descartadas (Realty_Id nulo) chega à aba de limitações.
    r = _resultado()
    nota = "2 vendas descartadas (Realty_Id nulo) — perfil sobre 175 ancoráveis de 177"
    linhas = linhas_parametros_e_limitacoes(r, PARAMS, notas_coleta=(nota,))
    itens_limitacao = [ln["item"] for ln in linhas if ln["tipo"] == "LIMITAÇÃO"]
    assert nota in itens_limitacao


def test_penalidade_serializada_bate_com_o_detalhe():
    # c1 tem 7 leads → sem penalidade SEM_LEAD; a coluna reflete o detalhe.
    r = _resultado()
    ln = next(x for x in linhas_destaque(r) if x["imovel_id"] == 11)
    det = r.detalhes[11]
    assert ln[f"pen_{Penalidade.SEM_LEAD_180D.value}"] == det.descontos_por_penalidade.get(
        Penalidade.SEM_LEAD_180D, 0.0
    )
    assert ln["desconto_total"] == det.desconto_total


def test_escrever_planilha_gera_os_quatro_csvs(tmp_path):
    r = _resultado()
    caminhos = escrever_planilha(r, PARAMS, tmp_path / "piloto")
    nomes = sorted(p.name for p in caminhos)
    assert nomes == [
        "destaque.csv",
        "excluidos_por_regra.csv",
        "parametros_e_limitacoes.csv",
        "super_destaque.csv",
    ]
    # o super_destaque.csv tem cabeçalho + a linha do imóvel 10
    with (tmp_path / "piloto" / "super_destaque.csv").open(encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    assert [ln["imovel_id"] for ln in linhas] == ["10"]
