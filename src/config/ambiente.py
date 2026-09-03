"""Carrega o `.env` DENTRO do Python, literalmente.

Existe porque faltava o meio-termo. Os runners leem `os.environ` direto
(`dados/newcore.py`, `dados/registro/conexao.py`), nada no projeto populava esse
ambiente, e o jeito óbvio de fazê-lo está **proibido**: `docs/mapa-de-dados.md`
registra que carregar o arquivo com `set -a; . arquivo` faz o shell **expandir
metacaracteres do valor** e produzir um `Access denied` indistinguível de
credencial errada. A instrução de lá é exatamente esta: ler o arquivo dentro do
Python, literalmente. Aqui ela vira código em vez de recado.

**Literalmente** quer dizer sem interpretação nenhuma do valor: nada de expandir
`$VAR`, nada de processar `\\n`, nada de juntar linhas. O que está entre o `=` e
o fim da linha é o valor, tirando um par de aspas externas se houver. Um valor
com `$`, com crase ou com `!` chega intacto — que é o ponto.

**Não sobrescreve por padrão.** O CI injeta as variáveis pelo ambiente do job e
não tem `.env`; um `.env` de máquina de desenvolvimento jamais pode vencer o que
o operador ou o CI já exportou. Quem quiser o contrário pede `sobrescrever=True`.

**Ausência não é erro.** Sem arquivo, devolve lista vazia e quem precisar da
variável falha depois, com a mensagem específica que já existe (`newcore.py` diz
quais faltam e manda gerar o `.env`; `conexao.py` idem). Um erro aqui roubaria
esse diagnóstico e diria só "arquivo não encontrado".

**O caminho padrão é relativo ao DIRETÓRIO CORRENTE, e isso é contrato, não
acaso.** `.env` é gerado na raiz do repositório (`op inject -i .env.tmpl -o .env`)
e os comandos são documentados para rodar de lá. Quem invocar de outro diretório
carrega nada — em silêncio, porque ausência não é erro — e falha adiante com
"variável ausente", que é o diagnóstico errado para o problema real. Duas
consequências práticas: o agendador do sistema operacional precisa entrar no
diretório antes (`cd <repo> && ...`), e o trabalhador que o console dispara fixa
o `cwd` explicitamente em vez de herdá-lo.

Ancorar o padrão na raiz do repositório foi considerado e recusado: tornaria
impossível um teste provar a AUSÊNCIA da variável, porque o `.env` real da árvore
seria encontrado de qualquer diretório — e é justamente essa a garantia que
`tests/test_aprovar.py` precisa exercer.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# `export ` opcional porque arquivos de ambiente frequentemente o trazem, e recusá-lo
# seria rigor sem ganho. O nome segue a convenção POSIX de variável de ambiente.
_LINHA = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


def _desaspar(valor: str) -> str:
    """Tira UM par de aspas externas. Não interpreta nada do miolo — nem escape,
    nem variável: `"a$b"` vale `a$b`, que é a razão de este módulo existir."""
    if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in ("'", '"'):
        return valor[1:-1]
    return valor


def carregar_env(caminho: Path | str = ".env", *, sobrescrever: bool = False) -> list[str]:
    """Põe no `os.environ` o que o arquivo declara. Devolve os nomes DEFINIDOS aqui.

    O retorno é a lista do que esta chamada mudou — não do que o arquivo continha.
    Serve para o chamador dizer "carreguei 5 variáveis do .env" sem nunca tocar em
    valor, e para um teste provar que a precedência do ambiente foi respeitada.
    """
    arquivo = Path(caminho)
    if not arquivo.is_file():
        return []

    definidas: list[str] = []
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        if not linha.strip() or linha.lstrip().startswith("#"):
            continue
        casa = _LINHA.match(linha)
        if casa is None:
            # Linha que não é atribuição não é erro: o template carrega comentários
            # e o arquivo pode ganhar seções. Ignorar em silêncio é o certo aqui —
            # o barulho útil vem de quem precisa da variável e não a encontra.
            continue
        nome, bruto = casa.group(1), casa.group(2)
        if not sobrescrever and nome in os.environ:
            continue
        os.environ[nome] = _desaspar(bruto)
        definidas.append(nome)
    return definidas
