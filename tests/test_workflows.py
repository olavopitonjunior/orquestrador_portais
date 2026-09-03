"""Os workflows do GitHub precisam ser YAML válido — e nada no CI pode provar isso.

Existe por incidente, em 03/09/2026. Um passo novo embutia um script Python
multilinha dentro de `run: |`, e a indentação escapou do bloco. O efeito não foi
um check vermelho: foi **nenhum check**. O painel do PR dizia "no checks
reported", que se lê como "não há o que verificar" em vez de "a verificação
quebrou".

**A proteção de branch SEGUROU, e a primeira versão deste texto dizia o
contrário.** Medido no commit quebrado: `check-runs` devolveu `total_count: 0` e o
status combinado ficou `pending` — o GitHub não trata contexto obrigatório ausente
como satisfeito, então o merge estava BLOQUEADO. O que falhou foi o sinal, não o
portão, e a distinção decide o que se conserta.

O risco real é outro, e continua de pé: `enforce_admins` está desligado, e o dono
do repositório está a um `--admin` de mesclar com verificação nenhuma — lendo um
painel silencioso como "nada a verificar". Fechar isso é ação administrativa dele;
o que este teste fecha é a reincidência do defeito. As duas juntas, não uma.

**Por que a guarda precisa morar aqui, no pytest.** Um workflow inválido não roda,
então ele não pode acusar a si mesmo: qualquer passo de validação escrito dentro
do próprio `ci.yml` some junto com o arquivo que deveria conferir. O pytest roda
na máquina de quem editou, antes do push, que é o único momento em que ainda dá
para consertar sem descobrir pelo silêncio.

A lição de desenho, escrita para não se repetir: **script multilinha não mora em
YAML.** Vai para arquivo próprio, onde a sintaxe é conferida por ferramenta e o
código é testável. O passo virou duas linhas de laço.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parent.parent
WORKFLOWS = sorted((RAIZ / ".github" / "workflows").glob("*.yml"))


def test_ha_workflow_a_conferir():
    """Contraprova: sem isto, tudo abaixo passaria vazio se o diretório mudasse."""
    assert WORKFLOWS, "nenhum workflow encontrado — o teste passaria guardando nada"


@pytest.mark.parametrize("arquivo", WORKFLOWS, ids=lambda p: p.name)
def test_workflow_e_yaml_valido(arquivo: Path):
    # `import` no topo, nunca `importorskip`: o pyyaml é dependência declarada em
    # `[dependency-groups] dev` e travada no lock, então a ausência dele é ambiente
    # quebrado, não configuração legítima. Pulando, a guarda sumiria em silêncio
    # exatamente no momento em que este arquivo diz existir para agir — e o backstop
    # do CI ("nenhum pode ser pulado") acusaria com uma mensagem que crava o Postgres
    # como causa, mandando quem depurar olhar o banco.
    try:
        conteudo = yaml.safe_load(arquivo.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        pytest.fail(f"{arquivo.name} não é YAML válido — NENHUM check rodaria:\n{e}")
    assert isinstance(conteudo, dict) and conteudo.get("jobs"), (
        f"{arquivo.name} não declara `jobs` — o workflow não faria nada"
    )


def _comandos(conteudo: dict) -> list[tuple[str, str]]:
    """Todo `run:` do arquivo, com o nome do passo. Percorre a ESTRUTURA parseada.

    A primeira versão procurava os literais `python -c "` e `node -e "` no texto
    cru, e por isso não via a forma que JÁ ESTAVA no `ci.yml`: um `python -c` com a
    quebra de linha ANTES da aspa, dentro de um bloco `>`. A regra ficava a uma
    quebra de linha de ser burlada, e a mutação que a validou usou justamente as
    formas que o literal pegava.
    """
    saida: list[tuple[str, str]] = []
    for job in (conteudo.get("jobs") or {}).values():
        for passo in job.get("steps") or []:
            if isinstance(passo, dict) and isinstance(passo.get("run"), str):
                saida.append((passo.get("name") or "(sem nome)", passo["run"]))
    return saida


@pytest.mark.parametrize("arquivo", WORKFLOWS, ids=lambda p: p.name)
def test_nenhum_passo_embute_script_multilinha_de_outra_linguagem(arquivo: Path):
    """A regra que o incidente ensinou.

    Um interpretador recebendo código multilinha dentro de `run:` é a forma que
    quebrou o arquivo: a indentação do código não pertence ao YAML, e um deslize
    derruba o workflow inteiro — sem check vermelho, porque não há check. Chame um
    script; ele tem sintaxe conferida por ferramenta e é testável.

    O limite é DUAS linhas: um `-c` de uma linha só é idiomático e inofensivo.
    """
    conteudo = yaml.safe_load(arquivo.read_text(encoding="utf-8"))
    for nome, comando in _comandos(conteudo):
        normalizado = " ".join(comando.split())
        for interpretador in ("python -c", "python3 -c", "node -e", "node --eval"):
            pos = normalizado.find(interpretador)
            if pos == -1:
                continue
            # Quantas linhas o comando ORIGINAL tem depois do interpretador?
            trecho = comando[comando.find(interpretador) :]
            assert trecho.count("\n") <= 1, (
                f"{arquivo.name}, passo {nome!r}: `{interpretador}` recebe script "
                "multilinha. Ponha num arquivo — YAML inválido não roda check NENHUM, "
                "e o painel diz 'no checks reported' em vez de acusar o erro."
            )
