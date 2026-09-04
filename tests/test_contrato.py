"""O contrato do formulário não pode divergir do validador da rodada.

A trava tem DUAS metades, e a primeira versão deste arquivo só tinha uma.

**Forma** — monta-se um TOML *a partir do contrato* e exige-se que
`config.parametros.carregar()` o aceite. Contrato que **inventa** um campo cai em
`ParametroInvalido` (nenhuma chave desconhecida, em todos os níveis). A direção
oposta mudou com a D-034: contrato que **esquece** um campo já não cai em
`ParametroAusente`, porque toda chave tem adotado — o carregador aceitaria o TOML
incompleto em silêncio. Quem fecha essa direção agora é a comparação direta entre
as seções do carregador e os caminhos obrigatórios do contrato, mais a prova de que
a chave removida cai no ADOTADO com a procedência certa, e de que a chave declarada
com valor diferente sai rotulada "declarado".

**Valor** — a ida e volta acima visita UM ponto interior por campo, então nada
nela enxerga `minimo`, `maximo`, `minimo_aberto`, `tipo` ou `escolhas`. Uma
auditoria hostil mutou os quatro e a suíte ficou verde nas quatro vezes. O pior
deles não é a faixa: é o `tipo`. `_numero` aceita `int` e `float`, então declarar
`inteiro` num campo fracionário **não erra em lugar nenhum** — o formulário
proíbe 2,5 pontos de desconto, o dono digita 2 ou 3 no lugar, o carregador
aceita, e a rodada decide 6.970 posições pagas com um número que ele não queria
mas que o formulário obrigou. Daí a bateria de sondas abaixo, que afirma
**aceita E recusa** em cada fronteira.

Os valores aqui são SONDAS: existem para provar fronteiras, e nada mais. Não são
sugestão, não são default, e não viajam para lugar nenhum.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, get_args

import pytest

from config.adotados import ADOTADOS, DECISAO_DOS_ADOTADOS
from config.contrato import CAMPOS, GRUPOS, PENDENTE_DE, REGRAS, Campo, Funcao, contrato
from config.parametros import SECOES, ParametroAusente, ParametroInvalido, carregar
from executar.contrato import main as main_contrato

RAIZ = Path(__file__).resolve().parent.parent
JSON_DO_CONSOLE = RAIZ / "console" / "lib" / "contrato-parametros.json"
ADOTADO = f"adotado {DECISAO_DOS_ADOTADOS}"

_POR_CAMINHO = {c.caminho: c for c in CAMPOS}
# Os três pesos não têm fronteira individual sondável: a regra de soma 100 domina, e
# mexer num deles quebra a soma antes de a faixa ser exercida. Quem os cobre é a regra
# cruzada, e a ida e volta prova que existem e são inteiros.
_PESOS = tuple(c.caminho for c in CAMPOS if c.caminho.startswith("portal.peso_"))
_OBRIGATORIOS = tuple(c.caminho for c in CAMPOS if c.obrigatorio)
_OPCIONAIS = tuple(c.caminho for c in CAMPOS if not c.obrigatorio)
# Pesos DIFERENTES dos adotados (70/30/0) em TODOS os três, somando 100 — para a
# prova de "declarado".
_PESOS_DIFERENTES = {
    "portal.peso_nota": 60,
    "portal.peso_cliques": 20,
    "portal.peso_visualizacoes": 20,
}


def _pesos_sem(removido: str) -> dict[str, int]:
    """Os outros dois pesos, diferentes dos adotados, que somam 100 com o ADOTADO do
    removido — só assim a remoção de um peso cai no adotado sem quebrar a soma."""
    outros = [p for p in _PESOS if p != removido]
    resto = 100 - int(ADOTADOS[removido])
    a, b = resto // 2, resto - resto // 2
    if a == ADOTADOS[outros[0]] or b == ADOTADOS[outros[1]]:
        a, b = a + 1, b - 1
    assert a != ADOTADOS[outros[0]] and b != ADOTADOS[outros[1]]
    return {outros[0]: a, outros[1]: b}


def _sonda(campo: Campo) -> Any:
    """Um valor interior válido. Sonda de teste, nunca sugestão."""
    if campo.tipo == "escolha":
        assert campo.escolhas, f"{campo.caminho}: escolha sem opções"
        return campo.escolhas[0]
    if campo.tipo == "inteiro":
        return int(campo.minimo) if campo.minimo is not None else 1
    if campo.minimo is not None and campo.maximo is not None:
        return (campo.minimo + campo.maximo) / 2
    if campo.minimo is not None:
        return campo.minimo + 1.0 if campo.minimo_aberto else campo.minimo
    return 1.0


def _sonda_diferente_do_adotado(campo: Campo) -> Any:
    """Um valor válido que NÃO é o adotado — para provar que o rótulo "declarado"
    nasce da diferença, não da presença."""
    if campo.tipo == "escolha":
        assert campo.escolhas
        return next(e for e in campo.escolhas if e != campo.adotado)
    valor = _sonda(campo)
    if valor == campo.adotado:
        valor = valor + 1 if campo.maximo is None or valor + 1 <= campo.maximo else valor - 1
    assert valor != campo.adotado, campo.caminho
    return valor


def _por(caminho: str, arvore: dict[str, Any], valor: Any) -> None:
    partes = caminho.split(".")
    no = arvore
    for parte in partes[:-1]:
        no = no.setdefault(parte, {})
    no[partes[-1]] = valor


def _de(caminho: str, arvore: dict[str, Any]) -> Any:
    no: Any = arvore
    for parte in caminho.split("."):
        no = no[parte]
    return no


def montar(*, incluir_opcionais: bool = False, diferente_do_adotado: bool = False) -> dict:
    """Monta a árvore do TOML A PARTIR DO CONTRATO — nunca de uma lista paralela."""
    arvore: dict[str, Any] = {}
    for campo in CAMPOS:
        if not campo.obrigatorio and not incluir_opcionais:
            continue
        if campo.exige is not None:
            alvo, esperado = campo.exige
            if _de(alvo, arvore) != esperado:
                continue
        valor = _sonda_diferente_do_adotado(campo) if diferente_do_adotado else _sonda(campo)
        _por(campo.caminho, arvore, valor)
    # As sondas individuais dos pesos (mínimo 0) não somam 100: a regra cruzada domina.
    for caminho, valor in _PESOS_DIFERENTES.items():
        _por(caminho, arvore, valor)
    if incluir_opcionais:
        # Derivado dos campos OPCIONAIS do contrato, não de um literal: era pelo
        # literal que os dois campos do parâmetro nº 14 podiam sumir do contrato com
        # a suíte verde — o formulário deixaria de oferecer a seção e ninguém veria.
        assert len(_OPCIONAIS) == 2, f"a seção opcional mudou de forma: {_OPCIONAIS}"
        # A regra cruzada `maior_que` exige super > destaque, estrito.
        for caminho, valor in zip(sorted(_OPCIONAIS, reverse=True), (2, 1), strict=True):
            _por(caminho, arvore, valor)
    return arvore


def _escrever_toml(arvore: dict[str, Any], destino: Path) -> Path:
    def render(no: dict[str, Any], prefixo: str = "") -> list[str]:
        linhas: list[str] = []
        escalares = {k: v for k, v in no.items() if not isinstance(v, dict)}
        if escalares and prefixo:
            linhas.append(f"[{prefixo}]")
        for chave, valor in escalares.items():
            linhas.append(f"{chave} = {json.dumps(valor, ensure_ascii=False)}")
        for chave, valor in no.items():
            if isinstance(valor, dict):
                linhas.extend(render(valor, f"{prefixo}.{chave}" if prefixo else chave))
        return linhas

    destino.write_text("\n".join(render(arvore)) + "\n", encoding="utf-8")
    return destino


def _carregar_com(tmp_path: Path, caminho: str, valor: Any, *, opcionais: bool = False):
    """Monta um TOML válido e troca UM campo."""
    arvore = montar(incluir_opcionais=opcionais or caminho in _OPCIONAIS)
    _por(caminho, arvore, valor)
    return carregar(_escrever_toml(arvore, tmp_path / "p.toml"))


# Campos cujo mínimo EFETIVO não é o declarado, porque uma regra cruzada o domina.
# `resultado_esperado.super_destaque` declara mínimo 1, mas a regra `maior_que` exige
# que ele supere o destaque, cujo mínimo também é 1 — logo o menor valor carregável é
# 2. Não é defeito do contrato: o `minimo` descreve o campo, a regra descreve o par, e
# o formulário precisa dos dois. Aqui só se pula a sonda de "aceita no limite".
_MINIMO_DOMINADO_POR_REGRA = frozenset(
    campo for regra in REGRAS if regra.tipo == "maior_que" for campo in regra.campos
)


# --------------------------------------------------------------------- contraprovas


def test_ha_contrato_a_conferir():
    """Contraprova com número EXATO. `>= 10` deixaria seis campos sumirem antes de a
    asserção acordar — e sumir campo é justamente como o formulário para de oferecer
    um parâmetro."""
    assert len(CAMPOS) == 16, f"o contrato mudou de tamanho: {len(CAMPOS)}"
    assert len(_OBRIGATORIOS) == 14
    assert len(REGRAS) == 3, f"as regras cruzadas mudaram: {len(REGRAS)}"


# ---------------------------------------------------------------------- forma


def test_o_toml_montado_DO_CONTRATO_carrega(tmp_path: Path):
    parametros = carregar(_escrever_toml(montar(), tmp_path / "p.toml"))
    assert parametros.resultado_esperado is None
    assert set(parametros.procedencia) == set(_OBRIGATORIOS)


def test_com_a_secao_opcional_tambem_carrega(tmp_path: Path):
    p = carregar(_escrever_toml(montar(incluir_opcionais=True), tmp_path / "p.toml"))
    assert p.resultado_esperado == {"super_destaque": 2, "destaque": 1}


def test_as_secoes_do_carregador_sao_os_obrigatorios_do_contrato():
    """A metade da trava que `ParametroAusente` deixou de fazer: chave que o carregador
    conhece e o contrato não descreve seria adotada em silêncio, e o formulário jamais
    a ofereceria. Comparação direta, sem sonda."""
    do_carregador = {f"{secao}.{chave}" for secao, chaves in SECOES.items() for chave in chaves}
    assert do_carregador == set(_OBRIGATORIOS)


@pytest.mark.parametrize("caminho", _OBRIGATORIOS)
def test_remover_campo_obrigatorio_cai_no_adotado_rotulado(tmp_path: Path, caminho: str):
    """Com a D-034, remover não é recusado: é adotado. O que se exige é que o valor
    seja EXATAMENTE o adotado que o contrato declara, e que a procedência diga isso
    — e que só ELE mude de rótulo."""
    arvore = montar(diferente_do_adotado=True)
    if caminho in _PESOS:
        for outro, valor in _pesos_sem(caminho).items():
            _por(outro, arvore, valor)
    partes = caminho.split(".")
    no = arvore
    for parte in partes[:-1]:
        no = no[parte]
    del no[partes[-1]]
    p = carregar(_escrever_toml(arvore, tmp_path / "p.toml"))
    assert p.efetivo[caminho] == _POR_CAMINHO[caminho].adotado
    assert p.procedencia[caminho] == ADOTADO
    assert caminho not in p.declarados_diferentes_do_adotado
    assert len(p.declarados_diferentes_do_adotado) == len(_OBRIGATORIOS) - 1


def test_todo_obrigatorio_declarado_diferente_e_rotulado_declarado(tmp_path: Path):
    p = carregar(_escrever_toml(montar(diferente_do_adotado=True), tmp_path / "p.toml"))
    assert set(p.procedencia.values()) == {"declarado"}
    assert p.declarados_diferentes_do_adotado == tuple(sorted(_OBRIGATORIOS))


def test_todo_obrigatorio_declarado_igual_ao_adotado_e_rotulado_adotado(tmp_path: Path):
    """Declarar o adotado não é escolha nova: a planilha não rotula PROVISÓRIO."""
    arvore: dict[str, Any] = {}
    for campo in CAMPOS:
        if campo.obrigatorio:
            _por(campo.caminho, arvore, campo.adotado)
    p = carregar(_escrever_toml(arvore, tmp_path / "p.toml"))
    assert set(p.procedencia.values()) == {ADOTADO}
    assert p.declarados_diferentes_do_adotado == ()


def test_campo_inventado_pelo_contrato_seria_recusado(tmp_path: Path):
    """A direção que sobreviveu à D-034: chave que o carregador não conhece é erro.
    Simula o contrato descrevendo um campo a mais."""
    arvore = montar()
    _por("portal.peso_inventado", arvore, 0)
    with pytest.raises(ParametroInvalido, match="peso_inventado"):
        carregar(_escrever_toml(arvore, tmp_path / "p.toml"))


# ------------------------------------------------------------------ valor: faixa

_COM_FAIXA = [
    c.caminho
    for c in CAMPOS
    if c.caminho not in _PESOS and (c.minimo is not None or c.maximo is not None)
]


@pytest.mark.parametrize("caminho", _COM_FAIXA)
def test_a_fronteira_declarada_e_a_do_carregador(tmp_path: Path, caminho: str):
    """Fecha a mutação "faixa errada", nas duas direções: contrato largo demais faz o
    formulário aceitar o que a rodada recusa; estreito demais faz recusar o que ela
    aceita. Usa `nextafter` em vez de um delta chutado — a fronteira é onde ela é."""
    campo = _POR_CAMINHO[caminho]
    inteiro = campo.tipo == "inteiro"

    if campo.minimo is not None:
        no_limite = int(campo.minimo) if inteiro else campo.minimo
        if campo.minimo_aberto:
            with pytest.raises(ParametroInvalido):
                _carregar_com(tmp_path, caminho, no_limite)
        elif caminho not in _MINIMO_DOMINADO_POR_REGRA:
            _carregar_com(tmp_path, caminho, no_limite)  # aceita
        abaixo = no_limite - 1 if inteiro else math.nextafter(campo.minimo, -math.inf)
        with pytest.raises(ParametroInvalido):
            _carregar_com(tmp_path, caminho, abaixo)

    if campo.maximo is not None:
        no_teto = int(campo.maximo) if inteiro else campo.maximo
        _carregar_com(tmp_path, caminho, no_teto)  # o teto é sempre fechado hoje
        acima = no_teto + 1 if inteiro else math.nextafter(campo.maximo, math.inf)
        with pytest.raises(ParametroInvalido):
            _carregar_com(tmp_path, caminho, acima)


def test_os_pesos_somam_cem_ou_sao_recusados(tmp_path: Path):
    """A regra cruzada `soma_igual` é a faixa efetiva dos pesos: aqui ela é
    exercida uma vez, já que a sonda individual não a alcança."""
    regra = next(r for r in REGRAS if r.tipo == "soma_igual")
    assert set(regra.campos) == set(_PESOS) and regra.valor == 100
    with pytest.raises(ParametroInvalido, match="somar 100"):
        _carregar_com(tmp_path, _PESOS[0], _PESOS_DIFERENTES[_PESOS[0]] + 1)


# ------------------------------------------------------------------- valor: tipo

# Os pesos ficam FORA da lista, não pulados no corpo: o passo "nenhum pode ser pulado"
# do CI reprova a build ao ver qualquer skip, e um teste que se auto-pula é ruído que
# vira vermelho na hora errada. A soma 100 domina a faixa deles de qualquer forma.
_NUMERICOS = [
    c.caminho for c in CAMPOS if c.tipo in ("inteiro", "numero") and c.caminho not in _PESOS
]


@pytest.mark.parametrize("caminho", _NUMERICOS)
def test_fracionario_e_aceito_se_e_so_se_o_tipo_for_numero(tmp_path: Path, caminho: str):
    """O furo mais perigoso, porque é MUDO. `_numero` aceita int e float, então marcar
    um campo fracionário como `inteiro` não quebra nada — só faz o formulário proibir
    o valor certo, e o dono digitar outro. Aqui a marcação passa a ter consequência."""
    campo = _POR_CAMINHO[caminho]
    minimo = campo.minimo if campo.minimo is not None else 0.0
    maximo = campo.maximo if campo.maximo is not None else minimo + 2.0
    fracionario = (minimo + maximo) / 2
    if fracionario == int(fracionario):
        fracionario += 0.5 if fracionario + 0.5 <= maximo else -0.5
    if campo.tipo == "inteiro":
        with pytest.raises(ParametroInvalido):
            _carregar_com(tmp_path, caminho, fracionario)
    else:
        _carregar_com(tmp_path, caminho, fracionario)


@pytest.mark.parametrize("caminho", [c.caminho for c in CAMPOS if c.tipo == "inteiro"])
def test_booleano_nao_passa_por_inteiro(tmp_path: Path, caminho: str):
    """`True` é `int` em Python; um formulário que mande `true` num campo inteiro
    precisa ser recusado, não lido como 1."""
    with pytest.raises(ParametroInvalido):
        _carregar_com(tmp_path, caminho, True)


# ----------------------------------------------------------------- valor: escolhas

_ESCOLHAS = [(c.caminho, e) for c in CAMPOS if c.escolhas for e in c.escolhas]


@pytest.mark.parametrize(("caminho", "escolha"), _ESCOLHAS)
def test_toda_escolha_declarada_e_aceita(tmp_path: Path, caminho: str, escolha: str):
    """A sonda antiga só visitava a primeira opção: da segunda em diante o contrato
    era decorativo, e o formulário podia oferecer uma forma que o carregador removeu
    de propósito. Aqui cada opção é exercida."""
    _carregar_com(tmp_path, caminho, escolha)


@pytest.mark.parametrize("caminho", [c.caminho for c in CAMPOS if c.escolhas])
def test_escolha_fora_da_lista_e_recusada(tmp_path: Path, caminho: str):
    with pytest.raises(ParametroInvalido):
        _carregar_com(tmp_path, caminho, "nao-existe-de-proposito")


# ---------------------------------------------------------- resultado_esperado (nº 14)


def test_meio_declarado_continua_sendo_ausencia(tmp_path: Path):
    """O ÚNICO `ParametroAusente` que sobrou: a régua nº 14 é indivisível."""
    arvore = montar()
    _por(_OPCIONAIS[0], arvore, 3)
    with pytest.raises(ParametroAusente, match="nº 14"):
        carregar(_escrever_toml(arvore, tmp_path / "p.toml"))


# ------------------------------------------------------------------- integridade


def test_toda_pendencia_conhecida_alcanca_algum_campo():
    """`PENDENTE_DE` é a fonte dos rótulos. Se uma chave de lá deixar de casar com
    algum campo — renomeada, por exemplo —, `_pendencia` devolve None em silêncio e o
    formulário fica mudo sobre qual decisão o dono está respondendo."""
    caminhos = {c.caminho for c in CAMPOS}
    for chave in PENDENTE_DE:
        alcanca = any(c == chave or c.startswith(f"{chave}.") for c in caminhos)
        assert alcanca, f"a pendência {chave!r} não rotula campo nenhum do contrato"


def test_so_a_regua_nula_carrega_pendencia():
    """Os adotados (D-034) não são pendentes: rotular um deles com "nº N" diria ao
    dono que ele está respondendo uma decisão já tomada."""
    com_pendencia = {c.caminho: c.pendencia for c in CAMPOS if c.pendencia}
    assert com_pendencia == dict(PENDENTE_DE)
    assert set(com_pendencia) == set(_OPCIONAIS)


def test_toda_regra_aponta_para_campos_que_existem():
    caminhos = {c.caminho for c in CAMPOS}
    for regra in REGRAS:
        orfas = set(regra.campos) - caminhos
        assert not orfas, f"regra {regra.tipo!r} aponta para campos inexistentes: {orfas}"


def test_toda_regra_e_executavel_pelo_formulario():
    """Prosa não é executável. Sem `tipo`, o console reimplementaria a semântica em
    TypeScript a partir de uma string — a duplicação que este módulo existe para
    evitar. `soma_igual` também precisa do alvo."""
    for regra in REGRAS:
        assert regra.tipo in ("soma_igual", "todos_ou_nenhum", "maior_que")
        assert len(regra.campos) >= 2, f"regra {regra.tipo!r} cruza menos de dois campos"
        if regra.tipo == "soma_igual":
            assert regra.valor is not None, "soma_igual sem alvo"


def test_todo_campo_tem_ajuda_e_faixa_coerente():
    for campo in CAMPOS:
        assert campo.ajuda.strip(), f"{campo.caminho} sem ajuda"
        if campo.minimo is not None and campo.maximo is not None:
            assert campo.minimo < campo.maximo, f"{campo.caminho}: faixa invertida"
        if campo.tipo == "escolha":
            assert campo.escolhas, f"{campo.caminho}: escolha sem opções"
        else:
            assert campo.escolhas is None, f"{campo.caminho}: opções em campo não-escolha"


def test_todo_campo_numerico_tem_unidade_e_efeito():
    """Toda unidade é concreta (dias, pontos de 100, %, corretores, leads): é o que
    faz o campo ser julgável sem a Spec ao lado. Escolhas não têm unidade — nem
    `se_aumentar`, porque não há "mais" numa lista fechada."""
    for campo in CAMPOS:
        if campo.tipo == "escolha":
            assert campo.unidade == "", f"{campo.caminho}: escolha com unidade"
            assert campo.se_aumentar == "", f"{campo.caminho}: escolha com se_aumentar"
        else:
            assert campo.unidade.strip(), f"{campo.caminho} sem unidade"
            assert campo.se_aumentar.strip(), f"{campo.caminho} sem se_aumentar"
            assert "0 a 1" not in campo.unidade, f"{campo.caminho}: escala abstrata"


def test_adotado_do_campo_e_o_de_config_adotados():
    """`adotado` nunca é redigitado no contrato: vem de `ADOTADOS`. Obrigatório ⇔ tem
    adotado; opcional ⇔ segue NULO (os dois campos do nº 14)."""
    for campo in CAMPOS:
        assert campo.adotado == ADOTADOS.get(campo.caminho), campo.caminho
        assert (campo.adotado is not None) == campo.obrigatorio, campo.caminho
    assert {c.caminho for c in CAMPOS if c.adotado is not None} == set(ADOTADOS)


def test_funcao_so_tem_tres_valores():
    """Excludente, classificatório, decisório: as três funções do modelo "o banco
    manda, o portal classifica". Uma quarta seria taxonomia nova sem decisão."""
    assert get_args(Funcao) == ("excludente", "classificatorio", "decisorio")
    assert {g.funcao for g in GRUPOS} == set(get_args(Funcao))


# ----------------------------------------------------------------- cópia do console


def test_o_json_commitado_no_console_esta_em_dia():
    """Compara BYTE A BYTE, como o passo de CI faz. Comparando JSON parseado, uma
    diferença de espaço em branco deixaria o teste verde e o CI vermelho — a divisão
    que faz alguém desconfiar do portão em vez do arquivo.

    Este teste detecta cópia VELHA, e só isso: ele dispara em qualquer mudança do
    contrato, certa ou errada, e a correção documentada dele é regerar. Não confunda
    com verificação de conteúdo — quem faz isso é a bateria de sondas acima."""
    assert JSON_DO_CONSOLE.is_file(), f"{JSON_DO_CONSOLE} não existe — gere com rodada-contrato"
    esperado = json.dumps(contrato(), ensure_ascii=False, indent=2) + "\n"
    assert JSON_DO_CONSOLE.read_text(encoding="utf-8") == esperado, (
        "o contrato mudou e o JSON do console não acompanhou. Regere com "
        "`uv run rodada-contrato > console/lib/contrato-parametros.json`"
    )


def test_o_json_commitado_carrega_unidade_e_adotado():
    """O console lê o JSON, não o Python: os campos novos precisam ter chegado lá."""
    saida = json.loads(JSON_DO_CONSOLE.read_text(encoding="utf-8"))
    por_caminho = {c["caminho"]: c for c in saida["campos"]}
    assert por_caminho["portal.peso_visualizacoes"]["adotado"] == 0
    assert por_caminho["portal.cobertura_minima"]["unidade"] == "%"
    assert por_caminho["resultado_esperado.destaque"]["adotado"] is None
    assert "externo.desempenho.forma" not in por_caminho


def test_o_comando_emite_o_contrato(capsys: pytest.CaptureFixture[str]):
    """Chama `main()` direto em vez de `subprocess uv run`: o wiring do console script
    já é coberto duas vezes pelo CI (a fumaça do `--help` e o passo de diff), e
    aninhar `uv run` dentro da suíte a prenderia ao gerenciador de pacotes."""
    assert main_contrato([]) == 0
    assert json.loads(capsys.readouterr().out) == contrato()


# --- B1: a taxonomia do formulário -------------------------------------------------


def test_os_grupos_sao_uma_sequencia_unica_e_contigua():
    ordens = [g.ordem for g in GRUPOS]
    assert ordens == list(range(1, len(GRUPOS) + 1)), "ordem = 1..N, na ordem da tupla"
    assert len({g.id for g in GRUPOS}) == len(GRUPOS)


def test_todo_campo_aponta_para_um_grupo_que_existe():
    ids = {g.id for g in GRUPOS}
    for c in CAMPOS:
        assert c.grupo in ids, c.caminho


def test_um_campo_com_grupo_inexistente_e_recusado_na_construcao():
    from config.contrato import _campo

    with pytest.raises(ValueError, match="grupo inexistente"):
        _campo("x.y", "numero", "ajuda", grupo="nao_existe")


def test_nenhum_grupo_e_vazio():
    """Cada seção mostra ALGO: campos, regras fixas ou pendentes sem campo. Uma seção
    sem nada seria um título sem explicação — o defeito que o dono apontou."""
    com_campo = {c.grupo for c in CAMPOS}
    for g in GRUPOS:
        assert g.explicacao.strip(), g.id
        assert g.id in com_campo or g.fixos_no_codigo or g.pendentes_sem_campo, g.id


def test_os_pendentes_sem_campo_nao_repetem_os_que_tem_campo():
    """O número de um parâmetro pendente aparece ou como campo (via `pendencia`) ou como
    `pendentes_sem_campo` — nunca nos dois, e nunca em dois grupos. Os nº 3, 5 e 7
    foram adotados (D-034) e os nº 12 e 13 deixaram de existir: nenhum deles é mais
    pendente, e listá-los diria ao dono que falta decidir o que já foi decidido."""
    com_campo: set[int] = set()
    for c in CAMPOS:
        if c.pendencia:
            m = re.match(r"nº (\d+)", c.pendencia)
            assert m, c.pendencia
            com_campo.add(int(m.group(1)))
    sem_campo: list[int] = [n for g in GRUPOS for n in g.pendentes_sem_campo]
    assert len(sem_campo) == len(set(sem_campo)), "número em dois grupos"
    assert not com_campo & set(sem_campo), com_campo & set(sem_campo)
    assert com_campo == {14}
    assert com_campo | set(sem_campo) == {2, 4, 6, 8, 9, 10, 11, 14, 15}


def test_o_contrato_emite_os_grupos_na_ordem():
    saida = contrato()
    assert [g["id"] for g in saida["grupos"]] == [g.id for g in GRUPOS]
    assert all("grupo" in c for c in saida["campos"])
