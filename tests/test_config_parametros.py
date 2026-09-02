"""Testes do carregador dos parâmetros da rodada.

O teste central é `test_nenhum_parametro_tem_default`: ele REMOVE, uma a uma, cada
chave do arquivo e exige que a rodada quebre. Sem ele, a regra "nenhum pendente pode
ser preenchido com valor inventado" seria só um comentário — e o dia em que alguém
acrescentasse um `bruto.get(chave, 0.5)` por conveniência, a suíte seguiria verde e a
sexta sairia com um número que ninguém escolheu, rotulado como se fosse do dono.
"""

from __future__ import annotations

import copy
import tomllib
from pathlib import Path
from typing import Any

import pytest

from config.parametros import (
    ParametroAusente,
    ParametroInvalido,
    carregar,
)
from dados.coletor_externo import DesempenhoAnuncio

EXEMPLO = Path(__file__).resolve().parent.parent / "docs" / "parametros-da-rodada.exemplo.toml"

VALIDO: dict[str, Any] = {
    "semelhanca": {"desconto_fragil": 0.5, "decaimento": 1.0},
    "intensidades": {
        "janela_sem_resultado": 0.10,
        "sem_avaliacao_por_categoria": 0.10,
        "sem_lead_180d": 0.10,
    },
    "decaimento_janela": {"forma": "geometrica", "razao": 0.5},
    "pesos": {
        "super_destaque": {
            "semelhanca_perfil": 25,
            "leads_positivo": 25,
            "desempenho_proprio": 25,
            "produtividade_gestor": 25,
        },
        "destaque": {
            "semelhanca_perfil": 25,
            "leads_positivo": 25,
            "desempenho_proprio": 25,
            "produtividade_gestor": 25,
        },
    },
    "externo": {
        "limiar_amarracao": 0.5,
        "idade_maxima_dias": 8,
        "desempenho": {"forma": "visualizacoes"},
    },
}

# Todo caminho que o arquivo PRECISA ter. Remover qualquer um destes é erro.
CAMINHOS_OBRIGATORIOS = [
    ("semelhanca",),
    ("semelhanca", "desconto_fragil"),
    ("semelhanca", "decaimento"),
    ("intensidades",),
    ("intensidades", "janela_sem_resultado"),
    ("intensidades", "sem_avaliacao_por_categoria"),
    ("intensidades", "sem_lead_180d"),
    ("decaimento_janela",),
    ("decaimento_janela", "forma"),
    ("decaimento_janela", "razao"),
    ("pesos",),
    ("pesos", "super_destaque"),
    ("pesos", "destaque"),
    ("pesos", "super_destaque", "semelhanca_perfil"),
    ("pesos", "super_destaque", "leads_positivo"),
    ("pesos", "super_destaque", "desempenho_proprio"),
    ("pesos", "super_destaque", "produtividade_gestor"),
    # Os QUATRO de `destaque` também: listar só um sugeria que este nível é menos
    # validado que `super_destaque`, e a lista é o que documenta a exigência.
    ("pesos", "destaque", "semelhanca_perfil"),
    ("pesos", "destaque", "leads_positivo"),
    ("pesos", "destaque", "desempenho_proprio"),
    ("pesos", "destaque", "produtividade_gestor"),
    ("externo",),
    ("externo", "limiar_amarracao"),
    ("externo", "idade_maxima_dias"),
    ("externo", "desempenho"),
    ("externo", "desempenho", "forma"),
]


def _valor(v: Any) -> str:
    return f'"{v}"' if isinstance(v, str) else repr(v)


def _toml(dados: dict[str, Any]) -> str:
    """Serializador mínimo (dois níveis) — evita uma dependência só para os testes."""
    linhas: list[str] = []
    for secao, corpo in dados.items():
        subtabelas = {k: v for k, v in corpo.items() if isinstance(v, dict)}
        escalares = {k: v for k, v in corpo.items() if not isinstance(v, dict)}
        linhas.append(f"[{secao}]")
        linhas += [f"{k} = {_valor(v)}" for k, v in escalares.items()]
        for nome, tabela in subtabelas.items():
            linhas.append(f"[{secao}.{nome}]")
            linhas += [f"{k} = {_valor(v)}" for k, v in tabela.items()]
    return "\n".join(linhas) + "\n"


def _arquivo(tmp_path: Path, dados: dict[str, Any]) -> Path:
    caminho = tmp_path / "parametros.toml"
    caminho.write_text(_toml(dados), encoding="utf-8")
    return caminho


def _sem(caminho: tuple[str, ...]) -> dict[str, Any]:
    dados = copy.deepcopy(VALIDO)
    alvo: Any = dados
    for chave in caminho[:-1]:
        alvo = alvo[chave]
    del alvo[caminho[-1]]
    return dados


# --- a garantia central -------------------------------------------------------


@pytest.mark.parametrize("caminho", CAMINHOS_OBRIGATORIOS, ids=lambda c: ".".join(c))
def test_nenhum_parametro_tem_default(tmp_path, caminho):
    """Remover QUALQUER chave obrigatória derruba a rodada. É o que impede um
    default de conveniência de nascer sem ninguém notar."""
    with pytest.raises(ParametroAusente):
        carregar(_arquivo(tmp_path, _sem(caminho)))


def test_arquivo_completo_carrega(tmp_path):
    """A contraprova: com todas as chaves, carrega. Sem isto, a varredura acima
    passaria mesmo se `carregar` levantasse SEMPRE."""
    p = carregar(_arquivo(tmp_path, VALIDO))
    assert p.decisao.pesos_super.semelhanca_perfil == 25
    assert p.externo.idade_maxima_dias == 8
    assert p.rotulo == "PROVISÓRIO"


def test_modelo_de_docs_continua_valido():
    """O arquivo-modelo é o que o dono copia. Se ele deixar de carregar, a primeira
    pessoa a rodar a sexta descobre isso no lugar errado."""
    p = carregar(EXEMPLO)
    assert p.decisao.pesos_destaque.leads_positivo == 50
    assert "exemplo" in p.origem


# --- procedência --------------------------------------------------------------


def test_declarado_e_verbatim(tmp_path):
    """O Registro grava o declarado, não uma reconstrução: as duas FORMAS viram
    função e não sobrevivem a `ParametrosDecisao`. Gravar só os números deixaria a
    rodada irreproduzível a partir do Registro (invariante 5)."""
    p = carregar(_arquivo(tmp_path, VALIDO))
    assert p.declarado["decaimento_janela"] == {"forma": "geometrica", "razao": 0.5}
    assert p.declarado["externo"]["desempenho"] == {"forma": "visualizacoes"}


def test_origem_aponta_o_arquivo(tmp_path):
    assert carregar(_arquivo(tmp_path, VALIDO)).origem.endswith("parametros.toml")


# --- typo não é ignorado ------------------------------------------------------


def test_chave_desconhecida_e_recusada(tmp_path):
    """`decaimeto` não pode ser descartado em silêncio: o dono digitou um valor e
    tem direito a saber que ele não foi usado."""
    dados = copy.deepcopy(VALIDO)
    dados["semelhanca"]["decaimeto"] = 0.7
    with pytest.raises(ParametroInvalido, match="decaimeto"):
        carregar(_arquivo(tmp_path, dados))


def test_secao_desconhecida_e_recusada(tmp_path):
    dados = copy.deepcopy(VALIDO)
    dados["ranking"] = {"peso": 1}
    with pytest.raises(ParametroInvalido, match="ranking"):
        carregar(_arquivo(tmp_path, dados))


def test_erro_de_ausencia_nomeia_o_pendente(tmp_path):
    """Quem opera a rodada precisa saber QUAL decisão do dono está faltando, não só
    qual chave TOML falta."""
    with pytest.raises(ParametroAusente, match="nº 12"):
        carregar(_arquivo(tmp_path, _sem(("pesos",))))


# --- faixas -------------------------------------------------------------------


def test_razao_fora_da_faixa_erra_no_carregamento(tmp_path):
    """Razão > 1 amplificaria a penalidade a cada ciclo. O domínio erguer erro no
    MEIO da rodada, imóvel a imóvel, seria tarde: aqui erra antes de tocar o banco."""
    dados = copy.deepcopy(VALIDO)
    dados["decaimento_janela"]["razao"] = 1.5
    with pytest.raises(ParametroInvalido, match="razao"):
        carregar(_arquivo(tmp_path, dados))


def test_pesos_que_nao_somam_cem_sao_recusados(tmp_path):
    dados = copy.deepcopy(VALIDO)
    dados["pesos"]["destaque"]["leads_positivo"] = 30
    with pytest.raises(ParametroInvalido, match="destaque"):
        carregar(_arquivo(tmp_path, dados))


def test_intensidade_negativa_e_recusada(tmp_path):
    """Intensidade negativa viraria BÔNUS: a penalidade somaria à nota em vez de
    descontar, invertendo a regra da Spec §6.4 sem nenhum sinal."""
    dados = copy.deepcopy(VALIDO)
    dados["intensidades"]["sem_lead_180d"] = -0.1
    with pytest.raises(ParametroInvalido, match="bônus"):
        carregar(_arquivo(tmp_path, dados))


def test_limiar_de_amarracao_fora_de_zero_um(tmp_path):
    dados = copy.deepcopy(VALIDO)
    dados["externo"]["limiar_amarracao"] = 1.4
    with pytest.raises(ParametroInvalido, match="taxa"):
        carregar(_arquivo(tmp_path, dados))


def test_booleano_nao_passa_por_numero(tmp_path):
    """`True` é `int` em Python: sem a guarda explícita, `desconto_fragil = true`
    viraria 1.0 silenciosamente."""
    dados = copy.deepcopy(VALIDO)
    dados["semelhanca"]["desconto_fragil"] = True
    with pytest.raises(ParametroInvalido):
        carregar(_arquivo(tmp_path, dados))


# --- formas nomeadas ----------------------------------------------------------


def test_forma_desconhecida_de_decaimento(tmp_path):
    dados = copy.deepcopy(VALIDO)
    dados["decaimento_janela"] = {"forma": "exponencial_negativa"}
    with pytest.raises(ParametroInvalido, match="Forma aceita"):
        carregar(_arquivo(tmp_path, dados))


def test_forma_desconhecida_de_desempenho(tmp_path):
    dados = copy.deepcopy(VALIDO)
    dados["externo"]["desempenho"] = {"forma": "soma_dos_cliques"}
    with pytest.raises(ParametroInvalido, match="nunca os soma"):
        carregar(_arquivo(tmp_path, dados))


def test_decaimento_geometrico_decai_e_fica_na_faixa(tmp_path):
    dados = copy.deepcopy(VALIDO)
    dados["decaimento_janela"] = {"forma": "geometrica", "razao": 0.5}
    d = carregar(_arquivo(tmp_path, dados)).decisao.decaimento_janela
    assert d(0) == 1.0  # sem ciclo decorrido, intensidade cheia
    assert d(1) == 0.5
    assert all(0.0 <= d(c) <= 1.0 for c in range(0, 50))  # a faixa que o domínio exige


def test_razao_um_nao_decai_e_continua_aceita(tmp_path):
    """Havia uma forma nomeada `sem_decaimento` para este caso. Era redundante: a
    geométrica com razão 1.0 já o produz. A forma saiu; o caso continua expressável,
    e quem o escolhe recebe a divergência com a §6.4 declarada na planilha."""
    dados = copy.deepcopy(VALIDO)
    dados["decaimento_janela"] = {"forma": "geometrica", "razao": 1.0}
    d = carregar(_arquivo(tmp_path, dados)).decisao.decaimento_janela
    assert d(0) == d(10) == 1.0


def test_forma_sem_decaimento_nao_existe_mais(tmp_path):
    dados = copy.deepcopy(VALIDO)
    dados["decaimento_janela"] = {"forma": "sem_decaimento"}
    with pytest.raises(ParametroInvalido, match="desconhecida"):
        carregar(_arquivo(tmp_path, dados))


# --- valores que passam por qualquer comparação de faixa ----------------------


@pytest.mark.parametrize("literal", ["nan", "inf", "-inf"])
def test_nao_finito_e_recusado_como_parametro(tmp_path, literal):
    """`nan` e `inf` são literais VÁLIDOS em TOML, e `nan < 0` é falso — passavam
    por toda checagem de faixa e só quebravam no domínio, com `ValueError` cru que o
    `main` não captura: a rodada saía com o código de FALHA DE ESCRITA e um
    traceback no stdout, mandando alguém investigar o Postgres por causa do arquivo."""
    caminho = tmp_path / "p.toml"
    caminho.write_text(
        _toml(VALIDO).replace("janela_sem_resultado = 0.1", f"janela_sem_resultado = {literal}"),
        encoding="utf-8",
    )
    with pytest.raises(ParametroInvalido, match="finito"):
        carregar(caminho)


def test_ausencia_dentro_de_secao_validada_continua_sendo_ausencia(tmp_path):
    """`ParametroAusente` e `ParametroInvalido` são ambos `ValueError`: um `try`
    largo demais em torno da leitura reclassificava a ausência como invalidez, e a
    regra 1 do módulo ("chave ausente é erro nomeado") deixava de valer justo ali."""
    with pytest.raises(ParametroAusente):
        carregar(_arquivo(tmp_path, _sem(("semelhanca", "decaimento"))))


# --- parâmetro nº 14 (D-022): a única seção OPCIONAL --------------------------


def test_resultado_esperado_ausente_e_nulo_nao_erro(tmp_path):
    """A D-022 deixou o nº 14 NULO. Exigir a seção obrigaria o dono a inventar os
    dois números para conseguir rodar — o oposto do que a decisão determinou."""
    assert carregar(_arquivo(tmp_path, VALIDO)).resultado_esperado is None


def test_resultado_esperado_declarado_carrega_os_dois_niveis(tmp_path):
    dados = copy.deepcopy(VALIDO)
    dados["resultado_esperado"] = {"super_destaque": 3, "destaque": 1}
    assert carregar(_arquivo(tmp_path, dados)).resultado_esperado == {
        "super_destaque": 3,
        "destaque": 1,
    }


def test_resultado_esperado_MEIO_declarado_e_recusado(tmp_path):
    """Meio-declarado é pior que nulo: metade das janelas julgada por um limiar e a
    outra sem julgamento, com a planilha declarando "limiar não definido" numa rodada
    que penalizou parte do estoque."""
    dados = copy.deepcopy(VALIDO)
    dados["resultado_esperado"] = {"super_destaque": 3}
    with pytest.raises(ParametroAusente, match="nº 14"):
        carregar(_arquivo(tmp_path, dados))


def test_resultado_esperado_negativo_e_recusado(tmp_path):
    dados = copy.deepcopy(VALIDO)
    dados["resultado_esperado"] = {"super_destaque": -1, "destaque": 1}
    with pytest.raises(ParametroInvalido, match="contagem de leads"):
        carregar(_arquivo(tmp_path, dados))


def test_limiar_ZERO_e_recusado_em_vez_de_desligar_em_silencio(tmp_path):
    """`leads >= 0` é sempre verdadeiro: a coluna sairia 0,0 para todos e NENHUMA
    limitação seria emitida (a de "limiar não definido" só sai quando ele é nulo).
    A D-022 é explícita — "nunca 0,0 silencioso". Para desligar, omite-se a seção."""
    dados = copy.deepcopy(VALIDO)
    dados["resultado_esperado"] = {"super_destaque": 2, "destaque": 0}
    with pytest.raises(ParametroInvalido, match="OMITA a seção"):
        carregar(_arquivo(tmp_path, dados))


def test_super_destaque_com_limiar_MENOR_que_destaque_e_recusado(tmp_path):
    """PRD, "Rotação e penalidade": "o resultado suficiente é proporcional ao tipo de
    posição: super destaque exige entrega SUPERIOR à de destaque". Sem esta guarda, um
    arquivo com a régua invertida carregaria em silêncio e a rodada penalizaria o
    super destaque menos que o destaque — o oposto do documento."""
    dados = copy.deepcopy(VALIDO)
    dados["resultado_esperado"] = {"super_destaque": 1, "destaque": 5}
    with pytest.raises(ParametroInvalido, match="MAIOR que destaque"):
        carregar(_arquivo(tmp_path, dados))

    dados["resultado_esperado"] = {"super_destaque": 3, "destaque": 3}  # empate também
    with pytest.raises(ParametroInvalido, match="MAIOR que destaque"):
        carregar(_arquivo(tmp_path, dados))


def test_nivel_desconhecido_em_resultado_esperado_e_recusado(tmp_path):
    dados = copy.deepcopy(VALIDO)
    dados["resultado_esperado"] = {"super_destaque": 3, "destaque": 1, "vitrine": 9}
    with pytest.raises(ParametroInvalido, match="vitrine"):
        carregar(_arquivo(tmp_path, dados))


def _anuncio(**kw) -> DesempenhoAnuncio:
    campos = {
        "imovel_id": 1,
        "id_portal": "X",
        "nota": 8.0,
        "visualizacoes": 30,
        "cliques": {"cliqueTelefone": 2, "cliqueWhatsapp": 5},
        "url": None,
    }
    return DesempenhoAnuncio(**{**campos, **kw})


def test_f3_nota_ausente_usa_o_valor_declarado(tmp_path):
    """Sem `quando_ausente` declarado, o código escolheria pelo dono — e um zero
    implícito puniria o anúncio pela AUSÊNCIA do dado, não pelo desempenho."""
    dados = copy.deepcopy(VALIDO)
    dados["externo"]["desempenho"] = {"forma": "nota", "quando_ausente": 5.0}
    compor = carregar(_arquivo(tmp_path, dados)).externo.compor_desempenho
    assert compor(_anuncio(nota=9.0)) == 9.0
    assert compor(_anuncio(nota=None)) == 5.0


def test_f3_nota_exige_quando_ausente(tmp_path):
    dados = copy.deepcopy(VALIDO)
    dados["externo"]["desempenho"] = {"forma": "nota"}
    with pytest.raises(ParametroAusente, match="quando_ausente"):
        carregar(_arquivo(tmp_path, dados))


def test_f3_cliques_le_um_tipo_e_nao_soma(tmp_path):
    """Contrato do coletor: tipos de clique medem intenções diferentes e nunca são
    somados. A forma lê UM tipo nomeado — 5, não 7."""
    dados = copy.deepcopy(VALIDO)
    dados["externo"]["desempenho"] = {"forma": "cliques_do_tipo", "tipo": "cliqueWhatsapp"}
    compor = carregar(_arquivo(tmp_path, dados)).externo.compor_desempenho
    assert compor(_anuncio()) == 5.0
    assert compor(_anuncio(cliques={})) == 0.0  # anúncio sem aquele clique: zero


def test_tipo_de_clique_inexistente_e_recusado(tmp_path):
    """Um tipo fora da lista da coleta devolvia 0 para TODO anúncio: F3
    uniformemente zerado, etapa marcada pronta, rodada COMPLETA e nenhuma limitação
    declarada. O silêncio exato que a regra 2 deste módulo existe para impedir."""
    dados = copy.deepcopy(VALIDO)
    dados["externo"]["desempenho"] = {"forma": "cliques_do_tipo", "tipo": "whatsapp"}
    with pytest.raises(ParametroInvalido, match="desconhecido"):
        carregar(_arquivo(tmp_path, dados))


def test_toml_malformado_vira_erro_de_parametro(tmp_path):
    caminho = tmp_path / "torto.toml"
    caminho.write_text("[semelhanca\ndesconto_fragil = ", encoding="utf-8")
    with pytest.raises(ParametroInvalido, match="TOML inválido"):
        carregar(caminho)


def test_serializador_do_teste_produz_toml_valido(tmp_path):
    """O serializador acima é do próprio teste: se ele produzisse TOML torto, a
    varredura de defaults passaria por motivo ERRADO (tudo falharia no parser)."""
    assert tomllib.loads(_toml(VALIDO)) == VALIDO
