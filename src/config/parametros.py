"""Carregador dos parâmetros da rodada: exige, valida e ROTULA a procedência.

Reescrito em 04/09/2026 (D-027 a D-034): o modelo passou a ser "o banco manda, o
portal classifica", com dezesseis parâmetros em três funções (quem entra, em que
ordem, quantos), TODOS em unidade concreta — dias, pontos de 100, por cento,
contagem. Nenhuma escala abstrata de 0 a 1 sobrevive.

Três regras que este módulo executa (não apenas descreve):

1. **Nenhum default INVENTADO.** Chave ausente no arquivo cai no valor ADOTADO
   (`config.adotados`, D-034), que tem decisão registrada — nunca num número de
   conveniência. O que segue NULO (a régua de resultado, nº 14) não tem adotado e
   só entra se o dono o declarar.
2. **Nenhuma chave desconhecida.** Um nome digitado errado é erro, nunca valor
   descartado em silêncio.
3. **Toda procedência é rotulada.** `ParametrosDaRodada.procedencia` diz, chave a
   chave, se o valor é "adotado D-034" ou "declarado nesta rodada"; a planilha e o
   Registro mostram isso, porque um número sem procedência numa planilha aprovada é
   indistinguível de um número adotado.

As duas escolhas de FORMA (`portal.sem_anuncio` e `portal.ordem_quando_nao_entra`)
são listas fechadas de nomes: expressão livre num arquivo de configuração seria
código executável fora da revisão, e o invariante 5 deixaria de ser verificável.
"""

from __future__ import annotations

import math
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config.adotados import ADOTADOS, DECISAO_DOS_ADOTADOS
from dados.coletor_externo import ParametrosExterno
from dominio.penalidades import IntensidadesPenalidade
from dominio.perfil import Dimensao
from dominio.ranking import PesosPortal
from piloto.decisao import (
    FORMAS_DE_ORDEM_SEM_PORTAL,
    FORMAS_SEM_ANUNCIO,
    ParametrosDecisao,
)


class ParametroAusente(ValueError):
    """Falta um parâmetro sem valor adotado. A rodada não prossegue."""


class ParametroInvalido(ValueError):
    """Valor presente mas fora do contrato (faixa, tipo ou forma desconhecida)."""


# Qual pendente da tabela do CLAUDE.md cada chave atende. Serve à mensagem de erro e ao
# rótulo do formulário. Indexado pelo CAMINHO COMPLETO.
PENDENTE_DE: Mapping[str, str] = {
    "resultado_esperado.super_destaque": "nº 14 (resultado esperado por nível, §6.4)",
    "resultado_esperado.destaque": "nº 14 (resultado esperado por nível, §6.4)",
}

# A dimensão que o perfil precisa CONTER para contar no filtro (D-027). Regra de
# decisão, não parâmetro da rodada: mudar é nova decisão.
DIMENSAO_EXIGIDA_NO_PERFIL = Dimensao.FAIXA_PRECO

SECOES: Mapping[str, tuple[str, ...]] = {
    "conversao": ("janela_dias",),
    "corretor": ("login_janela_dias", "minimo_no_distrito"),
    "portal": (
        "peso_nota",
        "peso_cliques",
        "peso_visualizacoes",
        "cobertura_minima",
        "idade_maxima_dias",
        "sem_anuncio",
        "ordem_quando_nao_entra",
    ),
    "desconto": ("janela_sem_resultado", "sem_avaliacao", "sem_lead_180d", "perdao_por_semana"),
}


@dataclass(frozen=True)
class ParametrosColeta:
    """O que a COLETA lê do TOML: as janelas que viram SQL (D-033)."""

    janela_conversao_dias: int
    login_janela_dias: int


@dataclass(frozen=True)
class ParametrosDaRodada:
    """O que o ponto de entrada injeta no grafo, mais a procedência.

    `declarado` é o conteúdo do arquivo verbatim (para o Registro); `efetivo` é o que
    a rodada de fato usou, chave a chave, já com os adotados preenchidos; e
    `procedencia` diz de onde cada chave veio. `resultado_esperado` é o nº 14: `None`
    = nulo, declarado como tal na planilha.
    """

    decisao: ParametrosDecisao
    externo: ParametrosExterno
    coleta: ParametrosColeta
    origem: str
    declarado: Mapping[str, Any]
    efetivo: Mapping[str, Any]
    procedencia: Mapping[str, str]
    resultado_esperado: Mapping[str, int] | None = None

    @property
    def declarados_diferentes_do_adotado(self) -> tuple[str, ...]:
        """As chaves que a rodada declarou com valor diferente do adotado — as que a
        planilha rotula PROVISÓRIO."""
        return tuple(sorted(k for k, v in self.procedencia.items() if v == "declarado"))


# --- leitura ------------------------------------------------------------------


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
    if not math.isfinite(valor):
        raise ParametroInvalido(f"`{contexto}` precisa ser finito, veio {valor}")
    return float(valor)


def _inteiro(valor: Any, contexto: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ParametroInvalido(f"`{contexto}` deve ser inteiro, veio {type(valor).__name__}")
    return valor


def _texto(valor: Any, contexto: str, formas: tuple[str, ...]) -> str:
    if not isinstance(valor, str) or valor not in formas:
        raise ParametroInvalido(f"`{contexto}` deve ser uma de {list(formas)}, veio {valor!r}")
    return valor


def _tabela(bruto: Mapping[str, Any], chave: str) -> Mapping[str, Any]:
    valor = bruto.get(chave, {})
    if not isinstance(valor, dict):
        raise ParametroInvalido(f"`{chave}` deve ser uma tabela [{chave}]")
    return valor


def _faixa_da_dataclass[T](construir: Callable[[], T], contexto: str) -> T:
    """Reergue a validação de faixa da dataclass como erro de PARÂMETRO."""
    try:
        return construir()
    except ValueError as e:
        raise ParametroInvalido(f"{contexto}: {e}") from e


def _decaimento_geometrico(razao: float) -> Callable[[int], float]:
    def decaimento(ciclos: int) -> float:
        return float(razao**ciclos)

    return decaimento


def _resolver(bruto: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    """Achata as seções em `caminho → valor` preenchendo os adotados, e anota a
    procedência de cada chave. Recusa chave e seção desconhecidas."""
    _so_estas_chaves(bruto, set(SECOES) | {"resultado_esperado"}, "")
    efetivo: dict[str, Any] = {}
    procedencia: dict[str, str] = {}
    for secao, chaves in SECOES.items():
        tabela = _tabela(bruto, secao)
        _so_estas_chaves(tabela, set(chaves), secao)
        for chave in chaves:
            caminho = f"{secao}.{chave}"
            if chave in tabela:
                efetivo[caminho] = tabela[chave]
                procedencia[caminho] = "declarado"
            elif caminho in ADOTADOS:
                efetivo[caminho] = ADOTADOS[caminho]
                procedencia[caminho] = f"adotado {DECISAO_DOS_ADOTADOS}"
            else:  # pragma: no cover — toda chave das seções tem adotado hoje
                raise ParametroAusente(f"falta `{caminho}` e não há valor adotado")
    # Declarado igual ao adotado não é escolha nova: rotula como adotado.
    for caminho, valor in efetivo.items():
        if procedencia[caminho] == "declarado" and valor == ADOTADOS.get(caminho):
            procedencia[caminho] = f"adotado {DECISAO_DOS_ADOTADOS}"
    return efetivo, procedencia


def _ler_resultado_esperado(bruto: Mapping[str, Any] | None) -> Mapping[str, int] | None:
    """O nº 14, se o dono o declarou. Os DOIS níveis ou nenhum, cada um ≥ 1 e o super
    MAIOR que o destaque (PRD: o resultado esperado é proporcional ao nível)."""
    if bruto is None:
        return None
    if not isinstance(bruto, dict):
        # `resultado_esperado = 3` é TOML válido; sem isto estourava TypeError cru.
        raise ParametroInvalido("`resultado_esperado` deve ser uma tabela [resultado_esperado]")
    niveis = ("super_destaque", "destaque")
    _so_estas_chaves(bruto, set(niveis), "resultado_esperado")
    valores: dict[str, int] = {}
    for n in niveis:
        if n not in bruto:
            pendente = PENDENTE_DE[f"resultado_esperado.{n}"]
            raise ParametroAusente(
                f"falta `resultado_esperado.{n}` — parâmetro pendente {pendente}"
                "; declare os DOIS níveis ou omita a seção"
            )
        valores[n] = _inteiro(bruto[n], f"resultado_esperado.{n}")
    for nivel, valor in valores.items():
        if valor < 1:
            raise ParametroInvalido(
                f"resultado_esperado.{nivel} = {valor}: o limiar é a contagem de leads que a "
                "janela precisa ter gerado, e precisa ser ao menos 1. Para deixá-lo nulo, "
                "OMITA a seção [resultado_esperado]"
            )
    if valores["super_destaque"] <= valores["destaque"]:
        raise ParametroInvalido(
            f"resultado_esperado.super_destaque ({valores['super_destaque']}) precisa ser "
            f"MAIOR que destaque ({valores['destaque']}): o resultado esperado é "
            "proporcional ao nível"
        )
    return valores


def montar(
    efetivo: Mapping[str, Any],
) -> tuple[ParametrosDecisao, ParametrosExterno, ParametrosColeta]:
    """Valida os valores efetivos (adotados + declarados) e monta os objetos do
    domínio. Toda faixa é conferida AQUI, antes de tocar o banco."""
    v = efetivo

    janela = _inteiro(v["conversao.janela_dias"], "conversao.janela_dias")
    if janela < 1:
        raise ParametroInvalido(f"conversao.janela_dias precisa ser ao menos 1 dia, veio {janela}")
    login = _inteiro(v["corretor.login_janela_dias"], "corretor.login_janela_dias")
    if login < 1:
        raise ParametroInvalido(
            f"corretor.login_janela_dias precisa ser ao menos 1 dia, veio {login}"
        )
    minimo = _inteiro(v["corretor.minimo_no_distrito"], "corretor.minimo_no_distrito")
    if minimo < 1:
        raise ParametroInvalido(
            f"corretor.minimo_no_distrito precisa ser ao menos 1 corretor, veio {minimo}"
        )

    pesos = _faixa_da_dataclass(
        lambda: PesosPortal(
            nota_anuncio=_inteiro(v["portal.peso_nota"], "portal.peso_nota"),
            cliques=_inteiro(v["portal.peso_cliques"], "portal.peso_cliques"),
            visualizacoes=_inteiro(v["portal.peso_visualizacoes"], "portal.peso_visualizacoes"),
        ),
        "portal",
    )
    cobertura = _numero(v["portal.cobertura_minima"], "portal.cobertura_minima")
    if not 0.0 <= cobertura <= 100.0:
        raise ParametroInvalido(
            f"portal.cobertura_minima fora de 0 a 100: {cobertura} — é por cento dos candidatos"
        )
    idade = _inteiro(v["portal.idade_maxima_dias"], "portal.idade_maxima_dias")
    if idade < 0:
        raise ParametroInvalido(f"portal.idade_maxima_dias negativa: {idade}")
    sem_anuncio = _texto(v["portal.sem_anuncio"], "portal.sem_anuncio", FORMAS_SEM_ANUNCIO)
    ordem = _texto(
        v["portal.ordem_quando_nao_entra"],
        "portal.ordem_quando_nao_entra",
        FORMAS_DE_ORDEM_SEM_PORTAL,
    )

    descontos: dict[str, float] = {}
    for chave in ("janela_sem_resultado", "sem_avaliacao", "sem_lead_180d"):
        valor = _numero(v[f"desconto.{chave}"], f"desconto.{chave}")
        if not 0.0 <= valor <= 100.0:
            raise ParametroInvalido(
                f"desconto.{chave} fora de 0 a 100: {valor} — é em pontos de 100 da nota"
            )
        descontos[chave] = valor
    perdao = _numero(v["desconto.perdao_por_semana"], "desconto.perdao_por_semana")
    if not 0.0 <= perdao <= 100.0:
        raise ParametroInvalido(
            f"desconto.perdao_por_semana fora de 0 a 100: {perdao} — é por cento por carga"
        )

    decisao = ParametrosDecisao(
        pesos_portal=pesos,
        sem_anuncio=sem_anuncio,
        ordem_sem_portal=ordem,
        intensidades=_faixa_da_dataclass(
            lambda: IntensidadesPenalidade(
                janela_sem_resultado=descontos["janela_sem_resultado"],
                sem_avaliacao_por_categoria=descontos["sem_avaliacao"],
                sem_lead_180d=descontos["sem_lead_180d"],
            ),
            "desconto",
        ),
        # perdão de p% por carga = razão (1 − p/100) por ciclo. Perdão 0 não decai — e
        # a rodada declara a divergência com a Spec §6.4.
        decaimento_janela=_decaimento_geometrico(1.0 - perdao / 100.0),
        minimo_corretores_distrito=minimo,
        exigir_dimensao_no_perfil=DIMENSAO_EXIGIDA_NO_PERFIL,
    )
    externo = ParametrosExterno(limiar_amarracao=cobertura / 100.0, idade_maxima_dias=idade)
    coleta = ParametrosColeta(janela_conversao_dias=janela, login_janela_dias=login)
    return decisao, externo, coleta


def carregar(caminho: Path | None) -> ParametrosDaRodada:
    """Lê o arquivo do dono (ou nenhum) e devolve os parâmetros da rodada, rotulados.

    Sem arquivo, tudo é adotado (D-034) e a régua nº 14 é nula. Com arquivo, cada
    chave declarada substitui a adotada e é rotulada; chave desconhecida é erro.
    """
    if caminho is None:
        bruto: dict[str, Any] = {}
        origem = f"adotados ({DECISAO_DOS_ADOTADOS})"
    else:
        try:
            with caminho.open("rb") as f:
                bruto = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ParametroInvalido(f"{caminho}: TOML inválido — {e}") from e
        origem = str(caminho)
    efetivo, procedencia = _resolver(bruto)
    decisao, externo, coleta = montar(efetivo)
    return ParametrosDaRodada(
        decisao=decisao,
        externo=externo,
        coleta=coleta,
        origem=origem,
        declarado=bruto,
        efetivo=efetivo,
        procedencia=procedencia,
        resultado_esperado=_ler_resultado_esperado(bruto.get("resultado_esperado")),
    )
