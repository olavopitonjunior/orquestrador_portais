"""Serialização da planilha-piloto: o ResultadoDecisao vira quatro CSVs.

SERIALIZA, não recomputa (condição do orchestrator): lê o ResultadoDecisao /
DetalheImovel / ResultadoRelaxamento produzidos pela costura e escreve — nota,
fator, penalidade, perfil e degrau de relaxamento já são autoritativos, nunca
recalculados aqui. Se algo fosse recalculado, a planilha justificaria um
recálculo parecido, não a decisão real.

Quatro abas (um CSV cada, mapeando 1:1 no Google Sheets do B4):
  1. super_destaque   — as posições de super destaque, com a justificativa.
  2. destaque         — as posições de destaque (ranking + recuperados por
                        relaxamento, com o degrau que cedeu).
  3. excluidos_por_regra — reprovados não recuperados, com as regras reprovadas.
  4. parametros_e_limitacoes — os provisórios (rotulados PROVISÓRIO) e as
                        limitações declaradas da rodada.

Privacidade (invariante 3): só imóvel, posição, notas e perfil — NUNCA corretor,
comprador ou lead. A saída vai para `saida/piloto/` (ignorada pelo .gitignore):
é dado de rodada, não código; nenhum CSV de saída é commitado.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from pathlib import Path

from dominio.penalidades import Penalidade
from dominio.perfil import PerfilConversao
from piloto.decisao import DetalheImovel, ParametrosDecisao, ResultadoDecisao

# As três penalidades, em ordem fixa de coluna (Spec §3.2, grupo Penalidades).
_PENALIDADES_COLUNAS = (
    Penalidade.JANELA_SEM_RESULTADO,
    Penalidade.SEM_AVALIACAO_POR_CATEGORIA,
    Penalidade.SEM_LEAD_180D,
)


def _perfil_texto(perfil: PerfilConversao | None) -> str:
    """O perfil que puxou como texto legível (identificador), ou vazio."""
    if perfil is None:
        return ""
    return "; ".join(
        f"{dim.value}={valor}" for dim, valor in zip(perfil.dimensoes, perfil.valores, strict=True)
    )


def _colunas_justificativa(det: DetalheImovel) -> dict[str, object]:
    """As colunas de justificativa comuns aos dois níveis (Spec §2.1/§3.2):
    os três fatores, cada penalidade, o desconto total e o perfil que puxou
    com sua evidência. Tudo lido do DetalheImovel — nada recalculado."""
    colunas: dict[str, object] = {
        "semelhanca_perfil": det.fatores.semelhanca_perfil,
        "desempenho_proprio": det.fatores.desempenho_proprio,
        "produtividade_gestor": det.fatores.produtividade_gestor,
    }
    for pen in _PENALIDADES_COLUNAS:
        colunas[f"pen_{pen.value}"] = det.descontos_por_penalidade.get(pen, 0.0)
    colunas["desconto_total"] = det.desconto_total
    colunas["perfil_que_puxou"] = _perfil_texto(det.perfil_que_puxou)
    colunas["perfil_num_vendas"] = (
        det.perfil_que_puxou.num_vendas if det.perfil_que_puxou is not None else ""
    )
    colunas["perfil_fragil"] = (
        det.perfil_que_puxou.fragil if det.perfil_que_puxou is not None else ""
    )
    return colunas


def linhas_super_destaque(resultado: ResultadoDecisao) -> list[dict[str, object]]:
    """Uma linha por posição de super destaque, com a justificativa.

    Carrega `origem`/`degrau_cedido` iguais à aba de destaque (Spec §3.2:
    "colunas iguais nos dois níveis") — no super são sempre "ranking"/vazio,
    porque o super destaque nunca relaxa (invariante 7).
    """
    linhas = []
    for pos in resultado.alocacao.super_destaque:
        det = resultado.detalhes[pos.imovel_id]
        linhas.append(
            {"posicao": pos.posicao, "imovel_id": pos.imovel_id, "nota": pos.nota}
            | _colunas_justificativa(det)
            | {"origem": "ranking", "degrau_cedido": ""}
        )
    return linhas


def linhas_destaque(resultado: ResultadoDecisao) -> list[dict[str, object]]:
    """As posições de destaque: primeiro o ranking, depois os recuperados por
    relaxamento (posições continuando), com o degrau que cedeu para cada."""
    linhas = []
    for pos in resultado.alocacao.destaque:
        det = resultado.detalhes[pos.imovel_id]
        linhas.append(
            {"posicao": pos.posicao, "imovel_id": pos.imovel_id, "nota": pos.nota}
            | _colunas_justificativa(det)
            | {"origem": "ranking", "degrau_cedido": ""}
        )
    # Recuperados continuam a numeração de posição após o ranking.
    proxima = len(resultado.alocacao.destaque)
    for rec in resultado.relaxamento.recuperados:
        proxima += 1
        det = resultado.detalhes[rec.imovel_id]
        linhas.append(
            {"posicao": proxima, "imovel_id": rec.imovel_id, "nota": rec.nota_destaque}
            | _colunas_justificativa(det)
            | {"origem": "relaxamento", "degrau_cedido": rec.degrau.value}
        )
    return linhas


def linhas_excluidos_por_regra(resultado: ResultadoDecisao) -> list[dict[str, object]]:
    """Reprovados que NÃO foram recuperados pelo relaxamento, com as regras que
    reprovaram (por que ficaram de fora). Ordenado por imovel_id (determinístico)."""
    recuperados = {rec.imovel_id for rec in resultado.relaxamento.recuperados}
    linhas = []
    for imovel_id in sorted(resultado.reprovados_regras):
        if imovel_id in recuperados:
            continue
        regras = resultado.reprovados_regras[imovel_id]
        linhas.append(
            {
                "imovel_id": imovel_id,
                "regras_reprovadas": "; ".join(sorted(r.value for r in regras)),
            }
        )
    return linhas


def linhas_parametros_e_limitacoes(
    resultado: ResultadoDecisao,
    parametros: ParametrosDecisao,
    notas_coleta: Sequence[str] = (),
) -> list[dict[str, object]]:
    """Os provisórios da rodada (rotulados PROVISÓRIO) e as limitações declaradas.

    O que faz o dono ler a piloto como TESTE DE CRITÉRIO, não lista final.
    `notas_coleta` são limitações vindas da COLETA (ex.: vendas descartadas por
    Realty_Id nulo) — contadas na rodada, declaradas aqui, nunca silenciosas.
    """
    linhas: list[dict[str, object]] = [
        {
            "tipo": "PROVISÓRIO",
            "item": "penalidade: janela sem resultado",
            "valor": parametros.intensidades.janela_sem_resultado,
        },
        {
            "tipo": "PROVISÓRIO",
            "item": "penalidade: sem avaliação por categoria",
            "valor": parametros.intensidades.sem_avaliacao_por_categoria,
        },
        {
            "tipo": "PROVISÓRIO",
            "item": "penalidade: sem lead em 180d",
            "valor": parametros.intensidades.sem_lead_180d,
        },
        {
            "tipo": "PROVISÓRIO",
            "item": "desconto de perfil frágil",
            "valor": parametros.semelhanca.desconto_fragil,
        },
    ]
    for limitacao in resultado.degradacoes:
        linhas.append({"tipo": "LIMITAÇÃO", "item": limitacao, "valor": ""})
    for nota in notas_coleta:
        linhas.append({"tipo": "LIMITAÇÃO", "item": nota, "valor": ""})
    linhas.append(
        {
            "tipo": "NOTA",
            "item": (
                "a piloto traz só as colunas de composição/justificativa da decisão; "
                "as descritivas e de portal (título, link, endereço, nota do portal, "
                "visualizações) vêm dos coletores/Redator no entregável final"
            ),
            "valor": "",
        }
    )
    return linhas


_ABAS = {
    "super_destaque": linhas_super_destaque,
    "destaque": linhas_destaque,
    "excluidos_por_regra": linhas_excluidos_por_regra,
}


def escrever_planilha(
    resultado: ResultadoDecisao,
    parametros: ParametrosDecisao,
    destino: Path,
    notas_coleta: Sequence[str] = (),
) -> list[Path]:
    """Escreve os quatro CSVs em `destino` e devolve os caminhos gerados.

    I/O de ARQUIVO LOCAL (entregável, não estado — invariante 2 é sobre o
    Registro, preservado). Vai para `saida/piloto/` (ignorada pelo .gitignore):
    dado de rodada, nunca commitado. `notas_coleta` são limitações da coleta
    (ex.: vendas descartadas) declaradas na aba de parâmetros.
    """
    destino.mkdir(parents=True, exist_ok=True)
    escritos: list[Path] = []

    for nome, construtor in _ABAS.items():
        escritos.append(_escrever_csv(destino / f"{nome}.csv", construtor(resultado)))
    escritos.append(
        _escrever_csv(
            destino / "parametros_e_limitacoes.csv",
            linhas_parametros_e_limitacoes(resultado, parametros, notas_coleta),
        )
    )
    return escritos


def _escrever_csv(caminho: Path, linhas: list[dict[str, object]]) -> Path:
    """Escreve as linhas (lista de dicts) num CSV; cabeçalho das chaves da 1ª.

    Lista vazia gera um CSV só com uma nota — a aba existe mesmo sem linhas
    (ex.: nenhum excluído), para o leitor saber que a etapa rodou.
    """
    with caminho.open("w", newline="", encoding="utf-8") as f:
        if not linhas:
            f.write("(sem linhas nesta rodada)\n")
            return caminho
        escritor = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        escritor.writeheader()
        escritor.writerows(linhas)
    return caminho
