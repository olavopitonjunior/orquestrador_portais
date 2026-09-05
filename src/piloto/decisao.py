"""Costura da decisão: encadeia as etapas do domínio sob "o banco manda, o portal
classifica" (D-027 a D-030, 04/09/2026).

  filtro de perfil (D-027) → elegibilidade (nove regras) → sinais do portal e do
  banco, normalizados SOBRE OS ELEGÍVEIS → descontos (pontos de 100) → nota (o
  portal; sem portal, o desempate de banco declarado) → alocação (cotas, piso,
  desempate por leads) → relaxamento (perfil é o primeiro degrau; trava do login).

Leituras estruturais, declaradas — não inventadas:

1. NORMALIZAÇÃO min-max sobre os ELEGÍVEIS (forma do parâmetro nº 2, provisória):
   o ranking das 475/6.495 posições não depende de imóveis reprovados. O pool de
   reprovados do relaxamento é normalizado ENTRE SI (D-016); a apuração diz de qual
   população cada nota veio.
2. O PERFIL é regra, não fator (D-027): a costura calcula `casa_perfil_de_conversao`
   para cada candidato — contra os perfis robustos que CONTÊM a dimensão exigida — e
   entrega o veredito à elegibilidade. Nenhum candidato chega a `regras_reprovadas`
   com o veredito em None.
3. A NOTA é do portal (D-028): pesos em pontos de 100 sobre nota do anúncio, cliques
   (somados entre tipos) e visualizações; imóvel SEM anúncio recebe o tratamento
   declarado (`sem_anuncio`). Quando o portal NÃO entrou (portas do Coletor Externo),
   a nota vem do desempate de banco declarado (`ordem_sem_portal`) e a rodada
   declara isso — nunca "todos zerados" em silêncio.
4. O DESEMPATE da alocação é o banco (leads em 180 dias, normalizado), depois o
   cadastro mais novo (D-009).
5. A TRAVA do login (D-029): reprovado em gestor_produtivo com gestor sem login não
   é recuperado pelo relaxamento; o resultado conta quantos.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from statistics import median

from dados.coletor_externo import DesempenhoAnuncio
from dominio.alocacao import COTA_DESTAQUE, Alocacao, CandidatoAlocacao, alocar
from dominio.elegibilidade import ImovelCandidato, Regra, regras_reprovadas
from dominio.penalidades import (
    ImovelPenalizavel,
    IntensidadesPenalidade,
    Penalidade,
    descontos_por_penalidade,
)
from dominio.perfil import Dimensao, PerfilConversao
from dominio.ranking import FatoresNormalizados, PesosPortal, nota_final, nota_portal
from dominio.relaxamento import CandidatoRelaxamento, ResultadoRelaxamento, relaxar
from piloto.semelhanca import DimensoesImovel, casa_algum, perfil_que_puxou, perfis_que_contam

FORMAS_SEM_ANUNCIO: tuple[str, ...] = ("fim_da_fila", "mediana")
FORMAS_DE_ORDEM_SEM_PORTAL: tuple[str, ...] = (
    "leads_180d",
    "produtividade_gestor",
    "cadastro_mais_novo",
)


@dataclass(frozen=True)
class ParametrosDecisao:
    """Os parâmetros que a costura consome, já validados pelo carregador.

    `pesos_portal`: pontos de 100 sobre nota do anúncio, cliques e visualizações.
    `sem_anuncio`: o que o imóvel sem anúncio raspado vale — "fim_da_fila" (o mínimo
    da população) ou "mediana" (a mediana de quem tem anúncio).
    `ordem_sem_portal`: quando as portas do Coletor Externo fecham, o que ordena —
    "leads_180d", "produtividade_gestor" ou "cadastro_mais_novo".
    `minimo_corretores_distrito`: a régua de capacidade do distrito (D-033).
    `exigir_dimensao_no_perfil`: a dimensão que o perfil precisa conter (D-027);
    None = qualquer perfil robusto conta (o que a medição mostrou não filtrar nada).
    """

    pesos_portal: PesosPortal
    sem_anuncio: str  # um de FORMAS_SEM_ANUNCIO (validado abaixo)
    ordem_sem_portal: str  # um de FORMAS_DE_ORDEM_SEM_PORTAL (validado abaixo)
    intensidades: IntensidadesPenalidade
    decaimento_janela: Callable[[int], float]
    minimo_corretores_distrito: int
    exigir_dimensao_no_perfil: Dimensao | None

    def __post_init__(self) -> None:
        if self.sem_anuncio not in FORMAS_SEM_ANUNCIO:
            raise ValueError(f"sem_anuncio desconhecido: {self.sem_anuncio!r}")
        if self.ordem_sem_portal not in FORMAS_DE_ORDEM_SEM_PORTAL:
            raise ValueError(f"ordem_sem_portal desconhecida: {self.ordem_sem_portal!r}")
        if self.minimo_corretores_distrito < 1:
            raise ValueError(
                f"minimo_corretores_distrito inválido: {self.minimo_corretores_distrito}"
            )


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
    # A nota ANTES dos descontos (0–100): a do portal, ou a do desempate de banco quando
    # o portal não entrou. A planilha mostra as duas; o Registro grava esta.
    nota_bruta: float = 0.0


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


def _penalizavel(
    imovel_id: int, penalizaveis: Mapping[int, ImovelPenalizavel]
) -> ImovelPenalizavel:
    pen = penalizaveis.get(imovel_id)
    if pen is None:
        raise ValueError(f"imóvel {imovel_id} sem ImovelPenalizavel: coleta desalinhada")
    return pen


def _sinal_do_portal(
    imoveis: Sequence[ImovelCandidato],
    anuncios: Mapping[int, DesempenhoAnuncio],
    extrair: Callable[[DesempenhoAnuncio], float | None],
    sem_anuncio: str,
) -> dict[int, float]:
    """Um sinal cru do portal por imóvel desta população, com o tratamento declarado
    para quem não tem anúncio (ou tem anúncio sem o dado): "fim_da_fila" recebe o
    MÍNIMO de quem tem (vira 0 no min-max — o pior, declarado, não silencioso);
    "mediana" recebe a mediana de quem tem. Sem ninguém com o dado, todos 0."""
    com_dado: dict[int, float] = {}
    for im in imoveis:
        an = anuncios.get(im.imovel_id)
        v = extrair(an) if an is not None else None
        if v is not None:
            com_dado[im.imovel_id] = float(v)
    if com_dado:
        substituto = (
            min(com_dado.values())
            if sem_anuncio == "fim_da_fila"
            else float(median(com_dado.values()))
        )
    else:
        substituto = 0.0
    return {im.imovel_id: com_dado.get(im.imovel_id, substituto) for im in imoveis}


def _fatores(
    imoveis: Sequence[ImovelCandidato],
    anuncios: Mapping[int, DesempenhoAnuncio],
    penalizaveis: Mapping[int, ImovelPenalizavel],
    sem_anuncio: str,
) -> dict[int, FatoresNormalizados]:
    """Os sinais normalizados (min-max) SOBRE ESTA população: os três do portal e os
    dois do banco. Passe os elegíveis para o ranking e os reprovados para o
    relaxamento (D-016). `casa_perfil` vem pronto no candidato (D-027)."""
    nota = _normalizar_minmax(_sinal_do_portal(imoveis, anuncios, lambda a: a.nota, sem_anuncio))
    # Cliques SOMADOS entre tipos (D-028: "mais cliques" — divergência registrada com o
    # contrato anterior do coletor, que nunca os somava).
    cliques = _normalizar_minmax(
        _sinal_do_portal(imoveis, anuncios, lambda a: float(sum(a.cliques.values())), sem_anuncio)
    )
    visualizacoes = _normalizar_minmax(
        _sinal_do_portal(imoveis, anuncios, lambda a: float(a.visualizacoes), sem_anuncio)
    )
    leads = _normalizar_minmax(
        {im.imovel_id: float(_penalizavel(im.imovel_id, penalizaveis).leads_180d) for im in imoveis}
    )
    produtividade = _normalizar_minmax(
        {im.imovel_id: float(im.produtividade_gestor_30d) for im in imoveis}
    )
    return {
        im.imovel_id: FatoresNormalizados(
            imovel_id=im.imovel_id,
            nota_anuncio=nota[im.imovel_id],
            cliques=cliques[im.imovel_id],
            visualizacoes=visualizacoes[im.imovel_id],
            leads=leads[im.imovel_id],
            produtividade_gestor=produtividade[im.imovel_id],
            casa_perfil=im.casa_perfil_de_conversao,  # tri-estado: None = não avaliado
        )
        for im in imoveis
    }


def _nota_bruta(fat: FatoresNormalizados, p: ParametrosDecisao, portal_entrou: bool) -> float:
    """A nota antes dos descontos: do portal, ou do desempate de banco quando ele não
    entrou (em pontos de 100, para os descontos valerem o mesmo nos dois casos)."""
    if portal_entrou:
        return nota_portal(fat, p.pesos_portal)
    if p.ordem_sem_portal == "leads_180d":
        return 100.0 * fat.leads
    if p.ordem_sem_portal == "produtividade_gestor":
        return 100.0 * fat.produtividade_gestor
    return 0.0  # cadastro_mais_novo: todos empatam e o desempate por imovel_id decide


def _desempate(fat: FatoresNormalizados, p: ParametrosDecisao, portal_entrou: bool) -> float:
    """D-028: o banco desempata por leads — exceto sob `cadastro_mais_novo` sem portal,
    forma que promete SÓ o cadastro mais novo: aí o desempate é o próprio imovel_id."""
    if not portal_entrou and p.ordem_sem_portal == "cadastro_mais_novo":
        return 0.0
    return fat.leads


def _descontos(
    imovel_id: int, penalizaveis: Mapping[int, ImovelPenalizavel], p: ParametrosDecisao
) -> dict[Penalidade, float]:
    """O desconto por penalidade do imóvel (autoritativo; o total é a soma)."""
    pen = penalizaveis.get(imovel_id)
    if pen is None:
        raise ValueError(f"imóvel {imovel_id} sem ImovelPenalizavel: coleta desalinhada")
    return descontos_por_penalidade(pen, p.intensidades, p.decaimento_janela)


def degradacao_sem_portal(ordem: str) -> str:
    return (
        "desempenho de portal ausente (a coleta não entrou): a ordem desta rodada veio do "
        f"desempate de banco declarado — {ordem} — e não do anúncio (D-028). Rodada DEGRADADA."
    )


def degradacao_sem_perfil(exigir: Dimensao | None) -> str:
    exigencia = f" que contenha `{exigir.value}`" if exigir is not None else ""
    return (
        f"perfil de conversão sem evidência robusta: nenhum perfil com N ≥ 3{exigencia}. "
        "O filtro de perfil (D-027) NÃO incidiu — ninguém foi reprovado por perfil — e a "
        "rodada opera sem a regra (Spec §7.3). Rodada DEGRADADA."
    )


def degradacao_sem_dimensoes(quantos: int) -> str:
    return (
        f"{quantos} candidato(s) sem dimensões na coleta de perfil: perfil não avaliado "
        "para eles (não reprovam por dado ausente) — limitação declarada."
    )


DEGRADACOES = (
    "forma de normalização (parâmetro nº 2) = min-max sobre os elegíveis: PROVISÓRIA, "
    "não adotada pelo dono (D-016).",
    "produtividade do gestor em 30 dias: a base não expõe contagem de vendas em 30d "
    "(Sells é de 365d), então a venda entra só como marca — limitação declarada.",
)


@dataclass(frozen=True)
class FiltroDePerfil:
    """O que a costura do perfil devolve: os candidatos com veredito, os perfis que
    contaram e as degradações a declarar."""

    candidatos: list[ImovelCandidato]
    perfis_que_contam: tuple[PerfilConversao, ...]
    sem_dimensoes: int
    degradacoes: tuple[str, ...]


def aplicar_filtro_de_perfil(
    candidatos: Sequence[ImovelCandidato],
    dims_por_imovel: Mapping[int, DimensoesImovel],
    perfis: Sequence[PerfilConversao],
    exigir_dimensao: Dimensao | None,
) -> FiltroDePerfil:
    """A regra do perfil (D-027) como veredito por candidato. FUNÇÃO PURA.

    None = NÃO AVALIADO, e a elegibilidade não reprova None: sem nenhum perfil que
    conte (Spec §7.3: "sem robustez opera sem o fator") ou sem dimensões do candidato,
    a regra não incide — e quem chama declara a degradação. Vive fora de `decidir`
    porque a PRÉVIA (`executar.previa`) aplica exatamente o mesmo filtro, e duas cópias
    da costura divergiriam em silêncio.
    """
    contam = perfis_que_contam(perfis, exigir_dimensao)
    sem_dimensoes = sum(1 for c in candidatos if c.imovel_id not in dims_por_imovel)

    def _veredito(c: ImovelCandidato) -> bool | None:
        dims = dims_por_imovel.get(c.imovel_id)
        if not contam or dims is None:
            return None
        return casa_algum(dims, contam)

    filtrados = [replace(c, casa_perfil_de_conversao=_veredito(c)) for c in candidatos]
    degradacoes: list[str] = []
    if not contam:
        degradacoes.append(degradacao_sem_perfil(exigir_dimensao))
    if sem_dimensoes:
        degradacoes.append(degradacao_sem_dimensoes(sem_dimensoes))
    return FiltroDePerfil(filtrados, contam, sem_dimensoes, tuple(degradacoes))


def decidir(
    candidatos: Sequence[ImovelCandidato],
    penalizaveis: Mapping[int, ImovelPenalizavel],
    dims_por_imovel: Mapping[int, DimensoesImovel],
    perfis: tuple[PerfilConversao, ...],
    parametros: ParametrosDecisao,
    data_referencia: date,
    anuncios: Mapping[int, DesempenhoAnuncio] | None = None,
    portal_entrou: bool = False,
) -> ResultadoDecisao:
    """Encadeia as etapas e devolve a alocação + o relaxamento.

    `anuncios` é o que a raspagem trouxe cru por imóvel; `portal_entrou` diz se as
    portas do Coletor Externo passaram. Sem portal, a nota vem do desempate de banco
    declarado e a rodada declara a degradação.

    Determinístico (invariante 5): mesma entrada e mesmos parâmetros ⇒ mesma saída.
    As cotas (invariante 6) e o relaxamento só-destaque (invariante 7) são garantidos
    pelos módulos do domínio, não reimplementados aqui.
    """
    contagem = Counter(c.imovel_id for c in candidatos)
    dups = sorted(i for i, n in contagem.items() if n > 1)
    if dups:
        raise ValueError(f"imovel_id duplicado no lote de candidatos: {dups}")

    anuncios = anuncios or {}
    if not anuncios:
        portal_entrou = False  # sem anúncio nenhum não há ordem de portal, entrou ou não

    # D-027: o filtro de perfil é calculado AQUI (só a costura conhece os perfis) e
    # entregue à elegibilidade como veredito — a mesma costura que a prévia reusa.
    filtro = aplicar_filtro_de_perfil(
        candidatos, dims_por_imovel, perfis, parametros.exigir_dimensao_no_perfil
    )
    candidatos = filtro.candidatos
    contam = filtro.perfis_que_contam
    extras = list(filtro.degradacoes)

    elegiveis: list[ImovelCandidato] = []
    reprovados: list[tuple[ImovelCandidato, frozenset[Regra]]] = []
    for c in candidatos:
        rr = regras_reprovadas(
            c, data_referencia, minimo_corretores_distrito=parametros.minimo_corretores_distrito
        )
        if rr:
            reprovados.append((c, rr))
        else:
            elegiveis.append(c)

    # Ranking primário: sinais normalizados SOBRE OS ELEGÍVEIS.
    fatores_el = _fatores(elegiveis, anuncios, penalizaveis, parametros.sem_anuncio)
    detalhes: dict[int, DetalheImovel] = {}
    aloc_entrada: list[CandidatoAlocacao] = []
    for c in elegiveis:
        fat = fatores_el[c.imovel_id]
        descontos = _descontos(c.imovel_id, penalizaveis, parametros)  # uma vez por imóvel
        desc_total = sum(descontos.values(), 0.0)
        bruta = _nota_bruta(fat, parametros, portal_entrou)
        nota = nota_final(bruta, desc_total)
        aloc_entrada.append(
            CandidatoAlocacao(
                imovel_id=c.imovel_id,
                preco=c.preco,
                nota_super_destaque=nota,
                nota_destaque=nota,
                desempate=_desempate(fat, parametros, portal_entrou),  # D-028
            )
        )
        detalhes[c.imovel_id] = DetalheImovel(
            imovel_id=c.imovel_id,
            fatores=fat,
            descontos_por_penalidade=descontos,
            desconto_total=desc_total,
            nota_super_destaque=nota,
            nota_destaque=nota,
            perfil_que_puxou=perfil_que_puxou(dims_por_imovel.get(c.imovel_id, {}), contam),
            nota_bruta=bruta,
        )
    alocacao = alocar(aloc_entrada)

    # Relaxamento (só destaque): reprovados normalizados ENTRE SI. O pool é montado
    # mesmo sem déficit: a trava do login (D-029) é contada sobre os candidatos, e a
    # apuração mostra a nota dos reprovados de qualquer jeito.
    deficit = COTA_DESTAQUE - len(alocacao.destaque)
    if reprovados:
        so_reprovados = [c for c, _ in reprovados]
        fatores_rep = _fatores(so_reprovados, anuncios, penalizaveis, parametros.sem_anuncio)
        pool: list[CandidatoRelaxamento] = []
        for c, rr in reprovados:
            fat = fatores_rep[c.imovel_id]
            descontos = _descontos(c.imovel_id, penalizaveis, parametros)
            desc_total = sum(descontos.values(), 0.0)
            bruta = _nota_bruta(fat, parametros, portal_entrou)
            nota_dest = nota_final(bruta, desc_total)
            pool.append(
                CandidatoRelaxamento(
                    imovel_id=c.imovel_id,
                    nota_destaque=nota_dest,
                    regras_reprovadas=rr,
                    desempate=_desempate(fat, parametros, portal_entrou),
                    # D-029: só a marca; a trava é aplicada pelo relaxamento.
                    gestor_sem_login=c.gestor_logou_na_janela is False,
                )
            )
            detalhes[c.imovel_id] = DetalheImovel(
                imovel_id=c.imovel_id,
                fatores=fat,
                descontos_por_penalidade=descontos,
                desconto_total=desc_total,
                nota_super_destaque=None,  # reprovado só disputa destaque (relaxamento)
                nota_destaque=nota_dest,
                perfil_que_puxou=perfil_que_puxou(dims_por_imovel.get(c.imovel_id, {}), contam),
                nota_bruta=bruta,
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
        degradacoes=(
            *extras,
            *(() if portal_entrou else (degradacao_sem_portal(parametros.ordem_sem_portal),)),
            *DEGRADACOES,
        ),
    )
