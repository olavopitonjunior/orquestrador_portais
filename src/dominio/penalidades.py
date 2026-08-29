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
"atingiu resultado" chega PRÉ-CALCULADO em `JanelaAnterior.atingiu_resultado`,
pela camada que o dono da decisão vier a definir. Nenhum limiar é inventado
neste módulo.

Invariantes 4 e 5: cálculo puro — sem I/O, sem relógio próprio, sem
aleatoriedade, sem chamada a modelo. A função de decaimento é injetada e
precisa ser pura; o módulo valida apenas o contrato do seu resultado.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
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
    """Entrada das penalidades, montada pelo Coletor Interno a partir do Registro.

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

    if any(not janela.atingiu_resultado for janela in imovel.janelas_anteriores):
        aplicaveis.add(Penalidade.JANELA_SEM_RESULTADO)
    if not imovel.alguma_categoria_avaliada:
        aplicaveis.add(Penalidade.SEM_AVALIACAO_POR_CATEGORIA)
    if imovel.leads_180d == 0:
        aplicaveis.add(Penalidade.SEM_LEAD_180D)

    return frozenset(aplicaveis)


def ciclos_desde_janela_sem_resultado(imovel: ImovelPenalizavel) -> int | None:
    """Ciclos desde a janela sem resultado MAIS RECENTE, ou None se não houver.

    Leitura estrutural adotada (declarada no PR, calibrável no parâmetro
    nº 3): a penalidade por janela aplica-se uma vez, dirigida pela janela
    sem resultado mais recente; a Spec não define acúmulo entre janelas.
    """
    ciclos = [
        janela.ciclos_desde_encerramento
        for janela in imovel.janelas_anteriores
        if not janela.atingiu_resultado
    ]
    return min(ciclos) if ciclos else None


def desconto_total(
    imovel: ImovelPenalizavel,
    intensidades: IntensidadesPenalidade,
    decaimento_janela: Callable[[int], float],
) -> float:
    """Soma dos descontos a subtrair da nota final (Spec §6.3).

    `decaimento_janela` é a forma pendente do parâmetro nº 3: recebe os
    ciclos desde a janela sem resultado mais recente e devolve o fator
    multiplicativo da intensidade. "Decai ao longo dos ciclos" (Spec §6.4)
    fixa o contrato: fator em [0, 1] — decair nunca amplifica a penalidade
    nem a converte em bônus. Fora da faixa, erro determinístico.
    """
    aplicaveis = penalidades_aplicaveis(imovel)
    total = 0.0

    # ciclos não é None ⇔ JANELA_SEM_RESULTADO ∈ aplicaveis (mesmo predicado
    # sobre a mesma tupla imutável); condicionar por ele dispensa narrowing.
    ciclos = ciclos_desde_janela_sem_resultado(imovel)
    if ciclos is not None:
        fator = decaimento_janela(ciclos)
        if not 0.0 <= fator <= 1.0:
            raise ValueError(f"decaimento fora de [0, 1]: {fator} para {ciclos} ciclos")
        total += intensidades.janela_sem_resultado * fator
    if Penalidade.SEM_AVALIACAO_POR_CATEGORIA in aplicaveis:
        total += intensidades.sem_avaliacao_por_categoria
    if Penalidade.SEM_LEAD_180D in aplicaveis:
        total += intensidades.sem_lead_180d

    return total
