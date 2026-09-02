"""Testes da serialização da planilha-piloto.

As funções de linha são puras (testadas sem arquivo): provam que o CSV
SERIALIZA o ResultadoDecisao campo a campo, sem recomputar. Um teste do writer
usa tmp_path (fora do repo) só para confirmar que os quatro arquivos saem.
"""

import csv
from datetime import date

from dominio.elegibilidade import ImovelCandidato
from dominio.penalidades import (
    ImovelPenalizavel,
    IntensidadesPenalidade,
    Penalidade,
)
from dominio.perfil import Dimensao, PerfilConversao
from dominio.ranking import PesosNivel
from entrega.planilha_piloto import (
    NAO_CONSULTADO,
    NAO_JULGADA,
    SEM_JANELA,
    descrever_ultima_janela,
    escrever_planilha,
    linhas_destaque,
    linhas_excluidos_por_regra,
    linhas_parametros_e_limitacoes,
    linhas_relaxamento,
    linhas_super_destaque,
)
from piloto.decisao import ParametrosDecisao, decidir
from piloto.semelhanca import ParametrosSemelhanca

HOJE = date(2026, 8, 31)
PARAMS = ParametrosDecisao(
    semelhanca=ParametrosSemelhanca(desconto_fragil=0.5, decaimento=1.0),
    intensidades=IntensidadesPenalidade(
        janela_sem_resultado=0.15, sem_avaliacao_por_categoria=0.10, sem_lead_180d=0.10
    ),
    decaimento_janela=lambda _c: 1.0,
    pesos_super=PesosNivel(
        semelhanca_perfil=60, leads_positivo=0, desempenho_proprio=25, produtividade_gestor=15
    ),
    pesos_destaque=PesosNivel(
        semelhanca_perfil=80, leads_positivo=0, desempenho_proprio=10, produtividade_gestor=10
    ),
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
        produtividade_gestor_30d=3,
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
    linhas = linhas_super_destaque(r, None, None)
    assert [ln["imovel_id"] for ln in linhas] == [10]
    ln = linhas[0]
    # a nota do CSV é a mesma do ResultadoDecisao (serializa, não recomputa)
    assert ln["nota"] == r.alocacao.super_destaque[0].nota
    assert ln["semelhanca_perfil"] == r.detalhes[10].fatores.semelhanca_perfil
    assert ln["leads"] == r.detalhes[10].fatores.leads  # F2 na composição (D-017)
    assert ln["perfil_que_puxou"] == "regiao=Centro"
    assert ln["perfil_num_vendas"] == 10
    # paridade de colunas com destaque (Spec §3.2): super tem origem/degrau vazios
    assert ln["origem"] == "ranking"
    assert ln["degrau_cedido"] == ""
    assert set(ln.keys()) == set(linhas_destaque(r, None, None)[0].keys())


def test_destaque_inclui_recuperado_com_degrau():
    r = _resultado()
    linhas = linhas_destaque(r, None, None)
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
    linhas = {ln["imovel_id"]: ln for ln in linhas_destaque(r, None, None)}
    # ranking: nota == pos.nota; recuperado: nota == rec.nota_destaque
    assert linhas[11]["nota"] == r.alocacao.destaque[0].nota
    rec = next(x for x in r.relaxamento.recuperados if x.imovel_id == 12)
    assert linhas[12]["nota"] == rec.nota_destaque


def test_excluidos_lista_so_os_nao_recuperados_com_as_regras():
    r = _resultado()
    linhas = linhas_excluidos_por_regra(r, None, None)
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
    ln = next(x for x in linhas_destaque(r, None, None) if x["imovel_id"] == 11)
    det = r.detalhes[11]
    assert ln[f"pen_{Penalidade.SEM_LEAD_180D.value}"] == det.descontos_por_penalidade.get(
        Penalidade.SEM_LEAD_180D, 0.0
    )
    assert ln["desconto_total"] == det.desconto_total


def test_escrever_planilha_gera_os_cinco_csvs(tmp_path):
    r = _resultado()
    caminhos = escrever_planilha(
        r, PARAMS, tmp_path / "piloto", historico_janelas=None, resultado_esperado=None
    )
    nomes = sorted(p.name for p in caminhos)
    assert nomes == [
        "destaque.csv",
        "excluidos_por_regra.csv",
        "parametros_e_limitacoes.csv",
        "relaxamento.csv",  # Spec §3.1/§6.6: obrigatória
        "super_destaque.csv",
    ]
    # o super_destaque.csv tem cabeçalho + a linha do imóvel 10
    with (tmp_path / "piloto" / "super_destaque.csv").open(encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    assert [ln["imovel_id"] for ln in linhas] == ["10"]


def test_escrever_planilha_inclui_nota_de_coleta_no_csv(tmp_path):
    r = _resultado()
    nota = "2 vendas descartadas (Realty_Id nulo)"
    escrever_planilha(
        r,
        PARAMS,
        tmp_path / "piloto",
        historico_janelas=None,
        resultado_esperado=None,
        notas_coleta=(nota,),
    )
    with (tmp_path / "piloto" / "parametros_e_limitacoes.csv").open(encoding="utf-8") as f:
        itens = [ln["item"] for ln in csv.DictReader(f)]
    assert nota in itens


def test_aba_de_relaxamento_traz_a_regra_e_as_posicoes_dependentes():
    """Spec §6.6, literal: "Cada cedência gera linha no relatório de relaxamento com
    a quantidade de posições que dependeram dela. Sem esse registro a etapa de
    decisão não é considerada pronta". O Registro já guardava o agregado; ele só não
    chegava à planilha, e a rodada saía COMPLETA assim mesmo."""
    r = _resultado()
    linhas = linhas_relaxamento(r, None, None)
    cedencias = [ln for ln in linhas if ln["ordem"] != ""]
    assert [ln["regra_cedida"] for ln in cedencias] == [
        linha.regra.value for linha in r.relaxamento.relatorio
    ]
    assert [ln["posicoes_dependentes"] for ln in cedencias] == [
        linha.posicoes_dependentes for linha in r.relaxamento.relatorio
    ]


def test_deficit_e_declarado_mesmo_sendo_zero():
    """As posições ainda vazias são grandeza da RODADA, não de uma cedência, e a §2.1
    as exige. Sem linha, zero seria indistinguível de "ninguém calculou"."""
    linhas = linhas_relaxamento(_resultado(), None, None)
    ultima = linhas[-1]
    assert "VAZIAS" in str(ultima["regra_cedida"])
    assert ultima["posicoes_dependentes"] == _resultado().relaxamento.deficit_restante


# --- a coluna da última janela (critérios de aceite do PRD :478 e :479) ---------


LIMIAR = {"destaque": 1, "super_destaque": 3}


def test_os_CINCO_estados_da_ultima_janela_saem_distintos():
    """Hoje os cinco saem como `0,0` na coluna de desconto, indistinguíveis — e é
    isso que o PRD cobra. O quinto (histórico não consultado) é o que mais engana:
    não é "sem janela anterior", é ninguém ter perguntado."""
    d = descrever_ultima_janela
    textos = [
        d(None, None),
        d((), None),
        d((("destaque", 3, 2),), None),
        d((("destaque", 0, 2),), LIMIAR),
        d((("super_destaque", 9, 0),), LIMIAR),
    ]
    assert len(set(textos)) == 5, f"estados colidiram: {textos}"


def test_nao_consultado_NAO_vira_sem_janela():
    """A confusão que o critério :479 do PRD proíbe: afirmar ausência de janela
    sobre um imóvel cujo histórico não foi lido."""
    assert descrever_ultima_janela(None, None) == NAO_CONSULTADO
    assert descrever_ultima_janela((), None) == SEM_JANELA


def test_sem_limiar_a_coluna_NAO_julga():
    """Com o nº 14 nulo não há veredito, e a coluna diz isso. "0 leads" sem rótulo
    lê como reprovação — reprovar por conta própria é o que a D-022 proíbe."""
    texto = descrever_ultima_janela(((("destaque", 0, 1),)), None)
    assert NAO_JULGADA in texto
    assert "atingiu" not in texto.lower()


def test_com_limiar_o_veredito_vem_do_DOMINIO():
    """O julgamento sai de `julgar_janelas`, a mesma função da penalidade. Duas
    comparações do mesmo limiar podem divergir, e a divergência apareceria como a
    planilha contradizendo o desconto que ela própria mostra, na mesma linha.

    O caso decisivo é o do MEIO, não os extremos: com 2 leads num nível cujo limiar é
    3, o domínio diz que NÃO atingiu, enquanto qualquer comparação improvisada do
    tipo "tem lead, então passou" diria o contrário. Só ele separa reusar o domínio
    de reescrever a régua — a primeira versão deste teste usava 0 e 5 leads contra
    limiar 1, onde as duas leituras coincidem, e a mutação sobrevivia."""
    assert "NÃO atingiu" in descrever_ultima_janela((("super_destaque", 2, 1),), LIMIAR)
    assert "NÃO atingiu" not in descrever_ultima_janela((("super_destaque", 3, 1),), LIMIAR)
    # e o limiar é POR NÍVEL: os mesmos 2 leads passam no destaque, cujo limiar é 1
    assert "NÃO atingiu" not in descrever_ultima_janela((("destaque", 2, 1),), LIMIAR)


def test_a_coluna_aparece_nas_abas_por_imovel():
    r = _resultado()
    historico = {10: (("super_destaque", 0, 2),)}
    # As DUAS abas que carregam justificativa por imóvel — e a de destaque inclui os
    # recuperados pelo relaxamento. `excluidos_por_regra` e `relaxamento` ficam de
    # fora de propósito: a primeira lista reprovados, que não têm ranking nem
    # detalhe, e a segunda tem uma linha por degrau cedido, não por imóvel.
    for construtor in (linhas_super_destaque, linhas_destaque):
        linhas = construtor(r, historico, LIMIAR)
        if not linhas:
            continue
        assert "ultima_janela" in linhas[0], f"{construtor.__name__} sem a coluna"
    super_ = linhas_super_destaque(r, historico, LIMIAR)
    assert "NÃO atingiu" in super_[0]["ultima_janela"]  # imóvel 10 tem janela ruim


def test_imovel_fora_do_mapa_e_SEM_JANELA_nao_nao_consultado():
    """Mapa presente e imóvel ausente dele = consultado e sem janela. É diferente de
    mapa None, que é não consultado."""
    r = _resultado()
    linhas = linhas_super_destaque(r, {999: (("destaque", 1, 1),)}, LIMIAR)
    assert linhas[0]["ultima_janela"] == SEM_JANELA


def test_sem_mapa_a_planilha_declara_NAO_CONSULTADO_em_todos():
    r = _resultado()
    linhas = linhas_super_destaque(r, None, LIMIAR)
    assert linhas[0]["ultima_janela"] == NAO_CONSULTADO


def test_a_coluna_de_desconto_continua_INTACTA():
    """Contraprova: a coluna nova não substitui `pen_janela_sem_resultado`, que
    responde outra pergunta (quanto foi descontado), e some se alguém a reaproveitar."""
    linhas = linhas_super_destaque(_resultado(), {10: (("destaque", 0, 1),)}, LIMIAR)
    assert "pen_janela_sem_resultado" in linhas[0]
    assert "ultima_janela" in linhas[0]


def test_o_TEXTO_da_coluna_concorda_com_o_veredito_da_penalidade():
    """A metade de apresentação da trava: a equivalência de ELEIÇÃO é do domínio
    (`tests/test_penalidades.py`); aqui se prova que o texto que o dono lê diz o
    mesmo que o desconto cobrado, no caso empatado em que a regra paralela errava."""
    cruas = (("super_destaque", 2, 4), ("destaque", 1, 4))
    assert "NÃO atingiu" in descrever_ultima_janela(cruas, LIMIAR)
    assert "super destaque" in descrever_ultima_janela(cruas, LIMIAR)
