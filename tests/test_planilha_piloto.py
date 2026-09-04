"""Testes da serialização da planilha-piloto.

As funções de linha são puras (testadas sem arquivo): provam que o CSV
SERIALIZA o ResultadoDecisao campo a campo, sem recomputar. Um teste do writer
usa tmp_path (fora do repo) só para confirmar que os quatro arquivos saem.
"""

import csv
from datetime import date

import pytest

from dados.coletor_externo import DesempenhoAnuncio
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
    ContextoApuracao,
    descrever_ultima_janela,
    escrever_planilha,
    linhas_apuracao,
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
        r,
        PARAMS,
        tmp_path / "piloto",
        historico_janelas=None,
        resultado_esperado=None,
        contexto=_contexto(_cands_da_apuracao()),
    )
    nomes = sorted(p.name for p in caminhos)
    assert nomes == [
        "apuracao.csv",
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
        contexto=_contexto(_cands_da_apuracao()),
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


# --- apuracao.csv: o resultado total, uma linha por candidato --------------------


def _contexto(resultado_cands, *, anuncios=None, externo_entrou=False):
    # Candidatos EMBARALHADOS de propósito: a ordenação por imovel_id da apuração tem de
    # fazer trabalho, senão remover o `sorted` passa em silêncio.
    return ContextoApuracao(
        candidatos=list(reversed(resultado_cands)),
        dims={
            c.imovel_id: {
                Dimensao.REGIAO: "Centro",
                Dimensao.DORMITORIOS: "3",
                Dimensao.FAIXA_METRAGEM: "60 - 80m2",
                Dimensao.VAGAS: "1",
            }
            for c in resultado_cands
        },
        penalizaveis={c.imovel_id: _pen(c.imovel_id) for c in resultado_cands},
        anuncios=anuncios or {},
        externo_entrou=externo_entrou,
    )


def _cands_da_apuracao():
    return [
        _cand(10),
        _cand(11, preco=400_000),
        _cand(12, preco=400_000, fotos=3),
        _cand(13, preco=400_000, categoria="Casa de Vila"),
    ]


def test_apuracao_tem_uma_linha_por_candidato_sem_sobreposicao():
    cands = _cands_da_apuracao()
    r = _resultado()
    linhas = linhas_apuracao(r, {}, None, _contexto(cands))
    assert [ln["imovel_id"] for ln in linhas] == [10, 11, 12, 13]  # todos, ordenados
    por_id = {ln["imovel_id"]: ln for ln in linhas}
    assert por_id[10]["desfecho"] == "super_destaque" and por_id[10]["posicao"] == 1
    assert por_id[11]["desfecho"] == "destaque" and por_id[11]["entrou_por"] == "ranking"
    assert por_id[12]["desfecho"] == "destaque" and por_id[12]["entrou_por"] == "relaxamento"
    assert por_id[12]["regra_cedida"] == "fotos" and por_id[12]["regras_reprovadas"] == "fotos"
    assert por_id[13]["desfecho"] == "reprovado" and por_id[13]["regras_reprovadas"] == "categoria"
    # as características que quem aplica a carga confere, fio a fio
    assert por_id[12]["qtd_fotos"] == 3 and por_id[10]["qtd_fotos"] == 20
    assert por_id[10]["faixa_metragem"] == "60 - 80m2" and por_id[10]["vagas"] == "1"
    assert por_id[10]["perfil_fragil"] is False
    # a numeração do destaque continua a da aba de destaque
    assert por_id[12]["posicao"] == len(r.alocacao.destaque) + 1


def test_apuracao_diz_entre_quem_cada_nota_foi_normalizada():
    """D-016: elegíveis e reprovados são normalizados em populações diferentes; a
    apuração não pode pôr os dois na mesma coluna sem dizer qual é qual."""
    cands = _cands_da_apuracao()
    linhas = {
        ln["imovel_id"]: ln for ln in linhas_apuracao(_resultado(), {}, None, _contexto(cands))
    }
    assert linhas[10]["notas_entre"] == "elegíveis" and linhas[11]["notas_entre"] == "elegíveis"
    # reprovados: pontuados entre si para ordenar o relaxamento — o recuperado e o que
    # ficou fora por regra que nunca relaxa
    assert linhas[12]["notas_entre"] == "reprovados"
    fora = linhas[13]
    assert fora["desfecho"] == "reprovado" and fora["notas_entre"] == "reprovados"
    assert fora["nota_final"] == "" and fora["posicao"] == ""  # nunca teve posição
    # mas as características do imóvel estão lá — é o que quem aplica a carga confere
    assert fora["preco"] == 400_000 and fora["categoria"] == "Casa de Vila"
    assert fora["distrito"] == "Centro" and fora["dormitorios"] == "3"
    assert fora["leads_180d"] == 7 and fora["gestor_produtivo"] == "sim"


def test_apuracao_quem_nao_foi_pontuado_tem_nota_VAZIA_nunca_zero():
    """Candidato que a decisão não pontuou (nem no ranking nem no relaxamento) sai com
    as colunas de nota vazias — zero seria uma afirmação sobre um número que não existe."""
    cands = [*_cands_da_apuracao(), _cand(14, preco=400_000)]  # 14 não passou pela decisão
    linhas = {
        ln["imovel_id"]: ln for ln in linhas_apuracao(_resultado(), {}, None, _contexto(cands))
    }
    sem = linhas[14]
    assert sem["desfecho"] == "nao_avaliado" and sem["notas_entre"] == ""
    for col in (
        "nota_final",
        "semelhanca_perfil",
        "leads",
        "desempenho_proprio",
        "produtividade_gestor",
        "desconto_total",
        "pen_janela_sem_resultado",
        "perfil_que_puxou",
        "perfil_num_vendas",
    ):
        assert sem[col] == "", col
    assert sem["preco"] == 400_000 and sem["distrito"] == "Centro"


def test_apuracao_notas_batem_com_as_abas_por_nivel():
    """Serializa, não recomputa: a nota da apuração é a MESMA das abas de nível."""
    cands = _cands_da_apuracao()
    r = _resultado()
    apur = {ln["imovel_id"]: ln for ln in linhas_apuracao(r, {}, None, _contexto(cands))}
    for ln in linhas_super_destaque(r, {}, None) + linhas_destaque(r, {}, None):
        assert apur[ln["imovel_id"]]["nota_final"] == ln["nota"]
        assert apur[ln["imovel_id"]]["posicao"] == ln["posicao"]
        assert apur[ln["imovel_id"]]["desconto_total"] == ln["desconto_total"]


def test_apuracao_traz_o_portal_cru_e_diz_se_pesou():
    cands = _cands_da_apuracao()
    an = {
        10: DesempenhoAnuncio(
            imovel_id=10,
            id_portal="x",
            nota=9580.0,
            visualizacoes=0,
            cliques={"cliqueContato": 2, "cliqueTelefone": 0},
            url=None,
        )
    }
    linhas = linhas_apuracao(
        _resultado(), {}, None, _contexto(cands, anuncios=an, externo_entrou=False)
    )
    por_id = {ln["imovel_id"]: ln for ln in linhas}
    assert por_id[10]["tem_anuncio"] == "sim" and por_id[10]["portal_nota_anuncio"] == 9580.0
    assert por_id[10]["portal_cliques"] == "cliqueContato=2"  # só os não-zero, nunca somados
    assert por_id[10]["portal_pesou"] == "não"  # tinha anúncio, mas o portal não entrou
    assert por_id[11]["tem_anuncio"] == "não" and por_id[11]["portal_nota_anuncio"] == ""


def test_apuracao_codigo_do_portal_vem_do_candidato():
    cands = _cands_da_apuracao()
    cands[0] = ImovelCandidato(**{**cands[0].__dict__, "codigo_portal": "10A"})
    linhas = linhas_apuracao(_resultado(), {}, None, _contexto(cands))
    assert linhas[0]["codigo_portal"] == "10A" and linhas[1]["codigo_portal"] == ""


def test_escrever_planilha_exige_o_contexto_e_escreve_o_sexto_arquivo(tmp_path):
    r = _resultado()
    with pytest.raises(TypeError):  # sem contexto não há apuração — e não há planilha
        escrever_planilha(
            r, PARAMS, tmp_path / "sem", historico_janelas={}, resultado_esperado=None
        )
    com = escrever_planilha(
        r,
        PARAMS,
        tmp_path / "com",
        historico_janelas={},
        resultado_esperado=None,
        contexto=_contexto(_cands_da_apuracao()),
    )
    assert [p.name for p in com][-1] == "apuracao.csv"
    texto = (tmp_path / "com" / "apuracao.csv").read_text(encoding="utf-8")
    cabecalho = texto.splitlines()[0].split(",")
    assert cabecalho[:3] == ["imovel_id", "codigo_portal", "desfecho"]
    assert len(texto.splitlines()) == 1 + 4  # cabeçalho + os quatro candidatos


def test_apuracao_elegivel_que_nao_coube_na_cota_e_dito_como_tal():
    """A ressalva da revisão: um elegível pontuado sem posição não é "fora" nem
    "reprovado" — é `nao_coube`, e leva a nota de destaque com que disputou."""
    from dataclasses import replace

    from dominio.alocacao import Alocacao
    from dominio.relaxamento import ResultadoRelaxamento

    r = _resultado()
    # Tira o imóvel 11 da alocação de destaque, como se a cota tivesse acabado antes dele.
    aloc = Alocacao(
        super_destaque=r.alocacao.super_destaque,
        destaque=tuple(p for p in r.alocacao.destaque if p.imovel_id != 11),
    )
    apertado = replace(r, alocacao=aloc, relaxamento=ResultadoRelaxamento((), (), 0))
    linhas = {
        ln["imovel_id"]: ln
        for ln in linhas_apuracao(apertado, {}, None, _contexto(_cands_da_apuracao()))
    }
    assert linhas[11]["desfecho"] == "nao_coube" and linhas[11]["regras_reprovadas"] == ""
    assert linhas[11]["posicao"] == "" and linhas[11]["notas_entre"] == "elegíveis"
    assert linhas[11]["nota_final"] == r.detalhes[11].nota_destaque


def test_apuracao_recusa_imovel_em_dois_desfechos():
    """Guarda da auditoria de invariantes: se a disjunção alocado↔recuperado quebrar a
    montante, a apuração falha alto em vez de rotular um super destaque como
    relaxamento (o estado que o invariante 7 proíbe)."""
    from dataclasses import replace

    from dominio.elegibilidade import Regra
    from dominio.relaxamento import ImovelRecuperado, ResultadoRelaxamento

    r = _resultado()
    super_id = r.alocacao.super_destaque[0].imovel_id
    furado = replace(
        r,
        relaxamento=ResultadoRelaxamento(
            (ImovelRecuperado(imovel_id=super_id, nota_destaque=1.0, degrau=Regra.FOTOS),), (), 0
        ),
    )
    with pytest.raises(ValueError, match="mais de um desfecho"):
        linhas_apuracao(furado, {}, None, _contexto(_cands_da_apuracao()))


def test_apuracao_regras_reprovadas_saem_ordenadas_mesmo_com_duas():
    """`frozenset[Regra]` itera em ordem que varia entre processos; sem o `sorted` a
    mesma entrada daria bytes diferentes em duas rodadas (invariante 5)."""
    velho = ImovelCandidato(
        **{**_cand(15, preco=400_000, fotos=3).__dict__, "atualizado_em": date(2025, 1, 1)}
    )
    cands = [*_cands_da_apuracao(), velho]
    pen = {c.imovel_id: _pen(c.imovel_id) for c in cands}
    dims = {c.imovel_id: {Dimensao.REGIAO: "Centro"} for c in cands}
    r = decidir(cands, pen, dims, PERFIS, PARAMS, HOJE)
    linhas = {ln["imovel_id"]: ln for ln in linhas_apuracao(r, {}, None, _contexto(cands))}
    assert linhas[15]["regras_reprovadas"] == "atualizacao_90d; fotos"


def test_apuracao_ultima_janela_distingue_nao_consultado_de_sem_janela():
    cands = _cands_da_apuracao()
    r = _resultado()
    nao_consultado = linhas_apuracao(r, None, None, _contexto(cands))
    assert all(ln["ultima_janela"] == NAO_CONSULTADO for ln in nao_consultado)
    consultado = linhas_apuracao(r, {}, None, _contexto(cands))
    assert all(ln["ultima_janela"] == SEM_JANELA for ln in consultado)


def test_apuracao_ultima_janela_julga_com_o_limiar_como_as_abas():
    """A coluna sai do MESMO domínio que as abas por nível: com histórico e limiar, o
    veredito da apuração é o das abas, palavra por palavra."""
    cands = _cands_da_apuracao()
    r = _resultado()
    historico = {10: (("super_destaque", 1, 1),)}  # JanelaCrua = (nível, leads, ciclos)
    limiar = {"super_destaque": 2, "destaque": 1}
    apur = {ln["imovel_id"]: ln for ln in linhas_apuracao(r, historico, limiar, _contexto(cands))}
    aba = {ln["imovel_id"]: ln for ln in linhas_super_destaque(r, historico, limiar)}
    assert apur[10]["ultima_janela"] == aba[10]["ultima_janela"]
    assert "NÃO atingiu" in apur[10]["ultima_janela"]
