"""Relatório de acompanhamento da rodada de SEGUNDA — Spec §4.1.

Escreve as três abas como CSV num diretório. O entregável final é planilha do Google
(Ferramentas §3); o CSV é o formato desta fatia — a publicação no Drive é do Redator,
que é também quem terá modelo. Aqui não há modelo nenhum: as três abas são geradas
por TEMPLATE, o que a D-006 exige justamente porque duas delas têm linhas nominais.

A aba Resumo abre declarando o ESTADO da rodada e as limitações: a Spec §7.2 manda a
rodada degradada entregar "com a limitação declarada de forma visível na planilha" —
quem lê a planilha precisa saber que a rodada foi degradada e por quê, sem ter de ir
ao Registro.

DADO PESSOAL: a aba "Leads sem tratamento" carrega identidade (Spec §4.2 exige as
oito colunas). É o destino LEGÍTIMO dessa PII — planilha lida por gente. O invariante
3 proíbe o envio a modelo, não a escrita aqui; nenhuma linha deste módulo fala com
modelo.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from pathlib import Path

from dominio.acompanhamento import ResultadoAcompanhamento

# Ordem das colunas de cada aba (Spec §4.2 e §4.3).
COLUNAS_DESEMPENHO = (
    "imovel_id",
    "nivel",
    "leads_gerados",
    "leads_sem_tratamento",
    "semanas_consecutivas",
    "leads_acumulados_janela",
)
COLUNAS_LEADS = (
    "lead_id",
    "imovel_id",
    "nivel",
    "entrada",
    "tempo_desde_distribuicao",
    "corretor_gestor",
    "gestor_distrito",
    "distrito",
)
_CAMPOS_RESUMO = (
    "rodada_decisao_id",
    "inicio_periodo",
    "fim_periodo",
    "posicoes_super",
    "posicoes_destaque",
    "leads_gerados",
    "leads_sem_tratamento",
    "imoveis_sem_lead",
    "leads_fora_do_periodo",
    "leads_fora_da_carga",
    "sem_tratamento_sem_responsavel",
    "sem_tratamento_sem_distribuicao",
)


def _escrever(caminho: Path, cabecalho: Sequence[str], linhas: Sequence[Sequence[object]]) -> None:
    with caminho.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cabecalho)
        w.writerows(linhas)


def escrever_relatorio(
    resultado: ResultadoAcompanhamento,
    estado: str,
    degradacoes: Sequence[str],
    destino: Path,
) -> list[Path]:
    """Escreve as três abas em `destino` e devolve os caminhos, na ordem da §4.1.

    `estado` e `degradacoes` NÃO são decoração: entram no topo do resumo porque a
    §7.2 exige a limitação visível na planilha (ver cabeçalho do módulo).
    """
    destino.mkdir(parents=True, exist_ok=True)
    r = resultado.resumo

    # Aba 1 — Resumo: estado e limitações PRIMEIRO, depois os totais.
    linhas_resumo: list[Sequence[object]] = [("ESTADO DA RODADA", estado)]
    linhas_resumo += [(f"LIMITAÇÃO {i}", d) for i, d in enumerate(degradacoes, start=1)]
    if not degradacoes:
        linhas_resumo.append(("LIMITAÇÕES", "nenhuma"))
    linhas_resumo += [(campo, getattr(r, campo)) for campo in _CAMPOS_RESUMO]
    resumo = destino / "resumo.csv"
    _escrever(resumo, ("campo", "valor"), linhas_resumo)

    # Aba 2 — Leads sem tratamento (§4.2): as oito colunas, com identidade.
    leads = destino / "leads_sem_tratamento.csv"
    _escrever(
        leads,
        COLUNAS_LEADS,
        [tuple(getattr(x, c) for c in COLUNAS_LEADS) for x in resultado.leads_sem_tratamento],
    )

    # Aba 3 — Desempenho por imóvel (§4.3): TODAS as posições, inclusive zero lead.
    desempenho = destino / "desempenho_por_imovel.csv"
    _escrever(
        desempenho,
        COLUNAS_DESEMPENHO,
        [tuple(getattr(d, c) for c in COLUNAS_DESEMPENHO) for d in resultado.desempenho],
    )
    return [resumo, leads, desempenho]
