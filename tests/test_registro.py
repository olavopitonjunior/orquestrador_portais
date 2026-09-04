"""Testes de integração do Registro (escrita/leitura no Postgres próprio).

I/O real: rodam contra o Postgres local e são PULADOS onde não há banco (CI),
como os demais testes de I/O do projeto. Cada teste roda numa transação que é
revertida no fim — nada persiste. Cobre o round-trip (grava → lê), a contagem
por nível (cotas) e a atomicidade/reforço de invariante pelo DDL.
"""

from dataclasses import replace
from datetime import date, datetime

import pytest

from dados.registro.conexao import conectar
from dados.registro.escrita import gravar_rodada_decisao
from dados.registro.leitura import contagem_por_nivel, ler_rodada, marcar_aprovada
from dominio.alocacao import Alocacao, PosicaoAlocada
from dominio.penalidades import IntensidadesPenalidade
from dominio.perfil import Dimensao, ImovelVendido, perfis_de_conversao
from dominio.ranking import PesosPortal
from piloto.decisao import ParametrosDecisao, decidir

HOJE = date(2026, 9, 1)

PARAMS = ParametrosDecisao(
    pesos_portal=PesosPortal(nota_anuncio=70, cliques=30, visualizacoes=0),
    sem_anuncio="fim_da_fila",
    ordem_sem_portal="leads_180d",
    intensidades=IntensidadesPenalidade(
        janela_sem_resultado=20.0, sem_avaliacao_por_categoria=5.0, sem_lead_180d=10.0
    ),
    decaimento_janela=lambda _c: 1.0,
    minimo_corretores_distrito=2,
    exigir_dimensao_no_perfil=None,  # o perfil de região do fixture conta
)

# O que o runner grava: o efetivo (adotados + declarados) e a procedência por chave.
PARAMS_SERIAL = {
    "efetivo": {
        "portal.peso_nota": 70,
        "portal.peso_cliques": 30,
        "desconto.perdao_por_semana": 50,
    },
    "procedencia": {
        "portal.peso_nota": "adotado D-034",
        "portal.peso_cliques": "adotado D-034",
        "desconto.perdao_por_semana": "adotado D-034",
    },
    "origem": "adotados (D-034)",
}


@pytest.fixture
def conn():
    try:
        c = conectar()
    except Exception as e:  # POSTGRES_URL ausente ou banco fora → pula (CI)
        pytest.skip(f"Postgres próprio indisponível: {e}")
    c.autocommit = False
    yield c
    c.rollback()  # nada persiste entre testes
    c.close()


def _candidato(imovel_id):
    from dominio.elegibilidade import ImovelCandidato

    return ImovelCandidato(
        imovel_id=imovel_id,
        publicacao_ativa=True,
        categoria="Apartamento",
        preco=850_000,
        qtd_fotos=20,
        atualizado_em=date(2026, 8, 20),
        notas_por_categoria={"Descrição do imóvel": 10},
        gestor_captou_ou_vendeu_30d=True,
        produtividade_gestor_30d=3,
        corretores_ativos_no_distrito=5,
    )


def _reprovado(imovel_id):
    """Reprovado recuperável: falha só em FOTOS (relaxável), preço de destaque."""
    from dominio.elegibilidade import ImovelCandidato

    return ImovelCandidato(
        imovel_id=imovel_id,
        publicacao_ativa=True,
        categoria="Apartamento",
        preco=400_000,
        qtd_fotos=3,  # < 10 → reprova em FOTOS (relaxável)
        atualizado_em=date(2026, 8, 20),
        notas_por_categoria={"Descrição do imóvel": 10},
        gestor_captou_ou_vendeu_30d=True,
        produtividade_gestor_30d=3,
        corretores_ativos_no_distrito=5,
    )


def _penalizavel(imovel_id):
    from dominio.penalidades import ImovelPenalizavel

    return ImovelPenalizavel(
        imovel_id=imovel_id, janelas_anteriores=(), alguma_categoria_avaliada=True, leads_180d=7
    )


def _resultado(cands):
    pen = {c.imovel_id: _penalizavel(c.imovel_id) for c in cands}
    dims = {c.imovel_id: {Dimensao.REGIAO: "Centro"} for c in cands}
    perfis = perfis_de_conversao(
        [
            ImovelVendido(
                imovel_id=900 + k,
                regiao="Centro",
                faixa_preco=None,
                faixa_metragem=None,
                dormitorios=None,
                vagas=None,
            )
            for k in range(3)
        ]
    )
    return decidir(cands, pen, dims, perfis, PARAMS, HOJE)


# DEFEITO no código congelado: o DDL do Registro não conhece a nona regra.
# `src/dados/registro/001_registro.sql:68-70` (decisao_imovel.regra_relaxada) e `:86-88`
# (relaxamento.regra_cedida) restringem a lista às CINCO regras anteriores à D-027, e nenhuma
# migração posterior (002–007) acrescenta `perfil_de_conversao`. Como `relaxar` grava uma
# linha por degrau cedido — inclusive com zero, e desce os seis degraus sempre que há déficit
# de destaque —, TODA rodada com déficit escreve `('perfil_de_conversao', 0, 0)` em
# `registro.relaxamento` e o Postgres recusa (CheckViolation) — em produção, `SinkFalhou`
# e rodada sem Registro. Recuperado por esse degrau, `regra_relaxada` cai no mesmo CHECK.
DDL_SEM_PERFIL = (
    "src/dados/registro/001_registro.sql:68-70 e :86-88 — os CHECKs de regra_relaxada/"
    "regra_cedida não incluem 'perfil_de_conversao' (D-027); falta migração 008"
)


def _gravar(conn, resultado, estado="degradada"):
    return gravar_rodada_decisao(
        conn,
        resultado=resultado,
        estado=estado,
        etapas={"coletor_interno": True, "decisor": True, "crivo": True, "externo": False},
        parametros=PARAMS_SERIAL,
        inicio=datetime(2026, 9, 1, 17, 0),
        fim=datetime(2026, 9, 1, 17, 5),
        motivo_degradacao="sem raspagem",
    )


def test_round_trip_grava_e_le(conn):
    resultado = _resultado([_candidato(1), _candidato(2)])
    rodada_id = _gravar(conn, resultado)
    resumo = ler_rodada(conn, rodada_id)
    assert resumo["tipo"] == "decisao"
    assert resumo["estado"] == "degradada"
    assert resumo["etapas"]["crivo"] is True
    assert resumo["aprovada_em"] is None
    # dois elegíveis ≥700k → dois super destaque; destaque vazio → déficit total 6495
    assert contagem_por_nivel(conn, rodada_id) == {"super_destaque": 2}
    assert resumo["posicoes_vazias_destaque"] == 6495  # Spec §2.1: não perde o déficit


def test_decisao_persiste_as_notas_com_os_valores_da_costura(conn):
    """As colunas ainda têm os nomes da geração anterior (F1..F4); o que entra nelas
    é o que existe hoje: casou o perfil (1/0), leads normalizado, a nota BRUTA do
    portal em 0–1 (`nota_bruta / 100`) e a produtividade normalizada."""
    resultado = _resultado([_candidato(1)])
    rodada_id = _gravar(conn, resultado)
    det = resultado.detalhes[1]
    with conn.cursor() as cur:
        cur.execute(
            "SELECT nota_perfil, nota_leads, nota_desempenho, nota_gestor, nota_final "
            "FROM registro.decisao_imovel WHERE rodada_id = %s",
            (rodada_id,),
        )
        linha = cur.fetchone()
    assert linha is not None
    assert len(linha) == 5
    nota_perfil, nota_leads, nota_desempenho, nota_gestor, nota_final = (float(v) for v in linha)
    assert nota_perfil == (1.0 if det.fatores.casa_perfil else 0.0) == 1.0
    assert nota_leads == det.fatores.leads
    assert nota_desempenho == det.nota_bruta / 100.0
    assert nota_gestor == det.fatores.produtividade_gestor
    assert nota_final == det.nota_super_destaque


def test_marcar_aprovada(conn):
    rodada_id = _gravar(conn, _resultado([_candidato(1)]))
    quando = datetime(2026, 9, 1, 20, 0)
    marcar_aprovada(conn, rodada_id, quando)
    # aprovada_em é timestamptz → volta tz-aware; compara o relógio de parede.
    gravado = ler_rodada(conn, rodada_id)["aprovada_em"]
    assert gravado is not None
    assert gravado.replace(tzinfo=None) == quando


def test_cota_excedida_e_rejeitada_pelo_ddl(conn):
    # O DDL impõe as cotas (CHECK posicao_dentro_da_cota): posição 476 no super
    # (limite 475) é rejeitada pelo banco — reforço do invariante 6 além do
    # domínio. A transação única não deixa rodada meio-gravada.
    import psycopg

    resultado = _resultado([_candidato(1)])  # imóvel 1 tem detalhe
    ruim = replace(
        resultado,
        alocacao=Alocacao(
            super_destaque=(PosicaoAlocada(posicao=476, imovel_id=1, nota=1.0),),
            destaque=(),
        ),
    )
    with pytest.raises(psycopg.errors.CheckViolation):
        _gravar(conn, ruim)
    conn.rollback()  # limpa o estado abortado da transação


def test_relaxamento_persiste_regra_e_deficit(conn):
    # 1 elegível (super) + 1 reprovado recuperável (fotos) → relaxamento preenche
    # 1 posição de destaque por cedência; o resto do destaque fica vazio.
    resultado = _resultado([_candidato(1), _reprovado(2)])
    assert len(resultado.relaxamento.recuperados) == 1  # o reprovado foi recuperado
    rodada_id = _gravar(conn, resultado)

    assert contagem_por_nivel(conn, rodada_id) == {"super_destaque": 1, "destaque": 1}
    with conn.cursor() as cur:
        # a posição de destaque carrega a regra que cedeu (fotos)
        cur.execute(
            "SELECT regra_relaxada FROM registro.decisao_imovel "
            "WHERE rodada_id = %s AND nivel = 'destaque'",
            (rodada_id,),
        )
        assert cur.fetchone()[0] == "fotos"
        # a tabela relaxamento tem UMA linha por degrau alcançado: com déficit que os
        # seis degraus não cobrem, todos são cedidos — só fotos recuperou alguém
        cur.execute(
            "SELECT regra_cedida, posicoes_dependentes FROM registro.relaxamento "
            "WHERE rodada_id = %s",
            (rodada_id,),
        )
        por_regra = dict(cur.fetchall())
        assert len(por_regra) == 6 and "perfil_de_conversao" in por_regra
        assert por_regra == {r: (1 if r == "fotos" else 0) for r in por_regra}
    # déficit residual = 6495 - 1 recuperado, persistido na rodada (não perdido)
    assert ler_rodada(conn, rodada_id)["posicoes_vazias_destaque"] == 6494


def test_o_ddl_aceita_o_perfil_de_conversao_como_regra_cedida_e_relaxada(conn):
    """A nona regra (D-027) é o PRIMEIRO degrau do relaxamento: o Registro precisa
    aceitá-la nas duas colunas — é o que a migração 008 acrescenta aos CHECKs da 001."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO registro.rodada (tipo, inicio) VALUES ('decisao', now()) RETURNING id"
        )
        rid = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO registro.relaxamento "
            "(rodada_id, regra_cedida, posicoes_dependentes, posicoes_vazias) "
            "VALUES (%s, 'perfil_de_conversao', 0, 0)",
            (rid,),
        )
        cur.execute(
            "INSERT INTO registro.decisao_imovel "
            "(rodada_id, imovel_id, nivel, posicao_ranking, nota_perfil, nota_leads, "
            "nota_desempenho, nota_gestor, nota_final, regra_relaxada) "
            "VALUES (%s, 1, 'destaque', 1, 0, 0, 0, 0, 0, 'perfil_de_conversao')",
            (rid,),
        )


def test_super_com_relaxamento_rejeitado_pelo_ddl(conn):
    # Invariante 7 reforçado no banco: um super destaque com regra_relaxada é
    # rejeitado pelo CHECK super_destaque_nunca_relaxa (simetria com o de cota).
    import psycopg

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO registro.rodada (tipo, inicio) VALUES ('decisao', now()) RETURNING id"
        )
        rid = cur.fetchone()[0]
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                "INSERT INTO registro.decisao_imovel "
                "(rodada_id, imovel_id, nivel, posicao_ranking, nota_perfil, nota_leads, "
                "nota_desempenho, nota_gestor, nota_final, regra_relaxada) "
                "VALUES (%s, 1, 'super_destaque', 1, 0, 0, 0, 0, 0, 'fotos')",
                (rid,),
            )
    conn.rollback()


def test_parametros_da_rodada_round_trip(conn):
    rodada_id = _gravar(conn, _resultado([_candidato(1)]))
    with conn.cursor() as cur:
        cur.execute(
            "SELECT parametros FROM registro.parametros_da_rodada WHERE rodada_id = %s",
            (rodada_id,),
        )
        assert cur.fetchone()[0] == PARAMS_SERIAL  # jsonb volta igual ao provisório gravado
    assert ler_rodada(conn, rodada_id)["motivo_degradacao"] == "sem raspagem"
