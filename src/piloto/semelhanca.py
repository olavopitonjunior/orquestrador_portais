"""O perfil de conversão como FILTRO: casa ou não casa.

Até a D-027 (04/09/2026) o perfil era um fator de nota — semelhança ponderada por
dimensão, normalizada, com peso por nível. O dono decidiu que ele FILTRA: só entra
na vitrine quem se parece com o que vendeu. E, sobre medição (o perfil de uma
dimensão em N ≥ 3 casava 100% do estoque elegível, porque a faixa de metragem
sozinha cobre tudo), decidiu que o perfil precisa CONTER a faixa de preço para
contar — é a dimensão que ele pôs em primeiro lugar na D-017. Com isso, 83,8% dos
elegíveis e 64% dos candidatos ao super destaque passam (medido em 04/09/2026).

O que sobrevive aqui: o MATCH (o candidato satisfaz todas as dimensões do perfil,
com a mesma bucketização dos dois lados) e o "perfil que puxou" como rótulo
explicativo — agora o perfil robusto de MAIS vendas entre os que o candidato casa.
Os parâmetros de ponderação (`desconto_fragil`, `decaimento`) deixaram de existir:
perfil frágil (N < 3, D-014) simplesmente não conta para o filtro.

Invariantes 4 e 5: cálculo puro — sem I/O, sem relógio, sem aleatoriedade, sem modelo.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from dominio.perfil import Dimensao, PerfilConversao, ValorDimensao

# Dimensões bucketizadas de um imóvel (candidato ou vendido): as preenchidas,
# no mesmo formato que ImovelVendido.valores() devolve.
type DimensoesImovel = Mapping[Dimensao, ValorDimensao]


def casa(dims_candidato: DimensoesImovel, perfil: PerfilConversao) -> bool:
    """True se o candidato satisfaz TODAS as dimensões do perfil (match exato)."""
    return all(
        dims_candidato.get(dim) == valor
        for dim, valor in zip(perfil.dimensoes, perfil.valores, strict=True)
    )


def perfis_que_contam(
    perfis: Sequence[PerfilConversao], exigir_dimensao: Dimensao | None
) -> tuple[PerfilConversao, ...]:
    """Os perfis que o filtro considera: ROBUSTOS (N ≥ evidência mínima, D-014) e,
    se exigido, contendo a dimensão dada. Ordem canônica preservada (invariante 5)."""
    return tuple(
        p
        for p in perfis
        if not p.fragil and (exigir_dimensao is None or exigir_dimensao in p.dimensoes)
    )


def _ordem_desempate(
    perfil: PerfilConversao,
) -> tuple[tuple[str, ...], tuple[tuple[str, ValorDimensao], ...]]:
    """Chave determinística e total para o desempate de exibição (por dimensões,
    depois valores). Só decide QUAL perfil é mostrado — não muda quem entra."""
    return (
        tuple(d.value for d in perfil.dimensoes),
        tuple((type(v).__name__, v) for v in perfil.valores),
    )


def perfil_que_puxou(
    dims_candidato: DimensoesImovel, perfis_que_contam_: Sequence[PerfilConversao]
) -> PerfilConversao | None:
    """O perfil de MAIS vendas entre os que o candidato casa (None se não casa
    nenhum). É o rótulo da justificativa (Spec §2.1: identificador e evidência do
    perfil casado). Empate: o mais específico (mais dimensões), depois a ordem
    canônica. Rótulo explicativo, não decisão: o filtro é binário."""
    casados = [p for p in perfis_que_contam_ if casa(dims_candidato, p)]
    if not casados:
        return None
    return min(casados, key=lambda p: (-p.num_vendas, -len(p.dimensoes), _ordem_desempate(p)))


def casa_algum(
    dims_candidato: DimensoesImovel, perfis_que_contam_: Sequence[PerfilConversao]
) -> bool:
    """O veredito do filtro: o candidato casa pelo menos um perfil que conta."""
    return any(casa(dims_candidato, p) for p in perfis_que_contam_)
