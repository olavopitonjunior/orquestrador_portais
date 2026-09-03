"""Emite o contrato do TOML da rodada como JSON, para o console consumir.

    uv run rodada-contrato > console/lib/contrato-parametros.json

O console importa esse JSON commitado em vez de chamar Python a cada requisição:
o painel não executa processo (é a regra de arquitetura do console), e um passo
de CI compara a saída deste comando com o arquivo commitado. Divergir os dois
quebra a build — que é como o formulário fica impedido de envelhecer em silêncio
enquanto o validador muda.

Saída determinística: `sort_keys` desligado de propósito (a ordem dos campos é a
do contrato, que é a ordem em que o formulário os apresenta), `ensure_ascii`
desligado para o texto de ajuda sair legível no diff, e uma quebra de linha final
para o arquivo casar com o que o `>` de um shell produz.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from config.contrato import contrato


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Emite o contrato dos parâmetros da rodada em JSON (para o console)."
    )
    p.parse_args(argv)
    print(json.dumps(contrato(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
