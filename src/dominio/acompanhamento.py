"""Apuração da rodada de SEGUNDA (acompanhamento) — Spec §4.

Mede o que a carga de sexta produziu desde que foi aplicada: quantos leads cada
imóvel em posição paga gerou e quais leads ficaram sem tratamento. É o produto do
Monitor Operacional (Spec §5), que consome "banco de leads + planilha aprovada
vigente" e entrega "lista de leads sem tratamento e contagem de leads por imóvel
em posição paga".

Módulo PURO (stdlib): sem I/O, sem modelo, determinístico — a leitura do banco e a
gravação no Registro ficam nos nós/`src/dados`. A rodada de segunda NÃO raspa nada
e não decide nada: só mede (nenhuma regra de elegibilidade/ranking aqui).

DADO PESSOAL (invariante 3): `LeadSemTratamento` carrega identidade — id do lead,
corretor gestor, gestor de distrito (colunas exigidas pela Spec §4.2). Isso existe
para a PLANILHA, que é lida por gente; o invariante proíbe o ENVIO a modelo, não a
modelagem. A fronteira é EXECUTÁVEL, não só documental: quem fala com modelo recebe
`PayloadModelo` (via `payload_para_modelo`), nunca `ResultadoAcompanhamento`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import TypeVar

_T = TypeVar("_T")


class Nivel(StrEnum):
    """Vocabulário FECHADO dos níveis (Spec §2.1; o mesmo CHECK do Registro).
    Fechado de propósito: um `"superdestaque"` datilografado sairia dos dois
    somatórios do resumo em silêncio."""

    SUPER_DESTAQUE = "super_destaque"
    DESTAQUE = "destaque"


@dataclass(frozen=True)
class PosicaoPaga:
    """Um imóvel que a carga de sexta colocou em posição paga."""

    imovel_id: int
    nivel: Nivel

    def __post_init__(self) -> None:
        # Valida na construção, como o resto do domínio (alocacao/penalidades/…).
        if self.imovel_id <= 0:
            raise ValueError(f"imovel_id inválido: {self.imovel_id}")
        if str(self.nivel) not in {n.value for n in Nivel}:
            raise ValueError(f"nível fora do vocabulário fechado (Spec §2.1): {self.nivel!r}")


@dataclass(frozen=True)
class LeadDoPeriodo:
    """Um lead recebido no período coberto, já amarrado ao imóvel de origem.

    `atendimento_registrado` e `contato_registrado` são os dois sinais da Spec §4.2
    — um lead só é "sem tratamento" quando AMBOS faltam (critério conservador, o
    abandono indiscutível).

    `entrada` e `distribuicao` são grandezas DISTINTAS, ambas exigidas pela §4.2
    ("data de entrada" e "tempo decorrido desde a distribuição"): o lead entra e
    depois é distribuído a um corretor. Medir desde a entrada diluiria a
    responsabilidade do corretor com a latência da distribuição — por isso uma NUNCA
    substitui a outra. `distribuicao=None` significa distribuição não registrada, e
    a ausência é declarada (contada no resumo), nunca preenchida com a entrada.
    """

    lead_id: int
    imovel_id: int
    entrada: date
    atendimento_registrado: bool
    contato_registrado: bool
    distribuicao: date | None = None
    corretor_gestor: str | None = None  # PII: planilha, nunca modelo
    gestor_distrito: str | None = None  # PII: planilha, nunca modelo
    distrito: str | None = None


def sem_tratamento(lead: LeadDoPeriodo) -> bool:
    """Spec §4.2: sem atendimento **e** sem contato. As duas ausências, juntas."""
    return not lead.atendimento_registrado and not lead.contato_registrado


@dataclass(frozen=True)
class LeadSemTratamento:
    """Uma linha da aba "Leads sem tratamento" (Spec §4.2), com as oito colunas
    exigidas. CARREGA PII — planilha, nunca modelo."""

    lead_id: int
    imovel_id: int
    nivel: Nivel
    entrada: date
    # "tempo decorrido desde a distribuição" (§4.2). None = distribuição não
    # registrada na origem: ausência declarada, não substituída pela entrada.
    tempo_desde_distribuicao: int | None
    corretor_gestor: str | None
    gestor_distrito: str | None
    distrito: str | None


@dataclass(frozen=True)
class DesempenhoImovel:
    """Uma linha da aba "Desempenho por imóvel" (Spec §4.3). Sem PII."""

    imovel_id: int
    nivel: Nivel
    leads_gerados: int
    leads_sem_tratamento: int
    semanas_consecutivas: int | None  # do histórico de janelas; None = não informado
    leads_acumulados_janela: int | None


@dataclass(frozen=True)
class ResumoAcompanhamento:
    """Totais da aba Resumo (Spec §4.1). SÓ AGREGADOS — é o que pode ir a modelo
    (invariante 3 / D-006), diferente de `LeadSemTratamento`."""

    rodada_decisao_id: int  # a carga de referência
    inicio_periodo: date
    fim_periodo: date
    posicoes_super: int
    posicoes_destaque: int
    leads_gerados: int
    leads_sem_tratamento: int
    imoveis_sem_lead: int
    # Qualidade do insumo, declarada em vez de silenciosa — TODO descarte é contado:
    leads_fora_do_periodo: int  # descartados por não pertencerem ao período
    leads_fora_da_carga: int  # descartados por serem de imóvel fora da carga
    # ATENÇÃO ao denominador: os dois contadores abaixo são sobre os leads SEM
    # TRATAMENTO (a lista da §4.2), não sobre todos os leads do período. O nome diz
    # isso de propósito — estes campos vão ao `PayloadModelo`, e um resumo que
    # dissesse "N leads sem responsável" sobre o denominador errado seria falso.
    # O "pronto" da rodada de segunda exige responsável nomeado (PRD): se
    # `sem_tratamento_sem_responsavel > 0`, o pronto não está cumprido.
    sem_tratamento_sem_responsavel: int
    sem_tratamento_sem_distribuicao: int  # sem data de distribuição na origem


@dataclass(frozen=True)
class ResultadoAcompanhamento:
    """O que a rodada de segunda apurou. Vira `registro.resultado_carga` — com o id
    da rodada de acompanhamento suprido pela camada de ESCRITA (que conhece o
    próprio id); aqui viaja só a carga de referência (`rodada_decisao_id`).

    ATENÇÃO: carrega PII (em `leads_sem_tratamento`). NUNCA envie este objeto a
    modelo — use `payload_para_modelo()`, a única porta autorizada.
    """

    resumo: ResumoAcompanhamento
    desempenho: tuple[DesempenhoImovel, ...]  # TODAS as posições, inclusive zero lead
    leads_sem_tratamento: tuple[LeadSemTratamento, ...]


@dataclass(frozen=True)
class PayloadModelo:
    """O ÚNICO recorte do acompanhamento que pode ser enviado a modelo (invariante 3
    / D-006): agregados da rodada + desempenho por imóvel (características de imóvel
    são explicitamente permitidas; identidade de pessoa, não).

    Tipo próprio de propósito: torna a fronteira EXECUTÁVEL em vez de documental —
    um nó que precise falar com modelo recebe `PayloadModelo`, não
    `ResultadoAcompanhamento`, e o type checker impede o objeto com PII de passar.
    """

    resumo: ResumoAcompanhamento
    desempenho: tuple[DesempenhoImovel, ...]


def payload_para_modelo(resultado: ResultadoAcompanhamento) -> PayloadModelo:
    """Projeta o resultado no recorte sem identidade de pessoa. É a ÚNICA porta de
    entrada de um modelo neste fluxo: descarta `leads_sem_tratamento` (PII) e
    entrega só agregados + desempenho por imóvel."""
    return PayloadModelo(resumo=resultado.resumo, desempenho=resultado.desempenho)


class SemCargaAprovada(Exception):
    """Spec §7.3: sem planilha aprovada vigente, o relatório NÃO é emitido e a
    ausência é declarada. Não é falha do sistema — é ausência de insumo.

    NOTA de escopo: este módulo puro só sabe reprovar a carga VAZIA. Conferir que a
    rodada de decisão de referência está de fato APROVADA (D-001) é da camada que lê
    o Registro, e a "declaração da ausência" (registrar a rodada e avisar o gestor)
    é do nó — a §7.3 só fica cumprida com as duas metades.
    """


def apurar(
    *,
    rodada_decisao_id: int,
    posicoes: Sequence[PosicaoPaga],
    leads: Sequence[LeadDoPeriodo],
    inicio_periodo: date,
    fim_periodo: date,
    historico: Mapping[int, tuple[int | None, int | None]] | None = None,
) -> ResultadoAcompanhamento:
    """Apura o período contra a carga aprovada de referência (Spec §4).

    `historico` traz, por imóvel, (semanas_consecutivas, leads_acumulados_janela)
    do histórico de janelas do Registro; imóvel ausente fica com None nas duas
    colunas — declarado, não inventado.

    Determinístico: a saída é ordenada por (nível, imóvel) e por (entrada, lead),
    nunca pela ordem de chegada da consulta. São descartados, com contagem no
    resumo: lead fora do período (a Spec mede "leads gerados NO período"), lead de
    imóvel fora da carga, e lead repetido por `lead_id`.
    """
    if not posicoes:
        raise SemCargaAprovada(
            "nenhuma posição na carga aprovada de referência — sem planilha aprovada "
            "vigente o relatório não é emitido (Spec §7.3)"
        )
    if fim_periodo < inicio_periodo:
        raise ValueError("fim do período anterior ao início")

    # NÃO é redundante com o `__post_init__` de `PosicaoPaga`: pickle/deepcopy não
    # executam `__post_init__`, e o estado do grafo atravessa o checkpointer
    # Postgres — uma posição que voltou de serialização só é conferida aqui.
    niveis_validos = {n.value for n in Nivel}
    invalidos = sorted({str(p.nivel) for p in posicoes} - niveis_validos)
    if invalidos:
        raise ValueError(f"nível fora do vocabulário fechado (Spec §2.1): {invalidos}")

    nivel_de = {p.imovel_id: Nivel(p.nivel) for p in posicoes}
    if len(nivel_de) != len(posicoes):
        raise ValueError("imovel_id repetido na carga de referência")

    # Higiene da entrada, cada descarte contado (nada some em silêncio): fora do
    # período, imóvel fora da carga, ou lead repetido pelo join.
    #
    # CONTRATO DO COLAPSO de duplicatas (o join por atendimento pode trazer o mesmo
    # lead_id em várias linhas, divergentes entre si). Nunca "o primeiro que chegou",
    # que faria a saída depender da ordem do banco (invariante 5). São DUAS regras,
    # ambas conservadoras no sentido da §4.2:
    #   1. sinais de tratamento: OR — se QUALQUER linha registrou atendimento ou
    #      contato, o lead foi tratado (não se acusa abandono que não houve);
    #   2. colunas opcionais: PRIMEIRO VALOR CONHECIDO — não se fabrica ausência
    #      sobre dado que a origem tem (ver `_conhecido`).
    # A ordem total (`_chave`) só desempata o determinismo; não decide conteúdo.
    # Ordem das portas: primeiro "é da carga?" (senão nem é assunto desta rodada),
    # depois "é do período?" — assim cada contador mede o que o nome diz.
    por_lead: dict[int, list[LeadDoPeriodo]] = {}
    fora_da_carga_ids: set[int] = set()
    fora_do_periodo_ids: set[int] = set()
    for lead in leads:
        if lead.imovel_id not in nivel_de:
            fora_da_carga_ids.add(lead.lead_id)
            continue
        if not (inicio_periodo <= lead.entrada <= fim_periodo):
            fora_do_periodo_ids.add(lead.lead_id)
            continue
        por_lead.setdefault(lead.lead_id, []).append(lead)

    def _chave(x: LeadDoPeriodo) -> tuple[int, date, date, str, str, str]:
        return (
            x.imovel_id,
            x.entrada,
            x.distribuicao or date.min,
            x.corretor_gestor or "",
            x.gestor_distrito or "",
            x.distrito or "",
        )

    def _conhecido(
        linhas: Sequence[LeadDoPeriodo], extrair: Callable[[LeadDoPeriodo], _T | None]
    ) -> _T | None:
        """Preferir o valor CONHECIDO entre as linhas do mesmo lead; None só quando
        nenhuma o tinha. É a mesma filosofia do OR dos sinais: um LEFT JOIN parcial
        (uma linha com corretor, outra sem) não pode fabricar uma ausência sobre um
        dado que a origem tem — isso inflaria `sem_tratamento_sem_responsavel` e esvaziaria
        colunas exigidas pela §4.2."""
        for x in linhas:
            valor = extrair(x)
            if valor is not None:
                return valor
        return None

    do_periodo: list[LeadDoPeriodo] = []
    for linhas_do_lead in por_lead.values():
        ordenadas = sorted(linhas_do_lead, key=_chave)
        base = ordenadas[0]
        do_periodo.append(
            base
            if len(ordenadas) == 1
            else LeadDoPeriodo(
                lead_id=base.lead_id,
                imovel_id=base.imovel_id,
                entrada=base.entrada,
                atendimento_registrado=any(x.atendimento_registrado for x in ordenadas),
                contato_registrado=any(x.contato_registrado for x in ordenadas),
                distribuicao=_conhecido(ordenadas, lambda x: x.distribuicao),
                corretor_gestor=_conhecido(ordenadas, lambda x: x.corretor_gestor),
                gestor_distrito=_conhecido(ordenadas, lambda x: x.gestor_distrito),
                distrito=_conhecido(ordenadas, lambda x: x.distrito),
            )
        )
    dentro = set(por_lead)
    fora_do_periodo = len(fora_do_periodo_ids - dentro)
    fora_da_carga = len(fora_da_carga_ids - dentro - fora_do_periodo_ids)

    gerados: dict[int, int] = dict.fromkeys(nivel_de, 0)
    sem_trat: dict[int, int] = dict.fromkeys(nivel_de, 0)
    linhas_leads: list[LeadSemTratamento] = []
    for lead in do_periodo:
        gerados[lead.imovel_id] += 1
        if sem_tratamento(lead):
            sem_trat[lead.imovel_id] += 1
            linhas_leads.append(
                LeadSemTratamento(
                    lead_id=lead.lead_id,
                    imovel_id=lead.imovel_id,
                    nivel=nivel_de[lead.imovel_id],
                    entrada=lead.entrada,
                    tempo_desde_distribuicao=(
                        (fim_periodo - lead.distribuicao).days
                        if lead.distribuicao is not None
                        else None  # ausência declarada, nunca a entrada no lugar
                    ),
                    corretor_gestor=lead.corretor_gestor,
                    gestor_distrito=lead.gestor_distrito,
                    distrito=lead.distrito,
                )
            )

    hist = historico or {}
    desempenho = tuple(
        DesempenhoImovel(
            imovel_id=p.imovel_id,
            nivel=nivel_de[p.imovel_id],
            leads_gerados=gerados[p.imovel_id],
            leads_sem_tratamento=sem_trat[p.imovel_id],
            # um único lookup por imóvel (são ~7 mil por rodada)
            semanas_consecutivas=(h := hist.get(p.imovel_id, (None, None)))[0],
            leads_acumulados_janela=h[1],
        )
        # super destaque primeiro, depois por imóvel — ordem estável (Spec §4.3
        # lista TODAS as posições, inclusive as que geraram zero lead)
        for p in sorted(
            posicoes, key=lambda p: (Nivel(p.nivel) is not Nivel.SUPER_DESTAQUE, p.imovel_id)
        )
    )

    resumo = ResumoAcompanhamento(
        rodada_decisao_id=rodada_decisao_id,
        inicio_periodo=inicio_periodo,
        fim_periodo=fim_periodo,
        posicoes_super=sum(1 for n in nivel_de.values() if n is Nivel.SUPER_DESTAQUE),
        posicoes_destaque=sum(1 for n in nivel_de.values() if n is Nivel.DESTAQUE),
        leads_gerados=len(do_periodo),
        leads_sem_tratamento=len(linhas_leads),
        imoveis_sem_lead=sum(1 for n in gerados.values() if n == 0),
        leads_fora_do_periodo=fora_do_periodo,
        leads_fora_da_carga=fora_da_carga,
        sem_tratamento_sem_responsavel=sum(1 for x in linhas_leads if not x.corretor_gestor),
        sem_tratamento_sem_distribuicao=sum(
            1 for x in linhas_leads if x.tempo_desde_distribuicao is None
        ),
    )
    return ResultadoAcompanhamento(
        resumo=resumo,
        desempenho=desempenho,
        leads_sem_tratamento=tuple(sorted(linhas_leads, key=lambda x: (x.entrada, x.lead_id))),
    )
