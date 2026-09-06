"""Leitura da saída do Coletor Externo (raspador TS) — contrato de arquivo (Spec §5, D-010).

O raspador (`coletor-externo/`, TypeScript/CDP) grava em `out/`:
- `<portal>.csv` (ex.: `canalpro.csv`): a COLETA COMPLETA. Uma linha por anúncio,
  16 colunas, TODAS entre aspas duplas, CRLF; um valor nulo vira célula vazia `""`.
- `<portal>.canario.csv`: a mesma forma, escrita pelo CANÁRIO — arquivo próprio,
  recomeçado a cada corrida. Enquanto os dois modos compartilhavam um arquivo, as
  corridas se empilhavam e o dedupe daqui, que fica com a PRIMEIRA ocorrência,
  entregava a linha mais antiga.
- `<portal>.anterior.csv`: uma geração guardada da coleta completa. NÃO é lida aqui.
- `status.json`: `{result: "ok"|"blocked"|"error"|"running", mode: "canary"|"full",
  finishedAt: ISO, portal, rows?, message?}`. É o `mode` que diz qual CSV a corrida
  produziu; `running` aparece enquanto uma coleta completa está em curso.
- `NEEDS_WARM.flag`: se existe, a sessão caiu (Cloudflare ou 401) e precisa re-login.
  O raspador a remove quando uma requisição autenticada responde.

A raspagem fica FORA do caminho da decisão (invariantes 4/5): esta leitura é
FONTE, datada pelo `finishedAt` próprio; o determinismo do produto se preserva
porque a coleta é entrada, não cálculo. Invariante 3: o raspador já coleta só
performance + amarração (o RECIPE exclui endereço/imagens), então nada de dado
pessoal transita aqui.

Amarração: a coluna `codigoImovel` (externalId) casa com o `imovel_id` interno
(`realties.Id`). O formato REAL, visto na primeira raspagem (03/09/2026 à noite, 300 de 300):
`{Id}{letra}` — seis dígitos e uma letra maiúscula (ex.: `431347A`). O prefixo é o
`realties.Id`; a letra varia entre anúncios do mesmo dia (21 letras em 300) e é o
marcador de rotação de marketing do portal, não parte da chave — é o
`realties.NewIdMarketingRotation` (300 de 300 iguais; registrado em
`docs/mapa-de-dados.md`), o id sob o qual a Newcore republica o anúncio. `_imovel_id_de` é a
única costura desse formato: dígitos ASCII, uma letra opcional, nada mais; o que não
casar conta como `sem_amarracao`.

URL vem sempre vazia da listagem do Canal Pro (lacuna documentada); preservada
como None, não é recuperável depois. Os cliques ficam POR TIPO nesta leitura
(Spec §5): a soma entre tipos pertence à nota (§6.3, D-028) e é feita na costura,
não aqui — tipos diferentes medem intenções diferentes, e quem some declara.
"""

from __future__ import annotations

import csv
import json
import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo

# Colunas do CSV, na ordem exata do raspador (canalpro.ts csvColumns).
COLUNAS = (
    "idPortal",
    "codigoImovel",
    "nota",
    "notaNome",
    "nivel",
    "situacao",
    "preco",
    "portais",
    "criadoEm",
    "visualizacoes",
    "cliqueContato",
    "cliqueTelefone",
    "cliqueProposta",
    "cliqueWhatsapp",
    "cliqueAgendamento",
    "url",
)
# Cliques por tipo — nunca somados (Spec §5; decisão explícita do raspador).
CLIQUES = (
    "cliqueContato",
    "cliqueTelefone",
    "cliqueProposta",
    "cliqueWhatsapp",
    "cliqueAgendamento",
)
NEEDS_WARM_FLAG = "NEEDS_WARM.flag"
# O fuso em que a IDADE da coleta é medida. Fato operacional (a máquina do gestor roda
# aqui — CLAUDE.md, "hospedagem na máquina física do gestor"), não parâmetro de decisão;
# FIXO e nomeado, nunca o fuso do SO: `astimezone()` sem argumento leria o ambiente, e a
# mesma coleta com o mesmo `--hoje` daria idade diferente noutra máquina (invariante 5 —
# o revisor provou com TZ=Pacific/Pago_Pago).
FUSO_DA_OPERACAO: tzinfo = ZoneInfo("America/Sao_Paulo")


@dataclass(frozen=True)
class DesempenhoAnuncio:
    """Sinais de portal de UM anúncio, amarrado ao imóvel interno. Crus (a nota é
    o LQS sem reescala); a composição na nota é do consumidor (§6.3)."""

    imovel_id: int
    id_portal: str
    nota: float | None  # LQS cru (~5.580–9.580); None se ausente
    visualizacoes: int
    cliques: Mapping[str, int]  # por tipo, nunca somados
    url: str | None  # sempre None na listagem do Canal Pro


@dataclass(frozen=True)
class ColetaExterna:
    """O que a raspagem entregou nesta rodada, mais o metadado que decide se ela
    entra no cálculo (idade, estado, cobertura). A `taxa_amarracao` NÃO vem do
    raspador (status.json não a grava) — calcula-se contra a lista-alvo do Coletor
    Interno com `taxa_amarracao()`."""

    estado: str  # "ok" | "blocked" | "error" | "ausente"
    coletado_em: datetime | None  # finishedAt do status.json (idade é derivada)
    por_imovel: Mapping[int, DesempenhoAnuncio]
    total_linhas: int  # linhas lidas do CSV (antes de dedupe por imóvel)
    sem_amarracao: int  # linhas com codigoImovel fora do formato {Id}{letra} (não amarraram)


# Dígitos ASCII (não `\d`, não `isdigit()`: "²" e "١" não são ids) e UMA letra MAIÚSCULA
# opcional — o marcador de rotação do portal. Minúscula, duas letras, hífen, espaço: não é
# o formato, e "nada mais" é a promessa.
_CODIGO_DO_PORTAL = re.compile(r"([0-9]+)[A-Z]?")


def _imovel_id_de(codigo: str) -> int | None:
    """Costura do formato da amarração: `{realties.Id}{letra opcional}`. A primeira
    versão exigia decimal puro e teria amarrado 0% do CSV real. Um código vazio ou
    fora do formato não amarra (retorna None)."""
    m = _CODIGO_DO_PORTAL.fullmatch(codigo.strip())
    return int(m.group(1)) if m else None


def _para_int(cell: str) -> int:
    """Contagem (visualizações/cliques): célula vazia OU malformada = 0 — nunca
    derruba a leitura (o contrato quer degradar, não abortar)."""
    cell = cell.strip()
    try:
        return int(cell) if cell else 0
    except ValueError:
        return 0


def _para_float(cell: str) -> float | None:
    """Medida opcional (nota/preço): célula vazia OU malformada = None (ausente,
    não zero) — nunca derruba a leitura."""
    cell = cell.strip()
    try:
        return float(cell) if cell else None
    except ValueError:
        return None


def _para_datetime(iso: str | None) -> datetime | None:
    """Sempre AWARE: o raspador escreve `toISOString()` (UTC com `Z`); um instante sem
    offset é tratado como UTC, explicitamente — nunca como o fuso da máquina."""
    if not iso:
        return None
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _ler_json(caminho: Path) -> dict | None:
    """Lê um JSON de status; None se ausente. Corrompido levanta, como antes."""
    if not caminho.is_file():
        return None
    return json.loads(caminho.read_text(encoding="utf-8"))


def ler_status(out_dir: Path, modo: str | None = None) -> dict | None:
    """Lê o status da coleta. None se ausente.

    Sem `modo`, lê `status.json` — "a última corrida", que é o que o painel mostra.
    Com `modo`, lê `status.<modo>.json`, o registro que a outra corrida não
    sobrescreve. A distinção existe porque um canário de segundos rodado depois de
    uma coleta completa de horas apagava o registro dela: a partir daí a rodada
    apontava para o CSV do canário, com o `finishedAt` novo passando na porta de
    idade, e o full ficava inalcançável. É a sequência que o console prescreve, já
    que o canário é o portão que libera o full.

    Compatibilidade: sem o arquivo por modo, aceita `status.json` se o `mode` dele
    casar — coleta anterior a esta correção só tinha um arquivo.
    """
    if modo is not None:
        por_modo = out_dir / f"status.{modo}.json"
        if por_modo.is_file():
            return _ler_json(por_modo)
        ultimo = _ler_json(out_dir / "status.json")
        if ultimo is not None and str(ultimo.get("mode", "")).strip().lower() == modo:
            return ultimo
        return None
    caminho = out_dir / "status.json"
    if not caminho.is_file():
        return None
    return json.loads(caminho.read_text(encoding="utf-8"))


def _linhas_do_csv(caminho: Path) -> tuple[list[DesempenhoAnuncio], int, int]:
    """Parseia o CSV → (anúncios amarrados, total de linhas, sem amarração).
    Dedup por `id_portal` (RECIPE: dedupe por id na leitura)."""
    anuncios: list[DesempenhoAnuncio] = []
    total = 0
    sem_amarracao = 0
    vistos: set[str] = set()
    with caminho.open(encoding="utf-8", newline="") as f:
        leitor = csv.DictReader(f)
        for linha in leitor:
            total += 1
            id_portal = (linha.get("idPortal") or "").strip()
            if id_portal:  # dedupe por id (RECIPE) — só quando há id; vazio nunca dedupa
                if id_portal in vistos:  # duplicata residual (~0,02%)
                    continue
                vistos.add(id_portal)
            imovel_id = _imovel_id_de(linha.get("codigoImovel") or "")
            if imovel_id is None:
                sem_amarracao += 1
                continue
            anuncios.append(
                DesempenhoAnuncio(
                    imovel_id=imovel_id,
                    id_portal=id_portal,
                    nota=_para_float(linha.get("nota") or ""),
                    visualizacoes=_para_int(linha.get("visualizacoes") or ""),
                    cliques={c: _para_int(linha.get(c) or "") for c in CLIQUES},
                    url=(linha.get("url") or "").strip() or None,
                )
            )
    return anuncios, total, sem_amarracao


def _por_imovel(anuncios: list[DesempenhoAnuncio]) -> dict[int, DesempenhoAnuncio]:
    """Indexa por imóvel. Se dois anúncios amarram no mesmo imóvel (raro), fica o
    de MAIS visualizações — determinístico (invariante 5), desempate por id_portal."""
    escolha: dict[int, DesempenhoAnuncio] = {}
    for a in anuncios:
        atual = escolha.get(a.imovel_id)
        if atual is None or (a.visualizacoes, a.id_portal) > (atual.visualizacoes, atual.id_portal):
            escolha[a.imovel_id] = a
    return escolha


def _csv_do_modo(out_dir: Path, portal: str, status: Mapping[str, object] | None) -> Path:
    """Qual CSV esta coleta produziu, pelo MODO que ela declarou.

    O canário e a coleta completa escrevem arquivos separados desde a correção do
    contrato de arquivo: o canário é a sonda que o console lê para liberar o full,
    a completa é o estoque. Enquanto compartilhavam `{portal}.csv`, uma sonda de
    mil linhas ficava indistinguível da cauda de uma coleta de 55 mil, e o
    deduplicador daqui — que fica com a PRIMEIRA ocorrência de cada `idPortal` —
    entregava sistematicamente a linha mais antiga do arquivo.

    Compatibilidade: `status.json` sem `mode` é de antes da correção, e nele o
    único arquivo possível é `{portal}.csv`.

    NÃO há fallback quando o modo é declarado e o arquivo dele não existe. Um
    canário que morre antes de gravar deixa em `out/` o CSV de uma coleta completa
    de dias atrás; cair nele daria à rodada amostral um universo velho carimbado
    com o `finishedAt` de hoje. Sem o arquivo do modo, `ler_coleta` devolve "error"
    com `por_imovel` vazio — degradar é o certo, e é barato de refazer.
    """
    completo = out_dir / f"{portal}.csv"
    bruto = status.get("mode") if status is not None else None
    # Normalizado, e só se for string: uma deriva de caixa no produtor ("CANARY"),
    # ou um `mode` que venha como lista, selecionaria o arquivo do full em silêncio —
    # a contaminação de volta por uma porta nova.
    modo = bruto.strip().lower() if isinstance(bruto, str) else ""
    return out_dir / f"{portal}.canario.csv" if modo == "canary" else completo


def ler_coleta(out_dir: Path, portal: str = "canalpro", modo: str | None = None) -> ColetaExterna:
    """Lê a saída completa do raspador em `out_dir`. Estado:
    - "blocked" se há `NEEDS_WARM.flag` ou o status diz blocked (sessão caiu);
    - o `result` do status.json ("ok"/"error") quando há status;
    - "ausente" se não há nem status nem CSV (o raspador não rodou).
    Nunca levanta por ausência — a decisão degrada, não aborta, sem portal.

    `modo` ("canary"/"full") pede a coleta DAQUELE modo, com o status próprio dela:
    é assim que a rodada amostral lê o canário que definiu a amostra e a rodada real
    lê a coleta completa, sem que uma sonda de segundos apague o registro da outra.
    Sem `modo`, vale a última corrida — o comportamento do painel."""
    status = ler_status(out_dir, modo)
    bloqueado = (out_dir / NEEDS_WARM_FLAG).exists() or (
        status is not None and status.get("result") == "blocked"
    )
    csv_path = (
        out_dir / f"{portal}.canario.csv"
        if modo == "canary"
        else out_dir / f"{portal}.csv"
        if modo == "full"
        else _csv_do_modo(out_dir, portal, status)
    )
    if status is None and not csv_path.is_file():
        return ColetaExterna("ausente", None, {}, 0, 0)

    anuncios, total, sem_amarracao = _linhas_do_csv(csv_path) if csv_path.is_file() else ([], 0, 0)
    if bloqueado:
        estado = "blocked"
    elif not csv_path.is_file():
        estado = "error"  # status presente mas CSV ausente: coleta incompleta
    elif status is not None:
        estado = status.get("result", "error")
    else:
        estado = "error"  # há CSV mas nenhum status: coleta incompleta
    return ColetaExterna(
        estado=estado,
        coletado_em=_para_datetime(status.get("finishedAt") if status else None),
        por_imovel=_por_imovel(anuncios),
        total_linhas=total,
        sem_amarracao=sem_amarracao,
    )


def casados(coleta: ColetaExterna, imoveis_alvo: Collection[int]) -> int:
    """Quantos imóveis da lista-alvo a raspagem casou a um anúncio. É a contagem
    por trás da taxa, exposta porque a admissão precisa dela CRUA: zero casados é
    um caso próprio, que a taxa (0.0) não distingue de um limiar 0.0."""
    return sum(1 for i in set(imoveis_alvo) if i in coleta.por_imovel)


def taxa_amarracao(coleta: ColetaExterna, imoveis_alvo: Collection[int]) -> float:
    """Fração da lista-alvo do Coletor Interno que a raspagem casou a um anúncio
    (Spec §5). 0.0 se a lista-alvo é vazia. É o número que a cobertura mínima
    (nº 7, adotada em 50 % pela D-034) compara para decidir se a nota do portal
    entra na ordem."""
    alvo = set(imoveis_alvo)
    if not alvo:
        return 0.0
    return casados(coleta, alvo) / len(alvo)


@dataclass(frozen=True)
class ParametrosExterno:
    """Parâmetros que decidem se a raspagem entra na ordem. Os dois limiares foram
    DEFINIDOS pela D-034 (cobertura mínima 50 %, idade máxima 2 dias) e chegam aqui
    injetados a partir do efetivo da rodada — o valor adotado mora em
    `config.adotados`, e este módulo não guarda cópia. A composição dos sinais numa
    nota não é mais deste contrato: desde a D-028 ela é da nota (§6.3), feita na
    costura, e aqui só se entrega o anúncio cru por imóvel."""

    limiar_amarracao: float  # cobertura mínima, como fração (portal.cobertura_minima / 100)
    idade_maxima_dias: int  # portal.idade_maxima_dias
    # Fuso da medição da idade: entrada EXPLÍCITA, com default fixo e nomeado. Ver
    # `FUSO_DA_OPERACAO`.
    fuso: tzinfo = FUSO_DA_OPERACAO


@dataclass(frozen=True)
class ResultadoExterno:
    """Veredito da admissão da coleta externa ao cálculo (Spec §7.3) + os números
    que a planilha declara (idade do dado, taxa de amarração, §3.1)."""

    entra: bool  # a performance externa entra no ranking?
    taxa_amarracao: float
    idade_dias: int | None  # None se a coleta não tem timestamp
    motivo: str  # razão da não-admissão (declarada); "" quando entra


def avaliar_coleta(
    coleta: ColetaExterna,
    imoveis_alvo: Collection[int],
    params: ParametrosExterno,
    data_referencia: date,
) -> ResultadoExterno:
    """Decide se a coleta entra no cálculo e, se sim, entrega os anúncios por imóvel.
    Determinístico (invariante 5): idade sai de `data_referencia` (input) menos o
    `coletado_em` do arquivo — nunca do relógio. Portas, na ordem da Spec §7.3, mais
    a porta 2, própria desta implementação (mais estrita que a Spec, não menos):

    1. coleta não-"ok" (blocked/ausente/error) → não entra;
    2. NENHUM imóvel da lista-alvo amarrou → não entra, seja qual for o limiar.
       Porta própria porque a de baixo não a cobre: com zero casados a taxa é 0.0,
       e `0.0 < 0.0` é falso — um limiar 0.0 (o que um piloto declararia) deixaria
       passar uma raspagem que não amarrou nada, e a rodada sairia COMPLETA com o
       sinal do portal zerado para todos, indistinguível de "todos empatados" — que
       é uma leitura legítima e diferente. O formato real do
       `codigoImovel` é `{Id}{letra}` (primeira raspagem, 03/09/2026); se o portal
       o mudar, esta é a falha, e ela precisa sair DECLARADA;
    3. taxa de amarração < limiar (nº 7) → performance externa NÃO entra, sinaliza;
    4. idade > máxima (nº 5) → fora da janela aceitável → não entra (a "reserva"
       da Spec §7.3 — reusar a última coleta válida — é fatia futura; aqui só se
       declara a idade e degrada).

    Passando as quatro, os anúncios amarrados seguem para a costura, que compõe a
    nota (§6.3) e normaliza min-max entre a população."""
    alvo = set(imoveis_alvo)  # uma vez: a taxa e a porta 2 contam sobre o mesmo conjunto
    n_casados = casados(coleta, alvo)
    taxa = n_casados / len(alvo) if alvo else 0.0
    # `finishedAt` é UTC (o raspador grava `toISOString()`), a data de referência é do
    # fuso da operação: sem converter, uma coleta das 21h de hoje (00h de amanhã em UTC)
    # sai com idade -1 — visto na primeira rodada real, 03/09/2026. Converte para
    # `params.fuso` (explícito, fixo) ANTES de tirar a data — nunca para o fuso do SO.
    idade = (
        (data_referencia - coleta.coletado_em.astimezone(params.fuso).date()).days
        if coleta.coletado_em
        else None
    )

    def _nao(motivo: str) -> ResultadoExterno:
        return ResultadoExterno(False, taxa, idade, motivo)

    if coleta.estado != "ok":
        return _nao(f"coleta externa {coleta.estado} — sem performance de portal")
    if n_casados == 0:
        return _nao(
            f"raspagem lida ({coleta.total_linhas} linhas, {coleta.sem_amarracao} fora "
            "do formato {Id}{letra}), mas NENHUMA amarrou com a lista-alvo — performance "
            "externa não entra. Não é 'todos iguais': é dado ausente. Confira o "
            "codigoImovel (externalId): o formato esperado é {Id}{letra}"
        )
    if taxa < params.limiar_amarracao:
        return _nao(
            f"taxa de amarração {taxa:.0%} < limiar {params.limiar_amarracao:.0%} (nº 7) "
            "— performance externa não entra no cálculo (Spec §7.3)"
        )
    if idade is None or idade > params.idade_maxima_dias:
        return _nao(
            f"idade da coleta {idade} dias > máxima {params.idade_maxima_dias} (nº 5) "
            "— fora da janela aceitável, sem reserva (Spec §7.3)"
        )
    # Passando as quatro portas, o que entra no cálculo são os anúncios CRUS
    # (`coleta.por_imovel`); a composição da nota é da costura (D-028).
    return ResultadoExterno(True, taxa, idade, "")
