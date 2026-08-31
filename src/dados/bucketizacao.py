"""Bucketização das dimensões de perfil — FONTE ÚNICA (vendas e candidatos).

As dimensões contínuas (preço, dormitórios, vagas) e textuais (região, faixa de
metragem) são reduzidas a buckets aqui, num único lugar, para que uma VENDA e um
CANDIDATO com o mesmo valor caiam SEMPRE no mesmo bucket. Se as duas leituras
bucketizassem de forma diferente, o match do perfil (piloto.semelhanca.casa)
nunca casaria e a semelhança viraria zero para todos — sem erro nenhum. Por isso
a lógica vive fora de vendas.py e de qualquer leitor de candidato: os dois
importam daqui.

A bucketização é escolha da coleta (não do domínio), declarada e calibrável.
NÃO é um dos onze parâmetros pendentes da D-004 (tem valor concreto, não é nulo),
MAS é config que AFETA a decisão: as faixas determinam qual candidato casa qual
perfil, que alimenta `semelhanca_perfil` (peso 60/80, o maior do ranking). Mudar
uma faixa muda quem casa qual perfil, muda o ranking, muda quem ganha posição
paga — portanto **mudança nas faixas EXIGE entrada no CHANGELOG** (a convenção
existe pela comparabilidade entre rodadas). Faixas de preço ancoradas nos pisos
da Spec §6.1 (R$ 300.000 geral, R$ 700.000 super destaque).
"""

from __future__ import annotations

from typing import Any

# Faixas de preço em REAIS, faixa [inferior, superior). Ancoradas nos pisos da
# Spec §6.1. Mudar as faixas muda quem casa qual perfil e portanto o ranking —
# config que afeta a decisão: mudança aqui EXIGE entrada no CHANGELOG (ver topo).
_FAIXAS_PRECO: tuple[tuple[int, str], ...] = (
    (300_000, "< 300k"),
    (500_000, "300k–500k"),
    (700_000, "500k–700k"),
    (1_000_000, "700k–1M"),
    (1_500_000, "1M–1,5M"),
    (3_000_000, "1,5M–3M"),
)
_FAIXA_PRECO_ACIMA = "≥ 3M"

# Acima destes valores, dormitórios e vagas colapsam em "N ou mais" (o int vira
# o teto, marcando o bucket). Espelha a bucketização da medição de 31/08.
TETO_DORMITORIOS = 5
TETO_VAGAS = 3


def para_int_reais(preco: Any) -> int | None:
    """Preço em reais como int (trunca centavos); None = ausente."""
    # int(Decimal) e int(float) já truncam os centavos; None = preço ausente
    # (preço vem por LEFT JOIN em realties e pode faltar).
    return None if preco is None else int(preco)


def faixa_de_preco(preco: int | None) -> str | None:
    """Rótulo da faixa de preço, ou None se o preço é ausente."""
    if preco is None:
        return None
    for limite, rotulo in _FAIXAS_PRECO:
        if preco < limite:
            return rotulo
    return _FAIXA_PRECO_ACIMA


def bucketiza_contagem(valor: Any, teto: int) -> int | None:
    """Inteiro não-negativo, colapsando valores ≥ teto no próprio teto ("N+")."""
    if valor is None:
        return None
    n = int(valor)
    if n < 0:
        return None
    return min(n, teto)


def texto_ou_none(v: Any) -> str | None:
    """Texto sem espaços nas bordas; vazio ou só-espaço vira None (ausência)."""
    if v is None:
        return None
    limpo = str(v).strip()
    return limpo or None
