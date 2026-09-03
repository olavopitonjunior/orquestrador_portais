"""Coletor Interno: monta os dataclasses do domínio a partir do Newcore.

É a camada de I/O que alimenta `src/dominio` — os contratos frozen de lá
(`ImovelCandidato`, `ImovelPenalizavel`) são a fonte da verdade; aqui só se
lê o banco e se converte. Fontes de cada campo confirmadas contra a base em
31/08/2026 (ver docs/mapa-de-dados.md, seção do Coletor Interno).

Leitura mínima (invariante 3 em profundidade): puxa só os campos que os
dataclasses exigem — contagens, datas, categoria, preço. Nenhum nome de
corretor, contato de lead ou identidade pessoal entra aqui.

`janelas_anteriores` de ImovelPenalizavel vêm do REGISTRO (Postgres), não do
Newcore — este módulo lê só o Newcore e deixa as janelas para o acesso ao
Registro (na primeira rodada/piloto, não há histórico: tupla vazia).
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from dados.newcore import consultar
from dominio.elegibilidade import ImovelCandidato
from dominio.penalidades import ImovelPenalizavel


class DefinicaoAtivoDistrito(StrEnum):
    """Qual coluna de FT_Districts define "corretor ativo no distrito".

    DECISÃO PENDENTE DO DONO: a regra de capacidade do distrito exige ≥2
    corretores ativos, e a escolha muda o funil (medição 31/08 dos ativos):
    total 94,8% ≥2 · produtivos 45,9% · logou-30d 76,8% · habilitado-leads.
    Nenhum default é inventado como verdade — o chamador escolhe.
    """

    TOTAL = "Brokers"
    PRODUTIVOS = "BrokersProductivity"
    LOGOU_30D = "Brokers_logged30d"
    HABILITADO_LEADS = "BrokersEnabledLeads"


# Recorte ativo canônico e todas as fontes numa query só (JOINs confirmados).
# A coluna de "ativo no distrito" é interpolada pelo nome do enum (valor de um
# conjunto fechado — não é entrada de usuário), o resto é parametrizado.
_SQL_CANDIDATOS = """
SELECT
  f.Realty_Id                                   AS imovel_id,
  -- STATUS: as DUAS fontes, e a redundância é deliberada. O espelho
  -- `FT_RealtyRelation` é mantido incrementalmente e atrasa ~13,5 h (medido
  -- 02/09/2026); sozinho, ele dá como ativo imóvel já removido no transacional.
  -- O primeiro termo repete o WHERE de propósito: a coluna documenta as duas
  -- fontes que definem "publicado", e quem apagar metade precisa ver qual.
  -- A redundância só é inócua ENQUANTO o WHERE continuar `= 'Ativo'`: se um dia
  -- ele admitir outro status para capturar mais candidatos, o primeiro termo
  -- deixa de ser tautológico e passa a fazer trabalho real — desejável, mas
  -- invisível para quem olhar a coluna isolada.
  -- Medido em 02/09/2026: 86 imóveis (0,176% do recorte) reprovam aqui, TODOS
  -- com status 3/Removido e TODOS saídos do ar nas últimas 24 h. Eles entram
  -- como candidatos e reprovam em `Regra.STATUS_ATIVO`, com motivo registrado
  -- na aba de excluídos — em vez de sumir em silêncio, que é o que um filtro
  -- no WHERE faria. Não voltam por relaxamento: status não é regra relaxável.
  -- NÃO conserta o caminho inverso: 54 imóveis publicados que o espelho ainda
  -- não viu seguem invisíveis, porque sem linha no espelho não há distrito nem
  -- gestor para avaliar. Limitação declarada, fatia própria.
  -- COALESCE porque a coluna é NULL-able por schema (79 nulos na base, nenhum
  -- no recorte): a escolha declarada é **nulo = não publicado**. Sem ele,
  -- `NULL = 1` devolve NULL, vira None e depois False — reprovaria pelo mesmo
  -- efeito, mas por acidente da linguagem em vez de decisão registrada.
  (f.RealtyStatus = 'Ativo'
     AND COALESCE(r.PublishStatus_Id, 0) = 1)   AS publicacao_ativa,
  cat.Description                               AS categoria,
  r.Price                                       AS preco,
  COALESCE(img.cnt, 0)                          AS qtd_fotos,
  r.UpdatedAt                                   AS atualizado_em,
  (COALESCE(p.Captations_per_week_last_30d, 0) > 0
     OR p.LastSell >= NOW() - INTERVAL 30 DAY)  AS gestor_ativo_30d,
  -- FATOR F4 (D-017): intensidade CONTÍNUA em 30d = taxa semanal de captação
  -- (0..15) + flag de venda recente. A base não tem contagem de vendas em 30d
  -- (Sells é 365d), então venda entra só como flag — limitação declarada.
  (COALESCE(p.Captations_per_week_last_30d, 0)
     + COALESCE(p.LastSell >= NOW() - INTERVAL 30 DAY, 0))  AS produtividade_gestor_30d,
  COALESCE(d.{coluna_ativo}, 0)                 AS ativos_no_distrito,
  (sc.realtyId IS NOT NULL)                     AS alguma_categoria_avaliada,
  f.Leads180D                                   AS leads_180d
FROM newcore_bi.FT_RealtyRelation f
JOIN newcore.realties   r   ON r.Id = f.Realty_Id
JOIN newcore.categories cat ON cat.Id = r.Category_Id
LEFT JOIN newcore_bi.productivityrating p ON p.User_Id = f.BrokerID
LEFT JOIN newcore_bi.FT_Districts d ON d.ID_District = f.DistrictID
LEFT JOIN (SELECT DISTINCT realtyId FROM newcore.realty_score_category_score) sc
       ON sc.realtyId = f.Realty_Id
LEFT JOIN (
  SELECT m.Realty_Id, COUNT(*) cnt
  FROM newcore.realtymultimedia m
  JOIN newcore.multimediasubtypes s
    ON s.Id = m.MultimediaSubtype_Id AND s.MultimediaType_Id = 1
  GROUP BY m.Realty_Id
) img ON img.Realty_Id = f.Realty_Id
WHERE f.RealtyStatus = 'Ativo'
{recorte}
ORDER BY f.Realty_Id
"""


def _clausula_recorte(recorte: Collection[int] | None) -> str:
    """`AND f.Realty_Id IN (...)` da rodada AMOSTRAL, ou vazio quando não há recorte.

    Interpolado, não parametrizado, e de propósito. `consultar` não pode receber
    parâmetros com este SQL: ele tem `%` em COMENTÁRIO (`0,176% do recorte`), e
    `% d` é especificador válido para o pymysql — a regressão está registrada em
    `test_sql_com_percentual_no_texto_nao_quebra_a_ponte`. Interpolar é seguro aqui
    porque o que entra não é texto de usuário: são ids já convertidos por `int()` na
    leitura do CSV, e a validação abaixo recusa qualquer outra coisa (`bool` inclusive,
    que é subclasse de `int` e viraria `1`/`0` em silêncio).

    Ordenado: o mesmo conjunto produz o mesmo SQL (invariante 5), e o log de uma rodada
    amostral fica comparável ao de outra.
    """
    if recorte is None:
        return ""
    for i in recorte:
        if not isinstance(i, int) or isinstance(i, bool):
            raise TypeError(f"recorte pela raspagem só aceita ids inteiros, veio {i!r}")
    ids = sorted(set(recorte))
    if not ids:
        raise ValueError("recorte pela raspagem VAZIO: nenhum imóvel para coletar")
    return "  AND f.Realty_Id IN (" + ", ".join(str(i) for i in ids) + ")"


# Notas por categoria: uma linha por (imóvel, categoria avaliada).
_SQL_NOTAS = """
SELECT s.realtyId AS imovel_id, c.name AS categoria, s.score AS score
FROM newcore.realty_score_category_score s
JOIN newcore.realty_score_category c ON c.id = s.categoryId
"""


def _para_int_reais(preco: Any) -> int:
    """Preço em REAIS como int (a base guarda decimal(18,2); trunca centavos)."""
    if isinstance(preco, Decimal):
        return int(preco)
    return int(preco or 0)


def _para_date(v: Any) -> date:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    raise ValueError(f"atualizado_em não é data: {v!r}")


def linha_para_candidato(row: dict[str, Any], notas: dict[str, int] | None) -> ImovelCandidato:
    """Converte uma linha da query + as notas do imóvel no contrato do domínio.

    `notas` é None quando o imóvel não tem NENHUMA categoria avaliada (o
    domínio trata None distinto de dict vazio — ver a regra cadastro completo,
    D-007). Vem do agrupamento de _SQL_NOTAS por imóvel.
    """
    return ImovelCandidato(
        imovel_id=int(row["imovel_id"]),
        publicacao_ativa=bool(row["publicacao_ativa"]),
        categoria=row["categoria"],
        preco=_para_int_reais(row["preco"]),
        qtd_fotos=int(row["qtd_fotos"]),
        atualizado_em=_para_date(row["atualizado_em"]),
        notas_por_categoria=MappingProxyType(dict(notas)) if notas is not None else None,
        gestor_captou_ou_vendeu_30d=bool(row["gestor_ativo_30d"]),
        produtividade_gestor_30d=int(row["produtividade_gestor_30d"] or 0),
        corretores_ativos_no_distrito=int(row["ativos_no_distrito"]),
    )


def linha_para_penalizavel(row: dict[str, Any]) -> ImovelPenalizavel:
    """Converte a linha no contrato de penalidades (parte do Newcore).

    `janelas_anteriores` fica vazio: o histórico vem do Registro (Postgres),
    lido em outra etapa; na primeira rodada não há janelas.
    """
    return ImovelPenalizavel(
        imovel_id=int(row["imovel_id"]),
        janelas_anteriores=(),
        alguma_categoria_avaliada=bool(row["alguma_categoria_avaliada"]),
        leads_180d=int(row["leads_180d"] or 0),
    )


def _agrupar_notas(linhas: list[dict[str, Any]]) -> dict[int, dict[str, int]]:
    """Agrupa as linhas de _SQL_NOTAS em {imovel_id: {categoria: score}}."""
    por_imovel: dict[int, dict[str, int]] = {}
    for ln in linhas:
        por_imovel.setdefault(int(ln["imovel_id"]), {})[ln["categoria"]] = int(ln["score"])
    return por_imovel


def coletar(
    definicao_ativo: DefinicaoAtivoDistrito,
    *,
    recorte: Collection[int] | None = None,
) -> tuple[list[ImovelCandidato], list[ImovelPenalizavel]]:
    """Lê o Newcore e devolve os candidatos e os penalizáveis dos imóveis ativos.

    `definicao_ativo` escolhe a coluna de "corretor ativo no distrito" (decisão
    do dono — ver DefinicaoAtivoDistrito). `recorte`, quando dado, restringe a
    leitura a esses ids — é a rodada AMOSTRAL, cujo universo é o que a raspagem
    amarrou; quem o passa é o runner, e a planilha e o Registro declaram a amostra.
    I/O: não é testado no CI (precisa do banco); as conversões puras acima são o
    que os testes cobrem.
    """
    sql = _SQL_CANDIDATOS.format(
        coluna_ativo=definicao_ativo.value, recorte=_clausula_recorte(recorte)
    )
    linhas = _dedup_por_imovel(consultar(sql))
    notas_por_imovel = _agrupar_notas(consultar(_SQL_NOTAS))

    candidatos = [
        linha_para_candidato(row, notas_por_imovel.get(int(row["imovel_id"]))) for row in linhas
    ]
    penalizaveis = [linha_para_penalizavel(row) for row in linhas]
    return candidatos, penalizaveis


def _dedup_por_imovel(linhas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mantém uma linha por imovel_id (primeira vista), preservando a ordem.

    FT_RealtyRelation é 1:1 por Realty_Id no recorte ativo e a query não infla
    (verificado em 31/08: 48.985 linhas = 48.985 imóveis). Este dedup é a rede
    contra deriva futura — se `productivityrating`/`FT_Districts` um dia ganharem
    mais de uma linha por chave, o Coletor não passa candidatos duplicados
    adiante (o domínio deduplica por imovel_id: ImovelCandidato não é hashável).
    """
    vistos: set[int] = set()
    saida: list[dict[str, Any]] = []
    for row in linhas:
        iid = int(row["imovel_id"])
        if iid not in vistos:
            vistos.add(iid)
            saida.append(row)
    return saida
