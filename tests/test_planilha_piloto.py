"""Testes da serialização da planilha-piloto.

As funções de linha são puras (testadas sem arquivo): provam que o CSV
SERIALIZA o ResultadoDecisao campo a campo, sem recomputar. Um teste do writer
usa tmp_path (fora do repo) só para confirmar que os seis arquivos saem.

Os parâmetros da rodada são os ADOTADOS (`carregar(None)`, D-034) — a planilha
recebe o `ParametrosDaRodada` inteiro porque rotula a procedência de cada chave.
"""

import csv
from dataclasses import replace
from datetime import date

import pytest

from config.parametros import carregar
from dados.bucketizacao import faixa_de_preco
from dados.coletor_externo import DesempenhoAnuncio
from dominio.elegibilidade import ImovelCandidato, Regra
from dominio.penalidades import ImovelPenalizavel, Penalidade
from dominio.perfil import Dimensao, PerfilConversao
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
from piloto.decisao import decidir

HOJE = date(2026, 8, 31)
PARAMS = carregar(None)  # tudo adotado (D-034); a régua nº 14 nula
DEC = PARAMS.decisao  # exige FAIXA_PRECO no perfil, como em produção

# Perfis robustos CONTENDO a faixa de preço (D-027): um por faixa que o fixture usa.
# Sem a faixa no perfil, todo candidato reprovaria em PERFIL_DE_CONVERSAO.
PERFIS = (
    PerfilConversao(dimensoes=(Dimensao.FAIXA_PRECO,), valores=("300k–500k",), num_vendas=5),
    PerfilConversao(dimensoes=(Dimensao.FAIXA_PRECO,), valores=("700k–1M",), num_vendas=10),
)


def _cand(imovel_id, *, preco=850_000, fotos=20, categoria="Apartamento", gestor=True, logou=None):
    return ImovelCandidato(
        imovel_id=imovel_id,
        publicacao_ativa=True,
        categoria=categoria,
        preco=preco,
        qtd_fotos=fotos,
        atualizado_em=date(2026, 8, 30),
        notas_por_categoria={"Descrição do imóvel": 10},
        gestor_captou_ou_vendeu_30d=gestor,
        produtividade_gestor_30d=3,
        corretores_ativos_no_distrito=5,
        gestor_logou_na_janela=logou,
    )


def _pen(imovel_id):
    return ImovelPenalizavel(
        imovel_id=imovel_id, janelas_anteriores=(), alguma_categoria_avaliada=True, leads_180d=7
    )


def _dims_de(cands):
    """As dimensões do candidato com a faixa de preço do BUCKET real do preço dele —
    a mesma bucketização dos dois lados (vendas e candidatos)."""
    return {
        c.imovel_id: {Dimensao.REGIAO: "Centro", Dimensao.FAIXA_PRECO: faixa_de_preco(c.preco)}
        for c in cands
    }


def _decidir(cands, **kw):
    pen = {c.imovel_id: _pen(c.imovel_id) for c in cands}
    return decidir(cands, pen, _dims_de(cands), PERFIS, DEC, HOJE, **kw)


def _cands_da_apuracao():
    # c0: super destaque (≥700k); c1: destaque (ranking); c2: reprovado por FOTOS
    # (relaxável → recuperado); c3: reprovado por CATEGORIA (não relaxável → excluído).
    return [
        _cand(10),
        _cand(11, preco=400_000),
        _cand(12, preco=400_000, fotos=3),
        _cand(13, preco=400_000, categoria="Casa de Vila"),
    ]


def _resultado():
    return _decidir(_cands_da_apuracao())


def test_o_fixture_casa_o_perfil_pela_faixa_de_preco():
    """Guarda do próprio fixture: se a faixa do candidato não casasse um perfil que
    conta, TODOS reprovariam em PERFIL_DE_CONVERSAO e os testes abaixo passariam
    por motivo errado."""
    r = _resultado()
    assert faixa_de_preco(850_000) == "700k–1M" and faixa_de_preco(400_000) == "300k–500k"
    assert not any(Regra.PERFIL_DE_CONVERSAO in rr for rr in r.reprovados_regras.values())
    assert r.n_elegiveis == 2


def test_super_destaque_serializa_a_nota_e_a_justificativa():
    r = _resultado()
    linhas = linhas_super_destaque(r, None, None)
    assert [ln["imovel_id"] for ln in linhas] == [10]
    ln = linhas[0]
    det = r.detalhes[10]
    # a nota do CSV é a mesma do ResultadoDecisao (serializa, não recomputa)
    assert ln["nota"] == r.alocacao.super_destaque[0].nota
    # os sinais do portal (D-028) e os do banco, lidos do detalhe
    assert ln["nota_portal"] == det.nota_bruta
    assert ln["nota_anuncio"] == det.fatores.nota_anuncio
    assert ln["cliques"] == det.fatores.cliques
    assert ln["visualizacoes"] == det.fatores.visualizacoes
    assert ln["leads"] == det.fatores.leads
    assert ln["produtividade_gestor"] == det.fatores.produtividade_gestor
    # as colunas da geração anterior não existem mais
    assert "semelhanca_perfil" not in ln and "desempenho_proprio" not in ln
    assert ln["perfil_que_puxou"] == "faixa_preco=700k–1M"
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
    assert linhas[11]["nota"] == r.alocacao.destaque[0].nota
    rec = next(x for x in r.relaxamento.recuperados if x.imovel_id == 12)
    assert linhas[12]["nota"] == rec.nota_destaque


def test_excluidos_lista_so_os_nao_recuperados_com_as_regras():
    r = _resultado()
    linhas = linhas_excluidos_por_regra(r, None, None)
    ids = [ln["imovel_id"] for ln in linhas]
    assert ids == [13]  # c2 (fotos) foi recuperado; c3 (categoria) não
    assert "categoria" in linhas[0]["regras_reprovadas"]


# --- a aba de parâmetros: procedência por chave (D-034) ------------------------------


def test_parametros_e_limitacoes_rotula_ADOTADOS_nulo_e_limitacoes():
    r = _resultado()
    linhas = linhas_parametros_e_limitacoes(r, PARAMS)
    tipos = {ln["tipo"] for ln in linhas}
    assert tipos == {"ADOTADO", "NULO", "LIMITAÇÃO", "NOTA"}
    adotados = [ln for ln in linhas if ln["tipo"] == "ADOTADO"]
    # uma linha por chave efetiva, com "caminho (procedência)" e o valor
    assert len(adotados) == len(PARAMS.efetivo) == 14
    por_item = {ln["item"]: ln["valor"] for ln in adotados}
    assert por_item["portal.peso_nota (adotado D-034)"] == 70
    assert por_item["portal.sem_anuncio (adotado D-034)"] == "fim_da_fila"
    assert por_item["desconto.perdao_por_semana (adotado D-034)"] == 50
    # a régua nº 14 nula é DITA, não omitida
    (nulo,) = [ln for ln in linhas if ln["tipo"] == "NULO"]
    assert "resultado_esperado" in nulo["item"] and "nº 14" in nulo["item"]
    limitacoes = [ln for ln in linhas if ln["tipo"] == "LIMITAÇÃO"]
    assert len(limitacoes) == len(r.degradacoes)  # sem bloqueados pelo login


def test_parametro_declarado_diferente_do_adotado_sai_PROVISORIO(tmp_path):
    arquivo = tmp_path / "p.toml"
    arquivo.write_text(
        "[portal]\npeso_nota = 60\npeso_cliques = 40\n[resultado_esperado]\n"
        "super_destaque = 3\ndestaque = 1\n",
        encoding="utf-8",
    )
    linhas = linhas_parametros_e_limitacoes(_resultado(), carregar(arquivo))
    por_item = {ln["item"]: ln for ln in linhas if ln["tipo"] in ("ADOTADO", "PROVISÓRIO")}
    assert por_item["portal.peso_nota (declarado)"]["tipo"] == "PROVISÓRIO"
    assert por_item["portal.peso_nota (declarado)"]["valor"] == 60
    assert por_item["portal.peso_cliques (declarado)"]["tipo"] == "PROVISÓRIO"
    assert por_item["portal.peso_visualizacoes (adotado D-034)"]["tipo"] == "ADOTADO"
    # a régua declarada sai PROVISÓRIA por nível, e a linha NULO some
    assert por_item["resultado_esperado.super_destaque (declarado)"]["valor"] == 3
    assert por_item["resultado_esperado.destaque (declarado)"]["valor"] == 1
    assert not any(ln["tipo"] == "NULO" for ln in linhas)


def test_bloqueados_pela_trava_do_login_viram_LIMITACAO_na_aba():
    """D-029: reprovado em gestor produtivo cujo gestor não logou não é recuperado; a
    planilha declara quantos ficaram fora por isso."""
    cands = [_cand(10), _cand(20, preco=400_000, gestor=False, logou=False)]
    r = _decidir(cands)
    assert r.relaxamento.bloqueados_por_login == 1
    linhas = linhas_parametros_e_limitacoes(r, PARAMS)
    (trava,) = [ln for ln in linhas if "trava do login" in str(ln["item"])]
    assert trava["tipo"] == "LIMITAÇÃO" and trava["item"].startswith("1 imóvel(is)")
    # sem bloqueados, a linha não existe (não é "0 imóveis")
    assert not any(
        "trava do login" in str(ln["item"])
        for ln in linhas_parametros_e_limitacoes(_resultado(), PARAMS)
    )


def test_notas_de_coleta_entram_como_limitacao():
    r = _resultado()
    nota = "2 vendas descartadas (Realty_Id nulo) — perfil sobre 175 ancoráveis de 177"
    linhas = linhas_parametros_e_limitacoes(r, PARAMS, notas_coleta=(nota,))
    itens_limitacao = [ln["item"] for ln in linhas if ln["tipo"] == "LIMITAÇÃO"]
    assert nota in itens_limitacao


def test_penalidade_serializada_bate_com_o_detalhe():
    r = _resultado()
    ln = next(x for x in linhas_destaque(r, None, None) if x["imovel_id"] == 11)
    det = r.detalhes[11]
    assert ln[f"pen_{Penalidade.SEM_LEAD_180D.value}"] == det.descontos_por_penalidade.get(
        Penalidade.SEM_LEAD_180D, 0.0
    )
    assert ln["desconto_total"] == det.desconto_total


def test_escrever_planilha_gera_os_seis_csvs(tmp_path):
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
    with (tmp_path / "piloto" / "super_destaque.csv").open(encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    assert [ln["imovel_id"] for ln in linhas] == ["10"]
    assert "nota_portal" in linhas[0] and "semelhanca_perfil" not in linhas[0]
    with (tmp_path / "piloto" / "parametros_e_limitacoes.csv").open(encoding="utf-8") as f:
        tipos = {ln["tipo"] for ln in csv.DictReader(f)}
    assert "ADOTADO" in tipos and "NULO" in tipos


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
    """Spec §6.6, literal: cada cedência gera linha com a quantidade de posições que
    dependeram dela. Com a D-027 o primeiro degrau é o perfil de conversão."""
    r = _resultado()
    linhas = linhas_relaxamento(r, None, None)
    cedencias = [ln for ln in linhas if ln["ordem"] != ""]
    assert [ln["regra_cedida"] for ln in cedencias] == [
        linha.regra.value for linha in r.relaxamento.relatorio
    ]
    assert cedencias[0]["regra_cedida"] == "perfil_de_conversao"
    assert [ln["posicoes_dependentes"] for ln in cedencias] == [
        linha.posicoes_dependentes for linha in r.relaxamento.relatorio
    ]


def test_deficit_e_declarado_mesmo_sendo_zero():
    linhas = linhas_relaxamento(_resultado(), None, None)
    ultima = linhas[-1]
    assert "VAZIAS" in str(ultima["regra_cedida"])
    assert ultima["posicoes_dependentes"] == _resultado().relaxamento.deficit_restante


# --- a coluna da última janela (critérios de aceite do PRD :478 e :479) ---------


LIMIAR = {"destaque": 1, "super_destaque": 3}


def test_os_CINCO_estados_da_ultima_janela_saem_distintos():
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
    assert descrever_ultima_janela(None, None) == NAO_CONSULTADO
    assert descrever_ultima_janela((), None) == SEM_JANELA


def test_sem_limiar_a_coluna_NAO_julga():
    texto = descrever_ultima_janela(((("destaque", 0, 1),)), None)
    assert NAO_JULGADA in texto
    assert "atingiu" not in texto.lower()


def test_com_limiar_o_veredito_vem_do_DOMINIO():
    assert "NÃO atingiu" in descrever_ultima_janela((("super_destaque", 2, 1),), LIMIAR)
    assert "NÃO atingiu" not in descrever_ultima_janela((("super_destaque", 3, 1),), LIMIAR)
    assert "NÃO atingiu" not in descrever_ultima_janela((("destaque", 2, 1),), LIMIAR)


def test_a_coluna_aparece_nas_abas_por_imovel():
    r = _resultado()
    historico = {10: (("super_destaque", 0, 2),)}
    for construtor in (linhas_super_destaque, linhas_destaque):
        linhas = construtor(r, historico, LIMIAR)
        if not linhas:
            continue
        assert "ultima_janela" in linhas[0], f"{construtor.__name__} sem a coluna"
    super_ = linhas_super_destaque(r, historico, LIMIAR)
    assert "NÃO atingiu" in super_[0]["ultima_janela"]


def test_imovel_fora_do_mapa_e_SEM_JANELA_nao_nao_consultado():
    r = _resultado()
    linhas = linhas_super_destaque(r, {999: (("destaque", 1, 1),)}, LIMIAR)
    assert linhas[0]["ultima_janela"] == SEM_JANELA


def test_sem_mapa_a_planilha_declara_NAO_CONSULTADO_em_todos():
    r = _resultado()
    linhas = linhas_super_destaque(r, None, LIMIAR)
    assert linhas[0]["ultima_janela"] == NAO_CONSULTADO


def test_a_coluna_de_desconto_continua_INTACTA():
    linhas = linhas_super_destaque(_resultado(), {10: (("destaque", 0, 1),)}, LIMIAR)
    assert "pen_janela_sem_resultado" in linhas[0]
    assert "ultima_janela" in linhas[0]


def test_o_TEXTO_da_coluna_concorda_com_o_veredito_da_penalidade():
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
                **_dims_de([c])[c.imovel_id],
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


def test_apuracao_tem_uma_linha_por_candidato_sem_sobreposicao():
    cands = _cands_da_apuracao()
    r = _resultado()
    linhas = linhas_apuracao(r, {}, None, _contexto(cands))
    assert [ln["imovel_id"] for ln in linhas] == [10, 11, 12, 13]
    por_id = {ln["imovel_id"]: ln for ln in linhas}
    assert por_id[10]["desfecho"] == "super_destaque" and por_id[10]["posicao"] == 1
    assert por_id[11]["desfecho"] == "destaque" and por_id[11]["entrou_por"] == "ranking"
    assert por_id[12]["desfecho"] == "destaque" and por_id[12]["entrou_por"] == "relaxamento"
    assert por_id[12]["regra_cedida"] == "fotos" and por_id[12]["regras_reprovadas"] == "fotos"
    assert por_id[13]["desfecho"] == "reprovado" and por_id[13]["regras_reprovadas"] == "categoria"
    assert por_id[12]["qtd_fotos"] == 3 and por_id[10]["qtd_fotos"] == 20
    assert por_id[10]["faixa_metragem"] == "60 - 80m2" and por_id[10]["vagas"] == "1"
    assert por_id[10]["perfil_fragil"] is False
    assert por_id[12]["posicao"] == len(r.alocacao.destaque) + 1


def test_apuracao_diz_entre_quem_cada_nota_foi_normalizada():
    cands = _cands_da_apuracao()
    linhas = {
        ln["imovel_id"]: ln for ln in linhas_apuracao(_resultado(), {}, None, _contexto(cands))
    }
    assert linhas[10]["notas_entre"] == "elegíveis" and linhas[11]["notas_entre"] == "elegíveis"
    assert linhas[12]["notas_entre"] == "reprovados"
    fora = linhas[13]
    assert fora["desfecho"] == "reprovado" and fora["notas_entre"] == "reprovados"
    assert fora["nota_final"] == "" and fora["posicao"] == ""
    assert fora["preco"] == 400_000 and fora["categoria"] == "Casa de Vila"
    assert fora["distrito"] == "Centro" and fora["dormitorios"] == "3"
    assert fora["leads_180d"] == 7 and fora["gestor_produtivo"] == "sim"


def test_apuracao_traz_os_sinais_do_portal_e_do_banco_do_detalhe():
    """As colunas de nota da apuração são as do DetalheImovel — os três sinais do
    portal (D-028), a nota bruta do portal e os dois do banco — nunca recomputadas."""
    cands = _cands_da_apuracao()
    r = _resultado()
    linhas = {ln["imovel_id"]: ln for ln in linhas_apuracao(r, {}, None, _contexto(cands))}
    for iid in (10, 11, 12):
        det = r.detalhes[iid]
        assert linhas[iid]["nota_portal"] == det.nota_bruta
        assert linhas[iid]["nota_anuncio"] == det.fatores.nota_anuncio
        assert linhas[iid]["cliques"] == det.fatores.cliques
        assert linhas[iid]["visualizacoes"] == det.fatores.visualizacoes
        assert linhas[iid]["leads"] == det.fatores.leads
        assert linhas[iid]["produtividade_gestor"] == det.fatores.produtividade_gestor
    assert "semelhanca_perfil" not in linhas[10] and "desempenho_proprio" not in linhas[10]


def test_apuracao_quem_nao_foi_pontuado_tem_nota_VAZIA_nunca_zero():
    cands = [*_cands_da_apuracao(), _cand(14, preco=400_000)]  # 14 não passou pela decisão
    linhas = {
        ln["imovel_id"]: ln for ln in linhas_apuracao(_resultado(), {}, None, _contexto(cands))
    }
    sem = linhas[14]
    assert sem["desfecho"] == "nao_avaliado" and sem["notas_entre"] == ""
    for col in (
        "nota_final",
        "nota_portal",
        "nota_anuncio",
        "cliques",
        "visualizacoes",
        "leads",
        "produtividade_gestor",
        "desconto_total",
        "pen_janela_sem_resultado",
        "perfil_que_puxou",
        "perfil_num_vendas",
        "casa_perfil",  # não avaliado: nem "sim" nem "não"
    ):
        assert sem[col] == "", col
    assert sem["preco"] == 400_000 and sem["distrito"] == "Centro"


def test_apuracao_casa_perfil_e_login_do_gestor_saem_como_sim_nao_ou_vazio():
    """`gestor_logou_na_janela` é lido do CANDIDATO do contexto (sim/não/vazio).
    `casa_perfil` NÃO: o veredito autoritativo é o dos fatores da decisão (`decidir`
    calcula por `replace` sobre cópias e o candidato do contexto fica com None), e
    None nos fatores = não avaliado = vazio."""
    cands = _cands_da_apuracao()
    cands[0] = replace(cands[0], casa_perfil_de_conversao=True, gestor_logou_na_janela=True)
    cands[1] = replace(cands[1], casa_perfil_de_conversao=False, gestor_logou_na_janela=False)
    r = _resultado()
    linhas = {ln["imovel_id"]: ln for ln in linhas_apuracao(r, {}, None, _contexto(cands))}
    assert linhas[10]["gestor_logou_na_janela"] == "sim"
    assert linhas[11]["gestor_logou_na_janela"] == "não"
    assert linhas[12]["gestor_logou_na_janela"] == ""
    esperado = {True: "sim", False: "não", None: ""}
    for iid in (10, 11, 12):
        assert linhas[iid]["casa_perfil"] == esperado[r.detalhes[iid].fatores.casa_perfil], iid
    # o candidato do contexto NÃO manda: 11 diz False e o veredito da decisão prevalece
    assert linhas[11]["casa_perfil"] == esperado[r.detalhes[11].fatores.casa_perfil]


def test_apuracao_casa_perfil_reflete_o_veredito_da_costura_para_quem_foi_pontuado():
    cands = _cands_da_apuracao()  # como o runner os passa: sem veredito pré-carregado
    r = _resultado()
    linhas = {ln["imovel_id"]: ln for ln in linhas_apuracao(r, {}, None, _contexto(cands))}
    assert r.detalhes[10].fatores.casa_perfil is True
    assert linhas[10]["casa_perfil"] == "sim"


def test_apuracao_notas_batem_com_as_abas_por_nivel():
    cands = _cands_da_apuracao()
    r = _resultado()
    apur = {ln["imovel_id"]: ln for ln in linhas_apuracao(r, {}, None, _contexto(cands))}
    for ln in linhas_super_destaque(r, {}, None) + linhas_destaque(r, {}, None):
        assert apur[ln["imovel_id"]]["nota_final"] == ln["nota"]
        assert apur[ln["imovel_id"]]["posicao"] == ln["posicao"]
        assert apur[ln["imovel_id"]]["desconto_total"] == ln["desconto_total"]
        assert apur[ln["imovel_id"]]["nota_portal"] == ln["nota_portal"]


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
    assert por_id[10]["portal_pesou"] == "não"
    assert por_id[11]["tem_anuncio"] == "não" and por_id[11]["portal_nota_anuncio"] == ""


def test_apuracao_com_portal_que_ENTROU_a_nota_portal_e_a_nota_do_anuncio():
    cands = _cands_da_apuracao()
    an = {
        10: DesempenhoAnuncio(10, "a", 9000.0, 0, {}, None),
        11: DesempenhoAnuncio(11, "b", 6000.0, 0, {}, None),
    }
    r = _decidir(cands, anuncios=an, portal_entrou=True)
    linhas = {
        ln["imovel_id"]: ln
        for ln in linhas_apuracao(r, {}, None, _contexto(cands, anuncios=an, externo_entrou=True))
    }
    assert linhas[10]["portal_pesou"] == "sim"
    assert linhas[10]["nota_anuncio"] == 1.0 and linhas[11]["nota_anuncio"] == 0.0
    assert linhas[10]["nota_portal"] == 70.0 and linhas[11]["nota_portal"] == 0.0


def test_apuracao_codigo_do_portal_vem_do_candidato():
    cands = _cands_da_apuracao()
    cands[0] = replace(cands[0], codigo_portal="10A")
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
    assert {"nota_portal", "nota_anuncio", "cliques", "visualizacoes", "casa_perfil"} <= set(
        cabecalho
    )
    assert "gestor_logou_na_janela" in cabecalho
    assert len(texto.splitlines()) == 1 + 4  # cabeçalho + os quatro candidatos


def test_apuracao_elegivel_que_nao_coube_na_cota_e_dito_como_tal():
    from dominio.alocacao import Alocacao
    from dominio.relaxamento import ResultadoRelaxamento

    r = _resultado()
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
    velho = replace(_cand(15, preco=400_000, fotos=3), atualizado_em=date(2025, 1, 1))
    cands = [*_cands_da_apuracao(), velho]
    r = _decidir(cands)
    linhas = {ln["imovel_id"]: ln for ln in linhas_apuracao(r, {}, None, _contexto(cands))}
    assert linhas[15]["regras_reprovadas"] == "atualizacao_90d; fotos"


def test_apuracao_reprovado_no_perfil_carrega_a_regra_e_o_veredito_no_detalhe():
    fora = _cand(16, preco=2_000_000)  # faixa "1,5M–3M": nenhum perfil que conta
    cands = [*_cands_da_apuracao(), fora]
    r = _decidir(cands)
    assert r.reprovados_regras[16] == frozenset({Regra.PERFIL_DE_CONVERSAO})
    linhas = {ln["imovel_id"]: ln for ln in linhas_apuracao(r, {}, None, _contexto(cands))}
    # o perfil é o PRIMEIRO degrau (D-027): com déficit, o 16 é recuperado por ele
    assert linhas[16]["entrou_por"] == "relaxamento"
    assert linhas[16]["regra_cedida"] == "perfil_de_conversao"
    assert linhas[16]["regras_reprovadas"] == "perfil_de_conversao"
    assert linhas[16]["perfil_que_puxou"] == "" and r.detalhes[16].fatores.casa_perfil is False


def test_apuracao_ultima_janela_distingue_nao_consultado_de_sem_janela():
    cands = _cands_da_apuracao()
    r = _resultado()
    nao_consultado = linhas_apuracao(r, None, None, _contexto(cands))
    assert all(ln["ultima_janela"] == NAO_CONSULTADO for ln in nao_consultado)
    consultado = linhas_apuracao(r, {}, None, _contexto(cands))
    assert all(ln["ultima_janela"] == SEM_JANELA for ln in consultado)


def test_apuracao_ultima_janela_julga_com_o_limiar_como_as_abas():
    cands = _cands_da_apuracao()
    r = _resultado()
    historico = {10: (("super_destaque", 1, 1),)}
    limiar = {"super_destaque": 2, "destaque": 1}
    apur = {ln["imovel_id"]: ln for ln in linhas_apuracao(r, historico, limiar, _contexto(cands))}
    aba = {ln["imovel_id"]: ln for ln in linhas_super_destaque(r, historico, limiar)}
    assert apur[10]["ultima_janela"] == aba[10]["ultima_janela"]
    assert "NÃO atingiu" in apur[10]["ultima_janela"]
