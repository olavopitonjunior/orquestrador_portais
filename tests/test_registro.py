"""Testes de integração do Registro (escrita/leitura no Postgres próprio).

I/O real: rodam contra o Postgres local e são PULADOS onde não há banco (CI),
como os demais testes de I/O do projeto. Cada teste roda numa transação que é
revertida no fim — nada persiste. Cobre o round-trip (grava → lê), a contagem
por nível (cotas) e a atomicidade/reforço de invariante pelo DDL.
"""

from dataclasses import replace
from datetime import date, datetime

import psycopg
import pytest
from psycopg.types.json import Json

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
        # Zero DECLARADO, não omitido: é o peso adotado das visualizações (medidas
        # zero em 300 de 300), e é o que permite refazer a nota bruta lendo o Registro.
        "portal.peso_visualizacoes": 0,
        "desconto.perdao_por_semana": 50,
    },
    "procedencia": {
        "portal.peso_nota": "adotado D-034",
        "portal.peso_cliques": "adotado D-034",
        "portal.peso_visualizacoes": "adotado D-034",
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


def _resultado_com_portal():
    """Uma rodada em que a conta tem o que fechar: DOIS candidatos com leads distintos
    (então o min-max não degenera e os sinais não são todos zero), anúncios com nota,
    cliques e visualizações distintos, o portal ENTRANDO no ranking (senão a nota bruta
    viria do desempate de banco, e a identidade `Σ peso × sinal` nem se aplica), e um
    imóvel sem avaliação por categoria, para haver desconto diferente de zero.

    A fixture de um candidato só, que os testes de round-trip usam, não serve aqui: com
    um elemento `min == max`, todo sinal vira 0,0 e as duas identidades viram `0 == 0`.
    """
    from dados.coletor_externo import DesempenhoAnuncio
    from dominio.penalidades import ImovelPenalizavel

    # TRÊS candidatos, não dois: com dois, o min-max joga um em 1,0 e o outro em 0,0, e
    # o que tem desconto sairia com nota bruta zero — a asserção voltaria a ser trivial.
    # O do MEIO é quem carrega o desconto, então bruta e desconto são ambos não-nulos.
    cands = [_candidato(1), _candidato(2), _candidato(3)]
    pen = {
        1: ImovelPenalizavel(
            imovel_id=1, janelas_anteriores=(), alguma_categoria_avaliada=True, leads_180d=40
        ),
        # sem avaliação por categoria → desconto de 5 pontos
        2: ImovelPenalizavel(
            imovel_id=2, janelas_anteriores=(), alguma_categoria_avaliada=False, leads_180d=20
        ),
        3: ImovelPenalizavel(
            imovel_id=3, janelas_anteriores=(), alguma_categoria_avaliada=True, leads_180d=1
        ),
    }
    dims = {c.imovel_id: {Dimensao.REGIAO: "Centro"} for c in cands}
    anuncios = {
        1: DesempenhoAnuncio(
            imovel_id=1,
            id_portal="1A",
            nota=9000.0,
            visualizacoes=120,
            cliques={"contato": 9},
            url=None,
        ),
        2: DesempenhoAnuncio(
            imovel_id=2,
            id_portal="2A",
            nota=7500.0,
            visualizacoes=60,
            cliques={"contato": 5},
            url=None,
        ),
        3: DesempenhoAnuncio(
            imovel_id=3,
            id_portal="3A",
            nota=6000.0,
            visualizacoes=10,
            cliques={"contato": 1},
            url=None,
        ),
    }
    return decidir(
        cands, pen, dims, _perfis_da_fixture(), PARAMS, HOJE, anuncios=anuncios, portal_entrou=True
    )


def _gravar(conn, resultado, estado="degradada", perfis=()):
    return gravar_rodada_decisao(
        conn,
        resultado=resultado,
        estado=estado,
        etapas={"coletor_interno": True, "decisor": True, "crivo": True, "externo": False},
        parametros=PARAMS_SERIAL,
        inicio=datetime(2026, 9, 1, 17, 0),
        fim=datetime(2026, 9, 1, 17, 5),
        motivo_degradacao="sem raspagem",
        perfis=perfis,
    )


def _perfis_da_fixture():
    """Os mesmos perfis que `_resultado` usa — para gravar e conferir o vínculo."""
    return perfis_de_conversao(
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


# ------------------------------------------------- os perfis da semana (issue #79)


def test_perfis_da_rodada_sao_gravados_com_a_classificacao(conn):
    """Spec §2.1: "os padrões que o Analista encontrou naquela semana". TODOS —
    robustos e frágeis —, porque sem os frágeis não dá para ver que a evidência
    era pouca."""
    perfis = _perfis_da_fixture()
    assert perfis, "a fixture precisa produzir ao menos um perfil"
    rodada_id = _gravar(conn, _resultado([_candidato(1)]), perfis=perfis)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT dimensoes, valores, vendas_sustentam, classificacao "
            "FROM registro.perfil_da_rodada WHERE rodada_id = %s ORDER BY id",
            (rodada_id,),
        )
        linhas = cur.fetchall()
    assert len(linhas) == len(perfis)
    for (dims, valores, vendas, classificacao), perfil in zip(linhas, perfis, strict=True):
        assert dims == [d.value for d in perfil.dimensoes]
        assert valores == list(perfil.valores)
        assert vendas == perfil.num_vendas
        assert classificacao == ("fragil" if perfil.fragil else "robusto")


def test_perfil_id_liga_o_imovel_ao_perfil_que_o_puxou(conn):
    """Desde a D-027 o perfil é regra eliminatória: sem este vínculo, o Registro não
    permite reconstituir QUAL perfil deixou o imóvel entrar."""
    resultado = _resultado([_candidato(1)])
    perfis = _perfis_da_fixture()
    rodada_id = _gravar(conn, resultado, perfis=perfis)
    puxou = resultado.detalhes[1].perfil_que_puxou
    assert puxou is not None
    with conn.cursor() as cur:
        cur.execute(
            "SELECT p.dimensoes, p.valores, p.vendas_sustentam, d.perfil_evidencia "
            "FROM registro.decisao_imovel d JOIN registro.perfil_da_rodada p "
            "ON p.id = d.perfil_id WHERE d.rodada_id = %s AND d.imovel_id = 1",
            (rodada_id,),
        )
        linha = cur.fetchone()
    assert linha is not None, "perfil_id ficou nulo — o vínculo é o ponto desta fatia"
    dims, valores, vendas, evidencia = linha
    assert dims == [d.value for d in puxou.dimensoes]
    assert valores == list(puxou.valores)
    assert vendas == puxou.num_vendas == evidencia


def test_sem_perfis_a_rodada_grava_e_o_vinculo_fica_nulo(conn):
    """Rodada sem perfil que conte ainda é rodada: grava, e a ausência do vínculo é
    a ausência real, não um corte de escopo."""
    rodada_id = _gravar(conn, _resultado([_candidato(1)]), perfis=())
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM registro.perfil_da_rodada WHERE rodada_id = %s", (rodada_id,)
        )
        assert cur.fetchone()[0] == 0
        cur.execute(
            "SELECT perfil_id FROM registro.decisao_imovel WHERE rodada_id = %s", (rodada_id,)
        )
        assert cur.fetchone()[0] is None


def test_o_mesmo_perfil_duas_vezes_na_rodada_e_recusado_pelo_ddl(conn):
    """A unicidade da migração 011 é o que permite ligar `perfil_id` sem ambiguidade."""
    perfil = _perfis_da_fixture()[0]
    dims, valores = Json([d.value for d in perfil.dimensoes]), Json(list(perfil.valores))
    sql = (
        "INSERT INTO registro.perfil_da_rodada "
        "(rodada_id, dimensoes, valores, vendas_sustentam, classificacao) "
        "VALUES (%s, %s, %s, 3, 'robusto')"
    )
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO registro.rodada (tipo, inicio) VALUES ('decisao', now()) RETURNING id"
        )
        rid = cur.fetchone()[0]
        cur.execute(sql, (rid, dims, valores))
        with pytest.raises(psycopg.errors.UniqueViolation):
            cur.execute(sql, (rid, dims, valores))
    conn.rollback()


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
    """A nota como a D-028 a define (migração 010): a bruta em PONTOS DE 100 — a
    mesma unidade da final e dos descontos —, os três sinais do anúncio reescalados,
    os dois de banco que só desempatam, e o veredito do perfil como booleano."""
    resultado = _resultado_com_portal()
    rodada_id = _gravar(conn, resultado)
    det = resultado.detalhes[2]  # o que tem desconto: sem avaliação por categoria
    with conn.cursor() as cur:
        cur.execute(
            "SELECT nota_bruta, sinal_nota_anuncio, sinal_cliques, sinal_visualizacoes, "
            "sinal_leads, sinal_produtividade, casa_perfil, nota_final, "
            "pen_janela_anterior, pen_sem_avaliacao, pen_sem_lead_180d "
            "FROM registro.decisao_imovel WHERE rodada_id = %s AND imovel_id = 2",
            (rodada_id,),
        )
        linha = cur.fetchone()
    assert linha is not None
    bruta, anuncio, cliques, visualizacoes, leads, produtividade = (float(v) for v in linha[:6])
    casa_perfil, nota_final = linha[6], float(linha[7])
    descontos = [float(v) for v in linha[8:]]
    f = det.fatores
    # `numeric` guarda ~15 dígitos significativos, então o valor não volta bit a bit
    # igual ao float que entrou. Comparar por igualdade exata aqui testaria a precisão
    # do tipo do Postgres, não a fidelidade da gravação; a tolerância é apertada de
    # propósito, e a auditoria de uma nota em pontos de 100 não precisa de mais.
    assert bruta == pytest.approx(det.nota_bruta, rel=1e-12)
    assert (anuncio, cliques, visualizacoes) == pytest.approx(
        (f.nota_anuncio, f.cliques, f.visualizacoes), rel=1e-12
    )
    assert (leads, produtividade) == pytest.approx((f.leads, f.produtividade_gestor), rel=1e-12)
    assert casa_perfil is True and f.casa_perfil is True
    assert nota_final == pytest.approx(det.nota_super_destaque, rel=1e-12)
    # A fixture precisa MESMO exercer a conta: sem isto o teste passaria com 0 == 0 - 0.
    assert bruta > 0 and sum(descontos) > 0
    # A conta fecha LENDO SÓ O REGISTRO — que é a razão de existir da migração 010.
    assert abs(nota_final - (bruta - sum(descontos))) < 1e-9


def test_casa_perfil_nulo_quando_a_regra_nao_foi_avaliada(conn):
    """NULL não é "não casou": é "a regra do perfil não incidiu" (D-027, Spec §6.1).
    Colapsar os dois afirmaria sobre o imóvel algo que a rodada não mediu."""
    from dataclasses import replace as _replace

    resultado = _resultado([_candidato(1)])
    det = resultado.detalhes[1]
    sem_veredito = _replace(det, fatores=_replace(det.fatores, casa_perfil=None))
    resultado = _replace(resultado, detalhes={1: sem_veredito})
    rodada_id = _gravar(conn, resultado)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT casa_perfil FROM registro.decisao_imovel WHERE rodada_id = %s", (rodada_id,)
        )
        assert cur.fetchone()[0] is None


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
            "(rodada_id, imovel_id, nivel, posicao_ranking, nota_final, regra_relaxada) "
            "VALUES (%s, 1, 'destaque', 1, 0, 'perfil_de_conversao')",
            (rid,),
        )


def test_super_com_relaxamento_rejeitado_pelo_ddl(conn):
    # Invariante 7 reforçado no banco: um super destaque com regra_relaxada é
    # rejeitado pelo CHECK super_destaque_nunca_relaxa (simetria com o de cota).
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO registro.rodada (tipo, inicio) VALUES ('decisao', now()) RETURNING id"
        )
        rid = cur.fetchone()[0]
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                "INSERT INTO registro.decisao_imovel "
                "(rodada_id, imovel_id, nivel, posicao_ranking, nota_final, regra_relaxada) "
                "VALUES (%s, 1, 'super_destaque', 1, 0, 'fotos')",
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


def test_a_mesma_entrada_grava_os_mesmos_perfis_na_mesma_ordem(conn):
    """Invariante 5 na borda de persistência: `perfil_da_rodada.id` é IDENTITY, então
    a ORDEM da iteração vira o id. Iterar um conjunto não ordenado daria id diferente
    a cada execução e o Registro deixaria de ser reproduzível — duas rodadas iguais
    teriam vínculos diferentes."""
    linhas_por_rodada = []
    for _ in range(2):
        # A fixture é recriada a cada volta DE PROPÓSITO: o que precisa ser determinístico
        # é a cadeia inteira — `perfis_de_conversao` devolvendo a mesma ordem e o gravador
        # preservando-a. Reusar uma lista só provaria a segunda metade.
        perfis = _perfis_da_fixture()
        rodada_id = _gravar(conn, _resultado([_candidato(1)]), perfis=perfis)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT dimensoes, valores FROM registro.perfil_da_rodada "
                "WHERE rodada_id = %s ORDER BY id",
                (rodada_id,),
            )
            linhas_por_rodada.append(cur.fetchall())
        # A ordem do banco é a ordem do DOMÍNIO, não só igual entre voltas: um `set` na
        # iteração daria a mesma ordem dentro do processo e passaria na comparação abaixo.
        assert linhas_por_rodada[-1] == [
            ([d.value for d in p.dimensoes], list(p.valores)) for p in perfis
        ]
    assert linhas_por_rodada[0] == linhas_por_rodada[1], "a ordem mudou entre execuções iguais"


def test_a_nota_bruta_e_refeita_pelos_pesos_gravados_na_mesma_rodada(conn):
    """A cadeia inteira dentro do banco: os pesos efetivos vão em
    `parametros_da_rodada`, os sinais em `decisao_imovel`, e `Σ peso × sinal` tem de
    dar a `nota_bruta` gravada. É o que torna a nota auditável sem o código na mão."""
    resultado = _resultado_com_portal()
    rodada_id = _gravar(conn, resultado)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT parametros -> 'efetivo' FROM registro.parametros_da_rodada "
            "WHERE rodada_id = %s",
            (rodada_id,),
        )
        efetivo = cur.fetchone()[0]
        cur.execute(
            "SELECT nota_bruta, sinal_nota_anuncio, sinal_cliques, sinal_visualizacoes "
            "FROM registro.decisao_imovel WHERE rodada_id = %s AND imovel_id = 1",
            (rodada_id,),
        )
        bruta, anuncio, cliques, visualizacoes = (float(v) for v in cur.fetchone())
    refeita = (
        float(efetivo["portal.peso_nota"]) * anuncio
        + float(efetivo["portal.peso_cliques"]) * cliques
        + float(efetivo["portal.peso_visualizacoes"]) * visualizacoes
    )
    # O imóvel 1 é o melhor dos dois em todo sinal: bruta = 70 × 1 + 30 × 1 + 0 × 1.
    assert bruta == 100.0 and anuncio == cliques == visualizacoes == 1.0
    assert abs(bruta - refeita) < 1e-9
