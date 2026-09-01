"""Trava a lista de pacotes do wheel contra o que existe em `src/`.

Por que existe: `src/piloto` ficou de fora de `[tool.hatch.build.targets.wheel]
packages` e ninguém notou, porque o EDITABLE install do hatchling põe `src/` inteiro
no path via `.pth` — então o pacote esquecido continua importável na máquina de quem
desenvolve, e o wheel sai quebrado só para quem instala. `grafo.estado` importa
`piloto.decisao`, então `python -m executar.segunda` morria com ModuleNotFoundError
fora do editable.

Nem o CI nem o passo de fumaça pegavam: os dois rodam contra o editable. Este teste
pega — no momento em que o sétimo pacote nascer, que é quando isso se repetiria.
"""

import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _pacotes_declarados() -> set[str]:
    with (RAIZ / "pyproject.toml").open("rb") as f:
        cfg = tomllib.load(f)
    declarados = cfg["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    return {Path(p).name for p in declarados}


def _pacotes_no_disco() -> set[str]:
    """Diretório de `src/` com pelo menos um .py é pacote que precisa ir no wheel."""
    return {
        d.name
        for d in (RAIZ / "src").iterdir()
        if d.is_dir() and not d.name.startswith((".", "__")) and any(d.glob("*.py"))
    }


def test_todo_pacote_de_src_vai_para_o_wheel():
    no_disco, declarados = _pacotes_no_disco(), _pacotes_declarados()
    faltando = no_disco - declarados
    assert not faltando, (
        f"pacote(s) em src/ fora do wheel: {sorted(faltando)}. "
        "Some em `[tool.hatch.build.targets.wheel] packages` do pyproject.toml — "
        "o editable install esconde isso, o wheel instalado não."
    )


def test_nao_se_declara_pacote_inexistente():
    sobrando = _pacotes_declarados() - _pacotes_no_disco()
    assert not sobrando, f"declarado(s) no wheel mas ausente(s) de src/: {sorted(sobrando)}"


def test_piloto_esta_no_wheel():
    """Regressão específica: `grafo.estado` importa `piloto.decisao`, então sem
    `piloto` no wheel o ponto de entrada não importa fora do editable."""
    assert "piloto" in _pacotes_declarados()
