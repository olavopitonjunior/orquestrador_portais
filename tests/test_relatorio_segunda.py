"""Testes do relatório de segunda (Spec §4.1) e da derivação da janela (§1).

Puros: escrevem em `tmp_path` e leem de volta. O que importa provar é que a planilha
declara a limitação (§7.2), que as três abas têm as colunas exigidas, e que a janela
sai da carga em vez de vir de quem chama.
"""

import csv
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from dominio.acompanhamento import LeadDoPeriodo, Nivel, PosicaoPaga, apurar
from entrega.relatorio_segunda import COLUNAS_DESEMPENHO, COLUNAS_LEADS, escrever_relatorio
from executar.segunda import DIAS_DO_PERIODO, janela_da_carga

INICIO, FIM = date(2026, 8, 28), date(2026, 8, 31)


def _resultado(*, com_lead_sem_tratamento=True):
    leads = []
    if com_lead_sem_tratamento:
        leads.append(
            LeadDoPeriodo(
                lead_id=100,
                imovel_id=1,
                entrada=date(2026, 8, 29),
                atendimento_registrado=False,
                contato_registrado=False,
                distribuicao=date(2026, 8, 29),
                corretor_gestor="Corretor X",
                gestor_distrito="Embaixador Y",
                distrito="Centro",
            )
        )
    return apurar(
        rodada_decisao_id=9,
        posicoes=[PosicaoPaga(1, Nivel.SUPER_DESTAQUE), PosicaoPaga(2, Nivel.DESTAQUE)],
        leads=leads,
        inicio_periodo=INICIO,
        fim_periodo=FIM,
    )


def _ler(caminho: Path) -> list[list[str]]:
    with caminho.open(encoding="utf-8") as f:
        return list(csv.reader(f))


# --- Spec §4.1: as três abas ---------------------------------------------------


def test_escreve_as_tres_abas(tmp_path):
    caminhos = escrever_relatorio(_resultado(), "completa", [], tmp_path)
    assert [p.name for p in caminhos] == [
        "resumo.csv",
        "leads_sem_tratamento.csv",
        "desempenho_por_imovel.csv",
    ]
    assert all(p.exists() for p in caminhos)


def test_desempenho_lista_todas_as_posicoes_inclusive_zero_lead(tmp_path):
    escrever_relatorio(_resultado(), "completa", [], tmp_path)
    linhas = _ler(tmp_path / "desempenho_por_imovel.csv")
    assert linhas[0] == list(COLUNAS_DESEMPENHO)
    assert len(linhas) == 3  # cabeçalho + AS DUAS posições (uma sem lead nenhum)


def test_aba_de_leads_tem_as_oito_colunas_da_spec(tmp_path):
    escrever_relatorio(_resultado(), "completa", [], tmp_path)
    linhas = _ler(tmp_path / "leads_sem_tratamento.csv")
    assert linhas[0] == list(COLUNAS_LEADS)
    assert len(linhas[0]) == 8  # §4.2 exige exatamente estas oito
    assert linhas[1][5] == "Corretor X"  # a identidade vai à planilha, legitimamente


# --- Spec §7.2: a limitação é visível NA PLANILHA -----------------------------


def test_resumo_abre_declarando_estado_e_limitacoes(tmp_path):
    escrever_relatorio(
        _resultado(), "degradada", ["11 leads sem imóvel", "15 sem distribuição"], tmp_path
    )
    linhas = _ler(tmp_path / "resumo.csv")
    assert linhas[1] == ["ESTADO DA RODADA", "degradada"]
    assert linhas[2][0] == "LIMITAÇÃO 1" and "sem imóvel" in linhas[2][1]
    assert linhas[3][0] == "LIMITAÇÃO 2"


def test_rodada_completa_diz_que_nao_ha_limitacao(tmp_path):
    escrever_relatorio(_resultado(), "completa", [], tmp_path)
    linhas = _ler(tmp_path / "resumo.csv")
    assert linhas[1] == ["ESTADO DA RODADA", "completa"]
    assert linhas[2] == ["LIMITAÇÕES", "nenhuma"]  # o silêncio seria ambíguo


def test_resumo_carrega_os_totais(tmp_path):
    escrever_relatorio(_resultado(), "completa", [], tmp_path)
    campos = {linha[0]: linha[1] for linha in _ler(tmp_path / "resumo.csv")[1:]}
    assert campos["rodada_decisao_id"] == "9"
    assert campos["posicoes_super"] == "1" and campos["posicoes_destaque"] == "1"
    assert campos["leads_sem_tratamento"] == "1"
    assert campos["imoveis_sem_lead"] == "1"


def test_sem_leads_sem_tratamento_a_aba_fica_so_com_cabecalho(tmp_path):
    escrever_relatorio(_resultado(com_lead_sem_tratamento=False), "completa", [], tmp_path)
    linhas = _ler(tmp_path / "leads_sem_tratamento.csv")
    assert len(linhas) == 1  # cabeçalho; a aba existe mesmo vazia


def test_cria_o_destino_se_nao_existir(tmp_path):
    destino = tmp_path / "nao" / "existe"
    escrever_relatorio(_resultado(), "completa", [], destino)
    assert (destino / "resumo.csv").exists()


# --- Spec §1: a janela sai da CARGA, não de quem chama ------------------------


def test_janela_derivada_da_aprovacao():
    inicio, fim = janela_da_carga(datetime(2026, 8, 28, 18, 30), hoje=date(2026, 9, 10))
    assert inicio == date(2026, 8, 28)  # o dia em que a carga foi aprovada
    assert fim == date(2026, 8, 31)  # + os três dias corridos da Spec §1
    assert (fim - inicio).days == DIAS_DO_PERIODO


def test_janela_nao_passa_de_hoje():
    """Medir dias que ainda não aconteceram inflaria o denominador."""
    inicio, fim = janela_da_carga(datetime(2026, 8, 30, 9, 0), hoje=date(2026, 8, 31))
    assert (inicio, fim) == (date(2026, 8, 30), date(2026, 8, 31))


def test_carga_antiga_mede_os_tres_dias_DELA():
    """Se a carga é de semanas atrás, a janela continua sendo a dela — é o efeito
    daquela carga que se mede, não o de hoje."""
    inicio, fim = janela_da_carga(datetime(2026, 7, 3, 12, 0), hoje=date(2026, 9, 1))
    assert (inicio, fim) == (date(2026, 7, 3), date(2026, 7, 6))


def test_carga_sem_aprovacao_nao_tem_janela():
    with pytest.raises(ValueError, match="aprovada_em"):
        janela_da_carga(None, hoje=date(2026, 9, 1))


def test_aprovacao_com_fuso_e_normalizada_ao_local():
    """`aprovada_em` é timestamptz. Sem normalizar, a mesma carga daria janelas
    diferentes em máquinas de fusos diferentes."""
    from datetime import timedelta as _td
    from datetime import timezone as _tz

    # 2026-08-28 23:00 em UTC-3 é o MESMO instante que 2026-08-29 02:00 UTC.
    local = datetime(2026, 8, 28, 23, 0, tzinfo=_tz(_td(hours=-3)))
    utc = local.astimezone(UTC)
    assert utc.date() != local.date()  # o instante cruza a meia-noite em UTC
    # As duas representações do MESMO instante têm de dar a mesma janela.
    assert janela_da_carga(local, hoje=date(2026, 9, 5)) == janela_da_carga(
        utc, hoje=date(2026, 9, 5)
    )


def test_janela_nunca_inverte():
    """Carga aprovada num instante que, pelo relógio de `hoje`, já passou: a janela
    degenera para o próprio dia em vez de inverter (fim < inicio viraria aborto)."""
    inicio, fim = janela_da_carga(datetime(2026, 9, 2, 9, 0), hoje=date(2026, 9, 1))
    assert inicio == fim == date(2026, 9, 2)
    assert fim >= inicio
