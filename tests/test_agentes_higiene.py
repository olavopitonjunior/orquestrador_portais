"""Os subagentes de desenvolvimento não escrevem na árvore do repositório.

A regra existe por incidente: duas vezes em 02/09/2026 um portão travou no meio e
deixou arquivo de trabalho em `tests/`. Subagente que só limpa ao terminar bem não
limpa quando trava — e antes disso uma sessão desfez mutação com `git checkout` e
reverteu trabalho não commitado, perda que só apareceu numa conferência linha a
linha.

Este teste é a única coisa que impede as duas cláusulas de sumirem numa edição
futura. Afirma a PRESENÇA DO CABEÇALHO, não o texto do bloco: exigir o corpo inteiro
faria qualquer reescrita legítima quebrar o CI, e teste que atrapalha vira teste
desligado.
"""

from __future__ import annotations

from pathlib import Path

import pytest

AGENTES = sorted((Path(__file__).resolve().parent.parent / ".claude" / "agents").glob("*.md"))
CABECALHOS = ("## Não escreve na árvore", "## Nunca desfaz mutação com git")


def test_ha_agentes_a_conferir():
    """Contraprova: sem esta linha, os testes abaixo passariam vazios se o diretório
    fosse renomeado ou os arquivos sumissem."""
    assert len(AGENTES) >= 5, f"esperava ao menos 5 subagentes, achei {len(AGENTES)}"


@pytest.mark.parametrize("agente", AGENTES, ids=lambda p: p.stem)
def test_todo_subagente_declara_a_higiene_de_trabalho(agente: Path):
    texto = agente.read_text(encoding="utf-8")
    faltando = [c for c in CABECALHOS if c not in texto]
    assert not faltando, (
        f"{agente.name} perdeu {faltando}. Sem essas cláusulas, um portão que trave "
        "deixa resíduo na árvore, ou desfaz mutação com git e apaga trabalho não "
        "commitado — os dois já aconteceram."
    )
