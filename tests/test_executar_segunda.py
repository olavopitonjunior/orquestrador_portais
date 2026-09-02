"""Testes da FIAÇÃO DE FALHA do ponto de entrada da segunda.

Sem banco: `conectar` e `escrever_relatorio` são monkeypatchados. O que se prova aqui
é a regra que evita corromper a auditoria da §7.3 e que até agora vivia só em
comentário — falha de sink NUNCA vira `declarar_ausencia`, porque o roteamento do
grafo gravaria uma SEGUNDA rodada para a mesma segunda.
"""

from datetime import date, datetime
from pathlib import Path

import pytest

import executar.segunda as mod
from dominio.acompanhamento import LeadDoPeriodo, Nivel, PosicaoPaga, apurar

AGORA = datetime(2026, 8, 31, 9, 0)


def _resultado():
    return apurar(
        rodada_decisao_id=9,
        posicoes=[PosicaoPaga(1, Nivel.DESTAQUE)],
        leads=[
            LeadDoPeriodo(
                lead_id=100,
                imovel_id=1,
                entrada=date(2026, 8, 29),
                atendimento_registrado=False,
                contato_registrado=False,
                distribuicao=date(2026, 8, 29),
                corretor_gestor="Corretor X",
            )
        ],
        inicio_periodo=date(2026, 8, 28),
        fim_periodo=date(2026, 8, 31),
    )


# --- falha ao REGISTRAR --------------------------------------------------------


def test_registrar_falho_avisa_e_propaga_sem_declarar_ausencia(tmp_path, monkeypatch):
    """Se o Postgres cair: avisa por outro canal e propaga. NÃO declara ausência —
    tentaria o mesmo banco caído E o roteamento gravaria uma segunda rodada."""

    def _conectar_quebrado():
        raise ConnectionError("postgres fora")

    monkeypatch.setattr(mod, "conectar", _conectar_quebrado)
    sinks = mod._sinks(tmp_path, AGORA, dry_run=False)

    with pytest.raises(mod.SinkFalhou):
        sinks.registrar(_resultado(), "degradada", "motivo", {"monitor": True})

    aviso = (tmp_path / "aviso.txt").read_text(encoding="utf-8")
    assert "FALHA ao gravar" in aviso
    assert "ConnectionError" in aviso  # o TIPO, não a mensagem


def test_aviso_nao_carrega_a_mensagem_da_excecao(tmp_path, monkeypatch):
    """A mensagem da exceção pode ecoar payload de lead; só o tipo é propagado."""

    def _conectar_quebrado():
        raise ConnectionError("erro ao gravar lead do corretor Fulano da Silva")

    monkeypatch.setattr(mod, "conectar", _conectar_quebrado)
    sinks = mod._sinks(tmp_path, AGORA, dry_run=False)
    with pytest.raises(mod.SinkFalhou):
        sinks.registrar(_resultado(), "degradada", None, {"monitor": True})
    assert "Fulano" not in (tmp_path / "aviso.txt").read_text(encoding="utf-8")


# --- falha ao ENTREGAR ---------------------------------------------------------


def test_entregar_falho_nao_declara_ausencia(tmp_path, monkeypatch):
    """A rodada JÁ está gravada: declarar ausência mentiria sobre uma rodada que
    existe — e o roteamento do grafo gravaria a segunda linha."""
    chamou_ausencia = []
    monkeypatch.setattr(
        mod, "escrever_relatorio", lambda *a, **k: (_ for _ in ()).throw(OSError("disco cheio"))
    )
    monkeypatch.setattr(
        mod, "declarar_ausencia_de_carga", lambda *a, **k: chamou_ausencia.append(1)
    )
    sinks = mod._sinks(tmp_path, AGORA, dry_run=False)

    with pytest.raises(mod.SinkFalhou):
        sinks.entregar(_resultado(), "degradada", ["limitação"])

    assert chamou_ausencia == []  # NUNCA
    assert "RELATÓRIO não foi escrito" in (tmp_path / "aviso.txt").read_text(encoding="utf-8")


def test_avisar_nao_substitui_a_excecao_original(tmp_path, monkeypatch):
    """`avisar` escreve em disco e é chamado de dentro do handler: se ele mesmo
    falhasse, trocaria o SinkFalhou por um OSError e esconderia a causa."""

    def _conectar_quebrado():
        raise ConnectionError("postgres fora")

    monkeypatch.setattr(mod, "conectar", _conectar_quebrado)
    destino = tmp_path / "arquivo_no_lugar_de_pasta"
    destino.write_text("sou um arquivo", encoding="utf-8")  # mkdir vai falhar
    sinks = mod._sinks(destino, AGORA, dry_run=False)

    with pytest.raises(mod.SinkFalhou):  # e NÃO OSError
        sinks.registrar(_resultado(), "degradada", None, {"monitor": True})


# --- dry-run: a garantia de "não escreve nada" --------------------------------


def test_dry_run_nao_abre_conexao_nem_escreve(tmp_path, monkeypatch):
    def _explode():
        raise AssertionError("dry-run não pode abrir conexão")

    monkeypatch.setattr(mod, "conectar", _explode)
    monkeypatch.setattr(
        mod,
        "escrever_relatorio",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("dry-run não pode escrever")),
    )
    sinks = mod._sinks(tmp_path, AGORA, dry_run=True)

    # Em ensaio a janela NÃO é atualizada: histórico e limitações saem vazios, e as
    # duas colunas da §4.3 ficam declaradas ausentes — a verdade sobre um ensaio, não
    # os números de uma semana que não foi gravada.
    rid, acumulo = sinks.registrar(_resultado(), "completa", None, {"monitor": True})
    assert (rid, acumulo.historico, acumulo.limitacoes) == (-1, {}, ())
    assert sinks.entregar(_resultado(), "completa", []) is None
    assert sinks.declarar_ausencia("sem carga", {"monitor": False}) == -1
    sinks.avisar("aviso em ensaio")
    assert not any(tmp_path.iterdir())  # nada foi escrito em disco


# --- declarar_ausencia falho: a §7.3 não pode falhar nas DUAS metades ---------


def test_declarar_ausencia_falho_ainda_avisa(tmp_path, monkeypatch):
    """O grafo chama `avisar` DEPOIS de `declarar_ausencia`: sem tratamento, a
    exceção subiria antes do aviso e a §7.3 falharia inteira."""

    def _conectar_quebrado():
        raise ConnectionError("postgres fora")

    monkeypatch.setattr(mod, "conectar", _conectar_quebrado)
    sinks = mod._sinks(tmp_path, AGORA, dry_run=False)

    with pytest.raises(mod.SinkFalhou):
        sinks.declarar_ausencia("nenhuma carga aprovada", {"monitor": False})

    aviso = (tmp_path / "aviso.txt").read_text(encoding="utf-8")
    assert "FALHA ao registrar a ausência" in aviso
    assert "nenhuma carga aprovada" in aviso  # o motivo original não se perde


# --- a carga é lida UMA vez (sem corrida entre janela e medição) --------------


def test_carga_aprovada_e_memoizada(monkeypatch):
    leituras = []

    class _Conn:
        def __enter__(self):
            leituras.append(1)
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(mod, "conectar", lambda: _Conn())
    monkeypatch.setattr(mod, "ultima_carga_aprovada", lambda _c: 9)
    fontes = mod._fontes()

    assert fontes.carga_aprovada() == 9
    assert fontes.carga_aprovada() == 9  # o runner e o grafo, cada um a sua
    assert len(leituras) == 1  # uma leitura só: sem janela da carga A medindo a B


# --- limitação de janela truncada (§7.2) --------------------------------------


def test_janela_truncada_vira_limitacao_declarada():
    assert mod.limitacao_de_janela(date(2026, 9, 1), date(2026, 9, 1)) != []
    assert "0 de 3" in mod.limitacao_de_janela(date(2026, 9, 1), date(2026, 9, 1))[0]


def test_janela_completa_nao_gera_limitacao():
    assert mod.limitacao_de_janela(date(2026, 8, 28), date(2026, 8, 31)) == []


def test_codigo_2_fica_reservado_ao_argparse():
    """Uso inválido da CLI sai com 2 (padrão do argparse). Os códigos semânticos
    evitam o 2 de propósito: sem isso, um argumento digitado errado no agendador
    sairia com o mesmo código de "não havia carga" e viraria no-op benigno."""
    with pytest.raises(SystemExit) as e:
        mod.main(["--opcao-que-nao-existe"])
    assert e.value.code == 2

    with pytest.raises(SystemExit) as e:
        mod.main(["--hoje", "2030-01-01"])  # futuro é recusado pelo parser
    assert e.value.code == 2


def test_destino_padrao_nao_e_absoluto():
    """O default é relativo ao cwd e está coberto pelo .gitignore (`saida/`)."""
    assert not Path("saida/segunda").is_absolute()
