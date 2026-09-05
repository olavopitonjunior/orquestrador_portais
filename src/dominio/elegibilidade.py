"""Elegibilidade: nove regras eliminatórias gerais + piso de nível do super destaque.

Fonte: Spec §6.1, lida conforme as decisões D-002 e D-003 (docs/decisoes.md), mais a
D-027 (04/09/2026): o PERFIL DE CONVERSÃO vira a nona regra — só entra quem casa com um
perfil robusto que contenha a faixa de preço. A regra é aplicada pela costura, que
conhece os perfis; aqui o veredito chega pronto no candidato (`casa_perfil_de_conversao`).
O piso de R$ 700.000 segue condição de nível, aplicada na alocação:
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
    """As nove regras eliminatórias gerais (D-002/D-003/D-027)."""

    STATUS_ATIVO = "status_ativo"
    CATEGORIA = "categoria"
    PRECO_GERAL = "preco_geral"
    FOTOS = "fotos"
    ATUALIZACAO_90D = "atualizacao_90d"
    CADASTRO_COMPLETO = "cadastro_completo"
    GESTOR_PRODUTIVO = "gestor_produtivo"
    CAPACIDADE_DISTRITO = "capacidade_distrito"
    # D-027: parece com o que vendeu (perfil robusto contendo a faixa de preço).
    PERFIL_DE_CONVERSAO = "perfil_de_conversao"


# Ordem de cedência no relaxamento (Spec §6.6 + D-027). Invariante 7: aplica-se
# apenas às posições de destaque. STATUS, CATEGORIA e PRECO_GERAL nunca relaxam.
# O perfil é o PRIMEIRO degrau cedido, por decisão do dono (04/09/2026): "preferir
# um imóvel com cadastro impecável fora do perfil a um dentro do perfil com nove
# fotos". Consequência declarada: no destaque o filtro é a primeira coisa de que o
# sistema abre mão quando faltam imóveis; no super destaque, que nunca relaxa, ele
# morde inteiro.
ORDEM_RELAXAMENTO: tuple[Regra, ...] = (
    Regra.PERFIL_DE_CONVERSAO,
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
    # REGRA de elegibilidade "gestor produtivo" (Spec §6.1): captou OU vendeu em
    # 30d. NÃO confundir com o fator de ranking abaixo — este binário decide a
    # elegibilidade e não mudou com nenhum redesenho do ranking.
    gestor_captou_ou_vendeu_30d: bool
    # Sinal de DESEMPATE (D-028; era o fator F4 da D-017): intensidade CONTÍNUA da
    # gestor em 30d = taxa semanal de captação (Captations_per_week_last_30d,
    # 0..15) + flag de venda recente (LastSell em 30d). A base NÃO expõe
    # contagem de vendas em 30d (Sells é de 365d), então a dimensão de venda
    # entra só como flag — limitação declarada, montada pela coleta. Substitui,
    # no ranking, o uso do binário acima (que era redundante com a elegibilidade).
    produtividade_gestor_30d: int
    corretores_ativos_no_distrito: int
    # DESCRITIVO, não regra: o código do anúncio no portal (`realties.NewIdMarketingRotation`,
    # igual ao `codigoImovel` do Canal Pro em 300/300, medido em 03/09/2026). Vai para o
    # CSV da apuração. `None` = a coleta não trouxe; nenhuma regra o lê.
    codigo_portal: str | None = None
    # Veredito do filtro de perfil (D-027), carregado pela COSTURA, que conhece os
    # perfis: True casa, False não casa (reprova em PERFIL_DE_CONVERSAO), None = não
    # avaliado — e não avaliado NÃO reprova: a regra só existe quando alguém a aplicou.
    # A costura garante que nenhum candidato chega à decisão com None.
    casa_perfil_de_conversao: bool | None = None
    # O gestor logou dentro da janela declarada (D-029)? Não é regra eliminatória —
    # medido em 04/09/2026: quem não loga também não capta nem vende, então excluiria
    # zero imóveis a mais. É TRAVA do relaxamento: o degrau `gestor_produtivo` não
    # recupera imóvel de gestor sem login. None = a coleta não trouxe.
    gestor_logou_na_janela: bool | None = None

    # Instâncias não são hasháveis (o mapping impede hash estável); deduplique
    # por imovel_id. O __post_init__ copia o mapping para um proxy imutável,
    # de modo que mutações no dict original não vazem para dentro da instância.
    __hash__ = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.notas_por_categoria is not None:
            object.__setattr__(
                self, "notas_por_categoria", MappingProxyType(dict(self.notas_por_categoria))
            )


def regras_reprovadas(
    imovel: ImovelCandidato,
    data_referencia: date,
    *,
    minimo_corretores_distrito: int = MINIMO_CORRETORES_ATIVOS_DISTRITO,
) -> frozenset[Regra]:
    """Aplica as nove regras em conjunto e devolve as reprovadas.

    Reprovar em uma basta para excluir (Spec §6.1); devolver todas as
    reprovadas — e não parar na primeira — é o que permite ao Decisor
    saber quais imóveis cada degrau de relaxamento recupera.

    `minimo_corretores_distrito` é o valor ADOTADO (2, D-015) e passa a ser
    declarável por rodada (D-033); o default é o adotado, não um palpite.
    """
    if minimo_corretores_distrito < 1:
        raise ValueError(f"mínimo de corretores no distrito inválido: {minimo_corretores_distrito}")
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
    # explícita. Para avaliação PARCIAL vale a decisão D-007 (docs/decisoes.md,
    # ratificada pelo dono em 29/08/2026): apenas zero explícito reprova;
    # categoria ausente não é zero — a única leitura consistente com o funil
    # medido do PRD.
    if imovel.notas_por_categoria is not None and any(
        nota == 0 for nota in imovel.notas_por_categoria.values()
    ):
        reprovadas.add(Regra.CADASTRO_COMPLETO)
    if not imovel.gestor_captou_ou_vendeu_30d:
        reprovadas.add(Regra.GESTOR_PRODUTIVO)
    if imovel.corretores_ativos_no_distrito < minimo_corretores_distrito:
        reprovadas.add(Regra.CAPACIDADE_DISTRITO)
    # D-027: só o veredito FALSO reprova. None é "ninguém aplicou o filtro" (por
    # exemplo, a medição do funil sem perfis) e não pode virar reprovação em silêncio.
    if imovel.casa_perfil_de_conversao is False:
        reprovadas.add(Regra.PERFIL_DE_CONVERSAO)

    return frozenset(reprovadas)


# As três funções abaixo são AUXILIARES DE LEITURA sobre `regras_reprovadas`, e não
# têm chamador de produção: a rodada usa `regras_reprovadas` direto, porque precisa
# saber QUAIS regras reprovaram, não só se reprovou. Existem porque expressam a regra
# na linguagem da Spec e são exercidas pelos testes. Recebem o mínimo do distrito
# porque a D-033 o tornou declarável: sem o kwarg, elas leriam a regra com um valor
# que a rodada pode não estar usando — uma segunda leitura da mesma regra.


def elegivel(
    imovel: ImovelCandidato,
    data_referencia: date,
    *,
    minimo_corretores_distrito: int = MINIMO_CORRETORES_ATIVOS_DISTRITO,
) -> bool:
    """Elegível ao nível destaque: aprova nas nove regras. Auxiliar de leitura."""
    return not regras_reprovadas(
        imovel, data_referencia, minimo_corretores_distrito=minimo_corretores_distrito
    )


def candidato_super_destaque(
    imovel: ImovelCandidato,
    data_referencia: date,
    *,
    minimo_corretores_distrito: int = MINIMO_CORRETORES_ATIVOS_DISTRITO,
) -> bool:
    """Candidato ao super destaque: elegível E acima do piso de nível (D-002).
    Auxiliar de leitura.

    Reprovar aqui não exclui do nível destaque. As posições de super destaque
    nunca recebem imóvel vindo de relaxamento (invariante 7).
    """
    return (
        elegivel(imovel, data_referencia, minimo_corretores_distrito=minimo_corretores_distrito)
        and imovel.preco >= PRECO_MINIMO_SUPER_DESTAQUE
    )


def elegivel_com_relaxamento(
    imovel: ImovelCandidato,
    data_referencia: date,
    regras_cedidas: frozenset[Regra],
    *,
    minimo_corretores_distrito: int = MINIMO_CORRETORES_ATIVOS_DISTRITO,
) -> bool:
    """Elegível ao destaque quando as regras cedidas são desconsideradas.
    Auxiliar de leitura: o Decisor desce os degraus por `dominio.relaxamento`.

    As regras fora da ordem de cedência (status, categoria, preço geral) nunca
    podem constar de `regras_cedidas`.
    """
    if not regras_cedidas <= frozenset(ORDEM_RELAXAMENTO):
        indevidas = sorted(r.value for r in regras_cedidas - frozenset(ORDEM_RELAXAMENTO))
        raise ValueError(f"regras não relaxáveis: {indevidas}")
    return (
        regras_reprovadas(
            imovel, data_referencia, minimo_corretores_distrito=minimo_corretores_distrito
        )
        <= regras_cedidas
    )
