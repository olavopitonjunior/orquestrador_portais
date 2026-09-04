"""Testes da leitura da saída do Coletor Externo (contrato de arquivo, Spec §5).

Sem raspagem real: escreve `out/canalpro.csv` + `out/status.json` num tmp no
formato EXATO do raspador TS (16 colunas, toda célula entre aspas, CRLF, null =
célula vazia) e confere o parse, a amarração, o dedupe e a taxa de amarração.
"""

from __future__ import annotations

import json
from datetime import UTC, date
from pathlib import Path

import pytest

from dados.coletor_externo import (
    COLUNAS,
    ParametrosExterno,
    avaliar_coleta,
    ler_coleta,
    taxa_amarracao,
)

# Parâmetros PROVISÓRIOS de teste (nº 5/nº 7 são nulos): limiar 50%, janela 8 dias,
# F3 = visualizações.
PARAMS_EXT = ParametrosExterno(
    limiar_amarracao=0.5, idade_maxima_dias=8, compor_desempenho=lambda a: a.visualizacoes
)
HOJE = date(2026, 9, 1)


def _escrever_csv(out: Path, linhas: list[dict], portal: str = "canalpro") -> None:
    """Grava no formato do raspador: cabeçalho + linhas, TODA célula entre aspas
    duplas, CRLF, null → vazio."""

    def cel(v) -> str:
        s = "" if v is None else str(v)
        return '"' + s.replace('"', '""') + '"'

    linhas_txt = [",".join(cel(c) for c in COLUNAS)]
    for linha in linhas:
        linhas_txt.append(",".join(cel(linha.get(c)) for c in COLUNAS))
    (out / f"{portal}.csv").write_text("\r\n".join(linhas_txt) + "\r\n", encoding="utf-8")


def _status(out: Path, **campos) -> None:
    (out / "status.json").write_text(json.dumps(campos), encoding="utf-8")


def _anuncio(id_portal, codigo, **extra) -> dict:
    base = {
        "idPortal": id_portal,
        "codigoImovel": codigo,
        "nota": 8442.5,
        "notaNome": "lqsBeta",
        "nivel": "PREMIUM",
        "situacao": "ACTIVE",
        "preco": 850000,
        "portais": "OLX|VIVAREAL|ZAP",
        "criadoEm": "10/01/2026 09:00:00",
        "visualizacoes": 128,
        "cliqueContato": 4,
        "cliqueTelefone": 9,
        "cliqueProposta": 2,
        "cliqueWhatsapp": 15,
        "cliqueAgendamento": 1,
        "url": None,
    }
    base.update(extra)
    return base


# --- happy path ---------------------------------------------------------------


def test_le_anuncios_amarrados_e_conta_sem_amarracao(tmp_path):
    _escrever_csv(
        tmp_path,
        [
            _anuncio("9000000001", "101"),
            _anuncio("9000000002", "202", visualizacoes=50),
            _anuncio("9000000003", None, visualizacoes=3),  # sem externalId → não amarra
        ],
    )
    _status(tmp_path, result="ok", finishedAt="2026-09-01T09:00:00.000Z", portal="canalpro", rows=3)
    coleta = ler_coleta(tmp_path)
    assert coleta.estado == "ok"
    assert set(coleta.por_imovel) == {101, 202}
    assert coleta.total_linhas == 3
    assert coleta.sem_amarracao == 1
    assert coleta.coletado_em is not None
    a = coleta.por_imovel[101]
    assert a.nota == 8442.5
    assert a.visualizacoes == 128
    assert a.cliques["cliqueWhatsapp"] == 15
    assert a.url is None  # sempre nulo na listagem


def test_codigo_nao_numerico_nao_amarra(tmp_path):
    _escrever_csv(tmp_path, [_anuncio("9000000001", "IMOVEL-0001")])
    _status(tmp_path, result="ok", finishedAt="2026-09-01T09:00:00Z", portal="canalpro")
    coleta = ler_coleta(tmp_path)
    assert coleta.por_imovel == {}
    assert coleta.sem_amarracao == 1


def test_o_formato_REAL_do_canal_pro_amarra_pelo_prefixo(tmp_path):
    """Primeira raspagem real (03/09/2026): `codigoImovel` vem como `{realties.Id}{letra}`
    — 300 de 300 casaram pelo prefixo; a letra varia (21 em 300) e é rotação de
    marketing, não chave. A versão que exigia decimal puro teria amarrado 0%."""
    _escrever_csv(
        tmp_path,
        [
            _anuncio("1", "431347A"),
            _anuncio("2", "431348Z", visualizacoes=7),
            _anuncio("3", "431372"),
        ],
    )
    _status(tmp_path, result="ok", finishedAt="2026-09-01T09:00:00Z", portal="canalpro")
    coleta = ler_coleta(tmp_path)
    assert set(coleta.por_imovel) == {431347, 431348, 431372}
    assert coleta.sem_amarracao == 0


def test_a_letra_e_rotacao_o_mesmo_imovel_pode_ter_dois_anuncios(tmp_path):
    """`431347A` e `431347B` são o mesmo imóvel republicado: os dois amarram, e fica o
    de mais visualizações (desempate por `id_portal`, determinístico)."""
    _escrever_csv(
        tmp_path,
        [_anuncio("1", "431347A", visualizacoes=10), _anuncio("2", "431347B", visualizacoes=200)],
    )
    _status(tmp_path, result="ok", finishedAt="2026-09-01T09:00:00Z", portal="canalpro")
    coleta = ler_coleta(tmp_path)
    assert coleta.total_linhas == 2 and coleta.sem_amarracao == 0
    assert set(coleta.por_imovel) == {431347}
    assert coleta.por_imovel[431347].visualizacoes == 200


@pytest.mark.parametrize(
    "ruim",
    [
        "431347AB",
        "431347-A",
        " 431347 A",
        "A431347",
        "\u00b2",
        "\u0661",
        "\uff11\uff10",
        "431347a",
        "",
    ],
)
def test_fora_do_formato_nao_amarra(tmp_path, ruim):
    """`isdigit()` aceitava "²" (e `int()` estourava) e "١" (e amarrava um id falso) —
    issue #61. Só dígitos ASCII e uma letra opcional."""
    _escrever_csv(tmp_path, [_anuncio("1", ruim)])
    _status(tmp_path, result="ok", finishedAt="2026-09-01T09:00:00Z", portal="canalpro")
    coleta = ler_coleta(tmp_path)
    assert coleta.por_imovel == {} and coleta.sem_amarracao == 1


def test_celulas_vazias_viram_none_ou_zero(tmp_path):
    _escrever_csv(
        tmp_path,
        [_anuncio("9000000001", "101", nota=None, visualizacoes=None, cliqueContato=None)],
    )
    _status(tmp_path, result="ok", finishedAt="2026-09-01T09:00:00Z", portal="canalpro")
    a = ler_coleta(tmp_path).por_imovel[101]
    assert a.nota is None  # medida ausente = None
    assert a.visualizacoes == 0  # contagem ausente = 0
    assert a.cliques["cliqueContato"] == 0


# --- dedupe -------------------------------------------------------------------


def test_dedupe_por_id_portal(tmp_path):
    _escrever_csv(
        tmp_path,
        [_anuncio("9000000001", "101"), _anuncio("9000000001", "101")],  # id repetido
    )
    _status(tmp_path, result="ok", finishedAt="2026-09-01T09:00:00Z", portal="canalpro")
    coleta = ler_coleta(tmp_path)
    assert coleta.total_linhas == 2  # duas linhas lidas
    assert set(coleta.por_imovel) == {101}  # uma só após dedupe por id


def test_dois_anuncios_no_mesmo_imovel_fica_o_de_mais_views(tmp_path):
    _escrever_csv(
        tmp_path,
        [
            _anuncio("9000000001", "101", visualizacoes=10),
            _anuncio("9000000002", "101", visualizacoes=200),
        ],
    )
    _status(tmp_path, result="ok", finishedAt="2026-09-01T09:00:00Z", portal="canalpro")
    a = ler_coleta(tmp_path).por_imovel[101]
    assert a.visualizacoes == 200  # o mais ativo, determinístico


# --- estados: blocked / ausente -----------------------------------------------


def test_needs_warm_flag_marca_blocked(tmp_path):
    _escrever_csv(tmp_path, [_anuncio("9000000001", "101")])
    _status(tmp_path, result="ok", finishedAt="2026-09-01T09:00:00Z", portal="canalpro")
    (tmp_path / "NEEDS_WARM.flag").write_text("2026-09-01T09:00:00Z", encoding="utf-8")
    assert ler_coleta(tmp_path).estado == "blocked"


def test_status_blocked_marca_blocked(tmp_path):
    _status(
        tmp_path,
        result="blocked",
        finishedAt="2026-09-01T09:00:00Z",
        portal="canalpro",
        message="Cloudflare",
    )
    assert ler_coleta(tmp_path).estado == "blocked"


def test_sem_arquivos_fica_ausente(tmp_path):
    coleta = ler_coleta(tmp_path)
    assert coleta.estado == "ausente"
    assert coleta.por_imovel == {}
    assert coleta.coletado_em is None


def test_status_ok_sem_csv_fica_error(tmp_path):
    # status diz ok mas o CSV não existe: coleta incompleta, não "ok" (achado do revisor)
    _status(tmp_path, result="ok", finishedAt="2026-09-01T09:00:00Z", portal="canalpro", rows=2)
    coleta = ler_coleta(tmp_path)
    assert coleta.estado == "error"
    assert coleta.por_imovel == {}


# --- robustez do parse (achados do revisor-de-código) -------------------------


def test_id_portal_vazio_nao_dedupa(tmp_path):
    # duas linhas com idPortal vazio mas codigoImovel distinto: ambas amarram
    # (vazio nunca é tratado como duplicata — senão perderia anúncio em silêncio).
    _escrever_csv(tmp_path, [_anuncio("", "101"), _anuncio("", "202")])
    _status(tmp_path, result="ok", finishedAt="2026-09-01T09:00:00Z", portal="canalpro")
    coleta = ler_coleta(tmp_path)
    assert set(coleta.por_imovel) == {101, 202}  # nenhuma descartada


def test_celula_malformada_nao_derruba_a_leitura(tmp_path):
    # nota "N/A" (não-numérica) não estoura ValueError — degrada para None.
    _escrever_csv(tmp_path, [_anuncio("1", "101", nota="N/A", visualizacoes="x")])
    _status(tmp_path, result="ok", finishedAt="2026-09-01T09:00:00Z", portal="canalpro")
    a = ler_coleta(tmp_path).por_imovel[101]
    assert a.nota is None  # medida malformada = None
    assert a.visualizacoes == 0  # contagem malformada = 0


# --- taxa de amarração --------------------------------------------------------


def test_taxa_de_amarracao(tmp_path):
    _escrever_csv(tmp_path, [_anuncio("1", "101"), _anuncio("2", "202")])
    _status(tmp_path, result="ok", finishedAt="2026-09-01T09:00:00Z", portal="canalpro")
    coleta = ler_coleta(tmp_path)
    assert taxa_amarracao(coleta, [101, 202, 303, 404]) == 0.5  # 2 de 4 casaram
    assert taxa_amarracao(coleta, []) == 0.0  # lista-alvo vazia


def test_taxa_de_amarracao_completa(tmp_path):
    _escrever_csv(tmp_path, [_anuncio("1", "101")])
    _status(tmp_path, result="ok", finishedAt="2026-09-01T09:00:00Z", portal="canalpro")
    coleta = ler_coleta(tmp_path)
    assert taxa_amarracao(coleta, [101]) == 1.0


# --- avaliar_coleta: portas de admissão (Spec §7.3) ---------------------------


def _coleta_fresca(tmp_path, linhas, dias_atras=0):
    dia = HOJE.toordinal() - dias_atras
    d = date.fromordinal(dia).isoformat()
    _escrever_csv(tmp_path, linhas)
    _status(tmp_path, result="ok", finishedAt=f"{d}T09:00:00Z", portal="canalpro")
    return ler_coleta(tmp_path)


def test_avaliar_entra_e_compoe_f3(tmp_path):
    coleta = _coleta_fresca(
        tmp_path, [_anuncio("1", "101", visualizacoes=300), _anuncio("2", "202", visualizacoes=50)]
    )
    r = avaliar_coleta(coleta, [101, 202], PARAMS_EXT, HOJE)
    assert r.entra is True
    assert r.motivo == ""
    assert r.desempenho_por_imovel == {101: 300.0, 202: 50.0}  # F3 = visualizações (provisório)
    assert r.taxa_amarracao == 1.0
    assert r.idade_dias == 0


def test_avaliar_amarracao_baixa_nao_entra(tmp_path):
    # 1 de 4 amarrado = 25% < 50% → performance externa não entra (Spec §7.3)
    coleta = _coleta_fresca(tmp_path, [_anuncio("1", "101")])
    r = avaliar_coleta(coleta, [101, 202, 303, 404], PARAMS_EXT, HOJE)
    assert r.entra is False
    assert "amarração" in r.motivo
    assert r.desempenho_por_imovel == {}
    assert r.taxa_amarracao == 0.25


def _params_de_piloto():
    """O que um piloto DECLARARIA para ver a raspagem entrar: limiar zero."""
    return ParametrosExterno(
        limiar_amarracao=0.0, idade_maxima_dias=8, compor_desempenho=lambda a: a.visualizacoes
    )


def test_amarracao_vazia_nao_entra_mesmo_com_limiar_zero(tmp_path):
    """Mutação que este teste apanha: sem a porta de zero casados, `0.0 < 0.0` é
    falso, a coleta passa, e a rodada sai COMPLETA com F3 = 0 para todos — a falha
    mais provável da primeira raspagem real, porque o formato do codigoImovel não
    tolera desvio."""
    coleta = _coleta_fresca(tmp_path, [_anuncio("1", "IMOVEL-0001"), _anuncio("2", "IMOVEL-0002")])
    assert coleta.por_imovel == {}  # nada amarrou
    r = avaliar_coleta(coleta, [101, 202], _params_de_piloto(), HOJE)
    assert r.entra is False
    assert "NENHUMA amarrou" in r.motivo
    # O diagnóstico nomeia o formato esperado — com chaves SIMPLES (os literais não são
    # f-strings; `{{` sairia literal, e foi o que o orquestrador apanhou).
    assert "o formato esperado é {Id}{letra}" in r.motivo and "{{" not in r.motivo
    assert r.desempenho_por_imovel == {}
    assert r.taxa_amarracao == 0.0


def test_amarracao_disjunta_da_lista_alvo_nao_entra(tmp_path):
    """Linhas amarradas a imóveis que NÃO são candidatos: a composição do F3 hoje
    percorre `por_imovel` inteiro, então sem a porta o resultado seria `entra=True`
    com desempenho só para quem não está na lista — e zero para todos os alvos."""
    coleta = _coleta_fresca(tmp_path, [_anuncio("1", "101", visualizacoes=300)])
    r = avaliar_coleta(coleta, [202, 303], _params_de_piloto(), HOJE)
    assert r.entra is False
    assert "NENHUMA amarrou" in r.motivo
    assert r.desempenho_por_imovel == {}


def test_csv_vazio_com_status_ok_nao_entra(tmp_path):
    coleta = _coleta_fresca(tmp_path, [])
    assert coleta.estado == "ok"
    assert coleta.total_linhas == 0
    r = avaliar_coleta(coleta, [101], _params_de_piloto(), HOJE)
    assert r.entra is False
    assert "0 linhas" in r.motivo


def test_um_casado_ja_passa_a_porta_de_vazio_e_cai_na_de_limiar(tmp_path):
    """As duas portas são distintas: um único casado sai da primeira e é julgado
    pela segunda, com a mensagem da segunda."""
    coleta = _coleta_fresca(tmp_path, [_anuncio("1", "101")])
    r = avaliar_coleta(coleta, [101, 202, 303, 404], PARAMS_EXT, HOJE)  # 25% < 50%
    assert r.entra is False
    assert "NENHUMA" not in r.motivo
    assert "limiar" in r.motivo


def test_idade_da_coleta_e_medida_no_fuso_da_OPERACAO_nao_no_da_maquina(tmp_path):
    """`finishedAt` é UTC; a data de referência é do fuso da operação (America/Sao_Paulo).
    Uma coleta das 21h04 de 03/09 (00h04 de 04/09 em UTC) tinha idade -1 na primeira rodada
    real. Data FIXA e fuso EXPLÍCITO: o resultado não pode depender do TZ do host (o revisor
    provou que dependia, com TZ=Pacific/Pago_Pago)."""
    from dados.coletor_externo import FUSO_DA_OPERACAO

    _escrever_csv(tmp_path, [_anuncio("1", "431347A")])
    _status(tmp_path, result="ok", finishedAt="2026-09-04T00:04:48.974Z", portal="canalpro")
    coleta = ler_coleta(tmp_path)
    assert coleta.coletado_em is not None and coleta.coletado_em.tzinfo is not None

    hoje = date(2026, 9, 3)
    r = avaliar_coleta(coleta, [431347], PARAMS_EXT, hoje)  # default: FUSO_DA_OPERACAO
    assert FUSO_DA_OPERACAO.key == "America/Sao_Paulo"  # type: ignore[attr-defined]
    assert r.idade_dias == 0 and r.entra is True
    # Em UTC a mesma coleta é "de amanhã": a diferença é o fuso declarado, não a máquina.
    em_utc = ParametrosExterno(0.5, 8, lambda a: a.visualizacoes, fuso=UTC)
    assert avaliar_coleta(coleta, [431347], em_utc, hoje).idade_dias == -1
    # E um `finishedAt` sem offset é UTC, explicitamente.
    _status(tmp_path, result="ok", finishedAt="2026-09-04T00:04:48", portal="canalpro")
    assert avaliar_coleta(ler_coleta(tmp_path), [431347], PARAMS_EXT, hoje).idade_dias == 0


def test_avaliar_coleta_velha_nao_entra(tmp_path):
    coleta = _coleta_fresca(tmp_path, [_anuncio("1", "101")], dias_atras=30)  # > 8 dias
    r = avaliar_coleta(coleta, [101], PARAMS_EXT, HOJE)
    assert r.entra is False
    assert "idade" in r.motivo
    assert r.idade_dias == 30


def test_avaliar_coleta_blocked_nao_entra(tmp_path):
    _status(tmp_path, result="blocked", finishedAt="2026-09-01T09:00:00Z", portal="canalpro")
    coleta = ler_coleta(tmp_path)
    r = avaliar_coleta(coleta, [101], PARAMS_EXT, HOJE)
    assert r.entra is False
    assert "blocked" in r.motivo
