"""Testes de integração do Registro na rodada de segunda (leitura da carga aprovada
e gravação do apurado).

I/O real: rodam contra o Postgres local e são PULADOS onde não há banco (CI), como
os demais testes de I/O. Cada teste roda numa transação revertida no fim — nada
persiste. Cobre as duas metades da Spec §7.3 que o domínio puro não alcançava: só a
carga APROVADA conta (D-001), e a ausência de carga é DECLARADA no Registro.
"""

from datetime import date, datetime

import pytest

from dados.registro.acompanhamento import (
    declarar_ausencia_de_carga,
    gravar_acompanhamento,
    ler_resultado_carga,
    posicoes_da_carga,
    ultima_carga_aprovada,
)
from dados.registro.conexao import conectar
from dominio.acompanhamento import LeadDoPeriodo, Nivel, PosicaoPaga, apurar

INICIO = datetime(2026, 8, 28, 18, 0)
FIM = datetime(2026, 8, 31, 9, 0)


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


def _rodada_decisao(conn, *, aprovada: bool, imoveis=((1, "super_destaque"), (2, "destaque"))):
    """Cria uma rodada de decisão com posições; aprovada ou não."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO registro.rodada (tipo, inicio, fim, estado, aprovada_em, aprovada_por) "
            "VALUES ('decisao', %s, %s, 'completa', %s, %s) RETURNING id",
            (INICIO, INICIO, datetime.now() if aprovada else None, "tácita" if aprovada else None),
        )
        rid = cur.fetchone()[0]
        for pos, (imovel_id, nivel) in enumerate(imoveis, start=1):
            cur.execute(
                # Só as colunas que a migração 010 manteve obrigatórias: os sinais
                # nascem nulos, e nulo aqui quer dizer "esta fixture não os mede".
                "INSERT INTO registro.decisao_imovel "
                "(rodada_id, imovel_id, nivel, posicao_ranking, nota_final) "
                "VALUES (%s, %s, %s, %s, 0)",
                (rid, imovel_id, nivel, pos),
            )
    return rid


# --- só a carga APROVADA conta (D-001) ---------------------------------------


def test_rodada_nao_aprovada_nao_e_carga_vigente(conn):
    """Uma NÃO aprovada criada DEPOIS da aprovada não pode ser escolhida — senão a
    segunda mediria contra uma seleção que ninguém autorizou a aplicar (D-001)."""
    aprovada = _rodada_decisao(conn, aprovada=True)
    nao_aprovada = _rodada_decisao(conn, aprovada=False)  # mais recente, sem aprovação
    escolhida = ultima_carga_aprovada(conn)
    assert escolhida == aprovada
    assert escolhida != nao_aprovada


def test_escolhe_a_aprovada_mais_recente(conn):
    aprovada = _rodada_decisao(conn, aprovada=True)
    assert ultima_carga_aprovada(conn) == aprovada


def test_posicoes_da_carga_vem_do_registro(conn):
    rid = _rodada_decisao(conn, aprovada=True, imoveis=((7, "super_destaque"), (8, "destaque")))
    posicoes = posicoes_da_carga(conn, rid)
    assert [(p.imovel_id, p.nivel) for p in posicoes] == [
        (8, Nivel.DESTAQUE),
        (7, Nivel.SUPER_DESTAQUE),
    ]  # ordenado por (nivel, imovel): 'destaque' < 'super_destaque'
    assert all(isinstance(p, PosicaoPaga) for p in posicoes)


# --- §7.3 segunda metade: a ausência é DECLARADA ------------------------------


def test_ausencia_de_carga_fica_registrada(conn):
    motivo = "nenhuma rodada de decisão aprovada — relatório não emitido (Spec §7.3)"
    rid = declarar_ausencia_de_carga(conn, inicio=INICIO, fim=FIM, motivo=motivo)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT tipo, estado, motivo_degradacao FROM registro.rodada WHERE id = %s", (rid,)
        )
        tipo, estado, mot = cur.fetchone()
    assert (tipo, estado) == ("acompanhamento", "abortada")
    assert mot == motivo  # a ausência não some: fica visível para o gestor


# --- gravação do apurado ------------------------------------------------------


def _resultado(rodada_decisao_id):
    pos = [PosicaoPaga(1, Nivel.SUPER_DESTAQUE), PosicaoPaga(2, Nivel.DESTAQUE)]
    # Com responsável nomeado: é o caminho "pronto" do PRD (96,4% dos leads reais
    # têm gestor), e sem ele a gravação como 'completa' seria — corretamente — recusada.
    leads = [
        LeadDoPeriodo(
            lead_id=100,
            imovel_id=1,
            entrada=date(2026, 8, 29),
            atendimento_registrado=False,
            contato_registrado=False,
            corretor_gestor="Corretor X",
        ),
        LeadDoPeriodo(
            lead_id=101,
            imovel_id=1,
            entrada=date(2026, 8, 30),
            atendimento_registrado=True,
            contato_registrado=False,
            corretor_gestor="Corretor X",
        ),
    ]
    return apurar(
        rodada_decisao_id=rodada_decisao_id,
        posicoes=pos,
        leads=leads,
        inicio_periodo=date(2026, 8, 28),
        fim_periodo=date(2026, 8, 31),
    )


def test_grava_e_le_resultado_carga(conn):
    decisao_id = _rodada_decisao(conn, aprovada=True)
    resultado = _resultado(decisao_id)
    rid, _acum = gravar_acompanhamento(conn, resultado=resultado, inicio=INICIO, fim=FIM)
    lido = ler_resultado_carga(conn, rid)
    # TODAS as posições entram, inclusive a de zero lead (Spec §4.3)
    assert lido == {1: (2, 1), 2: (0, 0)}


def test_pronto_do_monitor_e_derivado_nao_afirmado(conn):
    """PRD: o pronto exige responsável nomeado. Lead sem corretor gestor ⇒ o
    Registro NÃO pode gravar monitor=True."""
    decisao_id = _rodada_decisao(conn, aprovada=True)
    sem_resp = apurar(
        rodada_decisao_id=decisao_id,
        posicoes=[PosicaoPaga(1, Nivel.DESTAQUE)],
        leads=[
            LeadDoPeriodo(
                lead_id=200,
                imovel_id=1,
                entrada=date(2026, 8, 29),
                atendimento_registrado=False,
                contato_registrado=False,
                corretor_gestor=None,  # sem responsável nomeado
            )
        ],
        inicio_periodo=date(2026, 8, 28),
        fim_periodo=date(2026, 8, 31),
    )
    # "completa" com etapa não-pronta é linha que se contradiz: o glossário define
    # completa como TODAS as etapas prontas. A gravação recusa.
    with pytest.raises(ValueError, match="todas as etapas prontas"):
        gravar_acompanhamento(conn, resultado=sem_resp, inicio=INICIO, fim=FIM)

    # Declarando o estado honesto, grava — e o Registro diz que o pronto não saiu.
    rid, _acum = gravar_acompanhamento(
        conn,
        resultado=sem_resp,
        inicio=INICIO,
        fim=FIM,
        estado="degradada",
        motivo_degradacao="lead sem responsável nomeado (PRD: pronto não cumprido)",
    )
    with conn.cursor() as cur:
        cur.execute("SELECT etapas FROM registro.rodada WHERE id = %s", (rid,))
        etapas = cur.fetchone()[0]
    assert etapas["monitor"] is False  # pronto não cumprido, e o Registro diz isso
    assert "redator" not in etapas  # não se afirma etapa de quem não rodou
    # O UPDATE junta o motivo às limitações do acúmulo UMA por LINHA — o console divide
    # por `\n`, e "; " (como era) fundia a última degradação com as limitações.
    with conn.cursor() as cur:
        cur.execute("SELECT motivo_degradacao FROM registro.rodada WHERE id = %s", (rid,))
        motivo = cur.fetchone()[0]
    linhas = motivo.splitlines()
    assert linhas[0] == "lead sem responsável nomeado (PRD: pronto não cumprido)"
    assert len(linhas) >= 3  # mais as limitações do acúmulo (2 ou 3), cada uma na sua linha


def test_autocommit_e_recusado(conn):
    """A gravação é tudo-ou-nada: com autocommit, recusa (raise, não assert)."""
    conn.autocommit = True
    try:
        with pytest.raises(ValueError, match="autocommit"):
            gravar_acompanhamento(conn, resultado=_resultado(1), inicio=INICIO, fim=FIM)
    finally:
        conn.autocommit = False


def test_rodada_de_acompanhamento_referencia_a_carga(conn):
    decisao_id = _rodada_decisao(conn, aprovada=True)
    rid, _acum = gravar_acompanhamento(
        conn, resultado=_resultado(decisao_id), inicio=INICIO, fim=FIM
    )
    with conn.cursor() as cur:
        cur.execute("SELECT tipo, estado FROM registro.rodada WHERE id = %s", (rid,))
        assert cur.fetchone() == ("acompanhamento", "completa")
        cur.execute(
            "SELECT DISTINCT rodada_decisao_id FROM registro.resultado_carga "
            "WHERE rodada_acompanhamento_id = %s",
            (rid,),
        )
        assert cur.fetchone()[0] == decisao_id  # aponta para a carga medida


def test_pii_do_lead_nao_vai_para_o_registro(conn):
    """A lista de leads sem tratamento (com identidade) fica na planilha; o Registro
    guarda só a CONTAGEM por imóvel."""
    decisao_id = _rodada_decisao(conn, aprovada=True)
    resultado = _resultado(decisao_id)
    assert resultado.leads_sem_tratamento  # o resultado TEM a lista com PII
    rid, _acum = gravar_acompanhamento(conn, resultado=resultado, inicio=INICIO, fim=FIM)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'registro' AND table_name = 'resultado_carga'"
        )
        colunas = {c for (c,) in cur.fetchall()}
    assert colunas == {
        "rodada_acompanhamento_id",
        "rodada_decisao_id",
        "imovel_id",
        "leads_gerados",
        "leads_sem_tratamento",
    }  # nenhuma coluna de pessoa
    assert ler_resultado_carga(conn, rid)  # e a contagem está lá


def test_janela_usa_a_data_da_CARGA_nao_o_relogio(conn):
    """`gravar_acompanhamento` recebe `inicio`/`fim` que são o relógio da EXECUÇÃO.
    A janela precisa das datas da vitrine (Spec §2.1), e o proxy que o sistema tem é
    `aprovada_em` da carga — que chega como `resumo.inicio_periodo`.

    Sem esta trava, trocar a fonte da data de volta para o relógio passava despercebido:
    nenhum teste cobria a costura, e o efeito seria toda janela deslocada em dias e um
    reprocessamento carimbando o Registro com a data de hoje."""
    decisao_id = _rodada_decisao(conn, aprovada=True)
    resultado = apurar(
        rodada_decisao_id=decisao_id,
        posicoes=[PosicaoPaga(1, Nivel.SUPER_DESTAQUE)],
        leads=[],
        inicio_periodo=date(2026, 8, 28),  # a sexta da carga
        fim_periodo=date(2026, 8, 31),
    )
    # INICIO/FIM do relógio são 28/08 18h e 31/08 09h — datas DIFERENTES do período.
    gravar_acompanhamento(conn, resultado=resultado, inicio=INICIO, fim=FIM)

    with conn.cursor() as cur:
        cur.execute("SELECT inicio FROM registro.janela_destaque WHERE imovel_id = 1")
        (inicio,) = cur.fetchone()
    assert inicio == date(2026, 8, 28)  # a data da CARGA, não FIM.date()


def test_gravar_devolve_o_historico_da_janela(conn):
    """O histórico sai da MESMA transação que acumulou — uma leitura à parte veria o
    estado anterior e o relatório diria "2 semanas" na terceira."""
    decisao_id = _rodada_decisao(conn, aprovada=True)
    resultado = apurar(
        rodada_decisao_id=decisao_id,
        posicoes=[PosicaoPaga(1, Nivel.SUPER_DESTAQUE)],
        leads=[],
        inicio_periodo=date(2026, 8, 28),
        fim_periodo=date(2026, 8, 31),
    )
    _rid, acumulo = gravar_acompanhamento(conn, resultado=resultado, inicio=INICIO, fim=FIM)
    assert acumulo.historico == {1: (1, 0)}  # primeira semana, zero lead
