"""Leitura das vendas assinadas em 180 dias, que alimentam o perfil de conversão.

É a camada de I/O que monta `ImovelVendido` (src/dominio/perfil.py) a partir do
Newcore. Fonte da métrica: D-013 (docs/decisoes.md) — venda assinada em 180 dias
= linha de `newcore_bi.FT_LeadsOffers` com `SignedAt` não nulo nos últimos 180
dias, INCLUINDO as posteriormente canceladas (177 casos na medição de 31/08).

Leitura mínima (invariante 3): só características de imóvel. As dimensões de
perfil vêm da PRÓPRIA oferta (`District`, `PrivateArea_Range`, `QtyBedrooms`),
que têm cobertura melhor que `FT_RealtyRelation` (achado do investigador,
31/08); preço e vagas vêm de `realties` por JOIN em `Realty_Id`. `RealtyType`
(categoria) NÃO é dimensão de perfil (Spec §6.2) e não é lido aqui. `SignedAt`
é data, não pessoa. NENHUM nome/contato de comprador ou corretor.

A bucketização das dimensões contínuas mora AQUI (na coleta), não no domínio:
`perfil.py` recebe as dimensões já em faixas e é agnóstico a como foram feitas.
"""

from __future__ import annotations

from typing import Any

from dados.newcore import consultar
from dominio.perfil import ImovelVendido

# Recorte das vendas assinadas em 180 dias (D-013), com as dimensões de perfil.
# RealtyType não é projetado como dimensão separada aqui: a Spec §6.2 lista cinco
# dimensões (região, faixa de preço, faixa de metragem, dormitórios, vagas) e a
# categoria não é uma delas — fica fora do ImovelVendido de propósito.
_SQL_VENDAS = """
SELECT
  o.Realty_Id                          AS imovel_id,
  o.District                           AS regiao,
  o.PrivateArea_Range                  AS faixa_metragem,
  o.QtyBedrooms                        AS dormitorios,
  r.Price                              AS preco,
  r.QtyVacancies                       AS vagas
FROM newcore_bi.FT_LeadsOffers o
LEFT JOIN newcore.realties r ON r.Id = o.Realty_Id
WHERE o.SignedAt IS NOT NULL
  AND o.SignedAt >= CURDATE() - INTERVAL 180 DAY
ORDER BY o.Realty_Id, o.SignedAt
"""

# Faixas de preço ancoradas nos pisos da Spec §6.1 (R$ 300.000 geral, R$ 700.000
# super destaque). É escolha de bucketização da piloto, declarada e calibrável —
# não é um dos onze parâmetros pendentes. Limites em REAIS, faixa [inferior, sup).
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
_TETO_DORMITORIOS = 5
_TETO_VAGAS = 3


def _para_int_reais(preco: Any) -> int | None:
    # int(Decimal) e int(float) já truncam os centavos; None = preço ausente
    # (preço vem por LEFT JOIN em realties e pode faltar).
    return None if preco is None else int(preco)


def _faixa_de_preco(preco: int | None) -> str | None:
    if preco is None:
        return None
    for limite, rotulo in _FAIXAS_PRECO:
        if preco < limite:
            return rotulo
    return _FAIXA_PRECO_ACIMA


def _bucketiza_contagem(valor: Any, teto: int) -> int | None:
    """Inteiro não-negativo, colapsando valores ≥ teto no próprio teto ("N+")."""
    if valor is None:
        return None
    n = int(valor)
    if n < 0:
        return None
    return min(n, teto)


def _texto_ou_none(v: Any) -> str | None:
    """Texto sem espaços nas bordas; vazio ou só-espaço vira None (ausência)."""
    if v is None:
        return None
    limpo = str(v).strip()
    return limpo or None


def linha_para_vendido(row: dict[str, Any]) -> ImovelVendido:
    """Converte uma linha de _SQL_VENDAS em ImovelVendido (dimensões bucketizadas).

    `faixa_metragem` (`PrivateArea_Range`) já vem como faixa nativa da base;
    `regiao` (`District`) vem como texto; `dormitorios`/`vagas` colapsam o topo;
    `faixa_preco` deriva do preço em reais pelas faixas ancoradas na Spec §6.1.
    Strings vazias viram None (ausência, não bucket próprio).
    """
    return ImovelVendido(
        imovel_id=int(row["imovel_id"]),
        regiao=_texto_ou_none(row["regiao"]),
        faixa_preco=_faixa_de_preco(_para_int_reais(row["preco"])),
        faixa_metragem=_texto_ou_none(row["faixa_metragem"]),
        dormitorios=_bucketiza_contagem(row["dormitorios"], _TETO_DORMITORIOS),
        vagas=_bucketiza_contagem(row["vagas"], _TETO_VAGAS),
    )


def coletar_vendas() -> list[ImovelVendido]:
    """Lê as vendas assinadas em 180 dias (D-013) e as monta como ImovelVendido.

    I/O: não roda no CI (precisa do banco). Uma venda por linha de oferta
    assinada; um mesmo imóvel pode ter mais de uma venda no período e cada uma
    conta como um caso no perfil (a evidência é por venda, não por imóvel).
    """
    return [linha_para_vendido(row) for row in consultar(_SQL_VENDAS)]
