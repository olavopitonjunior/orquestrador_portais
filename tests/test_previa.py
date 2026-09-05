"""A prévia: o funil com os parâmetros da tela, pelas MESMAS regras da rodada.

Sem banco. As coletas são substituídas por fakes em `main`; `montar_previa` é pura.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from config.parametros import ParametrosDaRodada, carregar
from dominio.elegibilidade import ImovelCandidato, Regra
from dominio.penalidades import ImovelPenalizavel
from dominio.perfil import Dimensao, PerfilConversao
from executar import previa as mod
from executar.previa import ORDEM_DO_FUNIL, main, montar_previa
from piloto.decisao import decidir

HOJE = date(2026, 9, 4)


def _candidato(
    imovel_id: int,
    *,
    preco: int = 850_000,
    fotos: int = 20,
    categoria: str = "Apartamento",
    gestor: bool = True,
    logou: bool | None = True,
    corretores: int = 5,
) -> ImovelCandidato:
    return ImovelCandidato(
        imovel_id=imovel_id,
        publicacao_ativa=True,
        categoria=categoria,
        preco=preco,
        qtd_fotos=fotos,
        atualizado_em=date(2026, 9, 1),
        notas_por_categoria={"Descrição do imóvel": 10},
        gestor_captou_ou_vendeu_30d=gestor,
        produtividade_gestor_30d=1 if gestor else 0,
        corretores_ativos_no_distrito=corretores,
        gestor_logou_na_janela=logou,
    )


def _dims(regiao: str = "Centro", faixa: str = "700k–1M") -> dict[Dimensao, str]:
    return {Dimensao.REGIAO: regiao, Dimensao.FAIXA_PRECO: faixa}


PERFIL_CENTRO = PerfilConversao(
    dimensoes=(Dimensao.REGIAO, Dimensao.FAIXA_PRECO),
    valores=("Centro", "700k–1M"),
    num_vendas=10,
)
PERFIL_FRAGIL = PerfilConversao(dimensoes=(Dimensao.REGIAO,), valores=("Sul",), num_vendas=1)


def _params(**decisao) -> ParametrosDaRodada:
    p = carregar(None)  # tudo adotado (D-034): exige faixa de preço no perfil
    return replace(p, decisao=replace(p.decisao, **decisao)) if decisao else p


# --------------------------------------------------------------------- o funil


def test_o_funil_cobre_toda_regra_do_dominio_na_ordem_dos_tres_blocos():
    assert {r for r, _, _ in ORDEM_DO_FUNIL} == set(Regra)
    grupos = [g for _, _, g in ORDEM_DO_FUNIL]
    # os blocos não se intercalam: imóvel, depois perfil, depois corretor
    assert grupos == sorted(
        grupos, key=["quem_entra_imovel", "quem_entra_perfil", "quem_entra_corretor"].index
    )


def test_funil_acumulado_e_a_ultima_linha_e_o_numero_de_elegiveis():
    cands = [
        _candidato(1),
        _candidato(2, fotos=3),  # cai em fotos
        _candidato(3, categoria="Terreno"),  # cai em categoria
        _candidato(4, preco=200_000),  # cai em preço
    ]
    r = montar_previa(
        cands, {c.imovel_id: _dims() for c in cands}, (PERFIL_CENTRO,), _params(), HOJE
    )
    sobram = {ln["regra"]: ln["sobram"] for ln in r["funil"]}
    cortou = {ln["regra"]: ln["cortou"] for ln in r["funil"]}
    assert cortou["categoria"] == 1 and cortou["preco_geral"] == 1 and cortou["fotos"] == 1
    assert sobram["categoria"] == 3 and sobram["preco_geral"] == 2 and sobram["fotos"] == 1
    assert r["funil"][-1]["sobram"] == r["elegiveis"] == 1
    assert r["candidatos"] == 4


def test_o_perfil_corta_quem_nao_se_parece_com_o_que_vendeu():
    cands = [_candidato(1), _candidato(2)]
    dims = {1: _dims("Centro"), 2: _dims("Sul")}
    r = montar_previa(cands, dims, (PERFIL_CENTRO,), _params(), HOJE)
    linha = next(ln for ln in r["funil"] if ln["regra"] == "perfil_de_conversao")
    assert linha["cortou"] == 1 and linha["grupo"] == "quem_entra_perfil"
    assert r["perfil"]["filtro_incide"] is True and r["perfil"]["que_contam"] == 1
    assert r["reprovados_por_regra"] == {"perfil_de_conversao": 1}


def test_sem_perfil_que_conte_o_filtro_nao_incide_e_a_previa_declara():
    cands = [_candidato(1), _candidato(2)]
    dims = {1: _dims("Centro"), 2: _dims("Sul")}
    r = montar_previa(cands, dims, (PERFIL_FRAGIL,), _params(), HOJE)
    linha = next(ln for ln in r["funil"] if ln["regra"] == "perfil_de_conversao")
    assert linha["cortou"] == 0 and r["elegiveis"] == 2
    assert r["perfil"]["filtro_incide"] is False
    assert any("NÃO incidiu" in d for d in r["degradacoes"])


def test_a_exigencia_da_dimensao_vem_dos_parametros():
    # Perfil só de região é robusto, mas não contém a faixa de preço: com a exigência
    # adotada não conta; sem exigência, conta e corta quem é do Sul.
    so_regiao = PerfilConversao(dimensoes=(Dimensao.REGIAO,), valores=("Centro",), num_vendas=5)
    cands = [_candidato(1), _candidato(2)]
    dims = {1: _dims("Centro"), 2: _dims("Sul")}
    com = montar_previa(cands, dims, (so_regiao,), _params(), HOJE)
    sem = montar_previa(cands, dims, (so_regiao,), _params(exigir_dimensao_no_perfil=None), HOJE)
    assert com["perfil"]["que_contam"] == 0 and com["elegiveis"] == 2
    assert sem["perfil"]["que_contam"] == 1 and sem["elegiveis"] == 1
    assert com["perfil"]["exigencia"] == "faixa_preco" and sem["perfil"]["exigencia"] is None


def test_o_minimo_do_distrito_vem_dos_parametros():
    cands = [_candidato(1, corretores=2)]
    dims = {1: _dims()}
    com_2 = montar_previa(cands, dims, (PERFIL_CENTRO,), _params(), HOJE)
    com_3 = montar_previa(
        cands, dims, (PERFIL_CENTRO,), _params(minimo_corretores_distrito=3), HOJE
    )
    assert com_2["elegiveis"] == 1
    assert com_3["elegiveis"] == 0 and com_3["reprovados_por_regra"] == {"capacidade_distrito": 1}


# ------------------------------------------------------ posições e relaxamento


def test_projecao_de_posicoes_e_aritmetica_declarada():
    cands = [
        _candidato(1, preco=900_000),
        _candidato(2, preco=400_000),
        _candidato(3, preco=500_000),
    ]
    r = montar_previa(
        cands, {c.imovel_id: _dims() for c in cands}, (PERFIL_CENTRO,), _params(), HOJE
    )
    assert r["candidatos_super_destaque"] == 1
    assert r["posicoes"] == {"super_destaque": 475, "destaque": 6495, "total": 6970}
    proj = r["projecao"]
    assert proj["super_destaque_preenchido"] == 1 and proj["destaque_preenchido"] == 2
    assert proj["vazias_super_destaque"] == 474 and proj["vazias_destaque"] == 6493
    assert proj["vazias_total"] == 6967


def test_relaxamento_potencial_por_degrau_com_a_trava_do_login():
    cands = [
        _candidato(1),  # elegível
        _candidato(2, fotos=3),  # recuperável no degrau fotos
        _candidato(3, gestor=False, logou=False),  # travado pelo login (D-029)
        _candidato(4, gestor=False, logou=True),  # recuperável no degrau gestor
        _candidato(5, categoria="Terreno"),  # não relaxável: nunca entra
    ]
    r = montar_previa(
        cands, {c.imovel_id: _dims() for c in cands}, (PERFIL_CENTRO,), _params(), HOJE
    )
    rel = r["relaxamento"]
    assert rel["recuperaveis"] == 2 and rel["travados_pelo_login"] == 1
    por = {d["regra"]: d["recuperaveis_ate_aqui"] for d in rel["por_degrau"]}
    assert por["perfil_de_conversao"] == 0 and por["fotos"] == 1
    assert (
        por["atualizacao_90d"] == 1
        and por["gestor_produtivo"] == 2
        and por["capacidade_distrito"] == 2
    )
    # o único elegível (850k) vai ao super; o destaque fica todo vazio e a cedência
    # recuperaria 2
    assert rel["vazias_destaque_depois"] == 6495 - 2


def test_o_perfil_e_o_primeiro_degrau_do_relaxamento_potencial():
    cands = [_candidato(1), _candidato(2)]
    dims = {1: _dims("Centro"), 2: _dims("Sul")}
    r = montar_previa(cands, dims, (PERFIL_CENTRO,), _params(), HOJE)
    por = r["relaxamento"]["por_degrau"]
    assert por[0]["regra"] == "perfil_de_conversao" and por[0]["recuperaveis_ate_aqui"] == 1


# ------------------------------------------------------------- fidelidade


@pytest.mark.parametrize(
    ("hoje", "minimo", "exigir"),
    [
        (HOJE, 2, Dimensao.FAIXA_PRECO),
        (date(2026, 12, 15), 2, Dimensao.FAIXA_PRECO),  # atualização de 1/9 já venceu (90 d)
        (HOJE, 3, Dimensao.FAIXA_PRECO),  # o distrito de 2 corretores reprova
        (HOJE, 2, None),  # perfil só de região passa a contar
    ],
)
def test_a_previa_e_a_rodada_concordam_sobre_quem_e_elegivel(hoje, minimo, exigir):
    """A garantia central: mesma entrada, mesmas contagens que `decidir` produz — por
    regra (multiconjunto), travados pelo login, e o relaxamento degrau a degrau
    contra `relaxar` (o déficit de destaque aqui é a cota inteira, então tudo que é
    recuperável é recuperado)."""
    from collections import Counter

    cands = [
        _candidato(1),
        _candidato(2, fotos=3),
        _candidato(3, gestor=False, logou=False),
        _candidato(4, corretores=2),
        _candidato(5),
        _candidato(6, preco=200_000),
        _candidato(7, fotos=3, gestor=False, logou=True),  # degrau mínimo = gestor
        _candidato(8),
    ]
    cands[7] = replace(cands[7], notas_por_categoria={"Descrição do imóvel": 0})  # cadastro
    so_regiao = PerfilConversao(dimensoes=(Dimensao.REGIAO,), valores=("Norte",), num_vendas=4)
    dims = {i: _dims("Centro") for i in (1, 2, 3, 4, 7, 8)} | {5: _dims("Sul"), 6: _dims("Norte")}
    params = _params(minimo_corretores_distrito=minimo, exigir_dimensao_no_perfil=exigir)
    perfis = (PERFIL_CENTRO, so_regiao)
    r = montar_previa(cands, dims, perfis, params, hoje)
    pen = {
        c.imovel_id: ImovelPenalizavel(
            imovel_id=c.imovel_id,
            janelas_anteriores=(),
            alguma_categoria_avaliada=True,
            leads_180d=1,
        )
        for c in cands
    }
    d = decidir(cands, pen, dims, perfis, params.decisao, hoje)
    assert r["elegiveis"] == d.n_elegiveis
    assert r["reprovados_por_regra"] == dict(
        Counter(x.value for rr in d.reprovados_regras.values() for x in rr)
    )
    assert r["relaxamento"]["travados_pelo_login"] == d.relaxamento.bloqueados_por_login
    assert r["relaxamento"]["recuperaveis"] == len(d.relaxamento.recuperados)
    acumulado = 0
    por_degrau = {x["regra"]: x["recuperaveis_ate_aqui"] for x in r["relaxamento"]["por_degrau"]}
    for linha in d.relaxamento.relatorio:
        acumulado += linha.posicoes_dependentes
        assert por_degrau[linha.regra.value] == acumulado, linha.regra
    # e o cenário exercita mesmo o que promete
    if hoje == HOJE and minimo == 2 and exigir is Dimensao.FAIXA_PRECO:
        assert r["reprovados_por_regra"] == {
            "cadastro_completo": 1,
            "fotos": 2,
            "gestor_produtivo": 2,
            "perfil_de_conversao": 2,  # 5 (Sul) e 6 (Norte: só o perfil de região, que não conta)
            "preco_geral": 1,
        }
    if hoje != HOJE:
        assert r["reprovados_por_regra"].get("atualizacao_90d", 0) == len(cands)
    if minimo == 3:
        assert r["reprovados_por_regra"].get("capacidade_distrito", 0) == 1
    if exigir is None:
        assert (
            r["reprovados_por_regra"]["perfil_de_conversao"] == 1
        )  # só o Sul; Norte casa o perfil de região


def test_o_resultado_e_json_puro_sem_id_de_imovel():
    cands = [_candidato(987_654), _candidato(987_655, fotos=3)]
    r = montar_previa(
        cands, {c.imovel_id: _dims() for c in cands}, (PERFIL_CENTRO,), _params(), HOJE
    )
    texto = json.dumps(r, ensure_ascii=False)
    assert "987654" not in texto and "987655" not in texto
    assert "imovel_id" not in texto
    assert r["parametros"]["procedencia"]["portal.peso_nota"] == "adotado D-034"


# ------------------------------------------------------------------- main


def _fakes(monkeypatch, cands, dims, vendas=()):
    monkeypatch.setattr(mod, "coletar", lambda definicao, *, login_janela_dias: (cands, []))
    monkeypatch.setattr(mod, "coletar_vendas", lambda janela: (list(vendas), 0))
    monkeypatch.setattr(mod, "coletar_dimensoes_candidatos", lambda: dims)


def test_main_escreve_a_previa_com_codigo_zero(tmp_path: Path, monkeypatch):
    cands = [_candidato(1), _candidato(2, fotos=3)]
    _fakes(monkeypatch, cands, {1: _dims(), 2: _dims()})
    saida = tmp_path / "r.json"
    assert main(["--resultado", str(saida), "--hoje", "2026-09-04"]) == 0
    r = json.loads(saida.read_text())
    assert r["codigo"] == 0 and r["falha"] is None
    assert r["previa"]["hoje"] == "2026-09-04" and r["previa"]["candidatos"] == 2
    assert r["previa"]["vendas"] == {"assinadas": 0, "descartadas": 0, "janela_dias": 180}
    assert r["previa"]["perfil"]["filtro_incide"] is False  # sem vendas, sem perfil
    assert "duracao_s" in r["previa"]


def test_main_leva_as_janelas_declaradas_as_coletas(tmp_path: Path, monkeypatch):
    visto = {}

    def coletar(definicao, *, login_janela_dias):
        visto["login"] = login_janela_dias
        return [_candidato(1)], []

    def vendas(janela):
        visto["janela"] = janela
        return [], 0

    monkeypatch.setattr(mod, "coletar", coletar)
    monkeypatch.setattr(mod, "coletar_vendas", vendas)
    monkeypatch.setattr(mod, "coletar_dimensoes_candidatos", lambda: {1: _dims()})
    toml = tmp_path / "p.toml"
    toml.write_text("[conversao]\njanela_dias = 90\n[corretor]\nlogin_janela_dias = 45\n")
    assert main(["--resultado", str(tmp_path / "r.json"), "--parametros", str(toml)]) == 0
    assert visto == {"login": 45, "janela": 90}
    r = json.loads((tmp_path / "r.json").read_text())
    assert r["previa"]["parametros"]["declarados_diferentes_do_adotado"] == [
        "conversao.janela_dias",
        "corretor.login_janela_dias",
    ]


def test_main_recusa_parametro_invalido_com_5_sem_tocar_a_fonte(tmp_path: Path, monkeypatch):
    def nunca(*a, **k):
        raise AssertionError("a fonte não pode ser lida com parâmetro recusado")

    monkeypatch.setattr(mod, "coletar", nunca)
    toml = tmp_path / "p.toml"
    toml.write_text("[portal]\nforma = 'x'\n")
    saida = tmp_path / "r.json"
    assert main(["--resultado", str(saida), "--parametros", str(toml)]) == 5
    assert json.loads(saida.read_text())["falha"] == "ParametroInvalido"


def test_main_falha_de_fonte_sai_3_com_o_tipo_da_excecao(tmp_path: Path, monkeypatch):
    def cai(*a, **k):
        raise ConnectionError("host secreto")

    monkeypatch.setattr(mod, "coletar", cai)
    saida = tmp_path / "r.json"
    assert main(["--resultado", str(saida)]) == 3
    r = json.loads(saida.read_text())
    assert r["codigo"] == 3 and r["falha"] == "ConnectionError"
    assert "secreto" not in saida.read_text()


@pytest.mark.parametrize("regra", list(Regra))
def test_toda_regra_aparece_uma_vez_no_funil(regra):
    assert sum(1 for r, _, _ in ORDEM_DO_FUNIL if r is regra) == 1
