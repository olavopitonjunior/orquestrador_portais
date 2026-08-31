"""Leitura das dimensões de perfil do imóvel CANDIDATO (para o match do perfil).

O Coletor Interno (coletor_interno.py) lê o candidato para elegibilidade e
penalidade; esta leitura complementar traz as cinco dimensões de perfil da
Spec §6.2 de cada imóvel ativo, no formato que piloto.semelhanca consome, para
casá-lo com os PerfilConversao descobertos sobre as vendas.

FONTE ÚNICA (verificado no banco, 31/08): as dimensões do candidato saem das
MESMAS colunas nativas que as da venda, casando string-a-string —
`FT_RealtyRelation.District` (região; 66/66 distritos das vendas presentes nos
ativos), `FT_RealtyRelation.PrivateArea_Range` (faixa de metragem; os mesmos 8
rótulos nativos, sem bucketizar) e `FT_RealtyRelation.QtyBedrooms` (dormitórios);
preço e vagas vêm de `realties` por JOIN em `Realty_Id`, como no lado venda. A
bucketização é a de `dados.bucketizacao` — a mesma dos dois lados.

ARMADILHA (registrada no mapa): NÃO usar `FT_RealtyRelation.Price_Range` — tem
vocabulário próprio (`300 - 400mil`, `1 - 1.5M`) incompatível com `faixa_de_preco()`;
casar por ele com a venda daria zero. A faixa de preço vem SEMPRE de
`realties.Price` + `faixa_de_preco()`, nos dois lados. (`PrivateArea_Range`, ao
contrário, é compatível e nativo — a assimetria entre as duas colunas "_Range".)

Leitura mínima (invariante 3): só características de imóvel. Nenhuma identidade.
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
from dominio.perfil import Dimensao, ValorDimensao

# As cinco dimensões de perfil dos imóveis ATIVOS (candidatos). District e
# PrivateArea_Range são nativos e compatíveis com o lado venda; QtyBedrooms
# idem. Preço e vagas de realties por JOIN. Price_Range é DELIBERADAMENTE
# ignorado (vocabulário incompatível — ver docstring).
_SQL_DIMENSOES = """
SELECT
  f.Realty_Id          AS imovel_id,
  f.District           AS regiao,
  f.PrivateArea_Range  AS faixa_metragem,
  f.QtyBedrooms        AS dormitorios,
  r.Price              AS preco,
  r.QtyVacancies       AS vagas
FROM newcore_bi.FT_RealtyRelation f
LEFT JOIN newcore.realties r ON r.Id = f.Realty_Id
WHERE f.RealtyStatus = 'Ativo'
ORDER BY f.Realty_Id
"""


def linha_para_dimensoes(row: dict[str, Any]) -> dict[Dimensao, ValorDimensao]:
    """As dimensões de perfil preenchidas de um candidato (as None ficam de fora).

    Mesma bucketização do lado venda (dados.bucketizacao): é o que garante que
    candidato e venda com o mesmo valor casem no mesmo bucket.
    """
    bruto: dict[Dimensao, ValorDimensao | None] = {
        Dimensao.REGIAO: texto_ou_none(row["regiao"]),
        Dimensao.FAIXA_PRECO: faixa_de_preco(para_int_reais(row["preco"])),
        Dimensao.FAIXA_METRAGEM: texto_ou_none(row["faixa_metragem"]),
        Dimensao.DORMITORIOS: bucketiza_contagem(row["dormitorios"], TETO_DORMITORIOS),
        Dimensao.VAGAS: bucketiza_contagem(row["vagas"], TETO_VAGAS),
    }
    return {dim: v for dim, v in bruto.items() if v is not None}


def coletar_dimensoes_candidatos() -> dict[int, dict[Dimensao, ValorDimensao]]:
    """Dimensões de perfil de cada imóvel ativo, por imovel_id.

    I/O: não roda no CI (precisa do banco). O formato é o que
    piloto.semelhanca.semelhanca_por_imovel consome diretamente.

    A colapsagem por dict (uma entrada por imovel_id) é intencional: FT_RealtyRelation
    é 1:1 por Realty_Id no recorte ativo (48.985=48.985, mapa 31/08) e o JOIN é por
    PK, então não há duplicata hoje. Se um dia a fonte deixar de ser 1:1, o dict fica
    com a ÚLTIMA linha vista — critério diferente do coletor_interno (_dedup_por_imovel,
    primeira vista); a divergência é inócua enquanto a cardinalidade 1:1 se mantiver.
    """
    return {int(row["imovel_id"]): linha_para_dimensoes(row) for row in consultar(_SQL_DIMENSOES)}
