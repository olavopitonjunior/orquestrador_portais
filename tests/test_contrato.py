"""O contrato do formulário não pode divergir do validador da rodada.

A trava tem DUAS metades, e a primeira versão deste arquivo só tinha uma.

**Forma** — monta-se um TOML *a partir do contrato* e exige-se que
`config.parametros.carregar()` o aceite. Isso prova as duas direções de uma vez,
por causa das regras do próprio carregador: contrato que **esquece** um campo cai
em `ParametroAusente` (nenhum default); contrato que **inventa** um campo cai em
`ParametroInvalido` (nenhuma chave desconhecida, em todos os níveis).

**Valor** — a ida e volta acima visita UM ponto interior por campo, então nada
nela enxerga `minimo`, `maximo`, `minimo_aberto`, `tipo` ou `escolhas`. Uma
auditoria hostil mutou os quatro e a suíte ficou verde nas quatro vezes. O pior
deles não é a faixa: é o `tipo`. `_numero` aceita `int` e `float`, então declarar
`inteiro` num campo fracionário **não erra em lugar nenhum** — o formulário
proíbe 0,35 numa intensidade de penalidade, o dono digita 0 ou 1 no lugar, o
carregador aceita, e a rodada decide 6.970 posições pagas com um número que ele
não queria mas que o formulário obrigou. Daí a bateria de sondas abaixo, que
afirma **aceita E recusa** em cada fronteira.

E note a direção que passa despercebida: contrato mais ESTREITO que o carregador
é tão ruim quanto mais largo, e igualmente invisível — um `maximo` apertado faria
o formulário recusar um valor perfeitamente legal.

Os valores aqui são SONDAS: existem para provar fronteiras, e nada mais. Não são
sugestão, não são default, e não viajam para lugar nenhum.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import pytest

from config.contrato import CAMPOS, GRUPOS, PENDENTE_DE, REGRAS, Campo, contrato
from config.parametros import ParametroAusente, ParametroInvalido, carregar
from executar.contrato import main as main_contrato

RAIZ = Path(__file__).resolve().parent.parent
JSON_DO_CONSOLE = RAIZ / "console" / "lib" / "contrato-parametros.json"

_POR_CAMINHO = {c.caminho: c for c in CAMPOS}
# Os oito pesos não têm fronteira individual sondável: a regra de soma 100 domina, e
# mexer num deles quebra a soma antes de a faixa ser exercida. Quem os cobre é a regra
# cruzada, e a ida e volta prova que existem e são inteiros.
_PESOS = tuple(c.caminho for c in CAMPOS if c.caminho.startswith("pesos."))
_OPCIONAIS = tuple(c.caminho for c in CAMPOS if not c.obrigatorio)
_FORMAS_DESEMPENHO = _POR_CAMINHO["externo.desempenho.forma"].escolhas or ()


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


def _pesos_validos() -> dict[str, dict[str, int]]:
    fatores = ("semelhanca_perfil", "leads_positivo", "desempenho_proprio", "produtividade_gestor")
    return {nivel: dict.fromkeys(fatores, 25) for nivel in ("super_destaque", "destaque")}


def _por(caminho: str, arvore: dict[str, Any], valor: Any) -> None:
    partes = caminho.split(".")
    no = arvore
    for parte in partes[:-1]:
        no = no.setdefault(parte, {})
    no[partes[-1]] = valor


def montar(*, incluir_opcionais: bool = False, forma_desempenho: str | None = None) -> dict:
    """Monta a árvore do TOML A PARTIR DO CONTRATO — nunca de uma lista paralela."""
    forma = forma_desempenho or _FORMAS_DESEMPENHO[0]
    arvore: dict[str, Any] = {}
    escolhido = {"externo.desempenho.forma": forma}
    for campo in CAMPOS:
        if not campo.obrigatorio and not incluir_opcionais:
            continue
        if campo.exige is not None:
            alvo, esperado = campo.exige
            if escolhido.get(alvo) != esperado:
                continue
        _por(campo.caminho, arvore, escolhido.get(campo.caminho, _sonda(campo)))
    arvore["pesos"] = _pesos_validos()
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
    """Monta um TOML válido e troca UM campo. Respeita o `exige` do campo: um campo
    condicional só existe quando o campo que o governa tem o valor certo, e injetá-lo
    fora dessa condição produz "chave desconhecida" — erro real, mas do teste, não do
    contrato."""
    campo = _POR_CAMINHO[caminho]
    forma = campo.exige[1] if campo.exige is not None else None
    arvore = montar(incluir_opcionais=opcionais or caminho in _OPCIONAIS, forma_desempenho=forma)
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
    """Contraprova com número EXATO. `>= 16` deixaria seis campos sumirem antes de a
    asserção acordar — e sumir campo é justamente como o formulário para de oferecer
    um parâmetro pendente."""
    assert len(CAMPOS) == 22, f"o contrato mudou de tamanho: {len(CAMPOS)}"
    assert len(REGRAS) == 4, f"as regras cruzadas mudaram: {len(REGRAS)}"


# ---------------------------------------------------------------------- forma


@pytest.mark.parametrize("forma", _FORMAS_DESEMPENHO)
def test_o_toml_montado_DO_CONTRATO_carrega(tmp_path: Path, forma: str):
    """Nas três formas de desempenho — cada uma exige um conjunto diferente de campos
    condicionais, e é aí que um contrato desatualizado quebraria."""
    parametros = carregar(_escrever_toml(montar(forma_desempenho=forma), tmp_path / "p.toml"))
    assert parametros.rotulo == "PROVISÓRIO"
    assert parametros.resultado_esperado is None


def test_com_a_secao_opcional_tambem_carrega(tmp_path: Path):
    p = carregar(_escrever_toml(montar(incluir_opcionais=True), tmp_path / "p.toml"))
    assert p.resultado_esperado == {"super_destaque": 2, "destaque": 1}


@pytest.mark.parametrize(
    "caminho", [c.caminho for c in CAMPOS if c.obrigatorio and c.exige is None]
)
def test_remover_campo_obrigatorio_e_recusado(tmp_path: Path, caminho: str):
    arvore = montar()
    partes = caminho.split(".")
    no = arvore
    for parte in partes[:-1]:
        no = no[parte]
    del no[partes[-1]]
    with pytest.raises((ParametroAusente, ParametroInvalido)):
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


# ----------------------------------------------------------------- valor: escolhas

_ESCOLHAS = [(c.caminho, e) for c in CAMPOS if c.escolhas for e in c.escolhas]


@pytest.mark.parametrize(("caminho", "escolha"), _ESCOLHAS)
def test_toda_escolha_declarada_e_aceita(tmp_path: Path, caminho: str, escolha: str):
    """A sonda antiga só visitava a primeira opção: da segunda em diante o contrato
    era decorativo, e o formulário podia oferecer uma forma que o carregador removeu
    de propósito. Aqui cada opção é exercida."""
    if caminho == "externo.desempenho.forma":
        carregar(_escrever_toml(montar(forma_desempenho=escolha), tmp_path / "p.toml"))
    else:
        _carregar_com(tmp_path, caminho, escolha)


@pytest.mark.parametrize("caminho", [c.caminho for c in CAMPOS if c.escolhas])
def test_escolha_fora_da_lista_e_recusada(tmp_path: Path, caminho: str):
    with pytest.raises(ParametroInvalido):
        _carregar_com(tmp_path, caminho, "nao-existe-de-proposito")


# ------------------------------------------------------------------- integridade


def test_toda_pendencia_conhecida_alcanca_algum_campo():
    """`PENDENTE_DE` é a fonte dos rótulos. Se uma chave de lá deixar de casar com
    algum campo — renomeada, por exemplo —, `_pendencia` devolve None em silêncio e o
    formulário fica mudo sobre qual decisão o dono está respondendo."""
    caminhos = {c.caminho for c in CAMPOS}
    for chave in PENDENTE_DE:
        alcanca = any(c == chave or c.startswith(f"{chave}.") for c in caminhos)
        assert alcanca, f"a pendência {chave!r} não rotula campo nenhum do contrato"


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
    `pendentes_sem_campo` — nunca nos dois, e nunca em dois grupos."""
    com_campo: set[int] = set()
    for c in CAMPOS:
        if c.pendencia:
            m = re.match(r"nº (\d+)", c.pendencia)
            assert m, c.pendencia
            com_campo.add(int(m.group(1)))
    sem_campo: list[int] = [n for g in GRUPOS for n in g.pendentes_sem_campo]
    assert len(sem_campo) == len(set(sem_campo)), "número em dois grupos"
    assert not com_campo & set(sem_campo), com_campo & set(sem_campo)
    # Os catorze pendentes da tabela do CLAUDE.md (nº 2 a nº 15), todos alcançados.
    assert com_campo | set(sem_campo) == set(range(2, 16))


def test_o_contrato_emite_os_grupos_na_ordem():
    saida = contrato()
    assert [g["id"] for g in saida["grupos"]] == [g.id for g in GRUPOS]
    assert all("grupo" in c for c in saida["campos"])
