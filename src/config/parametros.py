"""Carregador dos parâmetros da rodada. **Nenhum valor mora aqui.**

Treze dos quatorze parâmetros (D-004, D-017) são NULOS: o dono da decisão ainda não
os definiu, e o CLAUDE.md proíbe preenchê-los com valor inventado. A rodada de
sexta, porém, não calcula nada sem eles. Este módulo é a saída honesta dessa
tensão: os valores vivem FORA do repositório, num arquivo que o dono escreve, e
o código apenas os **exige, valida e rotula**.

Três regras que este módulo executa (não apenas descreve):

1. **Nenhum default.** Chave ausente é erro nomeado — nunca um valor de
   conveniência. Um parâmetro que falta interrompe a rodada; não a deixa rodar
   com um número que ninguém escolheu.
2. **Nenhuma chave desconhecida.** `decaimeto` (typo) não é ignorado em
   silêncio: é erro. Sem isso, o typo viraria "chave ausente" numa mensagem
   confusa e o valor digitado seria descartado sem aviso.
3. **Tudo que entra é PROVISÓRIO.** Carregar não é adotar. `ParametrosDaRodada`
   carrega a origem e o rótulo para a planilha declarar de onde vieram os
   números — a adoção exige decisão do dono e entrada no CHANGELOG.

Os dois parâmetros que são FORMA e não número (`decaimento_janela` do nº 3 e a
composição do sinal F3) não aceitam expressão arbitrária: escolhem-se numa
lista fechada de formas nomeadas. Expressão livre num arquivo de configuração
seria código executável fora da revisão — e o invariante 5 (mesma entrada,
mesma lista) deixaria de ser verificável.
"""

from __future__ import annotations

import math
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dados.coletor_externo import CLIQUES, DesempenhoAnuncio, ParametrosExterno
from dominio.penalidades import IntensidadesPenalidade
from dominio.ranking import PesosNivel
from piloto.decisao import ParametrosDecisao
from piloto.semelhanca import ParametrosSemelhanca


class ParametroAusente(ValueError):
    """Falta um parâmetro pendente. A rodada não prossegue — não há default."""


class ParametroInvalido(ValueError):
    """Valor presente mas fora do contrato (faixa, tipo ou forma desconhecida)."""


# Qual pendente da tabela do CLAUDE.md cada chave atende. Serve à mensagem de
# erro: quem opera a rodada precisa saber QUAL decisão do dono está faltando,
# não só qual chave TOML falta.
#
# Indexado pelo CAMINHO COMPLETO, sem casamento por chave nua: `pesos` só rotula
# `nº 12` na raiz. Casar pela última chave faria qualquer `pesos` futuro em outro
# contexto herdar o rótulo errado — um erro que ninguém conferiria, porque a
# mensagem continuaria plausível.
PENDENTE_DE: Mapping[str, str] = {
    "semelhanca.decaimento": "nº 13 (decaimento do peso por dimensão do F1)",
    "intensidades": "nº 3 (intensidade das três penalidades)",
    "intensidades.janela_sem_resultado": "nº 3 (intensidade das três penalidades)",
    "intensidades.sem_avaliacao_por_categoria": "nº 3 (intensidade das três penalidades)",
    "intensidades.sem_lead_180d": "nº 3 (intensidade das três penalidades)",
    "decaimento_janela": "nº 3 (decaimento da penalidade por janela)",
    "decaimento_janela.forma": "nº 3 (decaimento da penalidade por janela)",
    "decaimento_janela.razao": "nº 3 (decaimento da penalidade por janela)",
    "pesos": "nº 12 (pesos dos quatro fatores do ranking, por nível)",
    "pesos.super_destaque": "nº 12 (pesos dos quatro fatores do ranking, por nível)",
    "pesos.destaque": "nº 12 (pesos dos quatro fatores do ranking, por nível)",
    "externo.limiar_amarracao": "nº 7 (limiar mínimo de taxa de amarração)",
    "externo.idade_maxima_dias": "nº 5 (idade máxima da coleta externa de reserva)",
    "resultado_esperado.super_destaque": "nº 14 (resultado esperado por nível, §6.4)",
    "resultado_esperado.destaque": "nº 14 (resultado esperado por nível, §6.4)",
}


@dataclass(frozen=True)
class ParametrosDaRodada:
    """O que o ponto de entrada injeta no grafo, mais a procedência.

    `origem` e `rotulo` existem para a planilha: a Spec §3 exige que os
    provisórios apareçam rotulados, e um número sem procedência numa planilha
    aprovada é indistinguível de um número adotado.

    `declarado` é o conteúdo do arquivo **verbatim**, para o Registro gravar o
    que foi de fato declarado — inclusive as duas FORMAS, que viram função e
    não sobrevivem a `ParametrosDecisao`. Sem ele, o Registro guardaria números
    sem a forma que os aplicou, e o invariante 5 (mesma entrada, mesma lista)
    deixaria de ser auditável a partir do Registro.
    """

    decisao: ParametrosDecisao
    externo: ParametrosExterno
    origem: str
    declarado: Mapping[str, Any]
    # Parâmetro nº 14 (D-022), por nível. `None` = o dono ainda não o definiu, e a
    # rodada DECLARA isso: a penalidade §6.4 não incide, e não incidir por falta de
    # limiar não é o mesmo que passar no critério.
    #
    # É a única SEÇÃO opcional do arquivo, e a exceção é deliberada. A regra "nenhum
    # default" existe para que nenhum VALOR seja inventado; ausência de seção não é
    # valor, é o estado nulo que a D-022 declarou — e ele vira limitação visível na
    # planilha, não silêncio. Dentro da seção não há opcional: quem a declara declara
    # os dois níveis.
    resultado_esperado: Mapping[str, int] | None = None
    rotulo: str = "PROVISÓRIO"


# --- formas nomeadas ----------------------------------------------------------


def _decaimento_geometrico(razao: float) -> Callable[[int], float]:
    def decaimento(ciclos: int) -> float:
        return float(razao**ciclos)

    return decaimento


def _f3_visualizacoes(anuncio: DesempenhoAnuncio) -> float:
    return float(anuncio.visualizacoes)


def _f3_nota(quando_ausente: float) -> Callable[[DesempenhoAnuncio], float]:
    """`nota` é opcional na coleta; o valor para o anúncio SEM nota é escolha do
    dono, declarada no arquivo. Sem essa declaração, o código escolheria por ele
    — e um zero implícito puniria o anúncio pela ausência do dado."""

    def compor(anuncio: DesempenhoAnuncio) -> float:
        return float(anuncio.nota) if anuncio.nota is not None else float(quando_ausente)

    return compor


def _f3_cliques_do_tipo(tipo: str) -> Callable[[DesempenhoAnuncio], float]:
    """Um tipo de clique, nomeado. Os cliques NUNCA são somados entre tipos
    (contrato do coletor): tipos diferentes medem intenções diferentes."""

    def compor(anuncio: DesempenhoAnuncio) -> float:
        return float(anuncio.cliques.get(tipo, 0))

    return compor


# --- leitura ------------------------------------------------------------------


def _exigir(bruto: Mapping[str, Any], chave: str, contexto: str) -> Any:
    if chave not in bruto:
        caminho = f"{contexto}.{chave}" if contexto else chave
        pendente = PENDENTE_DE.get(caminho)
        sufixo = f" — parâmetro pendente {pendente}" if pendente else ""
        raise ParametroAusente(f"falta `{caminho}`{sufixo}")
    return bruto[chave]


def _so_estas_chaves(bruto: Mapping[str, Any], esperadas: set[str], contexto: str) -> None:
    sobrando = set(bruto) - esperadas
    if sobrando:
        raise ParametroInvalido(
            f"chave(s) desconhecida(s) em `{contexto or 'raiz'}`: {sorted(sobrando)}. "
            f"Esperadas: {sorted(esperadas)}. Um nome digitado errado é recusado aqui — "
            "aceitá-lo descartaria o valor em silêncio."
        )


def _numero(valor: Any, contexto: str) -> float:
    if isinstance(valor, bool) or not isinstance(valor, int | float):
        raise ParametroInvalido(f"`{contexto}` deve ser número, veio {type(valor).__name__}")
    # `nan` e `inf` são literais VÁLIDOS em TOML e passam por qualquer comparação de
    # faixa (`nan < 0` é falso). Sem esta guarda eles chegavam ao domínio, que os
    # rejeita com `ValueError` cru — exceção que o `main` não captura: a rodada saía
    # com o código de FALHA DE ESCRITA e um traceback completo no stdout.
    if not math.isfinite(valor):
        raise ParametroInvalido(f"`{contexto}` precisa ser finito, veio {valor}")
    return float(valor)


def _inteiro(valor: Any, contexto: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ParametroInvalido(f"`{contexto}` deve ser inteiro, veio {type(valor).__name__}")
    return valor


def _tabela(bruto: Mapping[str, Any], chave: str, contexto: str) -> Mapping[str, Any]:
    valor = _exigir(bruto, chave, contexto)
    if not isinstance(valor, dict):
        caminho = f"{contexto}.{chave}" if contexto else chave
        raise ParametroInvalido(f"`{caminho}` deve ser uma tabela [{caminho}]")
    return valor


def _faixa_da_dataclass[T](construir: Callable[[], T], contexto: str) -> T:
    """Reergue a validação de faixa da dataclass como erro de PARÂMETRO.

    O `try` cobre SÓ a construção. Envolvendo também as leituras, um
    `ParametroAusente` (que também é `ValueError`) era reclassificado como
    `ParametroInvalido` — e a regra 1 deste módulo, "chave ausente é erro nomeado",
    deixava de valer justamente onde o `try` era largo demais.
    """
    try:
        return construir()
    except ValueError as e:
        raise ParametroInvalido(f"{contexto}: {e}") from e


def _ler_semelhanca(bruto: Mapping[str, Any]) -> ParametrosSemelhanca:
    _so_estas_chaves(bruto, {"desconto_fragil", "decaimento"}, "semelhanca")
    fragil = _numero(_exigir(bruto, "desconto_fragil", "semelhanca"), "semelhanca.desconto_fragil")
    decaimento = _numero(_exigir(bruto, "decaimento", "semelhanca"), "semelhanca.decaimento")
    return _faixa_da_dataclass(
        lambda: ParametrosSemelhanca(desconto_fragil=fragil, decaimento=decaimento), "semelhanca"
    )


def _ler_intensidades(bruto: Mapping[str, Any]) -> IntensidadesPenalidade:
    # TUPLA, não set: o dict comprehension abaixo itera sobre ela, e a ordem de um
    # set varia entre processos (PYTHONHASHSEED). Com duas chaves faltando, o mesmo
    # arquivo produzia mensagens de erro diferentes a cada execução — os valores não
    # mudavam, mas quem opera via dois diagnósticos para um único problema.
    campos = ("janela_sem_resultado", "sem_avaliacao_por_categoria", "sem_lead_180d")
    _so_estas_chaves(bruto, set(campos), "intensidades")
    valores = {c: _numero(_exigir(bruto, c, "intensidades"), f"intensidades.{c}") for c in campos}
    for nome, valor in valores.items():
        if valor < 0:
            raise ParametroInvalido(f"intensidades.{nome} negativa: {valor} — viraria bônus")
    return _faixa_da_dataclass(lambda: IntensidadesPenalidade(**valores), "intensidades")


def _ler_decaimento_janela(bruto: Mapping[str, Any]) -> Callable[[int], float]:
    """Uma forma só: geométrica.

    Havia uma segunda forma nomeada, `sem_decaimento`, justificada como "o
    caso-limite". O argumento não se sustentava: `geometrica` com `razao = 1.0` já
    produz fator 1.0 em todo ciclo, então a forma nomeada era um segundo nome para
    um caso que esta já admite. Razão 1.0 continua expressável — e o runner
    DECLARA a divergência com a Spec §6.4 ("decai ao longo dos ciclos") quando ela
    é escolhida, em vez de o código afirmar que não há divergência.
    """
    forma = _exigir(bruto, "forma", "decaimento_janela")
    if forma == "geometrica":
        _so_estas_chaves(bruto, {"forma", "razao"}, "decaimento_janela")
        razao = _numero(_exigir(bruto, "razao", "decaimento_janela"), "decaimento_janela.razao")
        if not 0.0 < razao <= 1.0:
            # Fora disso o domínio ergueria erro no MEIO da rodada, imóvel a
            # imóvel; aqui erra antes de tocar o banco.
            raise ParametroInvalido(
                f"decaimento_janela.razao fora de (0, 1]: {razao} — o fator precisa "
                "ficar em [0, 1] para todo ciclo (Spec §6.4: decair não amplifica)"
            )
        return _decaimento_geometrico(razao)
    raise ParametroInvalido(
        f"forma de decaimento_janela desconhecida: {forma!r}. "
        "Forma aceita: 'geometrica' (com razao em (0, 1]; razao = 1.0 não decai, e a "
        "rodada declara essa divergência com a Spec §6.4 na planilha)."
    )


def _ler_pesos(bruto: Mapping[str, Any], nivel: str) -> PesosNivel:
    campos = ("semelhanca_perfil", "leads_positivo", "desempenho_proprio", "produtividade_gestor")
    contexto = f"pesos.{nivel}"
    _so_estas_chaves(bruto, set(campos), contexto)  # tupla acima: ver `_ler_intensidades`
    valores = {c: _inteiro(_exigir(bruto, c, contexto), f"{contexto}.{c}") for c in campos}
    return _faixa_da_dataclass(lambda: PesosNivel(**valores), contexto)


def _ler_desempenho(bruto: Mapping[str, Any]) -> Callable[[DesempenhoAnuncio], float]:
    forma = _exigir(bruto, "forma", "externo.desempenho")
    if forma == "visualizacoes":
        _so_estas_chaves(bruto, {"forma"}, "externo.desempenho")
        return _f3_visualizacoes
    if forma == "nota":
        _so_estas_chaves(bruto, {"forma", "quando_ausente"}, "externo.desempenho")
        return _f3_nota(
            _numero(
                _exigir(bruto, "quando_ausente", "externo.desempenho"),
                "externo.desempenho.quando_ausente",
            )
        )
    if forma == "cliques_do_tipo":
        _so_estas_chaves(bruto, {"forma", "tipo"}, "externo.desempenho")
        tipo = _exigir(bruto, "tipo", "externo.desempenho")
        if tipo not in CLIQUES:
            # Sem esta guarda, um tipo inexistente devolvia 0 para TODO anúncio: F3
            # uniformemente zerado, `prontos["externo"] = True`, rodada COMPLETA e
            # nenhuma limitação declarada. Exatamente o silêncio que a regra 2 deste
            # módulo existe para impedir.
            raise ParametroInvalido(
                f"externo.desempenho.tipo desconhecido: {tipo!r}. "
                f"Tipos de clique que a coleta traz: {sorted(CLIQUES)}"
            )
        return _f3_cliques_do_tipo(tipo)
    raise ParametroInvalido(
        f"forma de externo.desempenho desconhecida: {forma!r}. Formas aceitas: "
        "'visualizacoes', 'nota' (com quando_ausente), 'cliques_do_tipo' (com tipo). "
        "Somar tipos de clique não é uma forma: o coletor nunca os soma."
    )


def _ler_resultado_esperado(bruto: Mapping[str, Any] | None) -> Mapping[str, int] | None:
    """O nº 14, se o dono o declarou. Os DOIS níveis ou nenhum.

    Meio-declarado seria pior que nulo: metade das janelas julgada por um limiar e a
    outra metade sem julgamento, com a planilha declarando "limiar não definido" para
    uma rodada que penalizou parte do estoque.
    """
    if bruto is None:
        return None
    niveis = ("super_destaque", "destaque")
    _so_estas_chaves(bruto, set(niveis), "resultado_esperado")
    valores = {
        n: _inteiro(_exigir(bruto, n, "resultado_esperado"), f"resultado_esperado.{n}")
        for n in niveis
    }
    for nivel, valor in valores.items():
        if valor < 1:
            # Zero desligaria a penalidade em SILÊNCIO: `leads >= 0` é sempre
            # verdadeiro, a coluna sairia 0,0 para todos e nenhuma limitação seria
            # emitida (a de "limiar não definido" só sai quando ele é nulo). A D-022
            # é explícita: "nunca 0,0 silencioso — um imóvel sem penalidade por falta
            # de limiar não é um imóvel que passou no critério". Para desligar a
            # penalidade, omita a seção; aí a rodada declara que o limiar é nulo.
            raise ParametroInvalido(
                f"resultado_esperado.{nivel} = {valor}: o limiar é a contagem de leads "
                "que a janela precisa ter gerado, e precisa ser ao menos 1. Zero "
                "desligaria a penalidade sem nenhuma declaração na planilha — para "
                "deixá-la nula, OMITA a seção [resultado_esperado]"
            )
    if valores["super_destaque"] <= valores["destaque"]:
        # PRD, "Rotação e penalidade": "Resultado suficiente é proporcional ao tipo de
        # posição: super destaque exige entrega SUPERIOR à de destaque". Sem esta
        # guarda, um arquivo com a régua invertida carregaria em silêncio e a rodada
        # penalizaria o super destaque menos que o destaque — o oposto do documento.
        raise ParametroInvalido(
            f"resultado_esperado.super_destaque ({valores['super_destaque']}) precisa ser "
            f"MAIOR que destaque ({valores['destaque']}): o PRD fixa que o resultado "
            "esperado é proporcional ao nível, e o super destaque exige entrega superior"
        )
    return valores


def _ler_externo(bruto: Mapping[str, Any]) -> ParametrosExterno:
    _so_estas_chaves(bruto, {"limiar_amarracao", "idade_maxima_dias", "desempenho"}, "externo")
    limiar = _numero(_exigir(bruto, "limiar_amarracao", "externo"), "externo.limiar_amarracao")
    if not 0.0 <= limiar <= 1.0:
        raise ParametroInvalido(f"externo.limiar_amarracao fora de [0, 1]: {limiar} — é uma taxa")
    idade = _inteiro(_exigir(bruto, "idade_maxima_dias", "externo"), "externo.idade_maxima_dias")
    if idade < 0:
        raise ParametroInvalido(f"externo.idade_maxima_dias negativa: {idade}")
    return ParametrosExterno(
        limiar_amarracao=limiar,
        idade_maxima_dias=idade,
        compor_desempenho=_ler_desempenho(_tabela(bruto, "desempenho", "externo")),
    )


def carregar(caminho: Path) -> ParametrosDaRodada:
    """Lê o arquivo do dono e devolve os parâmetros da rodada, rotulados.

    Erra — nunca completa — diante de parâmetro ausente, fora de faixa ou de
    forma desconhecida. É o que impede a rodada de sexta de sair com um número
    que ninguém escolheu.
    """
    try:
        with caminho.open("rb") as f:
            bruto = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ParametroInvalido(f"{caminho}: TOML inválido — {e}") from e

    _so_estas_chaves(
        bruto,
        {
            "semelhanca",
            "intensidades",
            "decaimento_janela",
            "pesos",
            "externo",
            "resultado_esperado",  # OPCIONAL — ver `ParametrosDaRodada.resultado_esperado`
        },
        "",
    )
    pesos = _tabela(bruto, "pesos", "")
    _so_estas_chaves(pesos, {"super_destaque", "destaque"}, "pesos")

    decisao = ParametrosDecisao(
        semelhanca=_ler_semelhanca(_tabela(bruto, "semelhanca", "")),
        intensidades=_ler_intensidades(_tabela(bruto, "intensidades", "")),
        decaimento_janela=_ler_decaimento_janela(_tabela(bruto, "decaimento_janela", "")),
        pesos_super=_ler_pesos(_tabela(pesos, "super_destaque", "pesos"), "super_destaque"),
        pesos_destaque=_ler_pesos(_tabela(pesos, "destaque", "pesos"), "destaque"),
    )
    return ParametrosDaRodada(
        decisao=decisao,
        externo=_ler_externo(_tabela(bruto, "externo", "")),
        origem=str(caminho),
        declarado=bruto,
        resultado_esperado=_ler_resultado_esperado(bruto.get("resultado_esperado")),
    )
