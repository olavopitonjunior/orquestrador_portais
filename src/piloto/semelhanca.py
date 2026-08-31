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


def sinal_bruto(
    dims_candidato: DimensoesImovel,
    perfis: tuple[PerfilConversao, ...],
    params: ParametrosSemelhanca,
) -> float:
    """Maior contribuição de perfil que o candidato casa (0 se não casa nenhum).

    Robusto contribui com num_vendas; frágil com num_vendas × desconto_fragil.
    """
    contribuicoes = [
        p.num_vendas * (params.desconto_fragil if p.fragil else 1.0)
        for p in perfis
        if casa(dims_candidato, p)
    ]
    return max(contribuicoes, default=0.0)


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
