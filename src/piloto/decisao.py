"""Costura da decisão da piloto: encadeia as seis etapas do domínio.

Rodada de TESTE fora do ciclo (não é o grafo de produção). Encadeia, como
cálculo puro (invariantes 4/5), as funções já revisadas do domínio:

  elegibilidade → fatores (semelhança ponderada por dimensão + leads + produtividade;
  desempenho degradado) → penalidades → ranking (nota por nível, pesos INJETADOS)
  → alocação (cotas) → relaxamento.

Leituras estruturais desta rodada (D-016/D-017), declaradas — não inventadas:

1. NORMALIZAÇÃO sobre os ELEGÍVEIS (forma do parâmetro nº 2, provisória). Os
   fatores são reescalados [0,1] por min-max SOBRE OS ELEGÍVEIS, para que o
   ranking das 475/6.495 posições NÃO dependa de imóveis reprovados (que nunca
   serão colocados). O pool de reprovados do relaxamento é normalizado ENTRE SI
   — e como min-max preserva ordem, isso não altera a saída do relaxamento
   (que ordena dentro do grau, sem comparar com corte). Vale para os quatro
   fatores, incluindo o F2 leads.
2. semelhança PONDERADA POR DIMENSÃO (F1, D-017): a contribuição de cada perfil
   é escalada pela importância das suas dimensões (preço > … > vagas), com o
   `decaimento` injetado (nº 13). É o que de-satura o sinal. A combinação para
   perfis de duas dimensões (máximo dos pesos) é leitura declarada em
   `piloto.semelhanca`.
3. F2 leads = min-max de `Leads180D` (fator POSITIVO vivo, do banco, via
   ImovelPenalizavel — D-017). Lead deixa de ser só penalidade e vira sinal.
4. desempenho_proprio = 0 para todos: a piloto não raspa o portal, então o
   fator roda DEGRADADO (D-017: é reforço, não bloqueia). Zerar uniformemente é
   order-preserving — declarado na saída.
5. produtividade_gestor = intensidade CONTÍNUA em 30d (F4, D-017):
   `produtividade_gestor_30d` (taxa semanal de captação + flag de venda recente),
   normalizada min-max. Substitui o binário morto (redundante com a
   elegibilidade). Limitação declarada: a base não expõe CONTAGEM de vendas em
   30d (Sells é de 365d), então a venda entra só como flag; a captação é a
   dimensão genuinamente contínua. O binário `gestor_captou_ou_vendeu_30d` segue
   como REGRA de elegibilidade, intocado.

Os pesos dos quatro fatores (nº 12) e o decaimento por dimensão (nº 13) são
INJETADOS run-local via `ParametrosDecisao`/`ParametrosSemelhanca` — fecha o
mandato de injeção da D-017 (invariante 5). Junto dos provisórios nº 2 (forma da
normalização) e nº 3 (intensidades), nunca em src/config, nunca adotados
(D-014). Todos rotulados na saída para a planilha.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from dominio.alocacao import COTA_DESTAQUE, Alocacao, CandidatoAlocacao, alocar
from dominio.elegibilidade import ImovelCandidato, Regra, regras_reprovadas
from dominio.penalidades import (
    ImovelPenalizavel,
    IntensidadesPenalidade,
    Penalidade,
    descontos_por_penalidade,
)
from dominio.perfil import PerfilConversao
from dominio.ranking import (
    FatoresNormalizados,
    PesosNivel,
    nota_final,
)
from dominio.relaxamento import CandidatoRelaxamento, ResultadoRelaxamento, relaxar
from piloto.semelhanca import (
    DimensoesImovel,
    ParametrosSemelhanca,
    perfil_que_puxou,
    semelhanca_por_imovel,
)


@dataclass(frozen=True)
class ParametrosDecisao:
    """Os provisórios da rodada, injetados run-local (nunca em src/config).

    `pesos_super`/`pesos_destaque` são os pesos dos quatro fatores por nível
    (D-017, parâmetro nulo nº 12): INJETADOS aqui, não lidos de constante em
    `src/dominio` — é o que fecha o mandato de injeção da D-017 (invariante 5:
    pesos injetados, não constantes escondidas). Provisórios da rodada,
    rotulados PROVISÓRIO na saída; nunca adotados.
    """

    semelhanca: ParametrosSemelhanca
    intensidades: IntensidadesPenalidade
    decaimento_janela: Callable[[int], float]
    pesos_super: PesosNivel
    pesos_destaque: PesosNivel


@dataclass(frozen=True)
class DetalheImovel:
    """Justificativa por imóvel (Spec §2.1/§3.2/§6.4): os números AUTORITATIVOS
    que produziram a nota — carregados da costura, não recomputados no B3c.

    `nota_super_destaque` é None para reprovados (só disputam destaque via
    relaxamento). `perfil_que_puxou` é o perfil de conversão de maior
    contribuição que o imóvel casou (Spec §2.1: identificador e evidência do
    perfil casado) — None se não casou nenhum; a própria evidência (num_vendas,
    frágil) viaja no PerfilConversao.
    """

    imovel_id: int
    fatores: FatoresNormalizados
    descontos_por_penalidade: Mapping[Penalidade, float]
    desconto_total: float
    nota_super_destaque: float | None
    nota_destaque: float
    perfil_que_puxou: PerfilConversao | None


@dataclass(frozen=True)
class ResultadoDecisao:
    """A saída da costura: alocação, relaxamento, o detalhamento e as limitações."""

    alocacao: Alocacao
    relaxamento: ResultadoRelaxamento
    # Justificativa por imóvel (elegíveis + reprovados que entraram no
    # relaxamento), carregada da costura para o B3c serializar sem recomputar.
    detalhes: Mapping[int, DetalheImovel]
    # As regras reprovadas de CADA imóvel reprovado (por imovel_id), carregadas
    # do split de elegibilidade — a aba "excluídos por regra" do B3c lê daqui,
    # não recomputa elegibilidade. Inclui recuperados e não-recuperados; o B3c
    # separa pelos recuperados do relaxamento.
    reprovados_regras: Mapping[int, frozenset[Regra]]
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


def _leads_do(imovel_id: int, penalizaveis: Mapping[int, ImovelPenalizavel]) -> int:
    """`Leads180D` do imóvel (via ImovelPenalizavel, onde o dado já é coletado).

    Falha alta se o imóvel não tem penalizável — a mesma garantia que `_descontos`
    exige, para não montar o fator de leads sobre coleta desalinhada.
    """
    pen = penalizaveis.get(imovel_id)
    if pen is None:
        raise ValueError(f"imóvel {imovel_id} sem ImovelPenalizavel: coleta desalinhada")
    return pen.leads_180d


def _fatores(
    imoveis: Sequence[ImovelCandidato],
    dims_por_imovel: Mapping[int, DimensoesImovel],
    perfis: tuple[PerfilConversao, ...],
    params_sem: ParametrosSemelhanca,
    penalizaveis: Mapping[int, ImovelPenalizavel],
    desempenho_por_imovel: Mapping[int, float],
) -> dict[int, FatoresNormalizados]:
    """Monta os QUATRO fatores normalizados SOBRE ESTA população (D-017).

    Os quatro são normalizados (min-max) ENTRE os imóveis passados — sobre os
    elegíveis no ranking primário, entre os reprovados no relaxamento (D-016).
    F1 semelhança; F2 leads = min-max de `Leads180D` (fator POSITIVO vivo, do
    banco); F3 desempenho_proprio = min-max do sinal de portal `desempenho_por_
    imovel` (composto pelo nó do Coletor Externo a partir da raspagem — nota/
    visualizações/cliques; imóvel sem raspagem entra com 0, o pior); F4
    produtividade = min-max de `produtividade_gestor_30d` (intensidade CONTÍNUA
    em 30d — captação como taxa + venda como flag, D-017), NÃO mais o binário
    (que é a regra de elegibilidade, à parte).
    Passe os elegíveis para o ranking primário e os reprovados para o relaxamento.
    """
    dims_pop = {im.imovel_id: dims_por_imovel.get(im.imovel_id, {}) for im in imoveis}
    semelhanca = semelhanca_por_imovel(dims_pop, perfis, params_sem)
    produtividade = _normalizar_minmax(
        {im.imovel_id: float(im.produtividade_gestor_30d) for im in imoveis}
    )
    leads = _normalizar_minmax(
        {im.imovel_id: float(_leads_do(im.imovel_id, penalizaveis)) for im in imoveis}
    )
    desempenho = _normalizar_minmax(
        {im.imovel_id: float(desempenho_por_imovel.get(im.imovel_id, 0.0)) for im in imoveis}
    )
    return {
        im.imovel_id: FatoresNormalizados(
            imovel_id=im.imovel_id,
            semelhanca_perfil=semelhanca.get(im.imovel_id, 0.0),
            desempenho_proprio=desempenho[im.imovel_id],
            produtividade_gestor=produtividade[im.imovel_id],
            leads=leads[im.imovel_id],
        )
        for im in imoveis
    }


def _descontos(
    imovel_id: int, penalizaveis: Mapping[int, ImovelPenalizavel], p: ParametrosDecisao
) -> dict[Penalidade, float]:
    """O desconto por penalidade do imóvel (autoritativo; o total é a soma)."""
    pen = penalizaveis.get(imovel_id)
    if pen is None:
        raise ValueError(f"imóvel {imovel_id} sem ImovelPenalizavel: coleta desalinhada")
    return descontos_por_penalidade(pen, p.intensidades, p.decaimento_janela)


# Declarada SÓ quando o F3 de fato não entrou. Era incondicional, e desde que o
# ponto de entrada da sexta passou a poder alimentar F3 com raspagem viva, uma
# rodada COMPLETA saía declarando "desempenho de portal ausente" duas linhas abaixo
# do próprio estado — limitação falsa na planilha que sustenta a aprovação (§7.2).
DEGRADACAO_SEM_PORTAL = (
    "desempenho próprio observado (portal) ausente (rodada sem raspagem): "
    "rodada DEGRADADA nesse fator, que roda zerado (D-017: é reforço, não bloqueia)."
)

DEGRADACOES = (
    "F2 leads = min-max de Leads180D (fator POSITIVO vivo, do banco — D-017).",
    "F4 produtividade do gestor agora CONTÍNUA (D-017): taxa semanal de captação "
    "+ flag de venda recente em 30d, normalizada. Limitação: a base não expõe "
    "contagem de vendas em 30d (Sells é de 365d), então a venda entra só como flag.",
    "pesos dos quatro fatores por nível (parâmetro nº 12) e decaimento por dimensão "
    "do F1 (parâmetro nº 13): PROVISÓRIOS desta rodada, injetados run-local, NÃO adotados (D-017).",
    "forma de normalização (parâmetro nº 2) = min-max: PROVISÓRIA, não adotada "
    "pelo dono — a forma não foi decidida (D-016).",
    "intensidades das penalidades e decaimento por janela (parâmetro nº 3): PROVISÓRIOS "
    "desta rodada, não adotados.",
)


def decidir(
    candidatos: Sequence[ImovelCandidato],
    penalizaveis: Mapping[int, ImovelPenalizavel],
    dims_por_imovel: Mapping[int, DimensoesImovel],
    perfis: tuple[PerfilConversao, ...],
    parametros: ParametrosDecisao,
    data_referencia: date,
    desempenho_por_imovel: Mapping[int, float] | None = None,
) -> ResultadoDecisao:
    """Encadeia as seis etapas e devolve a alocação + o relaxamento (Spec §6).

    `desempenho_por_imovel` é o sinal de portal por imóvel (F3), composto pelo nó
    do Coletor Externo a partir da raspagem; None/omisso = sem raspagem, F3 = 0
    para todos (rodada degradada nesse fator, como a piloto).

    Determinístico (invariante 5): mesma entrada e mesmos parâmetros ⇒ mesma
    saída. As cotas (invariante 6) e o relaxamento só-destaque (invariante 7)
    são garantidos pelos módulos do domínio, não reimplementados aqui.
    """
    # imovel_id único no lote: alocar/relaxar detectam duplicata dentro do seu
    # lote, mas um id que atravessasse elegível↔reprovado escaparia das duas
    # guardas e sobrescreveria silenciosamente em `detalhes`. A costura fecha isso.
    contagem = Counter(c.imovel_id for c in candidatos)
    dups = sorted(i for i, n in contagem.items() if n > 1)
    if dups:
        raise ValueError(f"imovel_id duplicado no lote de candidatos: {dups}")

    desempenho = desempenho_por_imovel or {}  # sem raspagem → F3 = 0 para todos

    elegiveis: list[ImovelCandidato] = []
    reprovados: list[tuple[ImovelCandidato, frozenset[Regra]]] = []
    for c in candidatos:
        rr = regras_reprovadas(c, data_referencia)
        if rr:
            reprovados.append((c, rr))
        else:
            elegiveis.append(c)

    # Ranking primário: fatores normalizados SOBRE OS ELEGÍVEIS.
    fatores_el = _fatores(
        elegiveis, dims_por_imovel, perfis, parametros.semelhanca, penalizaveis, desempenho
    )
    detalhes: dict[int, DetalheImovel] = {}
    aloc_entrada: list[CandidatoAlocacao] = []
    for c in elegiveis:
        fat = fatores_el[c.imovel_id]
        descontos = _descontos(c.imovel_id, penalizaveis, parametros)  # uma vez por imóvel
        desc_total = sum(descontos.values(), 0.0)
        nota_super = nota_final(fat, parametros.pesos_super, desc_total)
        nota_dest = nota_final(fat, parametros.pesos_destaque, desc_total)
        aloc_entrada.append(
            CandidatoAlocacao(
                imovel_id=c.imovel_id,
                preco=c.preco,
                nota_super_destaque=nota_super,
                nota_destaque=nota_dest,
            )
        )
        detalhes[c.imovel_id] = DetalheImovel(
            imovel_id=c.imovel_id,
            fatores=fat,
            descontos_por_penalidade=descontos,
            desconto_total=desc_total,
            nota_super_destaque=nota_super,
            nota_destaque=nota_dest,
            perfil_que_puxou=perfil_que_puxou(
                dims_por_imovel.get(c.imovel_id, {}), perfis, parametros.semelhanca
            ),
        )
    alocacao = alocar(aloc_entrada)

    # Relaxamento (só destaque): reprovados normalizados ENTRE SI.
    deficit = COTA_DESTAQUE - len(alocacao.destaque)
    if deficit > 0 and reprovados:
        so_reprovados = [c for c, _ in reprovados]
        fatores_rep = _fatores(
            so_reprovados, dims_por_imovel, perfis, parametros.semelhanca, penalizaveis, desempenho
        )
        pool: list[CandidatoRelaxamento] = []
        for c, rr in reprovados:
            fat = fatores_rep[c.imovel_id]
            descontos = _descontos(c.imovel_id, penalizaveis, parametros)
            desc_total = sum(descontos.values(), 0.0)
            nota_dest = nota_final(fat, parametros.pesos_destaque, desc_total)
            pool.append(
                CandidatoRelaxamento(
                    imovel_id=c.imovel_id, nota_destaque=nota_dest, regras_reprovadas=rr
                )
            )
            detalhes[c.imovel_id] = DetalheImovel(
                imovel_id=c.imovel_id,
                fatores=fat,
                descontos_por_penalidade=descontos,
                desconto_total=desc_total,
                nota_super_destaque=None,  # reprovado só disputa destaque (relaxamento)
                nota_destaque=nota_dest,
                perfil_que_puxou=perfil_que_puxou(
                    dims_por_imovel.get(c.imovel_id, {}), perfis, parametros.semelhanca
                ),
            )
        relaxamento = relaxar(deficit, pool)
    else:
        # deficit ≥ 0 sempre (o slice da alocação garante len(destaque) ≤ cota).
        relaxamento = relaxar(deficit, [])

    return ResultadoDecisao(
        alocacao=alocacao,
        relaxamento=relaxamento,
        detalhes=detalhes,
        reprovados_regras={c.imovel_id: rr for c, rr in reprovados},
        n_elegiveis=len(elegiveis),
        n_reprovados=len(reprovados),
        # A limitação do portal só é declarada se o portal REALMENTE não entrou.
        degradacoes=DEGRADACOES if desempenho_por_imovel else (DEGRADACAO_SEM_PORTAL, *DEGRADACOES),
    )
