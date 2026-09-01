"""Crivo de auditoria da rodada (D-017): fiscaliza a seleção antes da entrega.

Duas camadas de naturezas distintas (D-017 + emenda 2026-09-01):

- **Camada 1 — determinística, com VETO** (este módulo, stdlib puro): verifica
  por CÁLCULO que a seleção honra os critérios objetivos. Se alguma verificação
  falha, a rodada NÃO fica pronta (veto). Está no caminho da decisão e por isso
  é cálculo, nunca modelo (invariantes 4 e 5: mesmo resultado ⇒ mesmo veredito).
  NÃO recomputa a decisão — recebe o resultado pronto e o confere, de forma
  independente da lógica que o produziu (é o valor de um auditor: pegar o bug
  que a própria alocação não veria).

- **Camada 2 — consultiva, SEM veto** (contrato declarado abaixo, NÃO
  implementada aqui): um parecer de sanidade por modelo, só sobre AGREGADOS
  (D-006, invariante 3 — nenhuma identidade de lead/comprador/corretor), que o
  dono lê antes da aprovação. Por decisão do dono (emenda D-017), mora DENTRO do
  Redator — não é um quarto agente-modelo. Como o provedor de modelo ainda não
  foi escolhido e o Redator hoje é template, aqui só se DECLARA o contrato; a
  implementação é da fatia do Redator-com-modelo. Fica FORA do caminho da
  decisão, então não fere o invariante 4.

O que a camada 1 verifica (dominância marcada como elaboração de desenho na
D-017, ajustável): cotas não excedidas (invariante 6), piso de R$ 700.000 em
todo super destaque (D-002), super destaque nunca vindo de relaxamento
(invariante 7), nenhum imóvel em dois níveis, toda posição com justificativa, e
o CORTE do ranking honrado (nenhum elegível excluído com nota acima do corte do
seu nível — a forma verificável da "dominância").
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from dominio.alocacao import COTA_DESTAQUE, COTA_SUPER_DESTAQUE, Alocacao
from dominio.elegibilidade import PRECO_MINIMO_SUPER_DESTAQUE


@dataclass(frozen=True)
class ItemAuditavel:
    """O que a camada 1 precisa saber de cada imóvel para conferir a seleção.

    Cobre TODO elegível (para o corte) e todo recuperado por relaxamento (para
    conferir que veio ao destaque, nunca ao super). `nota_super` é None quando o
    imóvel não disputa o super (abaixo do piso, ou reprovado recuperado).
    """

    imovel_id: int
    preco: int  # em REAIS, como em elegibilidade/alocacao
    nota_super: float | None
    nota_destaque: float
    elegivel: bool
    veio_de_relaxamento: bool


@dataclass(frozen=True)
class Violacao:
    """Uma falha objetiva encontrada pela camada 1. `codigo` é estável para teste."""

    codigo: str
    detalhe: str


@dataclass(frozen=True)
class ResultadoAuditoria:
    """Veredito da camada 1. `pronta` é False se houve qualquer violação."""

    pronta: bool
    violacoes: tuple[Violacao, ...]


def auditar(alocacao: Alocacao, itens: Mapping[int, ItemAuditavel]) -> ResultadoAuditoria:
    """Camada 1 (determinística, com veto): confere a seleção contra os critérios.

    `itens` deve conter TODO imóvel alocado (senão falta justificativa) e todo
    elegível (senão o corte não pode ser conferido). Puro (invariantes 4/5):
    mesma entrada ⇒ mesmo veredito, sem I/O, sem relógio, sem modelo.
    """
    violacoes: list[Violacao] = []
    super_ids = [p.imovel_id for p in alocacao.super_destaque]
    destaque_ids = [p.imovel_id for p in alocacao.destaque]

    _checar_cotas(alocacao, violacoes)
    _checar_justificativa(super_ids, destaque_ids, itens, violacoes)
    _checar_dois_niveis(super_ids, destaque_ids, violacoes)
    _checar_piso_super(alocacao, itens, violacoes)
    _checar_super_sem_relaxamento(alocacao, itens, violacoes)
    _checar_elegibilidade_alocada(alocacao, itens, violacoes)
    _checar_corte_super(alocacao, itens, super_ids, violacoes)
    _checar_corte_destaque(alocacao, itens, super_ids, destaque_ids, violacoes)

    return ResultadoAuditoria(pronta=not violacoes, violacoes=tuple(violacoes))


def _checar_cotas(alocacao: Alocacao, violacoes: list[Violacao]) -> None:
    """Invariante 6: nenhuma cota excedida."""
    if len(alocacao.super_destaque) > COTA_SUPER_DESTAQUE:
        violacoes.append(
            Violacao(
                "cota_super_excedida", f"{len(alocacao.super_destaque)} > {COTA_SUPER_DESTAQUE}"
            )
        )
    if len(alocacao.destaque) > COTA_DESTAQUE:
        violacoes.append(
            Violacao("cota_destaque_excedida", f"{len(alocacao.destaque)} > {COTA_DESTAQUE}")
        )


def _checar_justificativa(
    super_ids: list[int],
    destaque_ids: list[int],
    itens: Mapping[int, ItemAuditavel],
    violacoes: list[Violacao],
) -> None:
    """Toda posição alocada precisa de um item (sua justificativa)."""
    sem = sorted(iid for iid in (*super_ids, *destaque_ids) if iid not in itens)
    if sem:
        violacoes.append(Violacao("sem_justificativa", f"imoveis sem item auditável: {sem}"))


def _checar_dois_niveis(
    super_ids: list[int], destaque_ids: list[int], violacoes: list[Violacao]
) -> None:
    """Um imóvel em NO MÁXIMO um nível (Spec §6.5)."""
    ambos = sorted(set(super_ids) & set(destaque_ids))
    if ambos:
        violacoes.append(Violacao("imovel_em_dois_niveis", f"{ambos}"))


def _checar_piso_super(
    alocacao: Alocacao, itens: Mapping[int, ItemAuditavel], violacoes: list[Violacao]
) -> None:
    """D-002: todo super destaque com preço ≥ R$ 700.000."""
    abaixo = sorted(
        p.imovel_id
        for p in alocacao.super_destaque
        if p.imovel_id in itens and itens[p.imovel_id].preco < PRECO_MINIMO_SUPER_DESTAQUE
    )
    if abaixo:
        violacoes.append(Violacao("piso_super_violado", f"super abaixo de 700k: {abaixo}"))


def _checar_super_sem_relaxamento(
    alocacao: Alocacao, itens: Mapping[int, ItemAuditavel], violacoes: list[Violacao]
) -> None:
    """Invariante 7: o super destaque nunca relaxa."""
    relaxados = sorted(
        p.imovel_id
        for p in alocacao.super_destaque
        if p.imovel_id in itens and itens[p.imovel_id].veio_de_relaxamento
    )
    if relaxados:
        violacoes.append(
            Violacao("super_com_relaxamento", f"super vindo de relaxamento: {relaxados}")
        )


def _checar_elegibilidade_alocada(
    alocacao: Alocacao, itens: Mapping[int, ItemAuditavel], violacoes: list[Violacao]
) -> None:
    """Toda posição alocada tem de ser legítima: um super destaque precisa ser
    ELEGÍVEL (o super nunca relaxa, inv. 7 — não há como entrar sem passar nas
    regras); um destaque precisa ser elegível OU ter vindo por relaxamento (a
    única via de um reprovado ao destaque, Spec §6.6). Um alocado que não é nem
    elegível nem recuperado vazou por bug — veto.
    """
    super_invalidos = sorted(
        p.imovel_id
        for p in alocacao.super_destaque
        if p.imovel_id in itens and not itens[p.imovel_id].elegivel
    )
    if super_invalidos:
        violacoes.append(Violacao("super_inelegivel", f"super não elegível: {super_invalidos}"))
    destaque_invalidos = sorted(
        p.imovel_id
        for p in alocacao.destaque
        if p.imovel_id in itens
        and not itens[p.imovel_id].elegivel
        and not itens[p.imovel_id].veio_de_relaxamento
    )
    if destaque_invalidos:
        violacoes.append(
            Violacao(
                "destaque_inelegivel_sem_relaxamento",
                f"destaque nem elegível nem recuperado: {destaque_invalidos}",
            )
        )


def _checar_corte_super(
    alocacao: Alocacao,
    itens: Mapping[int, ItemAuditavel],
    super_ids: list[int],
    violacoes: list[Violacao],
) -> None:
    """Corte do super honrado (forma verificável da "dominância"): nenhum elegível
    APTO ao super (preço ≥ 700k) que ficou de fora tem nota de super acima da
    menor nota do super selecionado. Se o super não está cheio, não há aptos
    excluídos e a verificação é vacuamente verdadeira.
    """
    if not alocacao.super_destaque:
        return
    menor_dentro = min(p.nota for p in alocacao.super_destaque)
    dentro = set(super_ids)
    excedentes = sorted(
        it.imovel_id
        for it in itens.values()
        if it.elegivel
        and it.preco >= PRECO_MINIMO_SUPER_DESTAQUE
        and it.imovel_id not in dentro
        and it.nota_super is not None
        and it.nota_super > menor_dentro
    )
    if excedentes:
        violacoes.append(
            Violacao(
                "corte_super_violado",
                f"elegíveis não selecionados para o super com nota maior: {excedentes}",
            )
        )


def _checar_corte_destaque(
    alocacao: Alocacao,
    itens: Mapping[int, ItemAuditavel],
    super_ids: list[int],
    destaque_ids: list[int],
    violacoes: list[Violacao],
) -> None:
    """Corte do destaque honrado: nenhum elegível excluído (fora de super E de
    destaque) tem nota de destaque acima da menor nota do destaque de RANKING
    (os recuperados por relaxamento não entram no corte — vêm por cedência, não
    por nota, e só existem quando o ranking esgotou os elegíveis).
    """
    ranking = [p for p in alocacao.destaque if not _veio_de_relaxamento(p.imovel_id, itens)]
    if not ranking:
        return
    menor_dentro = min(p.nota for p in ranking)
    colocados = set(super_ids) | set(destaque_ids)
    excedentes = sorted(
        it.imovel_id
        for it in itens.values()
        if it.elegivel and it.imovel_id not in colocados and it.nota_destaque > menor_dentro
    )
    if excedentes:
        violacoes.append(
            Violacao(
                "corte_destaque_violado",
                f"elegíveis fora do destaque com nota maior: {excedentes}",
            )
        )


def _veio_de_relaxamento(imovel_id: int, itens: Mapping[int, ItemAuditavel]) -> bool:
    item = itens.get(imovel_id)
    return item is not None and item.veio_de_relaxamento


# --------------------------------------------------------------------------- #
# Camada 2 — contrato DECLARADO (não implementado aqui; mora no Redator).
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class AgregadosParaParecer:
    """O que a camada 2 (parecer por modelo, no Redator) recebe — SÓ AGREGADOS.

    Invariante 3 / D-006: nenhuma identidade de lead, comprador ou corretor. São
    contagens e distribuições sobre a SELEÇÃO, o material com que o modelo julga
    se a lista reflete imóveis atrativos / que atraem leads / vendidos no período
    — sem nunca ver uma pessoa. Este é o contrato; a fatia do Redator-com-modelo
    é quem o preenche e chama o provedor. Aqui não há chamada de modelo.
    """

    n_super: int
    n_destaque: int
    n_recuperados_relaxamento: int
    # perfil de conversão que puxou cada posição → contagem (distribuição de
    # concentração/diversidade, o sinal da de-saturação).
    distribuicao_perfis_super: Mapping[str, int]
    distribuicao_perfis_destaque: Mapping[str, int]
    # limitações declaradas da rodada (degradações), para o parecer contextualizar.
    degradacoes: tuple[str, ...]
    # veredito da camada 1: o parecer nunca contradiz um veto determinístico.
    camada1_pronta: bool
