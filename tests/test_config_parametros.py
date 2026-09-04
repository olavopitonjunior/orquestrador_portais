"""Testes do carregador dos parâmetros da rodada (modelo D-034: adotados + declarados).

O teste central inverteu de sinal em 04/09/2026. Antes, remover uma chave DERRUBAVA
a rodada ("nenhum default"); agora toda chave tem um valor ADOTADO com decisão
registrada, e o que se exige é outra coisa: a chave ausente cai EXATAMENTE no
adotado e sai ROTULADA como tal. O dia em que um `bruto.get(chave, 0.5)` de
conveniência nascer, `test_chave_ausente_cai_no_adotado` acusa o valor; o dia em que
a procedência deixar de ser anotada, `test_declarar_diferente_rotula_declarado`
acusa o rótulo — porque um número sem procedência numa planilha aprovada é
indistinguível de um número adotado.
"""

from __future__ import annotations

import copy
import math
from pathlib import Path
from typing import Any

import pytest

from config.adotados import ADOTADOS, DECISAO_DOS_ADOTADOS
from config.parametros import (
    DIMENSAO_EXIGIDA_NO_PERFIL,
    SECOES,
    ParametroAusente,
    ParametroInvalido,
    ParametrosColeta,
    carregar,
    montar,
)
from dados.coletor_externo import ParametrosExterno
from dominio.penalidades import IntensidadesPenalidade
from dominio.perfil import Dimensao
from dominio.ranking import PesosPortal
from piloto.decisao import FORMAS_DE_ORDEM_SEM_PORTAL, FORMAS_SEM_ANUNCIO

EXEMPLO = Path(__file__).resolve().parent.parent / "docs" / "parametros-da-rodada.exemplo.toml"
ADOTADO = f"adotado {DECISAO_DOS_ADOTADOS}"

# Toda chave das seções, no formato do arquivo, com os valores ADOTADOS. É o ponto de
# partida de cada variação: um arquivo que declara exatamente o adotado.
IGUAL_AO_ADOTADO: dict[str, dict[str, Any]] = {
    secao: {chave: ADOTADOS[f"{secao}.{chave}"] for chave in chaves}
    for secao, chaves in SECOES.items()
}

# Um arquivo que declara valores DIFERENTES dos adotados em todas as chaves (os pesos
# continuam somando 100). Serve às provas de "declarado" e de verbatim.
DIFERENTE: dict[str, dict[str, Any]] = {
    "conversao": {"janela_dias": 90},
    "corretor": {"login_janela_dias": 15, "minimo_no_distrito": 3},
    "portal": {
        "peso_nota": 50,
        "peso_cliques": 40,
        "peso_visualizacoes": 10,
        "cobertura_minima": 60,
        "idade_maxima_dias": 1,
        "sem_anuncio": "mediana",
        "ordem_quando_nao_entra": "produtividade_gestor",
    },
    "desconto": {
        "janela_sem_resultado": 25,
        "sem_avaliacao": 2.5,
        "sem_lead_180d": 15,
        "perdao_por_semana": 25,
    },
}

CAMINHOS = [f"{secao}.{chave}" for secao, chaves in SECOES.items() for chave in chaves]


def _valor(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return f'"{v}"'
    if isinstance(v, float) and not math.isfinite(v):
        return repr(v)  # nan / inf / -inf são literais válidos em TOML
    return repr(v)


def _toml(dados: dict[str, Any]) -> str:
    """Serializador mínimo (seções de escalares) — evita uma dependência só para
    os testes."""
    linhas: list[str] = []
    for secao, corpo in dados.items():
        if not isinstance(corpo, dict):
            linhas.append(f"{secao} = {_valor(corpo)}")
            continue
        linhas.append(f"[{secao}]")
        linhas += [f"{k} = {_valor(v)}" for k, v in corpo.items()]
    return "\n".join(linhas) + "\n"


def _arquivo(tmp_path: Path, dados: dict[str, Any]) -> Path:
    caminho = tmp_path / "parametros.toml"
    caminho.write_text(_toml(dados), encoding="utf-8")
    return caminho


def _com(caminho: str, valor: Any, base: dict[str, Any] | None = None) -> dict[str, Any]:
    """Cópia da base (adotados por padrão) com UMA chave trocada."""
    dados = copy.deepcopy(base if base is not None else IGUAL_AO_ADOTADO)
    secao, chave = caminho.split(".")
    dados.setdefault(secao, {})[chave] = valor
    return dados


# Ao remover UM peso, os outros dois precisam somar 100 com o ADOTADO do removido — e
# continuar diferentes dos seus próprios adotados (70/30/0), senão a prova de
# "só ele mudou de rótulo" perderia o sentido.
_PESOS_QUANDO_FALTA: dict[str, dict[str, int]] = {
    "portal.peso_nota": {"peso_cliques": 20, "peso_visualizacoes": 10},
    "portal.peso_cliques": {"peso_nota": 60, "peso_visualizacoes": 10},
    "portal.peso_visualizacoes": {"peso_nota": 50, "peso_cliques": 50},
}


def _sem(caminho: str) -> dict[str, Any]:
    dados = copy.deepcopy(DIFERENTE)
    secao, chave = caminho.split(".")
    del dados[secao][chave]
    dados[secao].update(_PESOS_QUANDO_FALTA.get(caminho, {}))
    return dados


# --- sem arquivo: tudo adotado ------------------------------------------------


def test_sem_arquivo_tudo_e_adotado():
    """A rodada roda sem `--parametros`: cada chave vale o adotado e diz que é."""
    p = carregar(None)
    assert p.origem == f"adotados ({DECISAO_DOS_ADOTADOS})"
    assert dict(p.efetivo) == dict(ADOTADOS)
    assert set(p.procedencia) == set(CAMINHOS)
    assert set(p.procedencia.values()) == {ADOTADO}
    assert p.declarado == {}
    assert p.declarados_diferentes_do_adotado == ()
    assert p.resultado_esperado is None


def test_arquivo_vazio_equivale_a_nenhum(tmp_path):
    """Um arquivo sem nenhuma seção é legal e não muda nada — só a origem."""
    caminho = tmp_path / "vazio.toml"
    caminho.write_text("", encoding="utf-8")
    p = carregar(caminho)
    assert dict(p.efetivo) == dict(ADOTADOS)
    assert set(p.procedencia.values()) == {ADOTADO}
    assert p.origem == str(caminho)


def test_as_secoes_cobrem_exatamente_os_adotados():
    """Chave nas seções sem adotado seria `ParametroAusente` sem saída; adotado sem
    chave nas seções seria valor que ninguém consegue declarar."""
    assert set(CAMINHOS) == set(ADOTADOS)


def test_modelo_de_docs_continua_valido():
    """O arquivo-modelo é o que o dono copia. Se ele deixar de carregar, a primeira
    pessoa a rodar a sexta descobre isso no lugar errado. Ele declara os adotados,
    então nada nele é PROVISÓRIO."""
    p = carregar(EXEMPLO)
    assert dict(p.efetivo) == dict(ADOTADOS)
    assert p.declarados_diferentes_do_adotado == ()
    assert p.resultado_esperado is None
    assert "exemplo" in p.origem


# --- procedência --------------------------------------------------------------


def test_declarar_igual_ao_adotado_rotula_adotado(tmp_path):
    """Declarar o mesmo número não é escolha nova: a planilha não pode rotular
    PROVISÓRIO um valor que é o adotado."""
    p = carregar(_arquivo(tmp_path, IGUAL_AO_ADOTADO))
    assert set(p.procedencia.values()) == {ADOTADO}
    assert p.declarados_diferentes_do_adotado == ()


def test_declarar_diferente_rotula_declarado(tmp_path):
    p = carregar(_arquivo(tmp_path, DIFERENTE))
    assert set(p.procedencia.values()) == {"declarado"}
    assert p.declarados_diferentes_do_adotado == tuple(sorted(CAMINHOS))
    assert p.efetivo["portal.peso_nota"] == 50
    assert p.efetivo["desconto.sem_avaliacao"] == 2.5


def test_uma_chave_diferente_so_ela_e_declarada(tmp_path):
    dados = _com("portal.peso_nota", 60, _com("portal.peso_cliques", 40))
    p = carregar(_arquivo(tmp_path, dados))
    assert p.declarados_diferentes_do_adotado == ("portal.peso_cliques", "portal.peso_nota")
    assert p.procedencia["portal.peso_visualizacoes"] == ADOTADO
    assert p.procedencia["conversao.janela_dias"] == ADOTADO


@pytest.mark.parametrize("caminho", CAMINHOS)
def test_chave_ausente_cai_no_adotado(tmp_path, caminho):
    """Remover QUALQUER chave de um arquivo todo-diferente faz só ELA cair no
    adotado, rotulada — as outras continuam declaradas. É o que impede um default
    de conveniência de se passar por adotado."""
    p = carregar(_arquivo(tmp_path, _sem(caminho)))
    assert p.efetivo[caminho] == ADOTADOS[caminho]
    assert p.procedencia[caminho] == ADOTADO
    assert caminho not in p.declarados_diferentes_do_adotado
    assert len(p.declarados_diferentes_do_adotado) == len(CAMINHOS) - 1


@pytest.mark.parametrize("secao", sorted(SECOES))
def test_secao_inteira_ausente_cai_no_adotado(tmp_path, secao):
    dados = copy.deepcopy(DIFERENTE)
    del dados[secao]
    p = carregar(_arquivo(tmp_path, dados))
    for chave in SECOES[secao]:
        assert p.procedencia[f"{secao}.{chave}"] == ADOTADO
        assert p.efetivo[f"{secao}.{chave}"] == ADOTADOS[f"{secao}.{chave}"]


def test_declarado_e_verbatim(tmp_path):
    """O Registro grava o que o arquivo DISSE, não o efetivo: só assim se distingue
    "o dono declarou 180" de "o dono não declarou e caiu em 180"."""
    p = carregar(_arquivo(tmp_path, _sem("conversao.janela_dias")))
    assert "janela_dias" not in p.declarado["conversao"]
    assert p.declarado["portal"] == DIFERENTE["portal"]
    assert p.efetivo["conversao.janela_dias"] == ADOTADOS["conversao.janela_dias"]


def test_origem_aponta_o_arquivo(tmp_path):
    assert carregar(_arquivo(tmp_path, IGUAL_AO_ADOTADO)).origem.endswith("parametros.toml")


# --- typo não é ignorado ------------------------------------------------------


def test_chave_desconhecida_e_recusada(tmp_path):
    """`peso_notta` não pode ser descartado em silêncio: o dono digitou um valor e
    tem direito a saber que ele não foi usado — e, pior, o adotado entraria no
    lugar sem ninguém notar."""
    dados = copy.deepcopy(IGUAL_AO_ADOTADO)
    dados["portal"]["peso_notta"] = 70
    with pytest.raises(ParametroInvalido, match="peso_notta"):
        carregar(_arquivo(tmp_path, dados))


def test_secao_desconhecida_e_recusada(tmp_path):
    dados = copy.deepcopy(IGUAL_AO_ADOTADO)
    dados["ranking"] = {"peso": 1}
    with pytest.raises(ParametroInvalido, match="ranking"):
        carregar(_arquivo(tmp_path, dados))


def test_secao_antiga_e_recusada(tmp_path):
    """O formato pré-D-034 (`[pesos.super_destaque]`, `[externo]`) não pode carregar
    "por sorte": um arquivo velho seria lido como vazio e a rodada sairia toda
    adotada sem o dono saber que nada do que ele escreveu foi usado."""
    dados = copy.deepcopy(IGUAL_AO_ADOTADO)
    dados["externo"] = {"limiar_amarracao": 0.5}
    with pytest.raises(ParametroInvalido, match="externo"):
        carregar(_arquivo(tmp_path, dados))


def test_secao_que_nao_e_tabela_e_recusada(tmp_path):
    caminho = tmp_path / "p.toml"
    caminho.write_text("portal = 1\n", encoding="utf-8")
    with pytest.raises(ParametroInvalido, match=r"\[portal\]"):
        carregar(caminho)


def test_toml_invalido_e_parametro_invalido(tmp_path):
    """Erro de sintaxe é erro de PARÂMETRO (código de saída da rodada), não um
    traceback de `tomllib` que manda alguém investigar o Python."""
    caminho = tmp_path / "p.toml"
    caminho.write_text("[portal\npeso_nota = 70\n", encoding="utf-8")
    with pytest.raises(ParametroInvalido, match="TOML inválido"):
        carregar(caminho)


# --- faixas: cada campo, no limite e fora dele --------------------------------


@pytest.mark.parametrize(
    ("caminho", "valor", "trecho"),
    [
        ("conversao.janela_dias", 0, "ao menos 1 dia"),
        ("conversao.janela_dias", -30, "ao menos 1 dia"),
        ("corretor.login_janela_dias", 0, "ao menos 1 dia"),
        ("corretor.minimo_no_distrito", 0, "ao menos 1 corretor"),
        ("portal.cobertura_minima", 100.5, "0 a 100"),
        ("portal.cobertura_minima", -0.5, "0 a 100"),
        ("portal.idade_maxima_dias", -1, "negativa"),
        ("desconto.janela_sem_resultado", 101, "0 a 100"),
        ("desconto.janela_sem_resultado", -1, "0 a 100"),
        ("desconto.sem_avaliacao", 100.1, "0 a 100"),
        ("desconto.sem_lead_180d", -0.1, "0 a 100"),
        ("desconto.perdao_por_semana", 101, "0 a 100"),
        ("desconto.perdao_por_semana", -1, "0 a 100"),
    ],
)
def test_fora_da_faixa_e_recusado_nomeando_a_chave(tmp_path, caminho, valor, trecho):
    """A recusa acontece ANTES de tocar o banco e diz qual chave e por quê — o
    domínio erguer erro no meio da rodada, imóvel a imóvel, seria tarde."""
    with pytest.raises(ParametroInvalido, match=trecho) as e:
        carregar(_arquivo(tmp_path, _com(caminho, valor)))
    assert caminho in str(e.value)


@pytest.mark.parametrize(
    ("caminho", "valor"),
    [
        ("conversao.janela_dias", 1),
        ("corretor.login_janela_dias", 1),
        ("corretor.minimo_no_distrito", 1),
        ("portal.cobertura_minima", 0),
        ("portal.cobertura_minima", 100),
        ("portal.cobertura_minima", 33.3),
        ("portal.idade_maxima_dias", 0),
        ("desconto.janela_sem_resultado", 0),
        ("desconto.janela_sem_resultado", 100),
        ("desconto.sem_avaliacao", 0.5),
        ("desconto.sem_lead_180d", 100),
        ("desconto.perdao_por_semana", 0),
        ("desconto.perdao_por_semana", 100),
    ],
)
def test_no_limite_da_faixa_e_aceito(tmp_path, caminho, valor):
    """A contraprova das recusas acima: as fronteiras são fechadas onde o contrato
    diz que são. Sem isto, um carregador que recusasse TUDO passaria no teste
    anterior."""
    p = carregar(_arquivo(tmp_path, _com(caminho, valor)))
    assert p.efetivo[caminho] == valor


@pytest.mark.parametrize(
    "caminho",
    [
        "conversao.janela_dias",
        "corretor.login_janela_dias",
        "corretor.minimo_no_distrito",
        "portal.peso_nota",
        "portal.idade_maxima_dias",
    ],
)
def test_inteiro_nao_aceita_fracionario(tmp_path, caminho):
    """`180.0` é float em TOML. Aceitá-lo como inteiro seria o primeiro passo para
    aceitar `180.5` — e "meio dia" de janela não é uma quantidade que o SQL saiba
    ler."""
    with pytest.raises(ParametroInvalido, match="deve ser inteiro"):
        carregar(_arquivo(tmp_path, _com(caminho, float(ADOTADOS[caminho]))))


# --- pesos do portal ----------------------------------------------------------


def test_pesos_que_nao_somam_cem_sao_recusados_como_parametro(tmp_path):
    """A faixa vive em `PesosPortal` (domínio); aqui ela precisa reaparecer como erro
    de PARÂMETRO, com o nome da seção, e não como `ValueError` cru."""
    with pytest.raises(ParametroInvalido, match="portal") as e:
        carregar(_arquivo(tmp_path, _com("portal.peso_cliques", 40)))
    assert "somar 100" in str(e.value)


def test_peso_negativo_e_recusado_mesmo_somando_cem(tmp_path):
    dados = _com("portal.peso_nota", 110, _com("portal.peso_cliques", -10))
    with pytest.raises(ParametroInvalido, match="peso inválido"):
        carregar(_arquivo(tmp_path, dados))


@pytest.mark.parametrize("caminho", ["portal.peso_nota", "portal.peso_cliques"])
def test_peso_booleano_e_recusado(tmp_path, caminho):
    """`True` é `int` em Python: sem a guarda explícita, `peso_cliques = true`
    viraria 1 silenciosamente e os pesos deixariam de somar 100 por um ponto."""
    with pytest.raises(ParametroInvalido, match="deve ser inteiro"):
        carregar(_arquivo(tmp_path, _com(caminho, True)))


def test_peso_zero_e_legitimo(tmp_path):
    """Visualizações mediram zero em 300/300 anúncios: o peso zero é declarado, não
    omitido, e uma rodada só de nota também é expressável."""
    dados = _com("portal.peso_nota", 100, _com("portal.peso_cliques", 0))
    p = carregar(_arquivo(tmp_path, dados))
    assert p.decisao.pesos_portal == PesosPortal(nota_anuncio=100, cliques=0, visualizacoes=0)


def test_booleano_nao_passa_por_numero(tmp_path):
    with pytest.raises(ParametroInvalido, match="deve ser número"):
        carregar(_arquivo(tmp_path, _com("portal.cobertura_minima", True)))


# --- formas nomeadas ----------------------------------------------------------


@pytest.mark.parametrize("forma", FORMAS_SEM_ANUNCIO)
def test_toda_forma_de_sem_anuncio_e_aceita(tmp_path, forma):
    p = carregar(_arquivo(tmp_path, _com("portal.sem_anuncio", forma)))
    assert p.decisao.sem_anuncio == forma


@pytest.mark.parametrize("forma", FORMAS_DE_ORDEM_SEM_PORTAL)
def test_toda_ordem_sem_portal_e_aceita(tmp_path, forma):
    p = carregar(_arquivo(tmp_path, _com("portal.ordem_quando_nao_entra", forma)))
    assert p.decisao.ordem_sem_portal == forma


@pytest.mark.parametrize("caminho", ["portal.sem_anuncio", "portal.ordem_quando_nao_entra"])
def test_forma_fora_da_lista_e_recusada(tmp_path, caminho):
    """Lista FECHADA: expressão livre num arquivo de configuração seria código fora
    da revisão, e o invariante 5 deixaria de ser verificável."""
    with pytest.raises(ParametroInvalido, match="deve ser uma de"):
        carregar(_arquivo(tmp_path, _com(caminho, "zero")))


def test_forma_precisa_ser_texto(tmp_path):
    with pytest.raises(ParametroInvalido, match="deve ser uma de"):
        carregar(_arquivo(tmp_path, _com("portal.sem_anuncio", 0)))


# --- perdão: p% por carga = razão (1 − p/100) por ciclo ----------------------


@pytest.mark.parametrize("perdao", [0, 25, 50, 100])
def test_perdao_vira_razao_geometrica(tmp_path, perdao):
    """O dono escreve "quanto encolhe por carga"; o domínio consome uma razão. A
    conversão é verificável num único ciclo: `decaimento(1) == 1 − p/100`."""
    d = carregar(_arquivo(tmp_path, _com("desconto.perdao_por_semana", perdao))).decisao
    assert d.decaimento_janela(0) == 1.0  # sem ciclo decorrido, desconto cheio
    assert d.decaimento_janela(1) == pytest.approx(1.0 - perdao / 100.0)
    assert d.decaimento_janela(2) == pytest.approx((1.0 - perdao / 100.0) ** 2)
    assert all(0.0 <= d.decaimento_janela(c) <= 1.0 for c in range(0, 50))


def test_perdao_zero_nao_decai_e_continua_aceito(tmp_path):
    """Perdão 0 é expressável (nunca perdoa); quem o escolhe recebe a divergência
    com a §6.4 declarada na planilha — não uma recusa."""
    d = carregar(_arquivo(tmp_path, _com("desconto.perdao_por_semana", 0))).decisao
    assert d.decaimento_janela(0) == d.decaimento_janela(10) == 1.0


def test_perdao_total_zera_no_primeiro_ciclo(tmp_path):
    d = carregar(_arquivo(tmp_path, _com("desconto.perdao_por_semana", 100))).decisao
    assert d.decaimento_janela(1) == 0.0


# --- valores que passam por qualquer comparação de faixa ----------------------


@pytest.mark.parametrize("literal", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("caminho", ["portal.cobertura_minima", "desconto.janela_sem_resultado"])
def test_nao_finito_e_recusado_como_parametro(tmp_path, caminho, literal):
    """`nan` e `inf` são literais VÁLIDOS em TOML, e `nan < 0` é falso — passariam
    por toda checagem de faixa e só quebrariam no domínio, com `ValueError` cru."""
    with pytest.raises(ParametroInvalido, match="finito"):
        carregar(_arquivo(tmp_path, _com(caminho, literal)))


@pytest.mark.parametrize("literal", [float("nan"), float("inf")])
def test_nao_finito_em_campo_inteiro_e_recusado(tmp_path, literal):
    """Num campo inteiro o `nan` cai antes, na checagem de tipo — mas cai."""
    with pytest.raises(ParametroInvalido):
        carregar(_arquivo(tmp_path, _com("conversao.janela_dias", literal)))


# --- parâmetro nº 14 (D-022): a única seção OPCIONAL e sem adotado ------------


def test_resultado_esperado_ausente_e_nulo_nao_erro(tmp_path):
    """A régua segue NULA por decisão do dono. Exigir a seção obrigaria a inventar
    os dois números para conseguir rodar — o oposto do que a decisão determinou."""
    assert carregar(_arquivo(tmp_path, IGUAL_AO_ADOTADO)).resultado_esperado is None


def test_resultado_esperado_nao_tem_adotado():
    """Se um dia ganhar adotado, deixa de ser nulo — e isso é decisão do dono, não
    um item a mais em `ADOTADOS`."""
    assert not any(k.startswith("resultado_esperado") for k in ADOTADOS)


def test_resultado_esperado_declarado_carrega_os_dois_niveis(tmp_path):
    dados = copy.deepcopy(IGUAL_AO_ADOTADO)
    dados["resultado_esperado"] = {"super_destaque": 3, "destaque": 1}
    p = carregar(_arquivo(tmp_path, dados))
    assert p.resultado_esperado == {"super_destaque": 3, "destaque": 1}
    # A régua não entra em `efetivo`/`procedencia`: não é chave com adotado.
    assert not any(k.startswith("resultado_esperado") for k in p.efetivo)


@pytest.mark.parametrize("meio", [{"super_destaque": 3}, {"destaque": 1}])
def test_resultado_esperado_MEIO_declarado_e_recusado(tmp_path, meio):
    """Meio-declarado é pior que nulo: metade das janelas julgada por um limiar e a
    outra sem julgamento. É o ÚNICO caso de `ParametroAusente` que sobrou."""
    dados = copy.deepcopy(IGUAL_AO_ADOTADO)
    dados["resultado_esperado"] = meio
    with pytest.raises(ParametroAusente, match="nº 14"):
        carregar(_arquivo(tmp_path, dados))


def test_resultado_esperado_negativo_e_recusado(tmp_path):
    dados = copy.deepcopy(IGUAL_AO_ADOTADO)
    dados["resultado_esperado"] = {"super_destaque": -1, "destaque": 1}
    with pytest.raises(ParametroInvalido, match="contagem de leads"):
        carregar(_arquivo(tmp_path, dados))


def test_limiar_ZERO_e_recusado_em_vez_de_desligar_em_silencio(tmp_path):
    """`leads >= 0` é sempre verdadeiro: a coluna sairia 0,0 para todos e NENHUMA
    limitação seria emitida. Para desligar, omite-se a seção."""
    dados = copy.deepcopy(IGUAL_AO_ADOTADO)
    dados["resultado_esperado"] = {"super_destaque": 2, "destaque": 0}
    with pytest.raises(ParametroInvalido, match="OMITA a seção"):
        carregar(_arquivo(tmp_path, dados))


@pytest.mark.parametrize("par", [(1, 5), (3, 3)])
def test_super_destaque_precisa_ser_MAIOR_que_destaque(tmp_path, par):
    """PRD: "super destaque exige entrega SUPERIOR à de destaque". Régua invertida
    (ou empatada) penalizaria o super destaque menos que o destaque."""
    dados = copy.deepcopy(IGUAL_AO_ADOTADO)
    dados["resultado_esperado"] = {"super_destaque": par[0], "destaque": par[1]}
    with pytest.raises(ParametroInvalido, match="MAIOR que destaque"):
        carregar(_arquivo(tmp_path, dados))


def test_resultado_esperado_fracionario_e_recusado(tmp_path):
    dados = copy.deepcopy(IGUAL_AO_ADOTADO)
    dados["resultado_esperado"] = {"super_destaque": 2.5, "destaque": 1}
    with pytest.raises(ParametroInvalido, match="deve ser inteiro"):
        carregar(_arquivo(tmp_path, dados))


def test_nivel_desconhecido_em_resultado_esperado_e_recusado(tmp_path):
    dados = copy.deepcopy(IGUAL_AO_ADOTADO)
    dados["resultado_esperado"] = {"super_destaque": 3, "destaque": 1, "vitrine": 9}
    with pytest.raises(ParametroInvalido, match="vitrine"):
        carregar(_arquivo(tmp_path, dados))


def test_resultado_esperado_que_nao_e_tabela_e_recusado_como_parametro(tmp_path):
    caminho = tmp_path / "p.toml"
    caminho.write_text("resultado_esperado = 3\n", encoding="utf-8")
    with pytest.raises(ParametroInvalido):
        carregar(caminho)


# --- montar: dos valores efetivos aos objetos do domínio ---------------------


def test_montar_os_adotados_produz_os_objetos_do_dominio():
    """`montar` é pública porque o Registro reidrata `efetivo` e precisa dos mesmos
    objetos que a rodada usou. A cobertura vira limiar em FRAÇÃO (÷ 100)."""
    decisao, externo, coleta = montar(ADOTADOS)
    assert decisao.pesos_portal == PesosPortal(nota_anuncio=70, cliques=30, visualizacoes=0)
    assert decisao.sem_anuncio == "fim_da_fila"
    assert decisao.ordem_sem_portal == "leads_180d"
    assert decisao.intensidades == IntensidadesPenalidade(
        janela_sem_resultado=20.0, sem_avaliacao_por_categoria=5.0, sem_lead_180d=10.0
    )
    assert decisao.decaimento_janela(1) == 0.5
    assert decisao.minimo_corretores_distrito == 2
    assert decisao.exigir_dimensao_no_perfil is DIMENSAO_EXIGIDA_NO_PERFIL is Dimensao.FAIXA_PRECO
    assert externo == ParametrosExterno(limiar_amarracao=0.5, idade_maxima_dias=2)
    assert coleta == ParametrosColeta(janela_conversao_dias=180, login_janela_dias=30)


def test_montar_com_declarados_diferentes():
    efetivo = {f"{s}.{k}": v for s, corpo in DIFERENTE.items() for k, v in corpo.items()}
    decisao, externo, coleta = montar(efetivo)
    assert decisao.pesos_portal == PesosPortal(nota_anuncio=50, cliques=40, visualizacoes=10)
    assert decisao.sem_anuncio == "mediana"
    assert decisao.ordem_sem_portal == "produtividade_gestor"
    assert decisao.intensidades.sem_avaliacao_por_categoria == 2.5
    assert decisao.decaimento_janela(1) == 0.75
    assert decisao.minimo_corretores_distrito == 3
    assert externo.limiar_amarracao == 0.6
    assert externo.idade_maxima_dias == 1
    assert coleta == ParametrosColeta(janela_conversao_dias=90, login_janela_dias=15)


def test_carregar_e_montar_concordam(tmp_path):
    """O que `carregar` injeta no grafo é exatamente `montar(efetivo)`: quem reidratar
    do Registro obtém os mesmos objetos."""
    p = carregar(_arquivo(tmp_path, DIFERENTE))
    decisao, externo, coleta = montar(p.efetivo)
    assert p.decisao.pesos_portal == decisao.pesos_portal
    assert p.decisao.intensidades == decisao.intensidades
    assert p.decisao.sem_anuncio == decisao.sem_anuncio
    assert p.decisao.ordem_sem_portal == decisao.ordem_sem_portal
    assert p.decisao.minimo_corretores_distrito == decisao.minimo_corretores_distrito
    assert p.decisao.decaimento_janela(3) == decisao.decaimento_janela(3)
    assert p.externo == externo
    assert p.coleta == coleta


def test_montar_valida_faixa_sem_passar_pelo_arquivo():
    """A faixa é conferida em `montar`, não na leitura do TOML: valores reidratados
    do Registro passam pelo mesmo portão."""
    with pytest.raises(ParametroInvalido, match="ao menos 1 corretor"):
        montar({**ADOTADOS, "corretor.minimo_no_distrito": 0})
