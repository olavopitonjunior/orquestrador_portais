"""A fila de operação: dedup, reivindicação atômica e desfecho coerente.

O que estes testes protegem não é conveniência: é a única barreira contra rodada
duplicada. `gravar_rodada_decisao` não tem chave natural de deduplicação — duas
chamadas produzem duas rodadas válidas e indistinguíveis, e nada no esquema do
Registro impede. A dedup subiu de nível para cá, então é aqui que ela precisa
morder.
"""

from __future__ import annotations

import pytest

from dados.operacao import (
    TIPOS,
    Trabalho,
    TrabalhoEmVoo,
    bater_ponto,
    concluir,
    criar,
    evento,
    guardar_parametros,
    ler_trabalho,
    listar_trabalhos,
    reivindicar,
)
from dados.registro.conexao import conectar


@pytest.fixture
def conn():
    """Transação por teste, desfeita no fim — o mesmo isolamento dos testes do
    Registro. Na máquina do gestor este banco é o VIGENTE, então nada aqui pode
    persistir (ver tests/README.md)."""
    c = conectar()
    c.autocommit = False
    yield c
    c.rollback()
    c.close()


def test_criar_devolve_id_e_nasce_pendente(conn):
    tid = criar(conn, "sexta", pedido_por="olavo", argumentos={"dry_run": True})
    t = ler_trabalho(conn, tid)
    assert t is not None
    assert (t.tipo, t.estado, t.pedido_por) == ("sexta", "pendente", "olavo")
    assert t.argumentos == {"dry_run": True}
    assert t.codigo_saida is None and t.rodada_id is None


def test_dois_do_mesmo_tipo_em_voo_e_RECUSADO(conn):
    """O duplo-clique no botão. Sem esta guarda, seriam duas rodadas sobre o mesmo
    estoque, ambas gravadas, sem nada no Registro para distingui-las."""
    criar(conn, "sexta")
    with pytest.raises(TrabalhoEmVoo):
        criar(conn, "sexta")


def test_tipos_DIFERENTES_convivem_em_voo(conn):
    """A guarda é por tipo, não global: raspar enquanto se aprova uma rodada antiga é
    legítimo, e proibir isso travaria operação sem proteger nada."""
    criar(conn, "sexta")
    criar(conn, "canario")
    assert len({t.tipo for t in listar_trabalhos(conn)} & {"sexta", "canario"}) == 2


def test_depois_de_concluir_o_tipo_LIBERA(conn):
    """Parcial de propósito: o histórico repete tipos indefinidamente."""
    primeiro = criar(conn, "sexta")
    reivindicar(conn)
    concluir(conn, primeiro, codigo_saida=0)
    segundo = criar(conn, "sexta")  # não levanta
    assert segundo != primeiro


def test_reivindicar_marca_executando_e_grava_pid(conn):
    tid = criar(conn, "sexta")
    t = reivindicar(conn)
    assert t is not None and t.id == tid
    assert t.estado == "executando" and t.iniciado_em is not None
    assert t.pid and t.pid > 0


def test_reivindicar_sem_fila_devolve_None(conn):
    assert reivindicar(conn, ["publicar"]) is None


def test_reivindicar_respeita_o_filtro_de_tipo(conn):
    criar(conn, "canario")
    assert reivindicar(conn, ["sexta"]) is None
    assert (t := reivindicar(conn, ["canario"])) is not None and t.tipo == "canario"


def test_reivindicar_pega_o_MAIS_ANTIGO(conn):
    """Ordem de chegada. Sem ela, um pedido podia envelhecer indefinidamente enquanto
    outros do mesmo tipo entram e saem."""
    primeiro = criar(conn, "sexta")
    reivindicar(conn)
    concluir(conn, primeiro, codigo_saida=0)
    segundo = criar(conn, "sexta")
    t = reivindicar(conn, ["sexta"])
    assert t is not None and t.id == segundo


def test_concluir_com_zero_e_ok_e_com_outro_e_falhou(conn):
    tid = criar(conn, "sexta")
    reivindicar(conn)
    concluir(conn, tid, codigo_saida=3)
    t = ler_trabalho(conn, tid)
    assert t is not None and t.estado == "falhou" and t.codigo_saida == 3


def test_concluir_guarda_a_rodada_quando_ela_existe(conn):
    """E aceita None: rodada ABORTADA não deixa nenhuma linha no Registro, nem
    cabeçalho. É por isso que o trabalho é entidade própria — sem ele, um aborto não
    teria onde ser contado."""
    tid = criar(conn, "sexta")
    reivindicar(conn)
    concluir(conn, tid, codigo_saida=4, rodada_id=None)
    t = ler_trabalho(conn, tid)
    assert t is not None and t.rodada_id is None and t.codigo_saida == 4


def test_concluir_duas_vezes_e_RECUSADO(conn):
    """Concluir o que já foi concluído esconderia uma execução perdida — a segunda
    escrita sobreporia o desfecho da primeira sem nada acusar."""
    tid = criar(conn, "sexta")
    reivindicar(conn)
    concluir(conn, tid, codigo_saida=0)
    with pytest.raises(ValueError):
        concluir(conn, tid, codigo_saida=0)


def test_concluir_o_que_ninguem_reivindicou_e_RECUSADO(conn):
    tid = criar(conn, "sexta")
    with pytest.raises(ValueError):
        concluir(conn, tid, codigo_saida=0)


def test_o_banco_recusa_estado_terminal_sem_desfecho(conn):
    """A guarda de coerência mora no CHECK, não neste código: um caminho futuro que
    escreva direto na tabela não pode produzir 'ok' sem código de saída, senão a UI
    teria de adivinhar qual campo acreditar."""
    tid = criar(conn, "sexta")
    with pytest.raises(Exception):  # noqa: B017 — o erro é do banco, não desta camada
        with conn.cursor() as cur:
            cur.execute("UPDATE operacao.trabalho SET estado='ok' WHERE id=%s", (tid,))


def test_eventos_ficam_na_ordem_e_carregam_o_no_do_grafo(conn):
    tid = criar(conn, "sexta")
    evento(conn, tid, "começou")
    evento(conn, tid, "coletor pronto", no_grafo="coletor_interno")
    evento(conn, tid, "falhou", nivel="erro")
    with conn.cursor() as cur:
        cur.execute(
            "SELECT texto, nivel, no_grafo FROM operacao.trabalho_evento "
            "WHERE trabalho_id = %s ORDER BY id",
            (tid,),
        )
        linhas = cur.fetchall()
    assert [linha[0] for linha in linhas] == ["começou", "coletor pronto", "falhou"]
    assert linhas[1][2] == "coletor_interno"
    assert linhas[2][1] == "erro"


def test_bater_ponto_e_idempotente_e_atualiza(conn):
    bater_ponto(conn)
    with conn.cursor() as cur:
        cur.execute("SELECT visto_em FROM operacao.trabalhador WHERE nome='principal'")
        primeiro = cur.fetchone()
    bater_ponto(conn)
    with conn.cursor() as cur:
        cur.execute("SELECT count(*), max(visto_em) FROM operacao.trabalhador")
        quantos, ultimo = cur.fetchone()
    assert quantos == 1, "o batimento criou linha nova em vez de atualizar"
    assert primeiro is not None and ultimo >= primeiro[0]


def test_guardar_parametros_e_append_only(conn):
    a = guardar_parametros(conn, "razao = 0.5\n", por="olavo")
    b = guardar_parametros(conn, "razao = 0.7\n", por="olavo")
    assert a != b, "a segunda submissão sobrescreveu a primeira"
    with conn.cursor() as cur:
        cur.execute("SELECT toml FROM operacao.parametros_declarados WHERE id IN (%s,%s)", (a, b))
        assert {linha[0] for linha in cur.fetchall()} == {"razao = 0.5\n", "razao = 0.7\n"}


def test_tipo_desconhecido_e_recusado_ANTES_de_tocar_o_banco(conn):
    with pytest.raises(ValueError, match="desconhecido"):
        criar(conn, "inventado")


@pytest.mark.parametrize("tipo", TIPOS)
def test_todo_tipo_declarado_e_aceito_pelo_banco(conn, tipo: str):
    """Contraprova do CHECK: a tupla em Python e a lista no DDL precisam continuar
    dizendo a mesma coisa. Divergindo, o console ofereceria um botão cujo INSERT o
    banco recusa."""
    assert isinstance(ler_trabalho(conn, criar(conn, tipo)), Trabalho)


# --------------------------------------------------------------- o trabalhador

from datetime import UTC, datetime  # noqa: E402

from executar.trabalhador import COLETOR, RAIZ, ArgumentosInvalidos, comando  # noqa: E402


def _t(tipo: str, **argumentos) -> Trabalho:
    return Trabalho(
        id=1,
        tipo=tipo,
        estado="executando",
        pedido_em=datetime.now(UTC),
        pedido_por=None,
        argumentos=argumentos,
    )


def test_comando_da_sexta_leva_o_toml_e_roda_da_raiz():
    """O `cwd` é fixado, não herdado: `carregar_env` procura o `.env` no diretório
    corrente, e um trabalhador iniciado pelo agendador do sistema faria a rodada
    falhar com "variável ausente" — diagnóstico errado para "rodei do lugar errado"."""
    argv, cwd = comando(_t("sexta", parametros="/tmp/p.toml"))
    assert argv[1:4] == ["-m", "executar.sexta", "--parametros"]
    assert "/tmp/p.toml" in argv
    assert cwd == RAIZ


def test_a_sexta_SEM_parametros_e_recusada_antes_de_executar():
    """Treze dos catorze parâmetros são nulos e não há default: enfileirar uma sexta
    sem TOML é pedido malformado, e falhar aqui custa nada — falhar depois custa uma
    conexão ao Newcore e a espera do dono."""
    with pytest.raises(ArgumentosInvalidos, match="parametros"):
        comando(_t("sexta"))


def test_comando_da_sexta_encaixa_as_opcoes_declaradas():
    argv, _ = comando(
        _t("sexta", parametros="/tmp/p.toml", externo="/tmp/out", hoje="2026-09-04", dry_run=True)
    )
    assert "--externo" in argv and "/tmp/out" in argv
    assert "--hoje" in argv and "2026-09-04" in argv
    assert "--dry-run" in argv


def test_a_segunda_nao_exige_toml():
    """A segunda lê só o banco: exigir parâmetros dela seria copiar a regra da sexta
    para onde ela não vale."""
    argv, cwd = comando(_t("segunda"))
    assert argv[1:] == ["-m", "executar.segunda"] and cwd == RAIZ


def test_a_segunda_NAO_recebe_as_opcoes_que_so_a_sexta_tem():
    """`--eventos` e `--resultado` existem só na sexta. Passá-las à segunda faria o
    argparse recusar o comando inteiro — e o trabalho falharia por um argumento que
    ninguém pediu, com mensagem de uso em vez de diagnóstico."""
    argv, _ = comando(_t("segunda"))
    assert "--eventos" not in argv and "--resultado" not in argv


def test_a_sexta_RECEBE_os_arquivos_de_evento_e_resultado():
    """É por eles que o progresso chega à tela e o `rodada_id` chega ao Registro de
    operação — a alternativa seria parsear prosa de log."""
    argv, _ = comando(_t("sexta", parametros="/tmp/p.toml"))
    assert "--eventos" in argv and "--resultado" in argv
    assert any(a.endswith("trabalho-1.ndjson") for a in argv)
    assert any(a.endswith("trabalho-1.json") for a in argv)


@pytest.mark.parametrize(("tipo", "script"), [("canario", "canary"), ("full", "full")])
def test_a_raspagem_roda_pelos_scripts_do_package_json(tipo: str, script: str):
    """`npm run`, não `node` direto: os scripts são o contrato documentado do raspador
    e o runbook do operador manda usá-los."""
    argv, cwd = comando(_t(tipo))
    assert argv == ["npm", "run", script] and cwd == COLETOR


def test_aprovar_exige_rodada_e_autor():
    """Sem `por` restaria a aprovação tácita, que AFIRMA que um prazo decorreu — e o
    prazo é o parâmetro pendente nº 10, nulo."""
    with pytest.raises(ArgumentosInvalidos, match="por"):
        comando(_t("aprovar", rodada_id=12))
    argv, _ = comando(_t("aprovar", rodada_id=12, por="olavo"))
    assert argv[1:] == ["-m", "executar.aprovar", "aprovar", "12", "--por", "olavo"]


def test_tipo_sem_comando_e_recusado():
    with pytest.raises(ArgumentosInvalidos):
        comando(_t("publicar"))


def test_nenhum_comando_passa_por_shell():
    """`argv` é lista, sempre: um caminho de TOML com espaço ou metacaractere não pode
    virar dois argumentos nem executar nada."""
    argv, _ = comando(_t("sexta", parametros="/tmp/com espaço; echo x.toml"))
    assert "/tmp/com espaço; echo x.toml" in argv
    assert not any(";" in parte for parte in argv[:4])


def test_depois_do_TrabalhoEmVoo_a_conexao_CONTINUA_utilizavel(conn):
    """O caminho que o docstring chama de normal, e que estava quebrado.

    Uma violação de unicidade ABORTA a transação do Postgres. Traduzir a exceção não
    desfaz isso: sem savepoint, a conexão fica envenenada e o próximo comando estoura
    com `InFailedSqlTransaction`. E o próximo comando é justamente o que o console faz
    — capturar `TrabalhoEmVoo` e então LER a fila para montar a mensagem "já está
    rodando". A suíte não via porque o teste da guarda terminava no `raises`.
    """
    primeiro = criar(conn, "sexta")
    with pytest.raises(TrabalhoEmVoo):
        criar(conn, "sexta")
    # A leitura seguinte é o ponto: é ela que o console faz, e é ela que estourava.
    em_voo = [t for t in listar_trabalhos(conn) if t.estado in ("pendente", "executando")]
    assert any(t.id == primeiro for t in em_voo)
    # E a conexão continua boa para escrever, não só para ler.
    evento(conn, primeiro, "console explicou ao operador")


def test_cancelado_SEM_hora_e_recusado_pelo_banco(conn):
    """`cancelado` é terminal e precisa ter hora, mesmo sem código de saída.

    Ninguém escreve `cancelado` ainda — falta o recuperador de trabalho órfão,
    registrado em `bug.md`. A guarda entra agora justamente por isso: quando esse
    código for escrito, um cancelado SEM `terminado_em` — indistinguível de
    `executando` para quem olha os tempos — já não é representável.
    """
    tid = criar(conn, "sexta")
    reivindicar(conn)
    with pytest.raises(Exception):  # noqa: B017 — a guarda é do banco, não desta camada
        with conn.cursor() as cur:
            cur.execute("UPDATE operacao.trabalho SET estado='cancelado' WHERE id=%s", (tid,))


def test_cancelado_COM_hora_e_aceito(conn):
    """E o caminho que o recuperador vai usar precisa passar — senão a guarda acima
    impediria justamente o conserto que ela existe para viabilizar."""
    tid = criar(conn, "sexta")
    reivindicar(conn)
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE operacao.trabalho SET estado='cancelado', terminado_em=now() WHERE id=%s",
            (tid,),
        )
    t = ler_trabalho(conn, tid)
    assert t is not None and t.estado == "cancelado" and t.codigo_saida is None
