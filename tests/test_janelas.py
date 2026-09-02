"""Testes do produtor de `registro.janela_destaque` (D-021).

I/O real: rodam contra o Postgres local e são PULADOS onde não há banco (CI), como
os demais testes de I/O. Cada teste roda numa transação revertida no fim.

O que se prova aqui é a regra da D-021 — a janela fica aberta enquanto o imóvel
permanece nas cargas, acumulando, e fecha quando ele sai — mais as garantias que a
sustentam. A mais importante: **a unidade de acumulação é a CARGA, não a execução da
segunda**. Uma versão anterior chaveava a guarda pela rodada de acompanhamento, e ela
não guardava nada: cada reexecução abre uma rodada nova, com id novo, então
reprocessar somava os leads outra vez. O teste daquela versão passava porque chamava
duas vezes com o MESMO id — cenário que a fiação real nunca produz.
"""

from datetime import date, datetime

import psycopg
import pytest

from dados.registro.conexao import conectar
from dados.registro.janelas import atualizar_janelas, ciclos_desde, janelas_encerradas
from dominio.acompanhamento import DesempenhoImovel, Nivel

SEX_1 = date(2026, 9, 4)
SEX_2 = date(2026, 9, 11)
SEX_3 = date(2026, 9, 18)


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


def _rodada(conn, tipo: str, dia: date, *, aprovada: bool = True) -> int:
    carimbo = datetime(dia.year, dia.month, dia.day, 18)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO registro.rodada (tipo, inicio, fim, estado, aprovada_em) "
            "VALUES (%s, %s, %s, 'completa', %s) RETURNING id",
            (
                tipo,
                datetime(dia.year, dia.month, dia.day, 9),
                carimbo,
                carimbo if (aprovada and tipo == "decisao") else None,
            ),
        )
        return int(cur.fetchone()[0])


def _desempenho(*pares, nivel: Nivel = Nivel.DESTAQUE):
    """(imovel_id, leads_gerados) → o que a segunda mediu."""
    return [
        DesempenhoImovel(
            imovel_id=i,
            nivel=nivel,
            leads_gerados=leads,
            leads_sem_tratamento=0,
            semanas_consecutivas=None,
            leads_acumulados_janela=None,
        )
        for i, leads in pares
    ]


def _acumular(conn, *, carga: int, dia: date, desempenho):
    """Uma execução da segunda: rodada de acompanhamento NOVA a cada chamada, como
    `gravar_acompanhamento` faz de verdade."""
    return atualizar_janelas(
        conn,
        rodada_decisao_id=carga,
        rodada_acompanhamento_id=_rodada(conn, "acompanhamento", dia),
        desempenho=desempenho,
        data_da_carga=dia,
    )


def _janelas(conn, imovel_id: int):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT inicio, fim, leads_gerados, semanas_consecutivas, nivel "
            "FROM registro.janela_destaque WHERE imovel_id = %s ORDER BY inicio, id",
            (imovel_id,),
        )
        return cur.fetchall()


# --- a regra da D-021 ---------------------------------------------------------


def test_janela_abre_quando_o_imovel_entra_na_carga(conn):
    carga = _rodada(conn, "decisao", SEX_1)
    hist = _acumular(conn, carga=carga, dia=SEX_1, desempenho=_desempenho((10, 2)))

    assert hist == {10: (1, 2)}  # primeira semana, 2 leads
    ((inicio, fim, leads, semanas, nivel),) = _janelas(conn, 10)
    assert (inicio, fim, leads, semanas, nivel) == (SEX_1, None, 2, 1, "destaque")


def test_janela_ACUMULA_a_cada_CARGA_em_que_o_imovel_permanece(conn):
    """O coração da D-021, na sua letra: "a cada CARGA em que ele permanece, a janela
    acumula os leads do período e incrementa semanas_consecutivas"."""
    acumulado = 0
    for i, (dia, leads) in enumerate([(SEX_1, 2), (SEX_2, 3), (SEX_3, 1)]):
        acumulado += leads
        hist = _acumular(
            conn,
            carga=_rodada(conn, "decisao", dia),  # carga NOVA a cada sexta
            dia=dia,
            desempenho=_desempenho((10, leads)),
        )
        assert hist[10] == (i + 1, acumulado)

    assert len(_janelas(conn, 10)) == 1  # UMA janela, não três
    inicio, fim, leads, semanas, _ = _janelas(conn, 10)[0]
    assert (inicio, fim, leads, semanas) == (SEX_1, None, 6, 3)


def test_janela_FECHA_quando_o_imovel_sai_da_carga(conn):
    _acumular(
        conn,
        carga=_rodada(conn, "decisao", SEX_1),
        dia=SEX_1,
        desempenho=_desempenho((10, 2), (11, 0)),
    )
    hist = _acumular(  # carga seguinte não traz mais o 10
        conn,
        carga=_rodada(conn, "decisao", SEX_2),
        dia=SEX_2,
        desempenho=_desempenho((11, 4)),
    )

    assert 10 not in hist  # saiu: não é mais janela em curso
    ((_, fim, leads, semanas, _),) = _janelas(conn, 10)
    assert fim == SEX_2
    assert (leads, semanas) == (2, 1)  # congelado no que acumulou até sair
    assert hist[11] == (2, 4)  # quem ficou seguiu acumulando


def test_imovel_que_volta_depois_ganha_janela_NOVA(conn):
    """Sair e voltar são duas exposições distintas, e a §6.4 julga a janela — não o
    imóvel. Fundir as duas esconderia um período sem resultado dentro de outro."""
    for dia, desemp in [(SEX_1, (10, 1)), (SEX_2, (11, 0)), (SEX_3, (10, 5))]:
        _acumular(
            conn,
            carga=_rodada(conn, "decisao", dia),
            dia=dia,
            desempenho=_desempenho(desemp),
        )

    janelas = _janelas(conn, 10)
    assert len(janelas) == 2
    assert janelas[0][1] == SEX_2  # a primeira fechou quando ele saiu
    assert janelas[1][1] is None  # a segunda está em curso
    assert janelas[1][2] == 5


def test_mudanca_de_NIVEL_fecha_a_janela_e_abre_outra(conn):
    """A §6.4 julga "o resultado esperado PARA O NÍVEL" e o parâmetro nº 14 tem um
    valor por nível: uma janela que atravessasse destaque e super destaque não teria
    régua para ser julgada. Antes disto o nível ficava congelado no da abertura e a
    janela inteira era julgada pela régua errada, em silêncio."""
    _acumular(
        conn,
        carga=_rodada(conn, "decisao", SEX_1),
        dia=SEX_1,
        desempenho=_desempenho((10, 2), nivel=Nivel.DESTAQUE),
    )
    hist = _acumular(
        conn,
        carga=_rodada(conn, "decisao", SEX_2),
        dia=SEX_2,
        desempenho=_desempenho((10, 3), nivel=Nivel.SUPER_DESTAQUE),
    )

    janelas = _janelas(conn, 10)
    assert len(janelas) == 2
    assert (janelas[0][4], janelas[0][1], janelas[0][2]) == ("destaque", SEX_2, 2)
    assert (janelas[1][4], janelas[1][1], janelas[1][2]) == ("super_destaque", None, 3)
    assert hist[10] == (1, 3)  # a janela nova começa do zero


# --- a guarda que sustenta tudo ----------------------------------------------


def test_reprocessar_a_segunda_com_RODADA_NOVA_nao_acumula_duas_vezes(conn):
    """O cenário REAL de reprocessamento: `gravar_acompanhamento` abre uma rodada
    nova a cada execução, então o id é sempre diferente. Chaveada pela rodada de
    acompanhamento, a guarda nunca disparava aqui — e este é o único caminho que a
    operação de fato produz (o runner commita o Registro e só então escreve a
    planilha; se a planilha falha, a retomada documentada é rodar de novo)."""
    carga = _rodada(conn, "decisao", SEX_1)
    desemp = _desempenho((10, 3))

    primeira = _acumular(conn, carga=carga, dia=SEX_1, desempenho=desemp)
    segunda = _acumular(conn, carga=carga, dia=SEX_1, desempenho=desemp)  # rodada NOVA

    assert primeira == segunda == {10: (1, 3)}
    ((_, _, leads, semanas, _),) = _janelas(conn, 10)
    assert (leads, semanas) == (3, 1)


def test_duas_segundas_contra_a_MESMA_carga_contam_UMA_semana(conn):
    """Cenário concreto enquanto nada carimba `aprovada_em`: uma sexta que não rodou
    deixa a carga anterior vigente, e a segunda seguinte mede a MESMA carga. Contar
    duas semanas inflaria uma permanência que não houve — a D-021 conta por carga."""
    carga = _rodada(conn, "decisao", SEX_1)
    _acumular(conn, carga=carga, dia=SEX_1, desempenho=_desempenho((10, 2)))
    hist = _acumular(conn, carga=carga, dia=SEX_1, desempenho=_desempenho((10, 7)))

    assert hist[10] == (1, 2)  # nem semana nova, nem os leads remedidos


def test_duas_janelas_ABERTAS_para_o_mesmo_imovel_sao_recusadas_pelo_banco(conn):
    """Segunda linha de defesa, no schema (índice parcial da 005): sob a D-021 a
    janela em curso é a unidade de acumulação, e duas abertas somariam leads numa e
    semanas na outra sem nada acusar."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO registro.janela_destaque (imovel_id, nivel, inicio) "
            "VALUES (42, 'destaque', %s)",
            (SEX_1,),
        )
        with pytest.raises(psycopg.errors.UniqueViolation):
            cur.execute(
                "INSERT INTO registro.janela_destaque (imovel_id, nivel, inicio) "
                "VALUES (42, 'destaque', %s)",
                (SEX_2,),
            )


def test_desempenho_vazio_e_RECUSADO_em_vez_de_fechar_tudo(conn):
    """Sem a recusa, `desempenho` vazio fecharia TODAS as janelas abertas da base —
    apagando o insumo da §6.4 de todo o sistema numa transação que commita normal.
    Ausência de carga é declarada por `declarar_ausencia_de_carga`, não assim."""
    with pytest.raises(ValueError, match="desempenho vazio"):
        atualizar_janelas(
            conn,
            rodada_decisao_id=1,
            rodada_acompanhamento_id=1,
            desempenho=[],
            data_da_carga=SEX_1,
        )


def test_atualizar_exige_transacao(conn):
    """`raise`, não `assert`: sob `python -O` a garantia de atomicidade evaporaria
    justamente onde ela importa."""
    conn.rollback()
    conn.autocommit = True
    try:
        with pytest.raises(ValueError, match="transação"):
            atualizar_janelas(
                conn,
                rodada_decisao_id=1,
                rodada_acompanhamento_id=1,
                desempenho=_desempenho((1, 0)),
                data_da_carga=SEX_1,
            )
    finally:
        conn.autocommit = False


# --- leitura para a sexta -----------------------------------------------------


def test_janelas_encerradas_ignora_a_janela_em_curso(conn):
    """Contrato de `ImovelPenalizavel`: `janelas_anteriores` só contém janelas com
    fim não nulo. A janela em curso ainda não terminou de acumular e não pode ser
    julgada pela §6.4."""
    _acumular(
        conn,
        carga=_rodada(conn, "decisao", SEX_1),
        dia=SEX_1,
        desempenho=_desempenho((10, 1), (11, 0)),
    )
    assert janelas_encerradas(conn, [10, 11]) == {}  # nenhuma fechou ainda

    _acumular(  # o 10 sai
        conn,
        carga=_rodada(conn, "decisao", SEX_2),
        dia=SEX_2,
        desempenho=_desempenho((11, 0)),
    )
    encerradas = janelas_encerradas(conn, [10, 11])
    assert list(encerradas) == [10]
    assert encerradas[10] == (("destaque", 1, SEX_2),)


def test_janelas_encerradas_nao_inventa_ausencia(conn):
    """Imóvel sem janela encerrada some do dicionário — a §6.4 manda distinguir
    'sem histórico' de 'teve janela e não foi penalizado', e um zero aqui apagaria
    a diferença."""
    assert janelas_encerradas(conn, [999]) == {}
    assert janelas_encerradas(conn, []) == {}


def test_ciclos_conta_so_carga_APROVADA(conn):
    """`ciclo` é uma carga que entrou no ar. Uma sexta não aprovada não expôs imóvel
    nenhum — fazer o decaimento da penalidade avançar por ela contaria um ciclo que
    não aconteceu. A base é lida ANTES: `ciclos_desde` conta a tabela inteira, e o
    banco local carrega rodadas de outros testes."""
    base = ciclos_desde(conn, [SEX_1])[SEX_1]
    _rodada(conn, "decisao", SEX_2, aprovada=True)
    _rodada(conn, "decisao", SEX_3, aprovada=False)  # não aprovada: não conta
    _rodada(conn, "acompanhamento", SEX_3)  # não é decisão: não conta

    assert ciclos_desde(conn, [SEX_1])[SEX_1] == base + 1
    assert ciclos_desde(conn, []) == {}


def test_ciclos_agrega_datas_repetidas_numa_consulta(conn):
    """São ~7 mil imóveis por rodada e a maioria compartilha data de fim: uma
    consulta por imóvel seriam milhares de idas ao banco para a mesma pergunta."""
    assert ciclos_desde(conn, [SEX_1, SEX_1, SEX_2]).keys() == {SEX_1, SEX_2}


def test_carga_RETROATIVA_e_recusada_com_mensagem_propria(conn):
    """Rodar uma segunda antiga depois de uma nova tentaria fechar janelas com `fim`
    anterior ao `inicio`: o CHECK da 005 derrubaria a transação inteira com uma
    violação de constraint que não diz nada sobre a causa — e o caso irmão (ninguém
    saiu da carga) passaria em silêncio, acumulando dado velho sobre o novo."""
    _acumular(
        conn,
        carga=_rodada(conn, "decisao", SEX_2),
        dia=SEX_2,
        desempenho=_desempenho((10, 1)),
    )
    with pytest.raises(ValueError, match="anterior à janela aberta mais recente"):
        _acumular(
            conn,
            carga=_rodada(conn, "decisao", SEX_1),
            dia=SEX_1,  # sexta ANTERIOR
            desempenho=_desempenho((11, 0)),
        )
