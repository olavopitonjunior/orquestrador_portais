"""Penalidades: três descontos da nota final, sempre visíveis na planilha.

Fonte: Spec §6.4. As três penalidades — janela anterior sem resultado, sem
avaliação por categoria, sem lead em 180 dias — são descontadas da nota do
ranking (Spec §6.3). Imóvel sem histórico de destaque não é penalizado por
ausência de histórico.

A intensidade das três e o decaimento da penalidade por janela são o
parâmetro pendente nº 3 (D-004): permanecem nulos e entram aqui como
argumentos OBRIGATÓRIOS, sem valor default — chamada sem eles falha.

Pendência declarada, não resolvida (condição do orquestrador para este PR):
nenhum documento quantifica "o resultado esperado para o nível" (Spec §6.4);
o PRD diz apenas que é proporcional ao nível. Por isso o julgamento
"atingiu resultado" chega PRÉ-CALCULADO em `JanelaAnterior.atingiu_resultado`.
Quem o calcula é `julgar_janelas`, no fim deste módulo, e ele RECEBE o limiar
por nível como argumento — o parâmetro nº 14 (D-022), nulo. Nenhum limiar é
inventado neste módulo.

Invariantes 4 e 5: cálculo puro — sem I/O, sem relógio próprio, sem
aleatoriedade, sem chamada a modelo. A função de decaimento é injetada e
precisa ser pura; o módulo valida apenas o contrato do seu resultado.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import Enum


class Penalidade(Enum):
    """As três penalidades da Spec §6.4."""

    JANELA_SEM_RESULTADO = "janela_sem_resultado"
    SEM_AVALIACAO_POR_CATEGORIA = "sem_avaliacao_por_categoria"
    SEM_LEAD_180D = "sem_lead_180d"


@dataclass(frozen=True)
class JanelaAnterior:
    """Janela de destaque já encerrada do imóvel (registro.janela_destaque).

    `atingiu_resultado` chega pronto — ver a pendência declarada no topo do
    módulo; como o julgamento já é por nível, o nível da janela não viaja
    até aqui (o Registro o guarda). `ciclos_desde_encerramento` conta rodadas
    de decisão (sextas) completas desde o fim da janela; 0 = encerrada no
    ciclo corrente.
    """

    atingiu_resultado: bool
    ciclos_desde_encerramento: int

    def __post_init__(self) -> None:
        if self.ciclos_desde_encerramento < 0:
            raise ValueError(
                f"ciclos_desde_encerramento negativo: {self.ciclos_desde_encerramento}"
            )


@dataclass(frozen=True)
class ImovelPenalizavel:
    """Entrada das penalidades. O Coletor Interno a monta a partir do NEWCORE, com
    `janelas_anteriores` vazio; o histórico vem do Registro e é acoplado pelo nó do
    DECISOR (Spec §5: o único agente que lê o Registro durante a rodada).

    `janelas_anteriores` contém apenas janelas ENCERRADAS (fim não nulo);
    tupla vazia = imóvel sem histórico de destaque, que não recebe a
    penalidade por janela. `alguma_categoria_avaliada` deriva de
    realty_score_category_score: False = nenhuma das sete categorias avaliada
    (a penalidade da Spec §6.4 exige ausência TOTAL — a assimetria do parcial
    está registrada na D-007). `leads_180d` vem de FT_RealtyRelation.Leads180D.
    """

    imovel_id: int
    janelas_anteriores: tuple[JanelaAnterior, ...]
    alguma_categoria_avaliada: bool
    leads_180d: int

    def __post_init__(self) -> None:
        # Aceita qualquer iterável e congela em tupla: mutação da coleção
        # original não vaza para dentro da instância.
        object.__setattr__(self, "janelas_anteriores", tuple(self.janelas_anteriores))
        if self.leads_180d < 0:
            raise ValueError(f"leads_180d negativo: {self.leads_180d}")


@dataclass(frozen=True)
class IntensidadesPenalidade:
    """Parâmetro pendente nº 3 (D-004) — nenhum campo tem default.

    Os valores vivem fora do código (parametros_da_rodada do Registro) e
    permanecem nulos até o dono da decisão os definir. Construir sem os três
    campos falha com TypeError.
    """

    janela_sem_resultado: float
    sem_avaliacao_por_categoria: float
    sem_lead_180d: float

    def __post_init__(self) -> None:
        # Os valores virão de parametros_da_rodada (dado externo): a fronteira
        # de validação é aqui. Intensidade negativa converteria penalidade em
        # bônus; NaN/inf contaminaria a nota e quebraria a ordenação total do
        # ranking (invariante 5).
        for campo in ("janela_sem_resultado", "sem_avaliacao_por_categoria", "sem_lead_180d"):
            valor = getattr(self, campo)
            if not math.isfinite(valor) or valor < 0:
                raise ValueError(f"intensidade inválida para {campo}: {valor}")


def penalidades_aplicaveis(imovel: ImovelPenalizavel) -> frozenset[Penalidade]:
    """Aplica os três predicados binários e devolve as penalidades cabíveis.

    Toda penalidade aplicada é visível na justificativa da planilha (PRD,
    Estágio 3) — devolver o conjunto, e não só o desconto, é o que permite
    ao Redator justificar posição a posição. A ordem de iteração de um
    frozenset de Enum varia entre processos: quem renderizar o conjunto
    (Redator) deve ordenar por `.value` (invariante 5 na saída visível).
    """
    aplicaveis: set[Penalidade] = set()

    ultima = ultima_janela(imovel)
    if ultima is not None and not ultima.atingiu_resultado:
        aplicaveis.add(Penalidade.JANELA_SEM_RESULTADO)
    if not imovel.alguma_categoria_avaliada:
        aplicaveis.add(Penalidade.SEM_AVALIACAO_POR_CATEGORIA)
    if imovel.leads_180d == 0:
        aplicaveis.add(Penalidade.SEM_LEAD_180D)

    return frozenset(aplicaveis)


def ultima_janela(imovel: ImovelPenalizavel) -> JanelaAnterior | None:
    """A janela encerrada MAIS RECENTE — a única que a §6.4 julga (D-023).

    O dono decidiu que a penalidade olha só a última exposição, e não o histórico
    inteiro: é o que o PRD descreve ("o resultado da SUA ÚLTIMA janela"), e evita que
    uma janela ruim antiga persiga o imóvel para sempre — em especial o imóvel
    PROMOVIDO, cuja janela curta de destaque quase nunca bate o limiar e o penalizaria
    indefinidamente no super destaque (a promoção fecha a janela, D-021).

    "Mais recente" é o MENOR `ciclos_desde_encerramento`, não a posição na tupla: a
    ordem da lista é do chamador e não pode governar a regra (invariante 5).

    O empate é DEFENSIVO, não um caso esperado. Pelo produtor (D-021) fecha no máximo
    uma janela por imóvel por carga — o passo que fecha quem saiu e o que fecha quem
    mudou de nível operam sobre conjuntos disjuntos, e o índice único parcial impede
    duas abertas —, então duas janelas encerradas do mesmo imóvel têm sempre `fim`
    distintos; e como todo `fim` é data de carga aprovada, a contagem de ciclos as
    separa por pelo menos 1. Ou seja: hoje o empate é inalcançável. Ele existe porque
    a função precisa ser total, e a regra não pode passar a depender da ordem da lista
    no dia em que alguma dessas premissas mudar. O critério — a que NÃO atingiu
    resultado vence — é o conservador: entre duas exposições indistinguíveis para a
    §6.4, penaliza-se a que falhou.
    """
    return min(
        imovel.janelas_anteriores,
        key=lambda j: (j.ciclos_desde_encerramento, j.atingiu_resultado),
        default=None,
    )


def ciclos_desde_janela_sem_resultado(imovel: ImovelPenalizavel) -> int | None:
    """Ciclos desde a última janela, se ela NÃO atingiu resultado; senão None.

    Dirigida pela mesma janela que `penalidades_aplicaveis` julga — antes as duas
    divergiam (o predicado olhava qualquer janela, o desconto a mais recente sem
    resultado), e coincidiam só porque o desconto se aplica uma vez.
    """
    ultima = ultima_janela(imovel)
    if ultima is None or ultima.atingiu_resultado:
        return None
    return ultima.ciclos_desde_encerramento


def descontos_por_penalidade(
    imovel: ImovelPenalizavel,
    intensidades: IntensidadesPenalidade,
    decaimento_janela: Callable[[int], float],
) -> dict[Penalidade, float]:
    """O desconto de CADA penalidade aplicável, por penalidade (Spec §6.4/§2.1).

    A planilha justificada exige "o valor de cada uma das três penalidades"
    (Spec §2.1) — este é o detalhamento autoritativo, e `desconto_total` é a
    soma dele (nenhuma recomputação divergente possível). Só penalidades
    efetivamente aplicadas entram no dict; ausência = não aplicada.

    `decaimento_janela` é a forma pendente do parâmetro nº 3: recebe os
    ciclos desde a ÚLTIMA janela, quando ela não atingiu resultado (D-023 — não
    mais "a janela sem resultado mais recente": com histórico [falhou há 5,
    atingiu há 1] a leitura antiga daria 5, e a regra vigente não penaliza),
    e devolve o fator
    multiplicativo da intensidade. "Decai ao longo dos ciclos" (Spec §6.4)
    fixa o contrato: fator em [0, 1] — decair nunca amplifica a penalidade
    nem a converte em bônus. Fora da faixa, erro determinístico.
    """
    aplicaveis = penalidades_aplicaveis(imovel)
    descontos: dict[Penalidade, float] = {}

    # ciclos não é None ⇔ JANELA_SEM_RESULTADO ∈ aplicaveis (mesmo predicado
    # sobre a mesma tupla imutável); condicionar por ele dispensa narrowing.
    ciclos = ciclos_desde_janela_sem_resultado(imovel)
    if ciclos is not None:
        fator = decaimento_janela(ciclos)
        if not 0.0 <= fator <= 1.0:
            raise ValueError(f"decaimento fora de [0, 1]: {fator} para {ciclos} ciclos")
        descontos[Penalidade.JANELA_SEM_RESULTADO] = intensidades.janela_sem_resultado * fator
    if Penalidade.SEM_AVALIACAO_POR_CATEGORIA in aplicaveis:
        descontos[Penalidade.SEM_AVALIACAO_POR_CATEGORIA] = intensidades.sem_avaliacao_por_categoria
    if Penalidade.SEM_LEAD_180D in aplicaveis:
        descontos[Penalidade.SEM_LEAD_180D] = intensidades.sem_lead_180d

    return descontos


def desconto_total(
    imovel: ImovelPenalizavel,
    intensidades: IntensidadesPenalidade,
    decaimento_janela: Callable[[int], float],
) -> float:
    """Soma dos descontos a subtrair da nota final (Spec §6.3).

    É a soma de `descontos_por_penalidade` — a fonte autoritativa é o
    detalhamento; o total deriva dele, então breakdown e total nunca divergem.
    """
    # start=0.0 garante float mesmo sem penalidade (sum de dict vazio daria int 0).
    return sum(descontos_por_penalidade(imovel, intensidades, decaimento_janela).values(), 0.0)


# Uma janela encerrada, como o Registro a guarda: nível, leads acumulados e ciclos
# decorridos desde o encerramento. CRUA de propósito — o julgamento "atingiu
# resultado" depende do limiar por nível (parâmetro nº 14, D-022), que é injetado.
type JanelaCrua = tuple[str, int, int]


def julgar_janelas(
    cruas: Sequence[JanelaCrua], resultado_esperado: Mapping[str, int]
) -> tuple[JanelaAnterior, ...]:
    """Aplica o limiar por nível às janelas encerradas do Registro (Spec §6.4).

    É aqui que "não atingiu o resultado esperado PARA O NÍVEL" vira um booleano, e
    o limiar é ARGUMENTO — nunca constante deste módulo. A D-022 o deixou nulo, e o
    chamador que não o tiver simplesmente não chama: sem limiar não há julgamento, e
    não julgar é diferente de julgar como aprovado.

    `resultado_esperado` precisa cobrir todo nível que aparecer nas janelas. Nível
    ausente é erro, não um default: julgar uma janela de super destaque pela régua
    do destaque é exatamente o que a §6.4 proíbe ao dizer "para o nível".
    """
    julgadas = []
    for nivel, leads, ciclos in cruas:
        if nivel not in resultado_esperado:
            raise ValueError(
                f"resultado esperado não declarado para o nível {nivel!r}: a §6.4 julga "
                "POR NÍVEL, e usar a régua de outro nível é o erro que ela proíbe"
            )
        julgadas.append(
            JanelaAnterior(
                atingiu_resultado=leads >= resultado_esperado[nivel],
                ciclos_desde_encerramento=ciclos,
            )
        )
    return tuple(julgadas)


def com_janelas(imovel: ImovelPenalizavel, janelas: Sequence[JanelaAnterior]) -> ImovelPenalizavel:
    """O mesmo imóvel, com o histórico de janelas do Registro acoplado.

    O Coletor Interno lê só o Newcore e devolve `janelas_anteriores=()`; o histórico
    vive no Registro próprio, e a Spec §5 diz que quem o lê durante a rodada é o
    DECISOR. Esta função é a costura entre os dois, e é pura — a leitura acontece
    fora, no nó.
    """
    return replace(imovel, janelas_anteriores=tuple(janelas))
