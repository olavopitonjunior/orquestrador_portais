"""Escrita da rodada de decisão no Registro (Spec §2, invariante 2).

Persiste, numa ÚNICA transação (falha parcial não deixa rodada meio-gravada), a
rodada + a decisão por imóvel (as 6.970 posições, com notas dos quatro fatores
D-017, penalidades e a regra relaxada) + o relatório de relaxamento + os
parâmetros. Grava EXCLUSIVAMENTE no esquema `registro` do Postgres próprio —
nenhum toque no Newcore (invariante 1), nenhuma outra base (invariante 2).

Serializa o resultado pronto do domínio; não recomputa nada. As cotas (475/6.495)
e o invariante 7 (super nunca relaxa) são reforçados pelos CHECKs do próprio DDL
— uma segunda linha de defesa além do domínio.

Idempotência: cada chamada cria UMA rodada (uma execução). Como a `rodada.id` é
IDENTITY, não há chave natural para deduplicar duas execuções da mesma rodada
lógica — o chamador controla (grava uma vez por rodada). Registrado como ponto
para os portões/G2b, não resolvido inventando chave.

Cortes de escopo declarados da G2a (não silenciosos — CLAUDE.md exige apontar):
- **`perfil_id` fica NULL e `perfil_da_rodada` não é escrita.** O "perfil que
  casou" (Spec §2.1) persiste só como `perfil_evidencia` (a contagem de vendas),
  sem o identificador/dimensões. Escrever `perfil_da_rodada` e ligar `perfil_id`
  é fatia própria (com o Analista de produção).
- **`posicoes_vazias` por regra fica 0.** O domínio não computa vaga por regra
  cedida; o TOTAL de posições vazias vai para `rodada.posicoes_vazias_destaque`
  (`ResultadoRelaxamento.deficit_restante`, Spec §2.1). O per-regra 0 é
  placeholder até haver a decomposição.
- **`tentativas_por_etapa` fica '{}'** — só ganha valor com o retry do
  Orquestrador (parâmetro nº 4, nulo).
- **Sem controle de versão de schema** (tabela de migrations / aplicador em
  ordem): as `NNN_*.sql` são aplicadas à mão hoje; pendência para antes da G2b.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

import psycopg
from psycopg.types.json import Json

from dominio.penalidades import Penalidade
from piloto.decisao import DetalheImovel, ResultadoDecisao

# Colunas de decisao_imovel, na ordem do INSERT.
_COLS_DECISAO = (
    "rodada_id, imovel_id, nivel, posicao_ranking, "
    "nota_perfil, nota_leads, nota_desempenho, nota_gestor, "
    "pen_janela_anterior, pen_sem_avaliacao, pen_sem_lead_180d, "
    "nota_final, perfil_evidencia, regra_relaxada"
)


def _linha_decisao(rodada_id, imovel_id, nivel, posicao, nota_final, det, regra_relaxada):
    """Uma tupla de decisao_imovel a partir do DetalheImovel (serializa, não recomputa)."""
    f = det.fatores
    p = det.descontos_por_penalidade
    evidencia = det.perfil_que_puxou.num_vendas if det.perfil_que_puxou is not None else None
    return (
        rodada_id,
        imovel_id,
        nivel,
        posicao,
        f.semelhanca_perfil,
        f.leads,
        f.desempenho_proprio,
        f.produtividade_gestor,
        p.get(Penalidade.JANELA_SEM_RESULTADO, 0.0),
        p.get(Penalidade.SEM_AVALIACAO_POR_CATEGORIA, 0.0),
        p.get(Penalidade.SEM_LEAD_180D, 0.0),
        nota_final,
        evidencia,
        regra_relaxada,
    )


def _linhas_decisao(rodada_id: int, resultado: ResultadoDecisao) -> list[tuple]:
    """Todas as linhas de decisao_imovel: super destaque, destaque de ranking e
    recuperados por relaxamento (posição continuando após o ranking), na mesma
    leitura da planilha (entrega.planilha_piloto)."""
    det: Mapping[int, DetalheImovel] = resultado.detalhes
    linhas: list[tuple] = []
    for pos in resultado.alocacao.super_destaque:
        linhas.append(
            _linha_decisao(
                rodada_id,
                pos.imovel_id,
                "super_destaque",
                pos.posicao,
                pos.nota,
                det[pos.imovel_id],
                None,
            )
        )
    for pos in resultado.alocacao.destaque:
        linhas.append(
            _linha_decisao(
                rodada_id,
                pos.imovel_id,
                "destaque",
                pos.posicao,
                pos.nota,
                det[pos.imovel_id],
                None,
            )
        )
    proxima = len(resultado.alocacao.destaque)
    for rec in resultado.relaxamento.recuperados:
        proxima += 1
        linhas.append(
            _linha_decisao(
                rodada_id,
                rec.imovel_id,
                "destaque",
                proxima,
                rec.nota_destaque,
                det[rec.imovel_id],
                rec.degrau.value,
            )
        )
    return linhas


def gravar_rodada_decisao(
    conn: psycopg.Connection,
    *,
    resultado: ResultadoDecisao,
    estado: str,
    etapas: Mapping[str, bool],
    parametros: Mapping[str, object],
    inicio: datetime,
    fim: datetime,
    motivo_degradacao: str | None = None,
) -> int:
    """Grava a rodada de decisão inteira em UMA transação; devolve o `rodada.id`.

    `parametros` deve ser um dict serializável (o chamador extrai os provisórios,
    sem o callable de decaimento). `estado` ∈ {'completa','degradada','abortada'};
    `etapas` é o `prontos` por etapa. Não commita: o chamador controla a transação
    (use `with conn.transaction(): ...` ou o context manager da conexão).
    """
    if conn.autocommit:
        raise ValueError(
            "conexão em autocommit: a atomicidade da rodada exige autocommit=False "
            "(rodada + decisões + relaxamento num único commit)"
        )
    n_cols = len(_COLS_DECISAO.split(","))
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO registro.rodada "
            "(tipo, inicio, fim, estado, etapas, motivo_degradacao, posicoes_vazias_destaque) "
            "VALUES ('decisao', %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                inicio,
                fim,
                estado,
                Json(dict(etapas)),
                motivo_degradacao,
                resultado.relaxamento.deficit_restante,  # Spec §2.1: posições ainda vazias
            ),
        )
        rodada_id = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO registro.parametros_da_rodada (rodada_id, parametros) VALUES (%s, %s)",
            (rodada_id, Json(dict(parametros))),
        )

        linhas = _linhas_decisao(rodada_id, resultado)
        if linhas:
            cur.executemany(
                f"INSERT INTO registro.decisao_imovel ({_COLS_DECISAO}) "
                f"VALUES ({', '.join(['%s'] * n_cols)})",
                linhas,
            )

        relaxos = [
            (rodada_id, ln.regra.value, ln.posicoes_dependentes, 0)
            for ln in resultado.relaxamento.relatorio
        ]
        if relaxos:
            cur.executemany(
                "INSERT INTO registro.relaxamento "
                "(rodada_id, regra_cedida, posicoes_dependentes, posicoes_vazias) "
                "VALUES (%s, %s, %s, %s)",
                relaxos,
            )
    return rodada_id
