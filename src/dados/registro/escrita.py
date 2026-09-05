"""Escrita da rodada de decisão no Registro (Spec §2, invariante 2).

Persiste, numa ÚNICA transação (falha parcial não deixa rodada meio-gravada), a
rodada + os perfis de conversão da semana + a decisão por imóvel (as 6.970
posições, com a nota bruta e os sinais que a compõem, os descontos, o perfil
que puxou e a regra cedida) + o relatório de relaxamento + os parâmetros. Grava
EXCLUSIVAMENTE no esquema `registro` do Postgres próprio — nenhum toque no
Newcore (invariante 1), nenhuma outra base (invariante 2).

Serializa o resultado pronto do domínio; não recomputa nada. As cotas (475/6.495)
e o invariante 7 (super nunca relaxa) são reforçados pelos CHECKs do próprio DDL
— uma segunda linha de defesa além do domínio.

Idempotência: cada chamada cria UMA rodada (uma execução). Como a `rodada.id` é
IDENTITY, não há chave natural para deduplicar duas execuções da mesma rodada
lógica — o chamador controla (grava uma vez por rodada). Registrado como ponto
para os portões/G2b, não resolvido inventando chave.

A NOTA é gravada como a D-028 a define (migração 010): `nota_bruta` em pontos de
100 — a mesma unidade de `nota_final` e dos descontos, para a conta fechar na
fonte da verdade — mais os três sinais do anúncio reescalados, `sinal_leads` e
`sinal_produtividade` (que só desempatam) e `casa_perfil` tri-estado, em que NULL
quer dizer "a regra do perfil não foi avaliada", não "não casou".

Cortes de escopo declarados da G2a (não silenciosos — CLAUDE.md exige apontar):
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

from collections.abc import Mapping, Sequence
from datetime import datetime

import psycopg
from psycopg.types.json import Json

from dominio.penalidades import Penalidade
from dominio.perfil import PerfilConversao
from piloto.decisao import DetalheImovel, ResultadoDecisao

# Colunas de decisao_imovel, na ordem do INSERT (migração 010).
_COLS_DECISAO = (
    "rodada_id, imovel_id, nivel, posicao_ranking, "
    "nota_bruta, sinal_nota_anuncio, sinal_cliques, sinal_visualizacoes, "
    "sinal_leads, sinal_produtividade, casa_perfil, "
    "pen_janela_anterior, pen_sem_avaliacao, pen_sem_lead_180d, "
    "nota_final, perfil_id, perfil_evidencia, regra_relaxada"
)


def _linha_decisao(
    rodada_id, imovel_id, nivel, posicao, nota_final, det, regra_relaxada, perfil_id=None
):
    """Uma tupla de decisao_imovel a partir do DetalheImovel (serializa, não recomputa).

    `nota_bruta` vai em PONTOS DE 100, como `nota_final` e os descontos: é o que
    permite refazer a conta lendo só o Registro. Os sinais vão como entraram na nota,
    reescalados em [0, 1]."""
    f = det.fatores
    p = det.descontos_por_penalidade
    evidencia = det.perfil_que_puxou.num_vendas if det.perfil_que_puxou is not None else None
    return (
        rodada_id,
        imovel_id,
        nivel,
        posicao,
        det.nota_bruta,
        f.nota_anuncio,
        f.cliques,
        f.visualizacoes,
        f.leads,
        f.produtividade_gestor,
        f.casa_perfil,  # tri-estado: None = a regra não foi avaliada (D-027)
        p.get(Penalidade.JANELA_SEM_RESULTADO, 0.0),
        p.get(Penalidade.SEM_AVALIACAO_POR_CATEGORIA, 0.0),
        p.get(Penalidade.SEM_LEAD_180D, 0.0),
        nota_final,
        perfil_id,
        evidencia,
        regra_relaxada,
    )


def _gravar_perfis(
    cur: psycopg.Cursor, rodada_id: int, perfis: Sequence[PerfilConversao]
) -> dict[PerfilConversao, int]:
    """Grava os perfis que o Analista achou na semana e devolve o id de cada um.

    TODOS os perfis, robustos e frágeis (Spec §2.1: "os padrões que o Analista
    encontrou naquela semana"), porque a classificação é parte do que se audita: sem
    os frágeis não dá para ver que a evidência era pouca. Ordem canônica preservada
    (invariante 5) — os perfis chegam ordenados do domínio e são inseridos assim."""
    por_perfil: dict[PerfilConversao, int] = {}
    for perfil in perfis:
        # 'fragil' sem acento: é o que o CHECK da 001 exige. A planilha mostra
        # 'frágil' — mesma classificação, grafias diferentes por contrato de cada lado.
        cur.execute(
            "INSERT INTO registro.perfil_da_rodada "
            "(rodada_id, dimensoes, valores, vendas_sustentam, classificacao) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (
                rodada_id,
                Json([d.value for d in perfil.dimensoes]),
                Json(list(perfil.valores)),
                perfil.num_vendas,
                "fragil" if perfil.fragil else "robusto",
            ),
        )
        por_perfil[perfil] = cur.fetchone()[0]
    if len(por_perfil) != len(perfis):
        # `ValorDimensao = str | int`, e `bool` é subtipo de `int`: `(1,)` e `(True,)`
        # são iguais e têm o mesmo hash em Python, mas `[1]` e `[true]` são jsonb
        # distintos. O banco gravaria dois perfis e o mapa teria um — o vínculo
        # apontaria para o errado, com o banco íntegro. Falha antes de acontecer.
        raise ValueError(
            f"{len(perfis)} perfis gravados colapsaram em {len(por_perfil)} chaves: "
            "dois perfis distintos com a mesma chave — o vínculo perfil_id seria ambíguo"
        )
    return por_perfil


def _linhas_decisao(
    rodada_id: int,
    resultado: ResultadoDecisao,
    perfil_id: Mapping[PerfilConversao, int] | None = None,
) -> list[tuple]:
    """Todas as linhas de decisao_imovel: super destaque, destaque de ranking e
    recuperados por relaxamento (posição continuando após o ranking), na mesma
    leitura da planilha (entrega.planilha_piloto)."""
    det: Mapping[int, DetalheImovel] = resultado.detalhes
    ids = perfil_id or {}

    def _do_perfil(imovel_id: int) -> int | None:
        """O id do perfil que puxou este imóvel. Nulo só por AUSÊNCIA REAL: o imóvel
        não casou perfil nenhum, ou a rodada não tem perfis.

        Se o imóvel casou um perfil que não está entre os gravados, é divergência
        entre o que o Analista produziu e o que a decisão consumiu — e a linha sairia
        afirmando "houve perfil com N vendas" (em `perfil_evidencia`) e "nenhum perfil
        desta rodada" (em `perfil_id`) ao mesmo tempo. Isso é exatamente a perda de
        prova que esta fatia existe para acabar, então falha fechado, dentro da
        transação, antes de qualquer INSERT."""
        puxou = det[imovel_id].perfil_que_puxou
        if puxou is None or not ids:
            return None
        pid = ids.get(puxou)
        if pid is None:
            raise ValueError(
                f"imóvel {imovel_id} casou um perfil que não está entre os gravados: "
                "os perfis do Analista divergem dos que a decisão consumiu"
            )
        return pid

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
                regra_relaxada=None,
                perfil_id=_do_perfil(pos.imovel_id),
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
                regra_relaxada=None,
                perfil_id=_do_perfil(pos.imovel_id),
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
                regra_relaxada=rec.degrau.value,
                perfil_id=_do_perfil(rec.imovel_id),
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
    perfis: Sequence[PerfilConversao] = (),
) -> int:
    """Grava a rodada de decisão inteira em UMA transação; devolve o `rodada.id`.

    `parametros` deve ser um dict serializável (o chamador extrai os provisórios,
    sem o callable de decaimento). `estado` ∈ {'completa','degradada','abortada'};
    `etapas` é o `prontos` por etapa. `perfis` são os do Analista naquela semana:
    gravados em `perfil_da_rodada` e ligados por `perfil_id` a cada imóvel que casou
    — sem eles a rodada ainda grava, e o vínculo fica nulo, declarado. Não commita: o
    chamador controla a transação (use `with conn.transaction(): ...` ou o context
    manager da conexão).
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

        por_perfil = _gravar_perfis(cur, rodada_id, perfis)

        linhas = _linhas_decisao(rodada_id, resultado, por_perfil)
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
