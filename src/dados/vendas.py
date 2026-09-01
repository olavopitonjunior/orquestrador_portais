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

A bucketização das dimensões contínuas mora em `dados.bucketizacao` (FONTE
ÚNICA, compartilhada com a leitura de candidatos da piloto): `perfil.py` recebe
as dimensões já em faixas e é agnóstico a como foram feitas.
"""

from __future__ import annotations

from typing import Any

from dados.bucketizacao import (
    TETO_DORMITORIOS,
    TETO_VAGAS,
    bucketiza_contagem,
    faixa_de_preco,
    para_int_reais,
    texto_ou_none,
)
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


def linha_para_vendido(row: dict[str, Any]) -> ImovelVendido:
    """Converte uma linha de _SQL_VENDAS em ImovelVendido (dimensões bucketizadas).

    `faixa_metragem` (`PrivateArea_Range`) já vem como faixa nativa da base;
    `regiao` (`District`) vem como texto; `dormitorios`/`vagas` colapsam o topo;
    `faixa_preco` deriva do preço em reais pelas faixas ancoradas na Spec §6.1.
    Strings vazias viram None (ausência, não bucket próprio). `imovel_id` nulo
    é ERRO (fail-loud): uma oferta sem `Realty_Id` não ancora um imóvel — deve
    ter sido descartada por `_vendas_ancoraveis` antes de chegar aqui; se chegou,
    é estado inesperado (regressão), não um valor a mascarar.
    """
    if row["imovel_id"] is None:
        raise ValueError("venda com imovel_id (Realty_Id) nulo chegou a linha_para_vendido")
    return ImovelVendido(
        imovel_id=int(row["imovel_id"]),
        regiao=texto_ou_none(row["regiao"]),
        faixa_preco=faixa_de_preco(para_int_reais(row["preco"])),
        faixa_metragem=texto_ou_none(row["faixa_metragem"]),
        dormitorios=bucketiza_contagem(row["dormitorios"], TETO_DORMITORIOS),
        vagas=bucketiza_contagem(row["vagas"], TETO_VAGAS),
    )


def _vendas_ancoraveis(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Separa as ofertas ANCORÁVEIS (com Realty_Id) das descartadas (sem imóvel).

    Uma venda sem `Realty_Id` não pode ser montada como ImovelVendido: falta a
    ÂNCORA (`imovel_id`) e o preço/vagas que vêm do JOIN em realties. As três
    dimensões nativas da oferta (região, faixa de metragem, dormitórios) até
    existiriam, mas sem âncora nem preço/vagas a oferta não vira um ImovelVendido
    completo — então é descartada. É um encolhimento marginal da base do perfil
    (≈2 de 177, dentro da deriva que a D-013 admite), NUNCA em silêncio: devolve
    o número descartado para a rodada declarar (D-013 continua a métrica de 177;
    o perfil roda sobre as ancoráveis). Medido no dado real: ofertas assinadas em
    180d com `Realty_Id` nulo (o investigador sinalizou).
    """
    ancoraveis = [r for r in rows if r["imovel_id"] is not None]
    return ancoraveis, len(rows) - len(ancoraveis)


def coletar_vendas() -> tuple[list[ImovelVendido], int]:
    """Lê as vendas assinadas em 180 dias (D-013) e as monta como ImovelVendido.

    Devolve (vendas ancoráveis, nº descartado por Realty_Id nulo) — o descarte é
    contado, nunca silencioso, para a rodada declarar na aba de limitações.
    I/O: não roda no CI (precisa do banco). Uma venda por linha de oferta
    assinada; um mesmo imóvel pode ter mais de uma venda no período e cada uma
    conta como um caso no perfil (a evidência é por venda, não por imóvel).
    """
    ancoraveis, descartadas = _vendas_ancoraveis(consultar(_SQL_VENDAS))
    return [linha_para_vendido(row) for row in ancoraveis], descartadas
