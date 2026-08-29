"""Elegibilidade: oito regras eliminatórias gerais + piso de nível do super destaque.

Fonte: Spec §6.1, lida conforme as decisões D-002 e D-003 (docs/decisoes.md):
o piso de R$ 700.000 é condição de candidatura ao super destaque aplicada na
alocação, não regra eliminatória; o status impeditivo (vendido/reservado/
removido) é regra de saída imediata fora do ciclo, tratada na rotação.

Invariantes 4 e 5: este módulo é cálculo puro — sem I/O, sem relógio próprio
(a data de referência é entrada), sem aleatoriedade, sem chamada a modelo.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import Enum
from types import MappingProxyType

# Parâmetros COM valor definido (PRD, tabela de parâmetros; Spec §6.1).
CATEGORIAS_ACEITAS = frozenset(
    {"Casa", "Casa de condomínio", "Sobrado", "Cobertura", "Apartamento"}
)
PRECO_MINIMO_GERAL = 300_000
PRECO_MINIMO_SUPER_DESTAQUE = 700_000  # piso de nível (D-002), não elimina do destaque
MINIMO_FOTOS = 10
JANELA_ATUALIZACAO_DIAS = 90
MINIMO_CORRETORES_ATIVOS_DISTRITO = 2


class Regra(Enum):
    """As oito regras eliminatórias gerais (D-002/D-003)."""

    STATUS_ATIVO = "status_ativo"
    CATEGORIA = "categoria"
    PRECO_GERAL = "preco_geral"
    FOTOS = "fotos"
    ATUALIZACAO_90D = "atualizacao_90d"
    CADASTRO_COMPLETO = "cadastro_completo"
    GESTOR_PRODUTIVO = "gestor_produtivo"
    CAPACIDADE_DISTRITO = "capacidade_distrito"


# Ordem de cedência no relaxamento (Spec §6.6). Invariante 7: aplica-se apenas
# às posições de destaque. STATUS, CATEGORIA e PRECO_GERAL nunca relaxam.
ORDEM_RELAXAMENTO: tuple[Regra, ...] = (
    Regra.FOTOS,
    Regra.CADASTRO_COMPLETO,
    Regra.ATUALIZACAO_90D,
    Regra.GESTOR_PRODUTIVO,
    Regra.CAPACIDADE_DISTRITO,
)


@dataclass(frozen=True)
class ImovelCandidato:
    """Entrada da elegibilidade, montada pelo Coletor Interno.

    Os sinais derivados (gestor produtivo, corretores ativos no distrito) chegam
    prontos: derivá-los de productivityrating é responsabilidade da coleta,
    não do domínio. A ligação imóvel↔distrito vem de FT_RealtyRelation, nunca
    do endereço (defeito 2 do mapa de dados).
    """

    imovel_id: int
    publicacao_ativa: bool
    categoria: str
    # Em REAIS — os pisos da Spec §6.1 são em reais, e a unidade foi confirmada
    # contra a base em 29/08/2026 (35.592 ativos ≥ 300.000 vs. funil medido de
    # 35.560; apenas 232 ≥ 30.000.000). Se a fonte um dia entregar centavos,
    # a conversão é responsabilidade do Coletor Interno, antes deste módulo.
    preco: int
    qtd_fotos: int
    atualizado_em: date
    # Notas por categoria da nota interna (realty_score_category_score).
    # None = imóvel sem nenhuma avaliação por categoria: PASSA na regra e
    # recebe penalidade no ranking (Spec §6.1) — cada vez mais comum, porque o
    # pipeline está morto desde 16/10/2025 (defeito 4 do mapa de dados).
    notas_por_categoria: Mapping[str, int] | None
    gestor_captou_ou_vendeu_30d: bool
    corretores_ativos_no_distrito: int

    # Instâncias não são hasháveis (o mapping impede hash estável); deduplique
    # por imovel_id. O __post_init__ copia o mapping para um proxy imutável,
    # de modo que mutações no dict original não vazem para dentro da instância.
    __hash__ = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.notas_por_categoria is not None:
            object.__setattr__(
                self, "notas_por_categoria", MappingProxyType(dict(self.notas_por_categoria))
            )


def regras_reprovadas(imovel: ImovelCandidato, data_referencia: date) -> frozenset[Regra]:
    """Aplica as oito regras em conjunto e devolve as reprovadas.

    Reprovar em uma basta para excluir (Spec §6.1); devolver todas as
    reprovadas — e não parar na primeira — é o que permite ao Decisor
    saber quais imóveis cada degrau de relaxamento recupera.
    """
    reprovadas: set[Regra] = set()

    if not imovel.publicacao_ativa:
        reprovadas.add(Regra.STATUS_ATIVO)
    if imovel.categoria not in CATEGORIAS_ACEITAS:
        reprovadas.add(Regra.CATEGORIA)
    if imovel.preco < PRECO_MINIMO_GERAL:
        reprovadas.add(Regra.PRECO_GERAL)
    if imovel.qtd_fotos < MINIMO_FOTOS:
        reprovadas.add(Regra.FOTOS)
    # Data de atualização no futuro passa (diferença negativa): anomalia de
    # dado é responsabilidade da coleta interna, que aborta a rodada com dado
    # inválido (Spec §7.3) — este módulo não julga qualidade de fonte.
    if (data_referencia - imovel.atualizado_em).days > JANELA_ATUALIZACAO_DIAS:
        reprovadas.add(Regra.ATUALIZACAO_90D)
    # Cadastro completo: "nenhuma das sete categorias da nota interna com
    # pontuação zero". Sem avaliação alguma (None), o imóvel passa — a Spec é
    # explícita. Leitura adotada para avaliação PARCIAL (média medida: 4,7 das
    # 7 categorias): apenas zeros explícitos reprovam; categoria ausente não é
    # zero. Interpretação registrada no PR — se a Spec quiser as 7 presentes e
    # não zeradas, trocar por: len(notas) == 7 and all(n > 0).
    if imovel.notas_por_categoria is not None and any(
        nota == 0 for nota in imovel.notas_por_categoria.values()
    ):
        reprovadas.add(Regra.CADASTRO_COMPLETO)
    if not imovel.gestor_captou_ou_vendeu_30d:
        reprovadas.add(Regra.GESTOR_PRODUTIVO)
    if imovel.corretores_ativos_no_distrito < MINIMO_CORRETORES_ATIVOS_DISTRITO:
        reprovadas.add(Regra.CAPACIDADE_DISTRITO)

    return frozenset(reprovadas)


def elegivel(imovel: ImovelCandidato, data_referencia: date) -> bool:
    """Elegível ao nível destaque: aprova nas oito regras."""
    return not regras_reprovadas(imovel, data_referencia)


def candidato_super_destaque(imovel: ImovelCandidato, data_referencia: date) -> bool:
    """Candidato ao super destaque: elegível E acima do piso de nível (D-002).

    Reprovar aqui não exclui do nível destaque. As posições de super destaque
    nunca recebem imóvel vindo de relaxamento (invariante 7).
    """
    return elegivel(imovel, data_referencia) and imovel.preco >= PRECO_MINIMO_SUPER_DESTAQUE


def elegivel_com_relaxamento(
    imovel: ImovelCandidato, data_referencia: date, regras_cedidas: frozenset[Regra]
) -> bool:
    """Elegível ao destaque quando as regras cedidas são desconsideradas.

    Usada pelo Decisor ao descer os degraus de ORDEM_RELAXAMENTO. As regras
    fora da ordem de cedência (status, categoria, preço geral) nunca podem
    constar de `regras_cedidas`.
    """
    if not regras_cedidas <= frozenset(ORDEM_RELAXAMENTO):
        indevidas = sorted(r.value for r in regras_cedidas - frozenset(ORDEM_RELAXAMENTO))
        raise ValueError(f"regras não relaxáveis: {indevidas}")
    return regras_reprovadas(imovel, data_referencia) <= regras_cedidas
