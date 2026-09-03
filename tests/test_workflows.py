"""Os workflows do GitHub precisam ser YAML válido — e nada no CI pode provar isso.

Existe por incidente, em 03/09/2026. Um passo novo embutia um script Python
multilinha dentro de `run: |`, e a indentação escapou do bloco. O efeito não foi
um check vermelho: foi **nenhum check**. O painel do PR dizia "no checks
reported", que se lê como "não há o que verificar" em vez de "a verificação
quebrou" — e o merge seguiria com a proteção de branch satisfeita por vacuidade.

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

RAIZ = Path(__file__).resolve().parent.parent
WORKFLOWS = sorted((RAIZ / ".github" / "workflows").glob("*.yml"))


def test_ha_workflow_a_conferir():
    """Contraprova: sem isto, tudo abaixo passaria vazio se o diretório mudasse."""
    assert WORKFLOWS, "nenhum workflow encontrado — o teste passaria guardando nada"


@pytest.mark.parametrize("arquivo", WORKFLOWS, ids=lambda p: p.name)
def test_workflow_e_yaml_valido(arquivo: Path):
    yaml = pytest.importorskip("yaml", reason="pyyaml não instalado")
    try:
        conteudo = yaml.safe_load(arquivo.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        pytest.fail(f"{arquivo.name} não é YAML válido — NENHUM check rodaria:\n{e}")
    assert isinstance(conteudo, dict) and conteudo.get("jobs"), (
        f"{arquivo.name} não declara `jobs` — o workflow não faria nada"
    )


@pytest.mark.parametrize("arquivo", WORKFLOWS, ids=lambda p: p.name)
def test_nenhum_passo_embute_script_multilinha_de_outra_linguagem(arquivo: Path):
    """A regra que o incidente ensinou.

    `python -c "` seguido de quebra de linha dentro de um `run:` é exatamente a forma
    que quebrou o arquivo: a indentação do código não pertence ao YAML, e um deslize
    derruba o workflow inteiro em silêncio. Chame um script; ele tem sintaxe conferida.
    """
    texto = arquivo.read_text(encoding="utf-8")
    for marcador in ('python -c "', "python -c '", 'node -e "', "node -e '"):
        pos = texto.find(marcador)
        if pos == -1:
            continue
        resto = texto[pos + len(marcador) :]
        assert "\n" not in resto.split(marcador[-1])[0], (
            f"{arquivo.name} embute script multilinha em `{marcador.strip()}`. "
            "Ponha num arquivo: YAML inválido não roda check NENHUM, e o painel diz "
            "'no checks reported' em vez de acusar o erro."
        )
