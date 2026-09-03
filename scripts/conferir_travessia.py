"""Confere que o TOML gerado pelo console carrega na rodada — e no destino certo.

    uv run python scripts/conferir_travessia.py <arquivo.toml> <esperado.json>

É o lado Python da TRAVESSIA. O console serializa em TypeScript, a rodada valida em
Python, e cada lado pode concordar consigo mesmo enquanto discorda do outro: nenhum
teste de um lado só cobre isso.

**Confere DESTINO, não só estrutura.** Carregar sem erro prova que o arquivo é um TOML
válido com as chaves certas; não prova que cada valor chegou onde deveria. Trocar
`pesos.super_destaque` por `pesos.destaque` na serialização produz um arquivo que
carrega limpo, com os dois níveis do ranking invertidos — e essa é a assimetria central
do produto (super destaque persegue valor esperado, destaque persegue probabilidade de
lead). A comparação contra o JSON de esperados é o que fecha isso.

**Por que é um arquivo, e não um `python -c` dentro do YAML.** Estava embutido, e a
indentação do bloco quebrou o `ci.yml` inteiro. Workflow inválido não roda NENHUM
check: o painel diz "no checks reported", que se lê como "nada a verificar" em vez de
"a verificação quebrou". Script de verdade tem sintaxe conferida por ferramenta.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from config.parametros import carregar


def _no_caminho(arvore: Any, caminho: str) -> Any:
    no = arvore
    for parte in caminho.split("."):
        no = no[parte]
    return no


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    toml, esperados = Path(argv[0]), Path(argv[1])

    parametros = carregar(toml)
    declarado = parametros.declarado

    faltando: list[str] = []
    for caminho, valor in json.loads(esperados.read_text(encoding="utf-8")).items():
        try:
            obtido = _no_caminho(declarado, caminho)
        except KeyError:
            faltando.append(f"  {caminho}: não chegou ao arquivo")
            continue
        # Comparação por texto: o console emite string e o TOML devolve int ou float.
        # O que se confere aqui é DESTINO e VALOR, não tipo — o tipo já é conferido
        # pelo próprio `carregar`, que recusa float onde exige inteiro.
        if str(obtido) != str(valor):
            faltando.append(f"  {caminho}: o console pediu {valor!r}, chegou {obtido!r}")

    if faltando:
        print(f"a travessia divergiu em {toml.name}:", file=sys.stderr)
        print("\n".join(faltando), file=sys.stderr)
        return 1
    print(f"  travessia ok: {toml.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
