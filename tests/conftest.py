"""Carrega o `.env` UMA vez, no começo da sessão de testes.

Não é conveniência: é determinismo. Sem isto, o resultado da suíte depende da
ORDEM. Os pontos de entrada chamam `carregar_env()` dentro de `main()`, e
`os.environ` é global ao processo — então um teste que exercita `main` publica
`POSTGRES_URL` para todos os que rodarem depois dele. Medido: a mesma suíte
passou de 73 pulados para 29 só por causa dessa contaminação, e quais 29 dependia
de quem rodou antes. Um teste que passa por herdar ambiente de outro é um teste
que não prova o que diz.

Carregando aqui, no início, a resposta é a mesma em qualquer ordem: ou a máquina
tem `.env`/ambiente e os testes de Postgres RODAM, ou não tem e todos pulam
juntos, pelo mesmo motivo declarado.

**No CI nada muda.** Lá não existe `.env` — as variáveis vêm do ambiente do job,
e `carregar_env` não sobrescreve o que já está posto. O passo "nenhum pode ser
pulado" continua valendo com a mesma força.

Quem precisa provar a AUSÊNCIA de uma variável (o `main` sem `POSTGRES_URL`
saindo por falha de fonte, por exemplo) não pode confiar em `delenv` sozinho:
tem de trocar de diretório também, senão o `.env` ao lado a repõe. Está feito
assim em `tests/test_aprovar.py`.
"""

from __future__ import annotations

import pytest

from config.ambiente import carregar_env


@pytest.fixture(scope="session", autouse=True)
def _ambiente_da_sessao() -> None:
    """Não sobrescreve: ambiente explícito do operador ou do CI sempre vence."""
    carregar_env()
