"""Testes da FIAÇÃO do ponto de entrada da sexta.

Sem banco: `conectar` e `escrever_planilha` são monkeypatchados, e os testes de
`main` só percorrem os caminhos que retornam ANTES de o grafo tocar o Newcore.

O que se prova aqui é o que não cabe em comentário: que a rodada não sai sem os
parâmetros do dono, que a fiação do coletor externo é tudo-ou-nada, que falha de
escrita não é confundida com falha de fonte, e que uma VIOLAÇÃO DE INVARIANTE
apanhada pelo crivo não sai com o mesmo código de "não havia estoque".
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import executar.sexta as mod
from config.parametros import carregar
from dominio.penalidades import ImovelPenalizavel
from grafo.estado import Estado

EXEMPLO = Path(__file__).resolve().parent.parent / "docs" / "parametros-da-rodada.exemplo.toml"
AGORA = datetime(2026, 9, 4, 9, 0)
HOJE = date(2026, 9, 4)


@pytest.fixture
def parametros():
    return carregar(EXEMPLO)


@pytest.fixture
def arquivo_valido(tmp_path):
    """Cópia do modelo FORA do repositório — que é como ele deve ser usado. O
    original é recusado por `main` de propósito."""
    destino = tmp_path / "parametros-da-rodada.toml"
    destino.write_text(EXEMPLO.read_text(encoding="utf-8"), encoding="utf-8")
    return destino


def _estado(**kw):
    base = {"resultado": object(), "estado": Estado.COMPLETA, "prontos": {}}
    return {**base, **kw}


def _resultado_falso():
    """O mínimo que `executar` toca no `ResultadoDecisao` para montar as notas."""
    return SimpleNamespace(
        alocacao=SimpleNamespace(super_destaque=(), destaque=()),
        relaxamento=SimpleNamespace(deficit_restante=0, recuperados=()),
    )


# --- a rodada não sai sem os parâmetros do dono -------------------------------


def test_parametros_e_obrigatorio():
    """Sem `--parametros` não há rodada: treze dos quatorze são nulos, e um default
    aqui seria o valor inventado que o CLAUDE.md proíbe — invisível na planilha."""
    with pytest.raises(SystemExit) as e:
        mod.main([])
    assert e.value.code == 2  # argparse: argumento obrigatório ausente


def test_arquivo_de_parametros_inexistente_sai_com_5(tmp_path):
    """Código próprio: nada rodou e nada foi tocado. Tratá-lo como falha de fonte
    (3) mandaria alguém investigar o Newcore por causa de um caminho errado."""
    assert mod.main(["--parametros", str(tmp_path / "nao-existe.toml")]) == 5


def test_parametro_faltando_sai_com_5(tmp_path):
    arquivo = tmp_path / "incompleto.toml"
    arquivo.write_text("[semelhanca]\ndesconto_fragil = 0.5\n", encoding="utf-8")
    assert mod.main(["--parametros", str(arquivo)]) == 5


def test_toml_malformado_sai_com_5(tmp_path):
    arquivo = tmp_path / "torto.toml"
    arquivo.write_text("[semelhanca\n", encoding="utf-8")
    assert mod.main(["--parametros", str(arquivo)]) == 5


def test_modelo_ilustrativo_e_recusado_como_entrada_real(caplog):
    """O modelo CARREGA com sucesso e mora no repositório: sem esta recusa sairia
    dele uma planilha completa, de aparência normal, construída sobre números que o
    próprio arquivo declara ilustrativos."""
    assert mod.main(["--parametros", str(EXEMPLO)]) == 5
    assert "MODELO" in caplog.text


def test_modelo_recusado_mesmo_por_caminho_relativo(monkeypatch):
    """A recusa compara o caminho RESOLVIDO — senão bastaria invocá-lo por um
    caminho relativo ou com `..` no meio para contorná-la sem querer."""
    monkeypatch.chdir(EXEMPLO.parent)
    assert mod.main(["--parametros", "./parametros-da-rodada.exemplo.toml"]) == 5


def test_codigo_2_fica_reservado_ao_argparse():
    """Mesma reserva da segunda: sem ela, um argumento digitado errado no agendador
    sairia com um código semântico e viraria no-op benigno no monitoramento."""
    with pytest.raises(SystemExit) as e:
        mod.main(["--parametros", str(EXEMPLO), "--opcao-que-nao-existe"])
    assert e.value.code == 2

    with pytest.raises(SystemExit) as e:
        mod.main(["--parametros", str(EXEMPLO), "--hoje", "2030-01-01"])
    assert e.value.code == 2


# --- fiação do coletor externo: tudo ou nada ----------------------------------


def test_sem_externo_o_coletor_nao_e_fiado():
    fontes, _ = mod._fontes(None)
    assert fontes.coletar_externo is None  # o nó declara a degradação sozinho


def test_com_externo_o_coletor_e_fiado(tmp_path):
    fontes, _ = mod._fontes(tmp_path)
    assert fontes.coletar_externo is not None


def test_runner_nunca_fia_meio_coletor(tmp_path, monkeypatch, parametros):
    """O grafo recusa meia-fiação com ValueError. Este teste prova que o runner
    nunca a produz: sem `--externo`, `parametros_externo` também não vai — mesmo
    tendo sido carregado do arquivo, que sempre traz a seção [externo]."""
    capturado = {}

    class _Grafo:
        def invoke(self, _estado):
            return {"estado": Estado.ABORTADA, "motivo_aborto": "sem estoque"}

    def _falso_construir(fontes, params, **kw):
        capturado["externo_fonte"] = fontes.coletar_externo
        capturado["externo_params"] = kw.get("parametros_externo")
        return _Grafo()

    monkeypatch.setattr(mod, "construir_grafo", _falso_construir)
    mod.executar(tmp_path, parametros, externo=None, hoje=HOJE, dry_run=True)
    assert capturado["externo_fonte"] is None
    assert capturado["externo_params"] is None

    mod.executar(tmp_path, parametros, externo=tmp_path, hoje=HOJE, dry_run=True)
    assert capturado["externo_fonte"] is not None
    assert capturado["externo_params"] is not None


# --- aborto: duas causas de gravidade OPOSTA ----------------------------------


def _grafo_que_devolve(final):
    class _Grafo:
        def invoke(self, _estado):
            return final

    return lambda *a, **k: _Grafo()


def test_rodada_abortada_nao_escreve_planilha(tmp_path, monkeypatch, parametros):
    """Sem estoque não há decisão (Spec §7.2): não há `resultado` para escrever, e
    tentar escrevê-lo produziria uma planilha vazia indistinguível de uma real."""
    monkeypatch.setattr(
        mod,
        "construir_grafo",
        _grafo_que_devolve({"estado": Estado.ABORTADA, "motivo_aborto": "coleta interna vazia"}),
    )
    monkeypatch.setattr(
        mod,
        "escrever_planilha",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("não escrever em rodada abortada")),
    )
    final, rodada_id = mod.executar(tmp_path, parametros, hoje=HOJE)
    assert final["estado"] == Estado.ABORTADA
    assert rodada_id is None


def test_aborto_deixa_aviso_em_disco(tmp_path, monkeypatch, parametros):
    """No disco, uma sexta abortada seria indistinguível de uma máquina desligada —
    e a Ferramentas §5 cataloga exatamente esse risco ("depende de você notar a
    ausência da planilha")."""
    monkeypatch.setattr(
        mod,
        "construir_grafo",
        _grafo_que_devolve({"estado": Estado.ABORTADA, "motivo_aborto": "estoque vazio"}),
    )
    mod.executar(tmp_path, parametros, hoje=HOJE)
    aviso = (tmp_path / "2026-09-04" / "aviso.txt").read_text(encoding="utf-8")
    assert "ABORTADA" in aviso and "estoque vazio" in aviso


def test_veto_do_crivo_nao_sai_com_o_codigo_de_estoque_vazio(arquivo_valido, monkeypatch):
    """ABORTADA tem duas causas de gravidade OPOSTA. Veto do crivo é a auditoria
    apanhando violação de cota, de piso ou de relaxamento em super — invariantes 6 e
    7. Sob um código só, isso chegaria ao monitoramento com a cara de "não havia
    imóvel para decidir", e ninguém iria olhar."""
    monkeypatch.setattr(
        mod,
        "executar",
        lambda *a, **k: (
            {
                "estado": Estado.ABORTADA,
                "prontos": {"crivo": False},
                "motivo_aborto": "cota excedida",
            },
            None,
        ),
    )
    assert mod.main(["--parametros", str(arquivo_valido), "--dry-run"]) == 6


def test_estoque_vazio_sai_com_4(arquivo_valido, monkeypatch):
    monkeypatch.setattr(
        mod,
        "executar",
        lambda *a, **k: (
            {
                "estado": Estado.ABORTADA,
                "prontos": {"coletor_interno": False},
                "motivo_aborto": "x",
            },
            None,
        ),
    )
    assert mod.main(["--parametros", str(arquivo_valido), "--dry-run"]) == 4


def test_rodada_sem_resultado_nao_diz_que_entregou(tmp_path, monkeypatch, parametros):
    """Estado não-abortado sem `resultado` é incoerência: o nó de registro já rodou.
    Retornar 0 aqui diria ao agendador que a sexta entregou."""
    monkeypatch.setattr(
        mod, "construir_grafo", _grafo_que_devolve({"estado": Estado.COMPLETA, "resultado": None})
    )
    with pytest.raises(RuntimeError, match="sem resultado"):
        mod.executar(tmp_path, parametros, hoje=HOJE)


# --- falha ao REGISTRAR (o sink chamado de dentro do grafo) -------------------


def _registrador(parametros, avisar, *, dry_run=False, externo=None):
    return mod._registrador(parametros, HOJE, externo, AGORA, dry_run=dry_run, avisar=avisar)


def test_registrar_falho_avisa_com_o_tipo_e_propaga(tmp_path, monkeypatch, parametros):
    """A mensagem da exceção pode ecoar valor vindo do banco, e a saída do agendador
    vira e-mail/log capturado — só o TIPO é propagado para fora."""

    def _conectar_quebrado():
        raise ConnectionError("erro ao gravar imóvel do corretor Fulano da Silva")

    monkeypatch.setattr(mod, "conectar", _conectar_quebrado)
    avisar = mod._avisar(tmp_path, dry_run=False)
    registrar, capturado = _registrador(parametros, avisar)

    with pytest.raises(mod.SinkFalhou):
        registrar(_estado())

    aviso = (tmp_path / "aviso.txt").read_text(encoding="utf-8")
    assert "FALHA ao gravar" in aviso
    assert "ConnectionError" in aviso
    assert "Fulano" not in aviso
    assert capturado == []  # nada capturado: não houve rodada


def test_registrar_recusa_gravar_rodada_sem_resultado(tmp_path, monkeypatch, parametros):
    """Gravar a linha assim mesmo produziria uma "carga vigente" sem decisão, que a
    rodada de segunda mediria como se fosse real."""
    monkeypatch.setattr(
        mod, "conectar", lambda: (_ for _ in ()).throw(AssertionError("não deve conectar"))
    )
    registrar, _ = _registrador(parametros, mod._avisar(tmp_path, dry_run=False))
    with pytest.raises(RuntimeError, match="sem resultado"):
        registrar({"estado": Estado.COMPLETA, "prontos": {}})


def test_id_devolvido_e_o_ULTIMO_nao_o_primeiro(tmp_path, monkeypatch, parametros):
    """Se o nó for reexecutado (retry do Orquestrador, parâmetro nº 4), o Registro
    ganha uma SEGUNDA linha — não há chave natural para deduplicar. Informar a
    primeira mandaria o dono aprovar a rodada órfã.

    A asserção é sobre o RETORNO de `executar`, não sobre a lista de captura: a
    versão anterior fazia `capturado[-1] == 42`, indexando ela mesma a lista, o que é
    trivialmente verdadeiro para qualquer lista terminada em 42 — trocar o consumidor
    real de volta para `[0]` mantinha a suíte verde."""
    ids = iter([41, 42])

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def transaction(self):
            return self

    monkeypatch.setattr(mod, "conectar", lambda: _Conn())
    monkeypatch.setattr(mod, "gravar_rodada_decisao", lambda *a, **k: next(ids))
    monkeypatch.setattr(mod, "escrever_planilha", lambda *a, **k: [])

    resultado = _resultado_falso()

    class _Grafo:
        def __init__(self, registrar):
            self._registrar = registrar

        def invoke(self, _estado):
            estado = {"estado": Estado.COMPLETA, "resultado": resultado, "prontos": {}}
            self._registrar(estado)  # o retry: o nó roda duas vezes
            self._registrar(estado)
            return estado

    monkeypatch.setattr(mod, "construir_grafo", lambda _f, _p, **kw: _Grafo(kw["registrar"]))
    _final, rodada_id = mod.executar(tmp_path, parametros, hoje=HOJE)
    assert rodada_id == 42


def test_avisar_nao_substitui_a_excecao_original(tmp_path, monkeypatch, parametros):
    """`avisar` escreve em disco de dentro do handler: se ele mesmo falhasse,
    trocaria o SinkFalhou por um OSError e esconderia a causa."""

    def _conectar_quebrado():
        raise ConnectionError("postgres fora")

    monkeypatch.setattr(mod, "conectar", _conectar_quebrado)
    destino = tmp_path / "arquivo_no_lugar_de_pasta"
    destino.write_text("sou um arquivo", encoding="utf-8")  # mkdir vai falhar
    registrar, _ = _registrador(parametros, mod._avisar(destino, dry_run=False))

    with pytest.raises(mod.SinkFalhou):  # e NÃO OSError
        registrar(_estado())


def test_dry_run_nao_abre_conexao_nem_escreve(tmp_path, monkeypatch, parametros):
    monkeypatch.setattr(
        mod, "conectar", lambda: (_ for _ in ()).throw(AssertionError("dry-run não conecta"))
    )
    avisar = mod._avisar(tmp_path, dry_run=True)
    registrar, capturado = _registrador(parametros, avisar, dry_run=True)

    assert registrar(_estado()) is None
    avisar("aviso em ensaio")
    assert capturado == []
    assert not any(tmp_path.iterdir())  # nada foi escrito em disco


# --- procedência dos parâmetros no Registro e na planilha ---------------------


def test_registro_grava_a_forma_declarada_verbatim(parametros):
    """As duas FORMAS viram função e não sobrevivem a `ParametrosDecisao`. Gravar só
    os números deixaria a rodada irreproduzível a partir do Registro (invariante 5)."""
    serial = mod._serializaveis(parametros, HOJE, None)
    assert serial["rotulo"] == "PROVISÓRIO"
    assert serial["origem"].endswith(".toml")
    assert serial["decaimento_janela"] == {"forma": "geometrica", "razao": 0.5}
    assert serial["externo"]["desempenho"] == {"forma": "visualizacoes"}


def test_registro_grava_o_recorte_e_a_definicao_de_ativo(parametros, tmp_path):
    """Duas entradas da decisão que NÃO estão no TOML e não têm coluna no Registro:
    sem elas, uma rodada feita com `--hoje` fica irreproduzível, e ninguém saberia
    sob qual definição de gestor ativo a lista antiga saiu."""
    serial = mod._serializaveis(parametros, HOJE, tmp_path)
    assert serial["data_referencia"] == "2026-09-04"
    assert serial["definicao_ativo_distrito"] == mod.DEFINICAO_ATIVO.value
    assert serial["coleta_externa"] == str(tmp_path)
    assert mod._serializaveis(parametros, HOJE, None)["coleta_externa"] is None


def test_serializaveis_nao_leva_funcao(parametros):
    """`parametros_da_rodada` é gravado como JSON: uma função ali quebraria a
    gravação da rodada inteira, depois de a decisão já ter sido calculada."""
    import json

    json.dumps(mod._serializaveis(parametros, HOJE, None))  # não levanta


def test_notas_abrem_com_estado_e_limitacoes(parametros):
    """A §7.2 exige a limitação visível na planilha. Quem lê a lista precisa saber,
    ANTES dos números, se a rodada foi completa ou degradada."""
    notas = mod.notas_da_planilha(
        parametros, Estado.DEGRADADA, ["sem raspagem"], vendas_descartadas=3
    )
    assert notas[0] == "ESTADO DA RODADA: DEGRADADA"
    assert notas[1].startswith("LIMITAÇÃO 1: sem raspagem")
    assert any("PROVISÓRIO" in n and ".toml" in n for n in notas)
    assert any("3 venda(s)" in n for n in notas)


def test_notas_nao_afirmam_quem_declarou_os_parametros(parametros):
    """O runner sabe de qual ARQUIVO os valores vieram, não quem os escreveu. Dizer
    "declarados pelo dono" vira mentira no dia em que alguém apontar `--parametros`
    para outro arquivo qualquer."""
    notas = mod.notas_da_planilha(parametros, Estado.COMPLETA, [])
    assert not any("dono da decisão" in n for n in notas)


def test_sem_limitacao_a_ausencia_e_declarada(parametros):
    """ "Nenhuma limitação" precisa ser DITO: a ausência da linha é indistinguível
    de uma planilha que esqueceu de declará-las."""
    notas = mod.notas_da_planilha(parametros, Estado.COMPLETA, [])
    assert notas[1] == "LIMITAÇÕES: nenhuma"
    assert not any("venda(s)" in n for n in notas)


def test_notas_trazem_os_quatro_obrigatorios_da_secao_3_1(parametros):
    """Spec §3.1: idade do dado do portal, taxa de amarração, posições não
    preenchidas e variação de volume são OBRIGATÓRIOS na aba de resumo."""
    notas = mod.notas_da_planilha(
        parametros,
        Estado.COMPLETA,
        [],
        taxa_amarracao=0.83,
        idade_dias=2,
        posicoes_vazias=17,
    )
    texto = "\n".join(notas)
    assert "idade do dado do portal: 2 dia(s)" in texto
    assert "83.0%" in texto
    assert "não preenchidas: 17" in texto
    assert "variação do estoque elegível" in texto


def test_obrigatorios_ausentes_sao_DECLARADOS_ausentes(parametros):
    """Uma linha faltando é indistinguível de um número que ninguém calculou — o
    modo de falha que a §7.2 existe para impedir."""
    texto = "\n".join(mod.notas_da_planilha(parametros, Estado.DEGRADADA, []))
    assert "idade do dado do portal: AUSENTE" in texto
    assert "taxa de amarração anúncio↔imóvel: AUSENTE" in texto


def test_destino_padrao_vem_do_parser_e_e_relativo():
    """Lê o default do PRÓPRIO parser. A versão anterior redigitava o literal
    `Path("saida/sexta")` e o afirmava relativo — continuava verde com o default
    trocado para um caminho absoluto, que é justamente o que ela deveria pegar
    (`saida/` é o que o .gitignore cobre; fora dali a rodada escreve em lugar não
    ignorado)."""
    destino = mod.construir_parser().get_default("destino")
    assert not destino.is_absolute()
    assert destino.parts[0] == "saida"


# --- planilha e Registro dizem a MESMA coisa ----------------------------------


def _penalizavel(imovel_id, janelas=()):
    return ImovelPenalizavel(
        imovel_id=imovel_id,
        janelas_anteriores=janelas,
        alguma_categoria_avaliada=True,
        leads_180d=5,
    )


def test_limitacoes_da_fiacao_chegam_ao_MOTIVO_gravado(tmp_path, monkeypatch, parametros):
    """Sob a D-001 o Registro é a fonte da verdade, e é por ele que a rodada de
    segunda enxerga a carga. Se as limitações vivessem só no CSV, quem auditasse pelo
    banco não veria "histórico de janelas ausente" nem "distrito a 45,9%" — os dois
    artefatos discordariam sobre a mesma rodada."""
    gravado = {}

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def transaction(self):
            return self

    monkeypatch.setattr(mod, "conectar", lambda: _Conn())
    monkeypatch.setattr(mod, "gravar_rodada_decisao", lambda *a, **k: (gravado.update(k), 7)[1])
    registrar, _ = _registrador(parametros, mod._avisar(tmp_path, dry_run=False))
    registrar(_estado(janelas_lidas=0))

    motivo = gravado["motivo_degradacao"]
    assert "HISTÓRICO DE JANELAS" in motivo
    assert "45,9%" in motivo


def test_limitacao_de_janela_le_o_REGISTRO_nao_a_lista_julgada(parametros):
    """O predicado é "o Registro devolveu alguma janela encerrada?", não "alguém foi
    penalizado" nem "a lista chegou julgada". As três divergem, e as duas primeiras
    divergem justamente quando o consumidor passa a funcionar: com histórico presente
    e todas as janelas tendo dado resultado, a planilha declararia dado ausente sobre
    dado presente — a limitação falsa que este projeto já corrigiu duas vezes."""
    assert any("HISTÓRICO DE JANELAS" in x for x in mod.limitacoes_da_fiacao(parametros, 0))
    assert not any("HISTÓRICO DE JANELAS" in x for x in mod.limitacoes_da_fiacao(parametros, 7))


def test_sem_limiar_e_sem_historico_sao_limitacoes_DISTINTAS(parametros):
    """As duas zeram a penalidade §6.4 por motivos opostos — não há régua, ou não há
    o que julgar. Sob um sinal só, quem lê a planilha não saberia qual das duas
    corrigir, e a que está sob seu controle é só uma delas."""
    limitacoes = mod.limitacoes_da_fiacao(parametros, 0)
    assert any("HISTÓRICO DE JANELAS" in x for x in limitacoes)
    assert any("LIMIAR DE RESULTADO" in x for x in limitacoes)  # o exemplo não declara o nº 14


def test_razao_um_declara_a_divergencia_com_a_spec(tmp_path, parametros):
    """A §6.4 diz que a penalidade decai. Razão 1.0 é aceita como escolha do dono,
    mas a divergência aparece na planilha em vez de o código fingir que não existe."""
    assert not any("não decai" in x for x in mod.limitacoes_da_fiacao(parametros, 0))

    arquivo = tmp_path / "p.toml"
    arquivo.write_text(
        EXEMPLO.read_text(encoding="utf-8").replace("razao = 0.5", "razao = 1.0"), encoding="utf-8"
    )
    sem_decaimento = carregar(arquivo)
    assert any(
        "não decai" in x.lower() or "NÃO\ndecai" in x
        for x in mod.limitacoes_da_fiacao(sem_decaimento, 0)
    )


def test_notas_trazem_data_e_posicoes_preenchidas(parametros):
    """Spec §3.1: o resumo carrega "Data, estado da rodada, avisos, parâmetros
    vigentes, posições preenchidas e vazias". A subpasta datada não serve como data —
    quem abre o CSV solto, que é como ele viaja por e-mail, não vê o nome da pasta."""
    notas = mod.notas_da_planilha(
        parametros, Estado.COMPLETA, [], data_referencia=HOJE, posicoes_preenchidas=6970
    )
    assert notas[0] == "DATA DE REFERÊNCIA DA RODADA: 2026-09-04"
    assert any("preenchidas: 6970" in n for n in notas)
