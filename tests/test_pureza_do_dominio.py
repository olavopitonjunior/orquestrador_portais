"""`src/dominio` não importa nada de fora de `src/dominio`.

Por que este teste existe, e por que só agora. A pureza do domínio era propriedade
ACIDENTAL: verdadeira, mantida por disciplina, e sem nada que a travasse. O repo
tem guarda executável para os outros invariantes (credencial que não vaza, cotas,
perguntas abertas em dia) e não tinha para este. A fatia que move `DesempenhoAnuncio`
para cá tem como valor declarado exatamente a DIREÇÃO DA DEPENDÊNCIA — entregá-la
sem a guarda seria entregar metade, e a próxima pessoa desfaria a fatia sem
perceber.

O que ele protege, em uma frase: quem define o que o dado significa é a camada de
dentro; quem o produz é a de fora. Por isso `dados/` importa de `dominio/`, e nunca
o contrário. Um import a mais em qualquer módulo daqui inverte essa direção e
transforma o pacote de regras em cliente da camada de I/O.

Escrito ANTES do move, de propósito: rodado contra a `main` anterior ele passa
(a propriedade já existia), e continua passando depois — é assim que ele prova que
a fatia PRESERVOU a pureza, em vez de alguém afirmar que preservou.

TRÊS COISAS QUE ESTE TESTE PRESSUPÕE, ditas porque envelhecem em silêncio:

1. Import DINÂMICO escapa da varredura por AST — `importlib.import_module("dados.x")`
   é uma chamada, não um `ast.Import`, e o mesmo vale para `__import__` e `exec`.
   Por isso há uma segunda varredura, textual, para essas três formas. Não é
   completa (nada é, contra código que monta o nome em tempo de execução), mas
   fecha as formas que alguém escreveria sem má intenção. Achado da revisão.

2. Import dentro de `if TYPE_CHECKING:` É PEGO, e isso é intencional. `ast.walk`
   não distingue contexto, então entra em `if`, `try` e corpo de função. Um módulo
   do domínio que precise do TIPO de outra camada, ainda que só para anotação, tem
   o mesmo sintoma que motivou mover `DesempenhoAnuncio` para cá: o domínio
   precisando conhecer a forma de um dado de fora. A resposta certa é mover o tipo
   para o domínio, não abrir exceção. Se alguém "consertar" isto, leia esta linha.

3. Import RELATIVO não pode escapar de `dominio` porque `src/` NÃO é pacote — não
   tem `__init__.py`, e está no `pythonpath` do pytest, então `dominio` é pacote de
   topo. Subir além do topo estoura `ImportError` em tempo real. Se um dia
   `src/__init__.py` nascer, esta pressuposição cai junto e este teste precisa
   olhar os relativos também.
"""

import ast
import re
from pathlib import Path

import pytest

DOMINIO = Path(__file__).resolve().parent.parent / "src" / "dominio"

# Os pacotes do projeto. Um import de qualquer um deles (exceto `dominio`) dentro de
# `dominio` é a inversão que este teste existe para impedir. O resto — stdlib e
# dependências de terceiros — é permitido: `dominio` já usa `dataclasses`, `enum`,
# `datetime` e `statistics`, e nenhum deles é camada deste sistema.
PACOTES_DO_PROJETO = frozenset(
    {"config", "dados", "dominio", "entrega", "executar", "grafo", "piloto"}
)


def _modulos() -> list[Path]:
    return sorted(p for p in DOMINIO.rglob("*.py"))


def _raizes_importadas(arquivo: Path) -> set[str]:
    """A primeira parte de cada módulo importado — `dados.coletor_externo` → `dados`.

    Cobre as duas formas: `import x.y` e `from x.y import z`. Import RELATIVO
    (`from . import x`, `level > 0`) é interno ao pacote por construção e não pode
    escapar de `dominio`, então não entra na conta.
    """
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"), filename=str(arquivo))
    raizes: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            raizes.update(alias.name.split(".")[0] for alias in no.names)
        elif isinstance(no, ast.ImportFrom):
            if no.level:  # relativo: `from .x import y`
                continue
            if no.module:
                raizes.add(no.module.split(".")[0])
    return raizes


def test_o_dominio_tem_modulos_para_conferir():
    """Guarda do próprio teste: se o glob quebrar, os outros passariam vazios."""
    modulos = _modulos()
    assert len(modulos) >= 5, f"esperava os módulos do domínio, achei {modulos}"
    assert any(m.name == "elegibilidade.py" for m in modulos)


@pytest.mark.parametrize("arquivo", _modulos(), ids=lambda p: p.name)
def test_modulo_do_dominio_nao_importa_outra_camada(arquivo: Path):
    invasores = sorted((PACOTES_DO_PROJETO - {"dominio"}) & _raizes_importadas(arquivo))
    assert not invasores, (
        f"{arquivo.name} importa {invasores}: o domínio passaria a depender da camada "
        "de fora, invertendo a direção que sustenta a pureza. Quem define o que o dado "
        "significa é a camada de dentro; quem o produz é a de fora."
    )


# As formas de import que a AST não enxerga como import. Não é lista completa contra
# quem monta o nome do módulo em tempo de execução — é a rede contra quem escreveria
# uma delas sem perceber que está invertendo a dependência.
_IMPORT_DINAMICO = re.compile(r"\b(?:importlib\.import_module|__import__|exec)\s*\(")


@pytest.mark.parametrize("arquivo", _modulos(), ids=lambda p: p.name)
def test_modulo_do_dominio_nao_importa_de_forma_dinamica(arquivo: Path):
    """A varredura por AST não vê `importlib.import_module("dados.x")`: é uma chamada.

    Achado da revisão desta fatia — a mutação passava verde. O domínio não tem uso
    legítimo de import dinâmico: é pacote de regras puras, e o que ele precisa
    conhecer ele importa pelo nome, no topo.
    """
    achados = _IMPORT_DINAMICO.findall(arquivo.read_text(encoding="utf-8"))
    assert not achados, (
        f"{arquivo.name} usa import dinâmico ({achados}): a varredura por AST não o vê, "
        "e por ele o domínio pode passar a depender de outra camada sem nada acusar."
    )


def test_nenhum_modulo_solto_direto_em_src():
    """As duas guardas abaixo enxergam DIRETÓRIOS. Um `.py` solto em `src/` seria
    invisível às duas ao mesmo tempo: não entraria na lista de pacotes, e um
    `import estranho` no domínio não casaria nenhuma raiz conhecida. Segundo buraco
    da mesma família que o do `__init__.py`, achado pela revisão."""
    soltos = sorted(p.name for p in DOMINIO.parent.glob("*.py"))
    assert not soltos, (
        f"módulo(s) solto(s) em src/: {soltos}. Ou vire pacote, ou a guarda de pureza "
        "fica cega para ele — as duas checagens abaixo só olham diretórios."
    )


def test_a_lista_de_pacotes_do_projeto_esta_em_dia():
    """Se um pacote novo nascer em `src/` e não entrar na lista, o teste acima passaria
    a ignorá-lo — e a guarda envelheceria em silêncio, que é o defeito recorrente
    registrado em `bug.md`."""
    src = DOMINIO.parent
    # NÃO exige `__init__.py`: só `dominio` e `piloto` o têm — os demais são pacotes
    # de namespace, e exigi-lo fazia esta guarda enxergar dois diretórios de sete e
    # envelhecer em silêncio, que é o defeito que ela existe para impedir. Um
    # diretório de `src/` com qualquer `.py` dentro é camada deste sistema.
    reais = {
        p.name
        for p in src.iterdir()
        if p.is_dir() and p.name != "__pycache__" and any(p.rglob("*.py"))
    }
    assert reais <= PACOTES_DO_PROJETO, (
        f"pacote(s) novo(s) em src/ fora da lista: {sorted(reais - PACOTES_DO_PROJETO)}"
    )
