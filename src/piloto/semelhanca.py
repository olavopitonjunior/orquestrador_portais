"""Mapeamento imóvel candidato → fator `semelhanca_perfil` do ranking.

É o coração de regra da costura: transforma os `PerfilConversao` descobertos
sobre as vendas (Spec §6.2, módulo dominio.perfil) no número normalizado que
o ranking consome como `FatoresNormalizados.semelhanca_perfil` (peso 60 no
super destaque, 80 no destaque). Esse número é a "semelhança com o perfil de
conversão" da Spec §6.3.

A Spec não fixa COMO um candidato se assemelha a um conjunto de perfis; as
leituras estruturais abaixo são declaradas (não inventadas em silêncio) e o
revisor-de-regra as valida contra a Spec §6.2. Onde há número livre, ele é
PROVISÓRIO run-local, injetado por `ParametrosSemelhanca` — nunca constante
escondida, nunca em src/config (D-014 mantém o parâmetro nº 2 nulo).

Leituras estruturais declaradas:
1. MATCH: um candidato casa com um perfil quando, para TODA dimensão do perfil,
   o valor bucketizado do candidato é igual ao do perfil (mesma bucketização de
   dominio/dados.vendas). Dimensão que o candidato não tem (None) não casa.
2. SINAL BRUTO: entre os perfis que o candidato casa, o sinal é o MAIOR número
   de vendas (o padrão de conversão mais forte que ele satisfaz). Perfil frágil
   (Spec §6.2 "não recebe peso pleno") contribui com num_vendas × desconto_fragil
   (provisório). Candidato que não casa nenhum perfil tem sinal bruto 0.
   Alternativa registrada (calibrável): ponderar por especificidade (2-dim > 1-dim)
   em vez do máximo — fica para a calibração do dono, não v0.
3. NORMALIZAÇÃO (parâmetro nº 2, nulo): min-max sobre o conjunto elegível da
   rodada — reescala o sinal bruto para [0, 1]. Forma provisória escolhida pelo
   dono para a piloto; quando todos os sinais são iguais (min == max), todos
   recebem 0.0 (sem sinal discriminante, nenhum candidato é favorecido).

Invariantes 4 e 5: cálculo puro — sem I/O, sem relógio, sem aleatoriedade,
sem modelo. Mesma entrada ⇒ mesmo mapa.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from dominio.perfil import Dimensao, PerfilConversao, ValorDimensao

# Dimensões bucketizadas de um imóvel (candidato ou vendido): as preenchidas,
# no mesmo formato que ImovelVendido.valores() devolve.
type DimensoesImovel = Mapping[Dimensao, ValorDimensao]


@dataclass(frozen=True)
class ParametrosSemelhanca:
    """Parâmetros PROVISÓRIOS da piloto, injetados run-local — NÃO adotados.

    `desconto_fragil` é o peso reduzido de um perfil frágil (Spec §6.2 "não
    recebe peso pleno"): fator em [0, 1] que multiplica o num_vendas do perfil
    frágil no sinal bruto. Vive fora do código (escolha do dono na rodada);
    a validação de faixa é aqui. Não é nenhum dos onze parâmetros da D-004 —
    é tratamento de fragilidade, rotulado PROVISÓRIO na saída.
    """

    desconto_fragil: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.desconto_fragil <= 1.0:
            raise ValueError(f"desconto_fragil fora de [0, 1]: {self.desconto_fragil}")


def casa(dims_candidato: DimensoesImovel, perfil: PerfilConversao) -> bool:
    """True se o candidato satisfaz TODAS as dimensões do perfil (match exato)."""
    return all(
        dims_candidato.get(dim) == valor
        for dim, valor in zip(perfil.dimensoes, perfil.valores, strict=True)
    )


def _contribuicoes(
    dims_candidato: DimensoesImovel,
    perfis: tuple[PerfilConversao, ...],
    params: ParametrosSemelhanca,
) -> list[tuple[PerfilConversao, float]]:
    """Os perfis que o candidato casa, cada um com sua contribuição.

    FONTE ÚNICA do sinal (max desta lista) e do perfil que puxou (argmax): os
    dois derivam daqui, então o número e o perfil exibido como justificativa
    nunca divergem. Robusto contribui com num_vendas; frágil com
    num_vendas × desconto_fragil (Spec §6.2, "não recebe peso pleno").
    """
    return [
        (p, p.num_vendas * (params.desconto_fragil if p.fragil else 1.0))
        for p in perfis
        if casa(dims_candidato, p)
    ]


def sinal_bruto(
    dims_candidato: DimensoesImovel,
    perfis: tuple[PerfilConversao, ...],
    params: ParametrosSemelhanca,
) -> float:
    """Maior contribuição de perfil que o candidato casa (0 se não casa nenhum)."""
    return max(
        (c for _, c in _contribuicoes(dims_candidato, perfis, params)),
        default=0.0,
    )


def _ordem_desempate(perfil: PerfilConversao) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Chave determinística e total para o desempate de exibição (por dimensões,
    depois valores como texto). Só decide QUAL perfil é mostrado num empate de
    contribuição — não muda o número nem o ranking."""
    return (
        tuple(d.value for d in perfil.dimensoes),
        tuple(str(v) for v in perfil.valores),
    )


def perfil_que_puxou(
    dims_candidato: DimensoesImovel,
    perfis: tuple[PerfilConversao, ...],
    params: ParametrosSemelhanca,
) -> PerfilConversao | None:
    """O perfil de MAIOR contribuição — o que define `sinal_bruto`. None se o
    candidato não casa nenhum perfil.

    É o "perfil que puxou" da justificativa (Spec §2.1: identificador e
    evidência do perfil casado). Empate de contribuição: ganha o MAIS ESPECÍFICO
    (mais dimensões), depois a ordem canônica — o mais específico explica melhor.
    O empate é raro por construção: um perfil de uma dimensão agrega as vendas
    dos de duas que o contêm, então sua contribuição ≥ a deles (salvo o desconto
    de frágil mexer nas contribuições). Isto é rótulo explicativo, não decisão
    distributiva: não muda o número, o ranking, nem quem é alocado.
    """
    contrib = _contribuicoes(dims_candidato, perfis, params)
    if not contrib:
        return None
    # min com chave (-contribuição, -nº dimensões, chave canônica): maior
    # contribuição, depois mais específico, depois o primeiro na ordem canônica.
    return min(
        contrib,
        key=lambda pc: (-pc[1], -len(pc[0].dimensoes), _ordem_desempate(pc[0])),
    )[0]


def _normalizar_minmax(sinais: dict[int, float]) -> dict[int, float]:
    """Reescala os sinais brutos para [0, 1] (parâmetro nº 2, min-max provisório).

    min == max (todos iguais, inclusive todos zero) ⇒ todos 0.0: sem sinal
    discriminante, nenhum candidato é favorecido pelo fator de perfil.
    """
    if not sinais:
        return {}
    valores = sinais.values()
    menor, maior = min(valores), max(valores)
    faixa = maior - menor
    if faixa == 0.0:
        return {iid: 0.0 for iid in sinais}
    return {iid: (s - menor) / faixa for iid, s in sinais.items()}


def semelhanca_por_imovel(
    dims_por_imovel: Mapping[int, DimensoesImovel],
    perfis: tuple[PerfilConversao, ...],
    params: ParametrosSemelhanca,
) -> dict[int, float]:
    """O fator `semelhanca_perfil` normalizado [0, 1] de cada imóvel candidato.

    Determinístico (invariante 5): depende só das entradas, não da ordem delas.
    """
    brutos = {iid: sinal_bruto(dims, perfis, params) for iid, dims in dims_por_imovel.items()}
    return _normalizar_minmax(brutos)
