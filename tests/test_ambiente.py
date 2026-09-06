"""O carregador do `.env` não pode interpretar valor nem vencer o ambiente.

Os dois riscos são concretos, não teóricos. Interpretar valor reintroduz o
`Access denied` que o `docs/mapa-de-dados.md` registra: o shell expandindo
metacaractere da senha produz um erro indistinguível de credencial errada, e a
correção adotada foi ler o arquivo dentro do Python — o que só vale se o
"dentro do Python" também não expandir nada. Vencer o ambiente faria um `.env`
de máquina de desenvolvimento sobrepor o que o CI injeta no job.
"""

from __future__ import annotations

import ast
import os
import pathlib
import re
from pathlib import Path

import pytest

from config.ambiente import carregar_env


@pytest.fixture
def env_limpo(monkeypatch: pytest.MonkeyPatch):
    """Isola `os.environ` de verdade.

    `monkeypatch` sozinho NÃO basta: ele desfaz o que passa por `setenv`, e o módulo
    sob teste atribui direto em `os.environ`. Sem o instantâneo abaixo, as variáveis
    vazavam entre testes — e, como o carregador não sobrescreve, o segundo caso
    parametrizado via o valor do primeiro e falhava. O sintoma parecia defeito do
    módulo; era a guarda de precedência funcionando sobre um teste sujo."""
    antes = os.environ.copy()
    yield monkeypatch
    os.environ.clear()
    os.environ.update(antes)


def _escrever(tmp_path: Path, conteudo: str) -> Path:
    arquivo = tmp_path / ".env"
    arquivo.write_text(conteudo, encoding="utf-8")
    return arquivo


def test_define_o_que_o_arquivo_declara(tmp_path: Path, env_limpo):
    arquivo = _escrever(tmp_path, 'A=1\nB="dois"\n')
    definidas = carregar_env(arquivo)
    assert sorted(definidas) == ["A", "B"]
    assert os.environ["A"] == "1"
    assert os.environ["B"] == "dois"


@pytest.mark.parametrize(
    "valor",
    [
        "tem$cifrao",
        "tem`crase`",
        "tem!bang",
        "tem\\barra",
        "tem espaco e $HOME literal",
        "$(nao_executa)",
    ],
)
def test_valor_chega_INTACTO_sem_expansao(tmp_path: Path, env_limpo, valor: str):
    """O coração do módulo. Cada um destes é um caractere que o shell expandiria —
    e a expansão da senha é exatamente o defeito registrado no mapa de dados."""
    arquivo = _escrever(tmp_path, f'SEGREDO="{valor}"\n')
    carregar_env(arquivo)
    assert os.environ["SEGREDO"] == valor


def test_NAO_sobrescreve_o_que_o_ambiente_ja_tem(tmp_path: Path, env_limpo):
    """A precedência que protege o CI: lá as variáveis vêm do job, não de arquivo."""
    env_limpo.setenv("A", "do-ambiente")
    arquivo = _escrever(tmp_path, "A=do-arquivo\n")
    definidas = carregar_env(arquivo)
    assert definidas == [], "não deveria ter definido nada"
    assert os.environ["A"] == "do-ambiente"


def test_sobrescrever_True_inverte_a_precedencia(tmp_path: Path, env_limpo):
    env_limpo.setenv("A", "do-ambiente")
    arquivo = _escrever(tmp_path, "A=do-arquivo\n")
    assert carregar_env(arquivo, sobrescrever=True) == ["A"]
    assert os.environ["A"] == "do-arquivo"


def test_arquivo_ausente_NAO_levanta(tmp_path: Path, env_limpo):
    """Ausência não é erro: quem precisa da variável já tem mensagem própria e
    específica (`newcore.py` nomeia as que faltam e manda gerar o `.env`). Um erro
    aqui trocaria esse diagnóstico por 'arquivo não encontrado'."""
    assert carregar_env(tmp_path / "nao-existe") == []


def test_ignora_comentario_linha_vazia_e_prosa(tmp_path: Path, env_limpo):
    """O template real é quase todo comentário — inclusive comentários que contêm
    `=`, que não podem virar variável."""
    arquivo = _escrever(
        tmp_path,
        "# comentário\n\n  # indentado, com A=B dentro\nA=1\nprosa solta sem igual\n",
    )
    assert carregar_env(arquivo) == ["A"]


def test_aceita_export_e_tira_UM_par_de_aspas(tmp_path: Path, env_limpo):
    arquivo = _escrever(tmp_path, 'export A=\'um\'\nB="\\"aspas dentro\\""\n')
    carregar_env(arquivo)
    assert os.environ["A"] == "um"
    # O par externo sai; o que estava escapado no arquivo permanece literal.
    assert os.environ["B"] == '\\"aspas dentro\\"'


def test_o_env_tmpl_do_repositorio_e_parseavel(env_limpo):
    """Contraprova contra o regex apodrecer: o template versionado precisa continuar
    rendendo as chaves que os runners exigem. Roda sobre `.env.tmpl` (versionado),
    nunca sobre `.env` (que não existe no CI e não pode ser lido por teste).

    `sobrescrever=True` porque a pergunta aqui é o que o TEMPLATE declara, não o que
    esta chamada mudou: o `conftest` já carregou o ambiente da sessão, e sem isto a
    função devolveria lista vazia — corretamente, por não sobrescrever — e o teste
    mediria o efeito colateral em vez do conteúdo do arquivo."""
    tmpl = Path(__file__).resolve().parent.parent / ".env.tmpl"
    definidas = carregar_env(tmpl, sobrescrever=True)
    for exigida in (
        "NEWCORE_MYSQL_HOST",
        "NEWCORE_MYSQL_PORT",
        "NEWCORE_MYSQL_USER",
        "NEWCORE_MYSQL_PASSWORD",
        "POSTGRES_URL",
    ):
        assert exigida in definidas, f"{exigida} sumiu do .env.tmpl"


def test_o_env_tmpl_NAO_declara_credencial_do_portal(env_limpo):
    """A D-010 adotou login manual: usuário e senha do Canal Pro não são lidos por
    linha nenhuma de código. Estavam no template, apontavam para campos inexistentes
    no cofre e derrubavam o `op inject` inteiro — a causa do sintoma do [P-17]."""
    tmpl = Path(__file__).resolve().parent.parent / ".env.tmpl"
    definidas = carregar_env(tmpl, sobrescrever=True)
    assert "CANALPRO_USER" not in definidas
    assert "CANALPRO_PASSWORD" not in definidas


RAIZ = Path(__file__).resolve().parent.parent


def _postgres_url_de(tmpl: Path) -> str:
    valores = {}
    for linha in tmpl.read_text(encoding="utf-8").splitlines():
        if linha.startswith("POSTGRES_URL="):
            valores["url"] = linha.split("=", 1)[1].strip().strip("\"'")
    assert "url" in valores, f"{tmpl} não declara POSTGRES_URL"
    return valores["url"]


def test_os_dois_templates_concordam_sobre_a_postgres_url():
    """Existe por defeito real, achado em 02/09/2026. A raiz e o console têm templates
    SEPARADOS — o Next lê `console/.env`, nunca o da raiz —, e eles chegaram a afirmar
    coisas opostas sobre o MESMO campo do mesmo item: a raiz virou literal enquanto o
    console seguia apontando para uma referência de cofre que não existe, e que era
    justamente a que derrubava o `op inject`. Consertar um lado não conserta o console.

    Este teste não julga QUAL é o valor certo; exige que os dois digam o mesmo."""
    raiz = _postgres_url_de(RAIZ / ".env.tmpl")
    console = _postgres_url_de(RAIZ / "console" / ".env.tmpl")
    assert raiz == console, (
        f"os templates divergiram: raiz={raiz!r} console={console!r}. "
        "O console lê o próprio .env; deixar os dois diferentes faz o painel falhar "
        "com o ambiente da raiz aparentemente correto."
    )


def test_nenhum_template_referencia_campo_de_cofre_inexistente():
    """O `op inject` falha INTEIRO quando uma referência não resolve — foi assim que
    três referências mortas derrubaram a geração do `.env` por semanas. O item do cofre
    tem os quatro campos `NEWCORE_MYSQL_*`; qualquer outro nome aqui precisa ser criado
    lá ANTES, e este teste é o lembrete executável disso."""
    conhecidos = {
        "NEWCORE_MYSQL_HOST",
        "NEWCORE_MYSQL_PORT",
        "NEWCORE_MYSQL_USER",
        "NEWCORE_MYSQL_PASSWORD",
    }
    padrao = re.compile(r"op://[^/]+/[^/]+/([A-Z_]+)")
    for tmpl in (RAIZ / ".env.tmpl", RAIZ / "console" / ".env.tmpl"):
        referenciados = set(padrao.findall(tmpl.read_text(encoding="utf-8")))
        desconhecidos = referenciados - conhecidos
        assert not desconhecidos, (
            f"{tmpl.name} referencia campo(s) que o item do cofre não tem: "
            f"{sorted(desconhecidos)} — o `op inject` falharia inteiro."
        )


# Pontos de entrada que legitimamente NÃO carregam o ambiente, com a razão. Toda
# entrada aqui é uma dispensa consciente: se um módulo ganhar acesso a credencial,
# tem de sair desta lista, e o teste abaixo volta a cobri-lo.
SEM_CREDENCIAL = {
    "contrato": "só serializa o contrato de parâmetros; não abre conexão nenhuma",
}

# Módulos de `executar` que NÃO são ponto de entrada, com a razão. Existe para a
# conferência cruzada abaixo: sem ela, a contagem esperada seria número mágico, e a
# varredura poderia perder um módulo real sem nada ficar vermelho.
NAO_SAO_PONTO_DE_ENTRADA = {
    "resumos": "biblioteca de leitura dos resumos; não tem CLI",
}

# Sinais de que um módulo toca credencial mesmo sem chamar `carregar_env`.
_ACESSO_A_CREDENCIAL = re.compile(
    r"os\.environ|os\.getenv|NEWCORE_MYSQL|POSTGRES_URL|CANALPRO|carregar_env"
)


def _com_main(fonte: str) -> bool:
    """Tem `main` de nível de módulo? Por AST, não por texto.

    A busca textual que esta função substituiu (`"\ndef main(" in fonte`) casava só a
    forma exata, na coluna zero: `async def main`, `def main` indentado ou uma CLI
    declarativa escapariam calados — e escapar calado é a falha que este arquivo
    inteiro existe para impedir. O AST também elimina o falso positivo simétrico, um
    `def main(` citado dentro de docstring.
    """
    try:
        arvore = ast.parse(fonte)
    except SyntaxError:  # pragma: no cover — o ruff pegaria antes
        return False
    return any(
        isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef) and no.name == "main"
        for no in arvore.body
    )


def _modulos_de_executar() -> list[pathlib.Path]:
    raiz = pathlib.Path(__file__).resolve().parents[1] / "src" / "executar"
    return sorted(f for f in raiz.glob("*.py") if f.stem != "__init__")


def _pontos_de_entrada() -> list[str]:
    """Descobre os pontos de entrada em vez de listá-los à mão.

    A versão anterior deste teste trazia quatro nomes fixos e a prévia nasceu fora
    deles: ficou desde que nasceu sem carregar o `.env`, e o sintoma — "falha ao ler o
    Newcore: RuntimeError" — parecia fonte fora do ar, não configuração. Uma lista
    escrita à mão só cobre o que alguém lembrou de escrever.
    """
    return sorted(
        f.stem for f in _modulos_de_executar() if _com_main(f.read_text(encoding="utf-8"))
    )


def test_a_descoberta_de_pontos_de_entrada_bate_com_os_arquivos():
    """Conferência cruzada, não piso frouxo.

    Um piso (`>= 5`) deixaria a varredura perder módulos reais sem nada acusar — e
    perder um módulo é justamente deixá-lo fora da cobertura de `carregar_env`. Aqui os
    dois lados têm de fechar: todo arquivo de `executar` ou é ponto de entrada, ou está
    declarado em NAO_SAO_PONTO_DE_ENTRADA com a razão. Módulo novo obriga a escolher.
    """
    achados = set(_pontos_de_entrada())
    arquivos = {f.stem for f in _modulos_de_executar()}
    assert achados, "a varredura não achou ponto de entrada nenhum"
    assert achados == arquivos - set(NAO_SAO_PONTO_DE_ENTRADA), (
        "a varredura e os arquivos de src/executar divergem — "
        f"sem main: {sorted(arquivos - achados - set(NAO_SAO_PONTO_DE_ENTRADA))}; "
        f"declarados sem CLI mas com main: {sorted(achados & set(NAO_SAO_PONTO_DE_ENTRADA))}"
    )
    assert "previa" in achados and "sexta" in achados
    desconhecidos = set(SEM_CREDENCIAL) - achados
    assert not desconhecidos, (
        f"SEM_CREDENCIAL dispensa módulo que não existe mais: {sorted(desconhecidos)}"
    )


@pytest.mark.parametrize("modulo", [m for m in _pontos_de_entrada() if m not in SEM_CREDENCIAL])
def test_todo_ponto_de_entrada_carrega_o_ambiente(modulo: str, monkeypatch):
    """Sem isto, a chamada some de um deles sem nada quebrar — e o sintoma seria
    "variável ausente" numa máquina onde o `.env` existe, que é o diagnóstico errado."""
    import importlib

    mod = importlib.import_module(f"executar.{modulo}")
    chamou: list[bool] = []
    monkeypatch.setattr(mod, "carregar_env", lambda *a, **k: chamou.append(True) or [])
    with pytest.raises(SystemExit):
        mod.main(["--help"])
    assert chamou, f"executar.{modulo}.main não carregou o ambiente"


@pytest.mark.parametrize("modulo", sorted(SEM_CREDENCIAL))
def test_dispensado_de_ambiente_realmente_nao_toca_credencial(modulo: str):
    """A dispensa é afirmada, não pulada — o CI deste projeto recusa teste pulado, e
    com razão: um skip é indistinguível de um teste que passou.

    Olha o TEXTO-FONTE, não só o namespace. `not hasattr(mod, "carregar_env")` provaria
    menos do que esta docstring promete: um módulo que lesse `os.environ[...]` direto,
    ou que importasse o módulo em vez do nome, passaria afirmando o contrário do que
    faz. Qualquer sinal de credencial obriga a tirar o módulo de SEM_CREDENCIAL — que é
    exatamente quando o teste de cima volta a cobri-lo.
    """
    caminho = next(f for f in _modulos_de_executar() if f.stem == modulo)
    achados = sorted(set(_ACESSO_A_CREDENCIAL.findall(caminho.read_text(encoding="utf-8"))))
    assert not achados, (
        f"{modulo} passou a tocar credencial ({achados}): remova-o de SEM_CREDENCIAL"
    )
