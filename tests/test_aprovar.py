"""Ponto de entrada da APROVAÇÃO (`executar/aprovar.py`) — o elo que faltava entre a
sexta e a segunda.

I/O real contra o Postgres próprio, como os demais testes do Registro: cada teste
roda numa transação revertida no fim. O checkpointer é MemorySaver (a persistência
da pausa num PostgresSaver real já é coberta por `test_aprovacao.py`); o que se
prova aqui é o CONTRATO do runner — quais guardas recusam, com que código, e que o
carimbo é único.
"""

import os
from contextlib import nullcontext
from datetime import datetime, timedelta

import pytest
from langgraph.checkpoint.memory import MemorySaver

from dados.registro.acompanhamento import ultima_carga_aprovada
from dados.registro.conexao import conectar
from dados.registro.leitura import JaAprovada, ler_rodada, marcar_aprovada
from executar.aprovar import (
    FORA_DE_ORDEM,
    INCONSISTENTE,
    JA_APROVADA,
    NAO_APROVAVEL,
    OK,
    VALOR_INVALIDO,
    Recusa,
    carga_que_seguiria_vigente,
    conferir,
    executar,
    rodada_aprovada_mais_nova,
    thread_da_rodada,
)
from grafo.aprovacao import aprovar_explicita, aprovar_tacita

AGORA = datetime(2026, 9, 4, 18, 0).astimezone()  # sexta 18h, fuso local
INICIO = AGORA - timedelta(hours=2)
FIM = AGORA - timedelta(hours=1)


@pytest.fixture
def conn():
    try:
        c = conectar()
    except Exception as e:  # POSTGRES_URL ausente ou banco fora → pula (CI sobe o banco)
        pytest.skip(f"Postgres próprio indisponível: {e}")
    c.autocommit = False
    # ISOLA o universo em vez de herdá-lo. As guardas de ordem varrem `registro.rodada`
    # INTEIRA (`max(id)` entre aprovadas, `max(aprovada_em)`), então uma linha deixada
    # por qualquer execução manual anterior muda o veredito dos testes — o portão de
    # código mediu isso: com uma rodada aprovada residual no banco, quatro testes
    # passam a sair FORA_DE_ORDEM. O TRUNCATE roda DENTRO da transação e volta no
    # rollback, então o banco de quem roda fica como estava.
    with c.cursor() as cur:
        cur.execute("TRUNCATE registro.rodada CASCADE")
    yield c
    c.rollback()  # nada persiste entre testes
    c.close()


def _rodada(
    conn,
    *,
    tipo: str = "decisao",
    estado: str | None = "completa",
    aprovada_em: datetime | None = None,
    aprovada_por: str | None = None,
    fim: datetime | None = FIM,
) -> int:
    """INSERT direto: o alvo aqui é o runner, não o gravador da rodada."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO registro.rodada (tipo, inicio, fim, estado, aprovada_em, "
            "aprovada_por) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (tipo, INICIO, fim, estado, aprovada_em, aprovada_por),
        )
        return int(cur.fetchone()[0])


def _executar(conn, rodada_id, *, retomada=None, chamadas=None, **kw):
    """Roda o runner com o Registro da fixture e um MemorySaver por chamada, a menos
    que o teste passe o seu (para simular thread pré-existente)."""
    saver = kw.pop("checkpointer", None) or MemorySaver()
    return executar(
        rodada_id,
        retomada=retomada,
        em=kw.pop("em", None),
        agora=kw.pop("agora", AGORA),
        fora_de_ordem=kw.pop("fora_de_ordem", False),
        dry_run=kw.pop("dry_run", False),
        conectar_registro=lambda: nullcontext(conn),
        checkpointer_de=lambda _dsn: nullcontext(saver),
        **kw,
    )


# --- o que a fatia entrega: o carimbo, e a carga vigente que ele cria -----------


def test_aprovar_CARIMBA_o_registro_e_a_carga_passa_a_ser_a_VIGENTE(conn):
    """O ponto inteiro da fatia. Sem o carimbo, `ultima_carga_aprovada` devolve None
    e toda rodada de segunda declara ausência de carga."""
    rodada_id = _rodada(conn)
    assert ultima_carga_aprovada(conn) is None  # antes: nenhuma carga vigente

    assert _executar(conn, rodada_id, retomada=aprovar_explicita("olavo")) == OK

    resumo = ler_rodada(conn, rodada_id)
    assert resumo["aprovada_em"] is not None
    assert resumo["aprovada_por"] == "olavo"
    assert ultima_carga_aprovada(conn) == rodada_id  # a segunda agora acha a carga


def test_tacita_registra_QUEM_como_tacita(conn):
    """D-001 distingue a aprovação por decurso de prazo da explícita — é o que
    `aprovada_por` guarda, e o prazo (nº 10) segue nulo e fora deste módulo."""
    rodada_id = _rodada(conn)
    assert _executar(conn, rodada_id, retomada=aprovar_tacita()) == OK
    assert ler_rodada(conn, rodada_id)["aprovada_por"] == "tácita"


def test_abrir_deixa_PENDENTE_sem_carimbar(conn):
    """`abrir` cria a pausa e não decide: o Registro continua sem carimbo, e a
    rodada segue na fila de aprovação do console."""
    rodada_id = _rodada(conn)
    assert _executar(conn, rodada_id, retomada=None) == OK
    assert ler_rodada(conn, rodada_id)["aprovada_em"] is None
    assert ultima_carga_aprovada(conn) is None


def test_abrir_duas_vezes_e_depois_aprovar_carimba_UMA_vez(conn):
    """Abrir é idempotente do ponto de vista do que importa: duas aberturas não
    criam duas pendências nem dois carimbos. (A checagem `if not pausada` em si é
    conforto, não correção — reabrir thread PAUSADA é inócuo, verificado; o que
    seria destrutivo é reabrir a CONCLUÍDA, e disso cuida a guarda própria.)"""
    saver = MemorySaver()
    rodada_id = _rodada(conn)
    assert _executar(conn, rodada_id, retomada=None, checkpointer=saver) == OK
    assert _executar(conn, rodada_id, retomada=None, checkpointer=saver) == OK
    assert ler_rodada(conn, rodada_id)["aprovada_em"] is None
    assert _executar(conn, rodada_id, retomada=aprovar_tacita(), checkpointer=saver) == OK
    assert ler_rodada(conn, rodada_id)["aprovada_por"] == "tácita"
    # e a segunda tentativa de carimbar é recusada, não somada
    assert _executar(conn, rodada_id, retomada=aprovar_tacita(), checkpointer=saver) == JA_APROVADA


def test_abrir_e_depois_aprovar_carimba_uma_vez(conn):
    """O fluxo desenhado: a pausa abre quando a lista sai e é retomada quando o dono
    decide, possivelmente em processo outro (aqui, chamada outra no mesmo saver)."""
    saver = MemorySaver()
    rodada_id = _rodada(conn)
    _executar(conn, rodada_id, retomada=None, checkpointer=saver)
    assert _executar(conn, rodada_id, retomada=aprovar_explicita("olavo"), checkpointer=saver) == OK
    assert ler_rodada(conn, rodada_id)["aprovada_por"] == "olavo"


# --- a guarda central: o carimbo é ÚNICO ---------------------------------------


def test_recusa_RE_carimbo_e_o_carimbo_original_fica_INTACTO(conn):
    """Re-carimbar deslocaria a janela que a segunda mede e poderia trocar a carga
    vigente. A recusa tem código próprio, e o valor anterior não é tocado."""
    antes = AGORA - timedelta(days=7)
    rodada_id = _rodada(conn, aprovada_em=antes, aprovada_por="olavo")
    assert _executar(conn, rodada_id, retomada=aprovar_explicita("outro")) == JA_APROVADA
    resumo = ler_rodada(conn, rodada_id)
    assert resumo["aprovada_por"] == "olavo"  # não sobrescrito
    assert resumo["aprovada_em"] == antes  # nem o instante


def test_marcar_aprovada_recusa_o_SEGUNDO_carimbo_na_origem(conn):
    """A guarda do primitivo, independente do runner: é a que vale quando o chamador
    for outro (o console, um agendador)."""
    rodada_id = _rodada(conn)
    primeiro = AGORA - timedelta(days=1)
    marcar_aprovada(conn, rodada_id, primeiro, "olavo")
    with pytest.raises(JaAprovada, match="JÁ aprovada"):
        marcar_aprovada(conn, rodada_id, AGORA, "outro")
    assert ler_rodada(conn, rodada_id)["aprovada_em"] == primeiro


def test_marcar_aprovada_ainda_recusa_rodada_INEXISTENTE_com_erro_proprio(conn):
    """As duas recusas exigem ação oposta de quem opera — não podem virar a mesma
    mensagem. Contraprova da guarda acima."""
    with pytest.raises(ValueError, match="nenhuma rodada de decisão") as e:
        marcar_aprovada(conn, 99_999_999, AGORA, "olavo")
    assert not isinstance(e.value, JaAprovada)


def test_thread_JA_DECIDIDA_nao_e_reaberta_e_o_registro_nao_e_carimbado(conn):
    """A armadilha que originou a fatia: reinvocar o grafo numa thread concluída NÃO
    é no-op — ele reinicia, reabre a interrupção, e a retomada seguinte carimba de
    novo. Aqui o Registro está sem carimbo (reprovação, ou sink que falhou), então a
    guarda do Registro não pega; quem pega é a do grafo."""
    saver = MemorySaver()
    rodada_id = _rodada(conn)
    # Conclui a thread SEM que o Registro receba carimbo (sink que não grava).
    from langgraph.types import Command

    from grafo.aprovacao import construir_grafo_aprovacao

    g = construir_grafo_aprovacao(aplicar=lambda _r, _p: None, checkpointer=saver)
    conf = thread_da_rodada(rodada_id)
    g.invoke({"rodada_id": rodada_id}, conf)
    g.invoke(Command(resume=aprovar_explicita("olavo")), conf)

    assert (
        _executar(conn, rodada_id, retomada=aprovar_tacita(), checkpointer=saver) == INCONSISTENTE
    )
    assert ler_rodada(conn, rodada_id)["aprovada_em"] is None  # não carimbou
    # Código PRÓPRIO, não o de "já aprovada": aqui não há aprovação nenhuma no
    # Registro, e o monitoramento lê o número, não a mensagem.
    assert INCONSISTENTE != JA_APROVADA


# --- as demais guardas ---------------------------------------------------------


def test_recusa_rodada_inexistente(conn):
    assert _executar(conn, 99_999_999, retomada=aprovar_tacita()) == NAO_APROVAVEL


def test_recusa_rodada_de_ACOMPANHAMENTO(conn):
    """Só a rodada de decisão é aprovada; a de segunda produz relatório."""
    rodada_id = _rodada(conn, tipo="acompanhamento", estado="completa")
    assert _executar(conn, rodada_id, retomada=aprovar_tacita()) == NAO_APROVAVEL


def test_recusa_rodada_ABORTADA(conn):
    """Aprovar uma abortada criaria carga vigente sem imóvel nenhum, e a segunda
    mediria contra ela — pior que não ter carga, porque parece que tem."""
    rodada_id = _rodada(conn, estado="abortada")
    assert _executar(conn, rodada_id, retomada=aprovar_tacita()) == NAO_APROVAVEL
    assert ler_rodada(conn, rodada_id)["aprovada_em"] is None


def _parametros_da_rodada(conn, rodada_id: int, parametros: dict) -> None:
    from psycopg.types.json import Json

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO registro.parametros_da_rodada (rodada_id, parametros) VALUES (%s, %s)",
            (rodada_id, Json(parametros)),
        )


def test_recusa_rodada_AMOSTRAL(conn):
    """A amostra decide sobre o recorte que a raspagem trouxe, não sobre o estoque.
    Aprová-la faria mil imóveis virarem a carga da semana, com milhares de posições
    vazias — e a segunda mediria contra ela. A marca é DADO, não prosa."""
    rodada_id = _rodada(conn, estado="degradada")
    _parametros_da_rodada(conn, rodada_id, {"recorte_pela_raspagem": {"imoveis": 12}})
    assert _executar(conn, rodada_id, retomada=aprovar_tacita()) == NAO_APROVAVEL
    assert ler_rodada(conn, rodada_id)["aprovada_em"] is None


def test_a_marca_amostral_NULA_nao_recusa(conn):
    """`_serializaveis` grava a chave sempre, nula quando não há recorte. Nulo não é
    marca — senão toda rodada gravada depois da A2 ficaria inaprovável."""
    rodada_id = _rodada(conn, estado="degradada")
    _parametros_da_rodada(conn, rodada_id, {"recorte_pela_raspagem": None})
    assert _executar(conn, rodada_id, retomada=aprovar_tacita()) == OK


def test_aceita_rodada_DEGRADADA(conn):
    """Contraprova das duas recusas acima: degradada entrega lista com limitação
    declarada (Spec §7.2) e É aprovável. Sem ela, um código que recusasse tudo
    passaria nos testes de recusa."""
    rodada_id = _rodada(conn, estado="degradada")
    assert _executar(conn, rodada_id, retomada=aprovar_tacita()) == OK
    assert ler_rodada(conn, rodada_id)["aprovada_em"] is not None


# --- ordem das cargas ----------------------------------------------------------


def test_recusa_aprovar_rodada_ANTIGA_quando_ha_mais_nova_aprovada(conn):
    """`ultima_carga_aprovada` ordena por `aprovada_em DESC`: aprovar hoje a rodada
    velha lhe daria o carimbo mais recente e a promoveria a carga vigente, fazendo a
    segunda medir uma lista que já foi substituída."""
    velha = _rodada(conn)
    nova = _rodada(conn, aprovada_em=AGORA - timedelta(days=1), aprovada_por="olavo")
    assert _executar(conn, velha, retomada=aprovar_tacita()) == FORA_DE_ORDEM
    assert ler_rodada(conn, velha)["aprovada_em"] is None
    assert ultima_carga_aprovada(conn) == nova  # a vigente não mudou


def test_a_flag_fora_de_ordem_permite_e_a_vigente_MUDA(conn):
    """A recusa é default, não proibição: o dono pode insistir. E o teste crava a
    consequência que a mensagem promete."""
    velha = _rodada(conn)
    _rodada(conn, aprovada_em=AGORA - timedelta(days=1), aprovada_por="olavo")
    assert _executar(conn, velha, retomada=aprovar_tacita(), fora_de_ordem=True) == OK
    assert ultima_carga_aprovada(conn) == velha  # exatamente o risco declarado


def test_a_busca_de_rodada_mais_nova_olha_ESTRITAMENTE_para_frente(conn):
    """A função não pode contar a PRÓPRIA rodada como "mais nova". Hoje a guarda de
    já-aprovada roda antes e esconde a diferença — `id >= ` passava a suíte inteira.
    Mas a ordem das guardas é livre: sob `>=`, bastaria alguém conferir a ordem antes
    do carimbo para uma rodada já aprovada sair pelo código de FORA_DE_ORDEM,
    apontando a causa errada para quem opera."""
    rid = _rodada(conn, aprovada_em=AGORA, aprovada_por="olavo")
    assert rodada_aprovada_mais_nova(conn, rid) is None


def test_recusa_carimbo_que_NAO_tornaria_a_rodada_a_carga_vigente(conn):
    """O cenário que a guarda por id deixava passar, e que o `--em` desta fatia
    tornou alcançável em dois comandos comuns: a rodada 11 é aprovada tarde, e a 12 é
    aprovada com `--em` ANTERIOR ao carimbo da 11. Por id a guarda passa (12 > 11), o
    carimbo entra — e a vigente continua sendo a 11. O dono aprova a lista nova e a
    segunda segue medindo a antiga, sem aviso."""
    antiga = _rodada(conn, aprovada_em=AGORA - timedelta(hours=2), aprovada_por="olavo")
    nova = _rodada(conn, fim=AGORA - timedelta(days=3))
    fim_de_semana = AGORA - timedelta(days=2)  # anterior ao carimbo da antiga
    assert _executar(conn, nova, retomada=aprovar_tacita(), em=fim_de_semana) == FORA_DE_ORDEM
    assert ler_rodada(conn, nova)["aprovada_em"] is None
    assert ultima_carga_aprovada(conn) == antiga


def test_a_flag_libera_o_carimbo_que_nao_vira_vigente_e_a_consequencia_se_cumpre(conn):
    """Contraprova e cumprimento da promessa da mensagem: com a flag o carimbo entra,
    e a vigente REALMENTE continua sendo a outra."""
    antiga = _rodada(conn, aprovada_em=AGORA - timedelta(hours=2), aprovada_por="olavo")
    nova = _rodada(conn, fim=AGORA - timedelta(days=3))
    fim_de_semana = AGORA - timedelta(days=2)
    assert (
        _executar(conn, nova, retomada=aprovar_tacita(), em=fim_de_semana, fora_de_ordem=True) == OK
    )
    assert ler_rodada(conn, nova)["aprovada_em"] == fim_de_semana
    assert ultima_carga_aprovada(conn) == antiga  # exatamente o que a mensagem avisa


def test_a_eleicao_da_vigente_e_por_INSTANTE_nao_por_id(conn):
    """Contrato da consulta, isolado da ordem das guardas: uma rodada de id MAIOR com
    carimbo ANTERIOR não desbanca a de id menor. Sem esta trava, comparar ids
    passaria pela suíte inteira."""
    antiga = _rodada(conn, aprovada_em=AGORA - timedelta(hours=2), aprovada_por="olavo")
    nova = _rodada(conn)
    assert nova > antiga
    # carimbar a NOVA num instante anterior deixaria a ANTIGA vigente
    assert carga_que_seguiria_vigente(conn, nova, AGORA - timedelta(days=2)) == antiga
    # e num instante posterior, ela mesma passa a ser a vigente
    assert carga_que_seguiria_vigente(conn, nova, AGORA) is None


def test_rodada_MAIS_NOVA_que_a_aprovada_nao_dispara_a_guarda(conn):
    """Contraprova: a guarda olha para FRENTE (`id > %s`), não para qualquer
    aprovação existente. Sem ela, a segunda sexta da vida seria irrecusável."""
    _rodada(conn, aprovada_em=AGORA - timedelta(days=7), aprovada_por="olavo")
    nova = _rodada(conn)
    assert _executar(conn, nova, retomada=aprovar_tacita()) == OK


# --- o instante do carimbo -----------------------------------------------------


def test_o_carimbo_e_o_instante_DECLARADO_nao_o_relogio(conn):
    """`aprovada_em` é o proxy de "a carga entrou no ar". Aprovar na segunda uma
    carga aplicada na sexta, carimbando "agora", deslocaria a janela de medição da
    segunda em três dias sem nada acusar."""
    # O cenário real: a sexta terminou há três dias, a carga entrou no ar logo
    # depois, e o dono só carimba na segunda.
    sexta = AGORA - timedelta(days=3)
    rodada_id = _rodada(conn, fim=sexta)
    real = sexta + timedelta(minutes=30)
    assert _executar(conn, rodada_id, retomada=aprovar_tacita(), em=real) == OK
    assert ler_rodada(conn, rodada_id)["aprovada_em"] == real
    assert ler_rodada(conn, rodada_id)["aprovada_em"] != AGORA  # não é o relógio


def test_instante_no_FUTURO_e_recusado(conn):
    rodada_id = _rodada(conn)
    futuro = AGORA + timedelta(hours=1)
    assert _executar(conn, rodada_id, retomada=aprovar_tacita(), em=futuro) == VALOR_INVALIDO
    assert ler_rodada(conn, rodada_id)["aprovada_em"] is None


def test_instante_ANTERIOR_ao_fim_da_rodada_e_recusado(conn):
    """A carga não pode ter entrado no ar antes de a lista existir."""
    rodada_id = _rodada(conn)
    assert (
        _executar(conn, rodada_id, retomada=aprovar_tacita(), em=INICIO - timedelta(hours=1))
        == VALOR_INVALIDO
    )


def test_em_NAIVE_e_normalizado_ao_fuso_local(conn):
    """A coluna é `timestamptz` e `janela_da_carga` normaliza ao fuso local. Naive
    deixaria o Postgres interpretar pelo fuso da SESSÃO, e a janela medida mudaria
    conforme quem conectou."""
    sexta = AGORA - timedelta(days=3)
    rodada_id = _rodada(conn, fim=sexta)
    naive = (sexta + timedelta(minutes=30)).replace(tzinfo=None)
    assert _executar(conn, rodada_id, retomada=aprovar_tacita(), em=naive) == OK
    assert ler_rodada(conn, rodada_id)["aprovada_em"] == naive.astimezone()


# --- ensaio --------------------------------------------------------------------


def test_dry_run_confere_e_NAO_grava(conn):
    rodada_id = _rodada(conn)
    assert _executar(conn, rodada_id, retomada=aprovar_tacita(), dry_run=True) == OK
    assert ler_rodada(conn, rodada_id)["aprovada_em"] is None


def test_dry_run_ainda_RECUSA_o_que_seria_recusado(conn):
    """Ensaio que aprova tudo não serve para conferir antes de valer."""
    rodada_id = _rodada(conn, estado="abortada")
    assert _executar(conn, rodada_id, retomada=aprovar_tacita(), dry_run=True) == NAO_APROVAVEL


# --- `conferir` isolado (a lógica de guarda, sem grafo) ------------------------


def test_conferir_devolve_o_instante_quando_tudo_passa(conn):
    rodada_id = _rodada(conn)
    assert conferir(conn, rodada_id, em=None, agora=AGORA, fora_de_ordem=False) == AGORA


def test_conferir_levanta_recusa_com_o_codigo_da_causa(conn):
    rodada_id = _rodada(conn, aprovada_em=AGORA, aprovada_por="olavo")
    with pytest.raises(Recusa) as e:
        conferir(conn, rodada_id, em=None, agora=AGORA, fora_de_ordem=False)
    assert e.value.codigo == JA_APROVADA


# --- `main`: o contrato da linha de comando -----------------------------------


def test_main_exige_subcomando():
    """Sem subcomando o argparse sai com 2 — reservado, como nos outros runners:
    sem a reserva, um comando digitado errado sairia com o código de uma recusa
    legítima e o monitoramento o trataria como decisão do dono."""
    from executar.aprovar import main

    with pytest.raises(SystemExit) as e:
        main([])
    assert e.value.code == 2


def test_main_aprovar_exige_quem_aprovou():
    """`aprovada_por` distingue a aprovação explícita da tácita (D-001). Sem `--por`
    a explícita viraria anônima, indistinguível de decurso de prazo."""
    from executar.aprovar import main

    with pytest.raises(SystemExit) as e:
        main(["aprovar", "7"])
    assert e.value.code == 2


def test_main_sem_postgres_url_sai_por_FONTE(monkeypatch, tmp_path):
    """Fail-fast de `conexao.url`, traduzido para o código de falha de fonte — não
    para o de escrita: nada chegou a ser escrito.

    O `chdir` é parte do contrato, não conveniência de teste: `main` carrega o `.env`
    do diretório CORRENTE, então apagar a variável do ambiente não basta enquanto
    houver um `.env` ao lado — ele a reporia. Aqui se testa a ausência de verdade."""
    from executar.aprovar import FONTE, main

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    assert main(["tacita", "7"]) == FONTE


def test_main_pega_a_postgres_url_do_env_do_diretorio_corrente(monkeypatch, tmp_path):
    """O outro lado, e a razão de o carregador existir: com um `.env` ao lado, o
    comando roda sem o operador exportar nada. Antes disto não havia forma suportada
    de popular o ambiente — `set -a; . .env` é justamente o que a documentação proíbe,
    porque o shell expandiria metacaractere do valor."""
    from executar.aprovar import FONTE, main

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    (tmp_path / ".env").write_text(
        'POSTGRES_URL="postgresql:///nao-existe-de-proposito"\n', encoding="utf-8"
    )
    # Passa da guarda de variável ausente e falha adiante, ao tentar conectar — que
    # é o que prova que a variável foi lida. Continua FONTE, por outro motivo.
    assert main(["tacita", "7"]) == FONTE
    assert os.environ["POSTGRES_URL"] == "postgresql:///nao-existe-de-proposito"


def test_main_recusa_id_nao_numerico():
    from executar.aprovar import main

    with pytest.raises(SystemExit) as e:
        main(["tacita", "sete"])
    assert e.value.code == 2


def test_o_checkpointer_nasce_ANTES_de_a_conexao_do_registro_abrir(conn):
    """Ordem é CORREÇÃO aqui, não estilo. `PostgresSaver.setup()` roda `CREATE INDEX
    CONCURRENTLY`, que espera TODA transação concorrente do banco terminar — e o
    Registro e o checkpointer dividem o mesmo Postgres por desenho do projeto. Com a
    conexão do Registro já aberta, o índice espera por ela, ela espera o grafo, e o
    comando trava para sempre. Travou de verdade, e só apareceu ao simular o passo de
    CI: nenhum teste com MemorySaver o alcança, porque o impasse é entre duas
    conexões do MESMO Postgres."""
    from contextlib import contextmanager

    abertas: list[int] = []

    @contextmanager
    def registro():
        abertas.append(1)
        try:
            yield conn
        finally:
            abertas.pop()

    quando_nasceu: list[int] = []

    def checkpointer_de(_dsn: str):
        quando_nasceu.append(len(abertas))
        return nullcontext(MemorySaver())

    rodada_id = _rodada(conn)
    assert (
        executar(
            rodada_id,
            retomada=aprovar_tacita(),
            em=None,
            agora=AGORA,
            fora_de_ordem=False,
            dry_run=False,
            conectar_registro=registro,
            checkpointer_de=checkpointer_de,
        )
        == OK
    )
    assert quando_nasceu == [0], (
        "o checkpointer nasceu com conexão do Registro já aberta — é o impasse do "
        "CREATE INDEX CONCURRENTLY, e ele trava sem erro"
    )


# --- o veredito digitado é o que vale (achado do portão de código) ---------------


def _explode(*_a, **_k):
    raise RuntimeError("sink caiu")


def test_veredito_digitado_nao_e_TROCADO_pelo_anterior_apos_falha_do_sink(conn, monkeypatch):
    """O defeito mais grave que os portões apanharam. O LangGraph tem QUATRO estados
    aqui, e classificar por "tem próximo nó" colapsava dois que exigem tratamento
    oposto: a thread AGUARDANDO o dono e a thread TRAVADA no `aplicar` porque o sink
    levantou. Na travada não há interrupção pendente, então o `Command(resume=...)`
    não é consumido e o nó roda de novo com o veredito ANTERIOR — o dono digita
    `aprovar --por olavo` e o Registro grava `"tácita"`, com saída 0. Na direção
    oposta é pior: atribui a uma PESSOA uma aprovação que ela não deu. É justo o
    campo que a D-001 criou para distinguir as duas."""
    import executar.aprovar as mod

    saver = MemorySaver()
    rodada_id = _rodada(conn)
    monkeypatch.setattr(mod, "marcar_aprovada", _explode)
    # A falha do sink escapa do runner (só `Recusa` é traduzida aqui); quem a
    # traduz em código de saída é o `main`, como nos outros runners.
    with pytest.raises(RuntimeError):
        _executar(conn, rodada_id, retomada=aprovar_tacita(), checkpointer=saver)
    monkeypatch.undo()

    # A thread ficou com o veredito "tácita" consumido e o Registro sem carimbo.
    assert ler_rodada(conn, rodada_id)["aprovada_em"] is None
    assert (
        _executar(conn, rodada_id, retomada=aprovar_explicita("olavo"), checkpointer=saver)
        == INCONSISTENTE
    )
    assert ler_rodada(conn, rodada_id)["aprovada_por"] is None  # não gravou "tácita"


def test_refazer_descarta_a_thread_travada_e_grava_o_veredito_CERTO(conn, monkeypatch):
    """A saída do código 9. Sem ela, a rodada fica num estado que nenhum caminho
    oferecido desfaz — e é justo o estado que exige intervenção."""
    import executar.aprovar as mod

    saver = MemorySaver()
    rodada_id = _rodada(conn)
    monkeypatch.setattr(mod, "marcar_aprovada", _explode)
    with pytest.raises(RuntimeError):
        _executar(conn, rodada_id, retomada=aprovar_tacita(), checkpointer=saver)
    monkeypatch.undo()

    assert (
        _executar(
            conn,
            rodada_id,
            retomada=aprovar_explicita("olavo"),
            checkpointer=saver,
            refazer=True,
        )
        == OK
    )
    assert ler_rodada(conn, rodada_id)["aprovada_por"] == "olavo"  # o que foi digitado


def test_refazer_NAO_produz_carimbo_duplo(conn):
    """`--refazer` só age quando o Registro não tem carimbo: a guarda de já-aprovada
    roda antes e não é contornável pela flag."""
    rodada_id = _rodada(conn, aprovada_em=AGORA - timedelta(days=1), aprovada_por="olavo")
    assert _executar(conn, rodada_id, retomada=aprovar_tacita(), refazer=True) == JA_APROVADA
    assert ler_rodada(conn, rodada_id)["aprovada_por"] == "olavo"


# --- a fiação da linha de comando (achado do portão de código) -------------------


def test_main_repassa_CADA_flag_para_o_runner(monkeypatch):
    """Seis mutações sobreviviam à suíte inteira, quatro delas também ao CI — entre
    elas `dry_run=False` (o `--dry-run` documentado como "não grava" passaria a
    gravar) e `em=None` (o `--em` anulado em silêncio). A fiação é a única camada que
    traduz o que o dono digitou, e nada a segurava."""
    import executar.aprovar as mod

    vistos: dict = {}

    def falso(rodada_id, **kw):
        vistos.update(rodada_id=rodada_id, **kw)
        return OK

    monkeypatch.setattr(mod, "executar", falso)
    assert (
        mod.main(
            [
                "aprovar",
                "12",
                "--por",
                "olavo",
                "--dry-run",
                "--fora-de-ordem",
                "--refazer",
                "--em",
                "2026-09-04T18:30",
            ]
        )
        == OK
    )
    assert vistos["rodada_id"] == 12
    assert vistos["dry_run"] is True
    assert vistos["fora_de_ordem"] is True
    assert vistos["refazer"] is True
    assert vistos["em"] == datetime(2026, 9, 4, 18, 30)
    assert vistos["retomada"] == aprovar_explicita("olavo")
    # aware, senão a comparação com `agora` na guarda de instante levanta TypeError
    assert vistos["agora"].tzinfo is not None

    # E o NEGATIVO, sem o qual "flag fixada em True" passaria: sem as flags, todas
    # têm de chegar desligadas. É o caso do dia a dia — e é nele que uma guarda
    # fixada em `True` desativaria a recusa de fora-de-ordem em silêncio.
    vistos.clear()
    assert mod.main(["tacita", "12"]) == OK
    assert vistos["dry_run"] is False
    assert vistos["fora_de_ordem"] is False
    assert vistos["refazer"] is False
    assert vistos["em"] is None


def test_main_traduz_cada_subcomando_na_retomada_certa(monkeypatch):
    import executar.aprovar as mod

    vistos: dict = {}
    monkeypatch.setattr(mod, "executar", lambda rid, **kw: vistos.update(kw) or OK)

    mod.main(["tacita", "3"])
    assert vistos["retomada"] == aprovar_tacita()
    mod.main(["abrir", "3"])
    assert vistos["retomada"] is None  # abrir não decide
    mod.main(["aprovar", "3", "--por", "olavo"])
    assert vistos["retomada"] == aprovar_explicita("olavo")


def test_main_traduz_JaAprovada_no_codigo_proprio(monkeypatch):
    """A corrida em que o carimbo nasce ENTRE a conferência e o sink sai por 7, não
    pelo código genérico de escrita."""
    import executar.aprovar as mod

    def levanta(rid, **kw):
        raise JaAprovada("já aprovada")

    monkeypatch.setattr(mod, "executar", levanta)
    assert mod.main(["tacita", "3"]) == JA_APROVADA


# --- guardas de tipo e de namespace ---------------------------------------------


def test_marcar_aprovada_recusa_rodada_de_ACOMPANHAMENTO(conn):
    """A guarda `tipo = 'decisao'` no UPDATE — a que o docstring diz valer quando o
    chamador for outro. Sem ela, um relatório de segunda receberia carimbo de
    aprovação e viraria "carga vigente"."""
    rodada_id = _rodada(conn, tipo="acompanhamento")
    with pytest.raises(ValueError, match="nenhuma rodada de decisão"):
        marcar_aprovada(conn, rodada_id, AGORA, "olavo")
    assert ler_rodada(conn, rodada_id)["aprovada_em"] is None


def test_o_thread_id_tem_namespace_proprio(conn):
    """Hoje é o único usuário do checkpointer; quando o grafo de sexta ganhar o seu,
    um `thread_id` sem prefixo colidiria em silêncio."""
    assert thread_da_rodada(7) == {"configurable": {"thread_id": "rodada-7"}}


def test_retomada_sem_autor_grava_NULO_e_nao_string_vazia(conn):
    """Um resume montado à mão (fora dos construtores) pode trazer `por` vazio. O
    Registro guarda NULO — "não sei quem" — em vez de uma string vazia que passaria
    por autor conhecido."""
    rodada_id = _rodada(conn)
    assert _executar(conn, rodada_id, retomada={"decisao": "aprovada", "por": ""}) == OK
    assert ler_rodada(conn, rodada_id)["aprovada_por"] is None
