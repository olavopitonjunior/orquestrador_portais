"""Os prazos do MySQL são constantes inventariadas (`docs/prazos.md`): um teste pode
afirmá-los, e o inventário não deriva do código em silêncio."""

from pathlib import Path

from dados.newcore import CONEXAO_MYSQL_S, LEITURA_MYSQL_S

PRAZOS = Path(__file__).resolve().parent.parent / "docs" / "prazos.md"


def test_prazos_do_mysql_batem_com_o_inventario():
    texto = PRAZOS.read_text(encoding="utf-8")
    assert f"`LEITURA_MYSQL_S` {LEITURA_MYSQL_S} s" in texto
    assert f"`connect_timeout` {CONEXAO_MYSQL_S} s" in texto


def test_leitura_maior_que_a_consulta_medida():
    """109 s medidos em 03/09/2026 numa base carregada; o teto precisa de folga real."""
    assert LEITURA_MYSQL_S >= 5 * 109
