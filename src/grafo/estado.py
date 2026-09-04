"""Estado da rodada e fontes do grafo (marco F, esqueleto G1).

O estado que atravessa os nós do LangGraph (Spec §7.2: os três estados
completa/degradada/abortada; a entidade `rodada` do Registro já prevê os campos).
Puro de dados: nenhuma lógica de decisão aqui — os nós (fluxo.py) chamam os
módulos de domínio já prontos e escrevem seus produtos neste estado.

As FONTES de dado (coleta interna, dimensões, vendas) são INJETADAS, para o
grafo rodar em teste sem MySQL: em produção, ligadas ao Coletor Interno real;
em teste, a fakes. Nenhum timestamp/ID de rodada entra no cálculo da lista ou
das contagens (invariante 5): o estado carrega dados, não relógio.
"""

from __future__ import annotations

import operator
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Annotated, TypedDict

from dados.coletor_externo import ColetaExterna, DesempenhoAnuncio
from dominio.auditoria import ResultadoAuditoria
from dominio.elegibilidade import ImovelCandidato
from dominio.penalidades import ImovelPenalizavel, JanelaCrua
from dominio.perfil import ImovelVendido, PerfilConversao
from piloto.decisao import ResultadoDecisao
from piloto.semelhanca import DimensoesImovel


class Estado(StrEnum):
    """Os estados da rodada (Spec §7.2). EM_ANDAMENTO é o inicial, antes do
    veredito final; os três terminais são completa/degradada/abortada."""

    EM_ANDAMENTO = "em_andamento"
    COMPLETA = "completa"
    DEGRADADA = "degradada"
    ABORTADA = "abortada"


def _merge_dict(a: Mapping[str, bool], b: Mapping[str, bool]) -> dict[str, bool]:
    """Reducer para `prontos`: nós paralelos (perfil, externo) escrevem chaves
    distintas do mesmo dict — junta sem perder nenhuma."""
    return {**a, **b}


class EstadoRodada(TypedDict, total=False):
    """O estado que atravessa o grafo. `total=False`: cada nó preenche a sua parte.

    `degradacoes` e `prontos` têm reducer porque os nós paralelos (Analista de
    Perfil e Coletor Externo) escrevem os dois ao mesmo tempo.
    """

    data_referencia: date
    # produtos dos nós
    candidatos: list[ImovelCandidato]
    penalizaveis: dict[int, ImovelPenalizavel]
    dims: dict[int, DimensoesImovel]
    perfis: tuple[PerfilConversao, ...]
    externo_presente: bool
    # O que a raspagem trouxe CRU por imóvel (nota, visualizações, cliques), entre ou
    # não no cálculo. É o que a costura consome para a nota do portal (D-028) quando
    # `externo_presente` — e o que a apuração mostra mesmo quando ele não pesou.
    anuncios_por_imovel: dict[int, DesempenhoAnuncio]
    # Spec §3.1: a aba de resumo carrega OBRIGATORIAMENTE a idade do dado do portal e
    # a taxa de amarração. Os dois vinham no `ResultadoExterno` e eram descartados
    # justamente no caso de sucesso — só apareciam embutidos no motivo da REJEIÇÃO.
    # Ou seja: na rodada completa, os dois números exigidos não existiam.
    externo_taxa_amarracao: float
    externo_idade_dias: int | None  # None se a coleta não tem timestamp
    resultado: ResultadoDecisao | None
    veredito: ResultadoAuditoria | None
    # controle
    estado: Estado
    prontos: Annotated[dict[str, bool], _merge_dict]
    degradacoes: Annotated[list[str], operator.add]
    # Quantas janelas ENCERRADAS o Registro devolveu. `None` = o Registro NÃO foi
    # consultado (fonte não fiada), que é diferente de consultar e não achar nada —
    # e a limitação da planilha afirma o segundo. Sem a distinção, uma rodada montada
    # sem a fonte declararia "o Registro não devolveu janela nenhuma" sem ter
    # perguntado: a mesma classe de limitação falsa que este projeto já corrigiu duas
    # vezes. Junto com o limiar nulo, são TRÊS causas distintas para a mesma coluna
    # 0,0, e a planilha precisa dizer qual.
    janelas_lidas: int | None
    # Histórico CRU de janelas por imóvel, sem julgamento — insumo da coluna que o
    # PRD exige. `None` = NÃO consultado; dict vazio = consultado e sem janela. São
    # estados diferentes, e um sinal só impede a combinação incoerente.
    historico_janelas: dict[int, tuple[JanelaCrua, ...]] | None
    motivo_aborto: str | None


@dataclass(frozen=True)
class Fontes:
    """As fontes de dado injetadas nos nós de coleta — ligadas ao Coletor Interno
    real em produção, a fakes no teste. Mantém o grafo rodável sem MySQL e não
    põe I/O dentro do domínio.
    """

    coletar_interno: Callable[[], tuple[Sequence[ImovelCandidato], Sequence[ImovelPenalizavel]]]
    coletar_dimensoes: Callable[[], Mapping[int, DimensoesImovel]]
    coletar_vendas: Callable[[], tuple[Sequence[ImovelVendido], int]]
    # Coletor Externo: lê a saída do raspador (out/*.csv + status.json). None =
    # sem raspagem (esqueleto) → a rodada degrada nesse fator, como antes.
    coletar_externo: Callable[[], ColetaExterna] | None = None
    # O histórico de janelas do Registro, CRU (nível, leads, ciclos) — o julgamento
    # "atingiu resultado" é do domínio, com o limiar nº 14 injetado. Fonte separada
    # das demais porque a Spec §5 a atribui ao DECISOR: "o único agente que lê o
    # Registro durante a rodada, e o faz para obter o histórico de janelas necessário
    # ao cálculo da penalidade". None = rodada sem acesso ao Registro (teste, ensaio).
    coletar_janelas: (
        Callable[[Sequence[int], date], Mapping[int, tuple[JanelaCrua, ...]]] | None
    ) = None


# Etapas cujo "pronto" precisa valer para a rodada ser COMPLETA (Spec §7.3).
# O Coletor Externo entra aqui: sem raspagem admitida (ausente/velha/amarração
# baixa) a rodada é DEGRADADA nesse fator; com a raspagem fresca e amarrada (G4),
# o "externo" fica pronto e a rodada pode ser COMPLETA.
# `janelas` entrou com o consumidor da §6.4 (D-023): sem o histórico do Registro a
# decisão prossegue com dado parcial — uma das três penalidades não incide —, e a
# Spec §7.2 chama isso de DEGRADADA, não de rodada completa. Sem a etapa aqui, uma
# rodada cujo Registro caiu sairia COMPLETA com a penalidade silenciosamente inerte.
ETAPAS_PARA_COMPLETA = (
    "coletor_interno",
    "perfil",
    "externo",
    "janelas",
    "decisor",
    "crivo",
    "redator",
)


def estado_final(estado: EstadoRodada) -> Estado:
    """Deriva o estado terminal da rodada a partir do que cada etapa reportou.

    - ABORTADA se a coleta interna não ficou pronta (Spec §7.2: sem estoque não
      há decisão) — já marcada pelo nó de coleta.
    - COMPLETA se TODAS as etapas de `ETAPAS_PARA_COMPLETA` ficaram prontas.
    - DEGRADADA caso contrário (alguma fonte falhou e a decisão prosseguiu com
      dado parcial) — o caso do esqueleto G1, sem Coletor Externo.

    Puro e determinístico (invariante 5): função só do dicionário de prontos.
    """
    if estado.get("estado") == Estado.ABORTADA:
        return Estado.ABORTADA
    prontos = estado.get("prontos", {})
    if all(prontos.get(etapa, False) for etapa in ETAPAS_PARA_COMPLETA):
        return Estado.COMPLETA
    return Estado.DEGRADADA
