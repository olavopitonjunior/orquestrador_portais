"""Costura da decisão da piloto: encadeia as seis etapas do domínio.

Rodada de TESTE fora do ciclo (não é o grafo de produção). Encadeia, como
cálculo puro (invariantes 4/5), as funções já revisadas do domínio:

  elegibilidade → fatores (semelhança + produtividade; desempenho degradado)
  → penalidades → ranking (nota por nível) → alocação (cotas) → relaxamento.

Leituras estruturais desta rodada (D-016), declaradas — não inventadas:

1. NORMALIZAÇÃO sobre os ELEGÍVEIS (forma do parâmetro nº 2, provisória). Os
   fatores são reescalados [0,1] por min-max SOBRE OS ELEGÍVEIS, para que o
   ranking das 475/6.495 posições NÃO dependa de imóveis reprovados (que nunca
   serão colocados). O pool de reprovados do relaxamento é normalizado ENTRE SI
   — e como min-max preserva ordem, isso não altera a saída do relaxamento
   (que ordena dentro do grau, sem comparar com corte).
2. desempenho_proprio = 0 para todos: a piloto não raspa o portal, então o
   fator (peso 25 super / 10 destaque) roda DEGRADADO. Zerar uniformemente é
   order-preserving — a rodada é degradada nesse fator, declarado na saída.
3. produtividade_gestor = sinal binário `gestor_captou_ou_vendeu_30d` (1/0),
   min-max — na v0 vira efetivamente um flag. Alternativa futura: o sinal rico
   de productivityrating, que o candidato não traz hoje.

Os provisórios nº 2 (forma da normalização) e nº 3 (intensidades das
penalidades + decaimento) são INJETADOS run-local — nunca em src/config, nunca
adotados (D-014). Vão rotulados na saída para a planilha.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from dominio.alocacao import COTA_DESTAQUE, Alocacao, CandidatoAlocacao, alocar
from dominio.elegibilidade import ImovelCandidato, Regra, regras_reprovadas
from dominio.penalidades import ImovelPenalizavel, IntensidadesPenalidade, desconto_total
from dominio.perfil import PerfilConversao
from dominio.ranking import (
    PESOS_DESTAQUE,
    PESOS_SUPER_DESTAQUE,
    FatoresNormalizados,
    nota_final,
)
from dominio.relaxamento import CandidatoRelaxamento, ResultadoRelaxamento, relaxar
from piloto.semelhanca import DimensoesImovel, ParametrosSemelhanca, semelhanca_por_imovel


@dataclass(frozen=True)
class ParametrosDecisao:
    """Os provisórios da rodada, injetados run-local (nunca em src/config)."""

    semelhanca: ParametrosSemelhanca
    intensidades: IntensidadesPenalidade
    decaimento_janela: Callable[[int], float]


@dataclass(frozen=True)
class ResultadoDecisao:
    """A saída da costura: alocação, relaxamento e as limitações declaradas."""

    alocacao: Alocacao
    relaxamento: ResultadoRelaxamento
    n_elegiveis: int
    n_reprovados: int
    # Limitações da rodada, para a aba de limitações da planilha (B3c).
    degradacoes: tuple[str, ...]


def _normalizar_minmax(bruto: dict[int, float]) -> dict[int, float]:
    """Min-max sobre a população dada (forma do parâmetro nº 2, provisória).

    Mesma forma usada em piloto.semelhanca; min == max → todos 0.0 (sem sinal
    discriminante). Reescalar preserva ordem, então a escolha da população só
    importa quando fatores de escalas diferentes se combinam por pesos — daí a
    normalização do ranking primário ser sobre os elegíveis.
    """
    if not bruto:
        return {}
    menor, maior = min(bruto.values()), max(bruto.values())
    faixa = maior - menor
    if faixa == 0.0:
        return dict.fromkeys(bruto, 0.0)
    return {iid: (v - menor) / faixa for iid, v in bruto.items()}


def _fatores(
    imoveis: Sequence[ImovelCandidato],
    dims_por_imovel: Mapping[int, DimensoesImovel],
    perfis: tuple[PerfilConversao, ...],
    params_sem: ParametrosSemelhanca,
) -> dict[int, FatoresNormalizados]:
    """Monta os três fatores normalizados SOBRE ESTA população.

    semelhança e produtividade são normalizadas entre os imóveis passados;
    desempenho_proprio é 0 (degradado). Passe os elegíveis para o ranking
    primário e os reprovados (entre si) para o relaxamento.
    """
    dims_pop = {im.imovel_id: dims_por_imovel.get(im.imovel_id, {}) for im in imoveis}
    semelhanca = semelhanca_por_imovel(dims_pop, perfis, params_sem)
    produtividade = _normalizar_minmax(
        {im.imovel_id: (1.0 if im.gestor_captou_ou_vendeu_30d else 0.0) for im in imoveis}
    )
    return {
        im.imovel_id: FatoresNormalizados(
            imovel_id=im.imovel_id,
            semelhanca_perfil=semelhanca.get(im.imovel_id, 0.0),
            desempenho_proprio=0.0,  # D-016: degradado (sem raspagem de portal)
            produtividade_gestor=produtividade[im.imovel_id],
        )
        for im in imoveis
    }


def _desconto(
    imovel_id: int, penalizaveis: Mapping[int, ImovelPenalizavel], p: ParametrosDecisao
) -> float:
    pen = penalizaveis.get(imovel_id)
    if pen is None:
        raise ValueError(f"imóvel {imovel_id} sem ImovelPenalizavel: coleta desalinhada")
    return desconto_total(pen, p.intensidades, p.decaimento_janela)


DEGRADACOES = (
    "desempenho próprio observado ausente (a piloto não raspa o portal): "
    "rodada DEGRADADA nesse fator, que roda zerado (ordena pelos outros dois).",
    "produtividade do gestor é binária na v0 (captou/vendeu em 30d: sim/não).",
    "normalização (parâmetro nº 2) e intensidades das penalidades (nº 3) são "
    "PROVISÓRIAS desta rodada — não adotadas.",
)


def decidir(
    candidatos: Sequence[ImovelCandidato],
    penalizaveis: Mapping[int, ImovelPenalizavel],
    dims_por_imovel: Mapping[int, DimensoesImovel],
    perfis: tuple[PerfilConversao, ...],
    parametros: ParametrosDecisao,
    data_referencia: date,
) -> ResultadoDecisao:
    """Encadeia as seis etapas e devolve a alocação + o relaxamento (Spec §6).

    Determinístico (invariante 5): mesma entrada e mesmos parâmetros ⇒ mesma
    saída. As cotas (invariante 6) e o relaxamento só-destaque (invariante 7)
    são garantidos pelos módulos do domínio, não reimplementados aqui.
    """
    elegiveis: list[ImovelCandidato] = []
    reprovados: list[tuple[ImovelCandidato, frozenset[Regra]]] = []
    for c in candidatos:
        rr = regras_reprovadas(c, data_referencia)
        if rr:
            reprovados.append((c, rr))
        else:
            elegiveis.append(c)

    # Ranking primário: fatores normalizados SOBRE OS ELEGÍVEIS.
    fatores_el = _fatores(elegiveis, dims_por_imovel, perfis, parametros.semelhanca)
    aloc_entrada = []
    for c in elegiveis:
        desc = _desconto(c.imovel_id, penalizaveis, parametros)  # uma vez por imóvel
        fat = fatores_el[c.imovel_id]
        aloc_entrada.append(
            CandidatoAlocacao(
                imovel_id=c.imovel_id,
                preco=c.preco,
                nota_super_destaque=nota_final(fat, PESOS_SUPER_DESTAQUE, desc),
                nota_destaque=nota_final(fat, PESOS_DESTAQUE, desc),
            )
        )
    alocacao = alocar(aloc_entrada)

    # Relaxamento (só destaque): reprovados normalizados ENTRE SI.
    deficit = COTA_DESTAQUE - len(alocacao.destaque)
    if deficit > 0 and reprovados:
        so_reprovados = [c for c, _ in reprovados]
        fatores_rep = _fatores(so_reprovados, dims_por_imovel, perfis, parametros.semelhanca)
        pool = [
            CandidatoRelaxamento(
                imovel_id=c.imovel_id,
                nota_destaque=nota_final(
                    fatores_rep[c.imovel_id],
                    PESOS_DESTAQUE,
                    _desconto(c.imovel_id, penalizaveis, parametros),
                ),
                regras_reprovadas=rr,
            )
            for c, rr in reprovados
        ]
        relaxamento = relaxar(deficit, pool)
    else:
        # deficit ≥ 0 sempre (o slice da alocação garante len(destaque) ≤ cota).
        relaxamento = relaxar(deficit, [])

    return ResultadoDecisao(
        alocacao=alocacao,
        relaxamento=relaxamento,
        n_elegiveis=len(elegiveis),
        n_reprovados=len(reprovados),
        degradacoes=DEGRADACOES,
    )
