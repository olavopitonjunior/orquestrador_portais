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
from collections.abc import Mapping, Sequence
from pathlib import Path

from dominio.penalidades import JanelaCrua, Penalidade, eleger_ultima_janela, julgar_janelas
from dominio.perfil import PerfilConversao
from dominio.ranking import PesosNivel
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


# Os CINCO estados em que a última janela de um imóvel pode estar. Hoje os cinco
# saem como `0,0` na coluna de penalidade, indistinguíveis — e é isso que os dois
# critérios de aceite do PRD (§478 e §479) cobram: "o resultado da sua última
# janela, quando houver" e "imóveis sem janela anterior são identificados como tal".
#
# O quinto é o que mais engana e o que quase ficou de fora: histórico NÃO LIDO
# (Registro indisponível, rodada degradada — Spec §7.2) não é "sem janela anterior".
# Colapsar um no outro faria a planilha afirmar ausência de janela sobre um imóvel
# cujo histórico ninguém consultou.
NAO_CONSULTADO = "HISTÓRICO NÃO CONSULTADO — Registro indisponível nesta rodada"
SEM_JANELA = "sem janela anterior"
NAO_JULGADA = "NÃO JULGADA — limiar da §6.4 pendente (parâmetro nº 14)"


def descrever_ultima_janela(
    cruas: tuple[JanelaCrua, ...] | None,
    resultado_esperado: Mapping[str, int] | None,
) -> str:
    """Como a última janela do imóvel aparece na planilha, sem inventar veredito.

    `cruas` é o histórico do imóvel: `None` quer dizer que o histórico NÃO foi
    consultado (Registro fora, rodada degradada — Spec §7.2), e tupla vazia quer
    dizer consultado e sem janela. São estados diferentes, e colapsá-los afirmaria
    ausência de janela sobre imóvel cujo histórico ninguém leu.

    A eleição da janela e o veredito vêm do DOMÍNIO — `eleger_ultima_janela` e
    `julgar_janelas`, as mesmas que a penalidade usa. Nada é reescrito aqui: duas
    leituras do mesmo limiar podem divergir, e a divergência apareceria como a
    planilha contradizendo o desconto que ela própria mostra, na mesma linha.

    Sem limiar não há veredito, e a coluna diz isso em vez de omitir: "0 leads" sem
    rótulo lê como reprovação, e reprovar por conta própria é o que a D-022 proíbe ao
    manter o nº 14 nulo."""
    if cruas is None:
        return NAO_CONSULTADO
    crua = eleger_ultima_janela(cruas, resultado_esperado)
    if crua is None:
        return SEM_JANELA
    nivel, leads, ciclos = crua
    # `ciclos == 0` = nenhuma carga aprovada entrou no ar depois do encerramento —
    # NÃO "encerrada nesta rodada": quem fecha janela é a rodada de segunda, sobre a
    # carga anterior, e a sexta corrente não encerra nenhuma. O contrato de
    # `JanelaAnterior` chama isso de "encerrada no ciclo corrente".
    quando = "no ciclo corrente" if ciclos == 0 else f"há {ciclos} ciclo(s)"
    fato = f"{nivel.replace('_', ' ')} · {leads} lead(s) · encerrada {quando}"
    if resultado_esperado is None:
        return f"{fato} — {NAO_JULGADA}"
    # Levanta ValueError para nível fora do limiar — aqui isso aconteceria DEPOIS de
    # a rodada estar gravada, virando SinkFalhou (rodada sem artefato). Hoje é
    # inalcançável porque o grafo julga as mesmas cruas antes e estoura primeiro, com
    # o MESMO objeto de limiar; se um dia forem dois, este vira o ponto frágil.
    julgada = julgar_janelas([crua], resultado_esperado)[0]
    veredito = "atingiu" if julgada.atingiu_resultado else "NÃO atingiu"
    return f"{fato} — {veredito} o resultado esperado para o nível"


def _colunas_justificativa(
    det: DetalheImovel,
    historico: Mapping[int, tuple[JanelaCrua, ...]] | None,
    resultado_esperado: Mapping[str, int] | None,
) -> dict[str, object]:
    """As colunas de justificativa comuns aos dois níveis (Spec §2.1/§3.2):
    os QUATRO fatores (D-017), cada penalidade, o desconto total e o perfil que
    puxou com sua evidência. Tudo lido do DetalheImovel — nada recalculado."""
    colunas: dict[str, object] = {
        "semelhanca_perfil": det.fatores.semelhanca_perfil,
        "leads": det.fatores.leads,
        "desempenho_proprio": det.fatores.desempenho_proprio,
        "produtividade_gestor": det.fatores.produtividade_gestor,
    }
    for pen in _PENALIDADES_COLUNAS:
        colunas[f"pen_{pen.value}"] = det.descontos_por_penalidade.get(pen, 0.0)
    colunas["desconto_total"] = det.desconto_total
    # Critérios de aceite do PRD: "o resultado da sua última janela, quando houver" e
    # "imóveis sem janela anterior são identificados como tal". A coluna de desconto
    # acima NÃO responde isso — ela sai 0,0 em cinco situações diferentes.
    colunas["ultima_janela"] = descrever_ultima_janela(
        None if historico is None else historico.get(det.imovel_id, ()),
        resultado_esperado,
    )
    colunas["perfil_que_puxou"] = _perfil_texto(det.perfil_que_puxou)
    colunas["perfil_num_vendas"] = (
        det.perfil_que_puxou.num_vendas if det.perfil_que_puxou is not None else ""
    )
    colunas["perfil_fragil"] = (
        det.perfil_que_puxou.fragil if det.perfil_que_puxou is not None else ""
    )
    return colunas


def linhas_super_destaque(
    resultado: ResultadoDecisao,
    historico: Mapping[int, tuple[JanelaCrua, ...]] | None,
    resultado_esperado: Mapping[str, int] | None,
) -> list[dict[str, object]]:
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
            | _colunas_justificativa(det, historico, resultado_esperado)
            | {"origem": "ranking", "degrau_cedido": ""}
        )
    return linhas


def linhas_destaque(
    resultado: ResultadoDecisao,
    historico: Mapping[int, tuple[JanelaCrua, ...]] | None,
    resultado_esperado: Mapping[str, int] | None,
) -> list[dict[str, object]]:
    """As posições de destaque: primeiro o ranking, depois os recuperados por
    relaxamento (posições continuando), com o degrau que cedeu para cada."""
    linhas = []
    for pos in resultado.alocacao.destaque:
        det = resultado.detalhes[pos.imovel_id]
        linhas.append(
            {"posicao": pos.posicao, "imovel_id": pos.imovel_id, "nota": pos.nota}
            | _colunas_justificativa(det, historico, resultado_esperado)
            | {"origem": "ranking", "degrau_cedido": ""}
        )
    # Recuperados continuam a numeração de posição após o ranking.
    proxima = len(resultado.alocacao.destaque)
    for rec in resultado.relaxamento.recuperados:
        proxima += 1
        det = resultado.detalhes[rec.imovel_id]
        linhas.append(
            {"posicao": proxima, "imovel_id": rec.imovel_id, "nota": rec.nota_destaque}
            | _colunas_justificativa(det, historico, resultado_esperado)
            | {"origem": "relaxamento", "degrau_cedido": rec.degrau.value}
        )
    return linhas


def linhas_excluidos_por_regra(
    resultado: ResultadoDecisao,
    historico: Mapping[int, tuple[JanelaCrua, ...]] | None,
    resultado_esperado: Mapping[str, int] | None,
) -> list[dict[str, object]]:
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


def linhas_relaxamento(
    resultado: ResultadoDecisao,
    historico: Mapping[int, tuple[JanelaCrua, ...]] | None,
    resultado_esperado: Mapping[str, int] | None,
) -> list[dict[str, object]]:
    """O relatório de relaxamento da Spec §6.6, na ordem de cedência.

    Existe porque a §6.6 é literal: "Cada cedência gera linha no relatório de
    relaxamento com a quantidade de posições que dependeram dela. **Sem esse
    registro a etapa de decisão não é considerada pronta**". A §3.1 lista a aba
    como obrigatória e o PRD repete que o relatório é *na planilha*. O Registro já
    guardava o agregado por regra; ele só não chegava ao artefato que as pessoas
    leem — e a rodada saía COMPLETA assim mesmo.

    A coluna `degrau_cedido` por imóvel, que já existia na aba de destaque, não
    substitui isto: falta nela o agregado por regra e as posições ainda vazias.

    A última linha é o DÉFICIT — as posições que os cinco graus não cobriram. É
    grandeza da rodada, não de uma cedência, e vem declarada mesmo quando é zero:
    ausência de linha seria indistinguível de "ninguém calculou".
    """
    linhas: list[dict[str, object]] = [
        {
            "ordem": i,
            "regra_cedida": linha.regra.value,
            "posicoes_dependentes": linha.posicoes_dependentes,
        }
        for i, linha in enumerate(resultado.relaxamento.relatorio, 1)
    ]
    linhas.append(
        {
            "ordem": "",
            "regra_cedida": "POSIÇÕES AINDA VAZIAS (nenhum grau cobriu)",
            "posicoes_dependentes": resultado.relaxamento.deficit_restante,
        }
    )
    return linhas


def _texto_pesos(pesos: PesosNivel) -> str:
    """Os quatro pesos do nível como texto, na ordem semelhança/leads/desempenho/
    produtividade (mesma ordem do rótulo da linha)."""
    return (
        f"{pesos.semelhanca_perfil}/{pesos.leads_positivo}/"
        f"{pesos.desempenho_proprio}/{pesos.produtividade_gestor}"
    )


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
        {
            "tipo": "PROVISÓRIO",
            "item": "decaimento do peso por dimensão do F1 (parâmetro nº 13)",
            "valor": parametros.semelhanca.decaimento,
        },
        {
            "tipo": "PROVISÓRIO",
            "item": ("pesos super destaque (nº 12) — semelhança/leads/desempenho/produtividade"),
            "valor": _texto_pesos(parametros.pesos_super),
        },
        {
            "tipo": "PROVISÓRIO",
            "item": ("pesos destaque (nº 12) — semelhança/leads/desempenho/produtividade"),
            "valor": _texto_pesos(parametros.pesos_destaque),
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
    "relaxamento": linhas_relaxamento,  # Spec §3.1/§6.6: obrigatória
}


def escrever_planilha(
    resultado: ResultadoDecisao,
    parametros: ParametrosDecisao,
    destino: Path,
    *,
    historico_janelas: Mapping[int, tuple[JanelaCrua, ...]] | None,
    resultado_esperado: Mapping[str, int] | None,
    notas_coleta: Sequence[str] = (),
) -> list[Path]:
    """Escreve os cinco CSVs em `destino` e devolve os caminhos gerados.

    I/O de ARQUIVO LOCAL (entregável, não estado — invariante 2 é sobre o
    Registro, preservado). Vai para `saida/piloto/` (ignorada pelo .gitignore):
    dado de rodada, nunca commitado. `notas_coleta` são limitações da coleta
    (ex.: vendas descartadas) declaradas na aba de parâmetros.

    `historico_janelas` é o histórico CRU de janelas por imóvel, do Registro. `None` tem
    significado próprio e não é "vazio": quer dizer que o histórico NÃO foi
    consultado (rodada degradada), que é diferente de consultar e não achar nada. A
    coluna por imóvel distingue os dois — colapsá-los afirmaria ausência de janela
    sobre imóvel cujo histórico ninguém leu.
    """
    destino.mkdir(parents=True, exist_ok=True)
    escritos: list[Path] = []

    for nome, construtor in _ABAS.items():
        escritos.append(
            _escrever_csv(
                destino / f"{nome}.csv",
                construtor(resultado, historico_janelas, resultado_esperado),
            )
        )
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
