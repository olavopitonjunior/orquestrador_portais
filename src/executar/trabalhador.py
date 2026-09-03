"""O processo que executa o que o console enfileira.

    uv run rodada-trabalhador            # laço contínuo
    uv run rodada-trabalhador --uma-vez  # pega no máximo um trabalho e sai

**Por que existe um processo separado.** O console é uma aplicação web e a rodada
leva minutos. Disparar por `spawn` dentro de uma requisição dá um filho que morre
no recarregamento do servidor de desenvolvimento — ou, se destacado, vira zumbi
que ninguém reconcilia — e uma linha "executando" que fica assim para sempre,
porque não há quem observe a transição. Aqui o console só INSERE; o estado vive no
banco e nada precisa sobreviver ao reinício.

**Chama o CLI, não a função.** Poderia importar `executar.sexta.executar` e ganhar
alguns milissegundos. Não faz, e a razão é dura: `main()` é quem recusa o arquivo-
modelo como entrada real, quem recusa `--hoje` no futuro e quem traduz cada falha
no seu código de saída. Reimplementar isso aqui seria manter duas versões da mesma
guarda, e a segunda envelheceria calada.

**Nunca re-tenta sozinho.** `gravar_rodada_decisao` não tem chave natural de
deduplicação: um processo que morre DEPOIS do commit e antes de terminar, se
retentado, produz a segunda rodada — válida, indistinguível, e ninguém saberia
qual foi aplicada. Retentar é ato explícito do dono, com as rodadas da janela
mostradas antes.

**Roda o filho em nível INFO.** Os runners mandam só o TIPO da exceção ao log e
guardam a causa em `debug` — em `DEBUG`, um traceback com dado do Newcore chegaria
à tabela de eventos e à tela.
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from config.ambiente import carregar_env
from dados.operacao import Trabalho, bater_ponto, concluir, criar, evento, reivindicar
from dados.registro.conexao import conectar

log = logging.getLogger("trabalhador")

# A raiz do repositório, deduzida deste arquivo. O `cwd` do filho é fixado aqui em vez
# de herdado: `carregar_env` procura o `.env` no diretório CORRENTE, e um trabalhador
# iniciado pelo agendador do sistema (cujo cwd é qualquer um) faria a rodada falhar com
# "variável ausente" — diagnóstico errado para "rodei do lugar errado".
RAIZ = Path(__file__).resolve().parent.parent.parent
COLETOR = RAIZ / "coletor-externo"


class ArgumentosInvalidos(ValueError):
    """O trabalho foi enfileirado com argumentos que não montam um comando."""


def comando(trabalho: Trabalho) -> tuple[list[str], Path]:
    """Traduz um trabalho no comando a executar. FUNÇÃO PURA — nada de I/O.

    Separada para ser testável sem subir processo: é aqui que mora a única lógica do
    trabalhador que pode estar errada de forma interessante, e um teste que precisasse
    raspar um portal para exercê-la não seria escrito.
    """
    a: Mapping[str, Any] = trabalho.argumentos
    py = [sys.executable, "-m"]

    if trabalho.tipo in ("sexta", "segunda"):
        argv = [*py, f"executar.{trabalho.tipo}"]
        if trabalho.tipo == "sexta":
            toml = a.get("parametros")
            if not toml:
                raise ArgumentosInvalidos(
                    "a sexta exige `parametros` (caminho do TOML declarado pelo dono): "
                    "treze dos catorze parâmetros são nulos e não há default"
                )
            argv += ["--parametros", str(toml)]
            if a.get("externo"):
                argv += ["--externo", str(a["externo"])]
        if a.get("destino"):
            argv += ["--destino", str(a["destino"])]
        if a.get("hoje"):
            argv += ["--hoje", str(a["hoje"])]
        if a.get("dry_run"):
            argv.append("--dry-run")
        return argv, RAIZ

    if trabalho.tipo in ("canario", "full"):
        # `npm run`, não `node` direto: os scripts do package.json são o contrato
        # documentado do raspador, e o README do operador manda usá-los.
        return ["npm", "run", "canary" if trabalho.tipo == "canario" else "full"], COLETOR

    if trabalho.tipo == "aprovar":
        rodada = a.get("rodada_id")
        por = a.get("por")
        if not rodada or not por:
            raise ArgumentosInvalidos(
                "aprovar exige `rodada_id` e `por`. Sem `por` só restaria a aprovação "
                "tácita, e ela AFIRMA que um prazo decorreu — prazo que é o parâmetro "
                "pendente nº 10, nulo"
            )
        return [*py, "executar.aprovar", "aprovar", str(rodada), "--por", str(por)], RAIZ

    raise ArgumentosInvalidos(f"não sei executar trabalho do tipo {trabalho.tipo!r}")


def _drenar(processo: subprocess.Popen[str], trabalho_id: int) -> None:
    """Lê o filho linha a linha e grava cada uma como evento, com commit por linha.

    Commit por linha é deliberado: a tela de acompanhamento existe para mostrar o que
    está acontecendo AGORA, e uma transação aberta até o fim da rodada mostraria tudo
    de uma vez, ao final, quando ninguém mais precisa.
    """
    assert processo.stdout is not None
    with conectar() as conn:
        conn.autocommit = True
        for linha in processo.stdout:
            texto = linha.rstrip("\n")
            if not texto:
                continue
            nivel = (
                "erro"
                if texto.startswith(("ERROR", "CRITICAL"))
                else ("aviso" if texto.startswith("WARNING") else "info")
            )
            evento(conn, trabalho_id, texto[:4000], nivel=nivel)


def executar_trabalho(trabalho: Trabalho) -> int:
    """Roda o trabalho e devolve o código de saída do processo filho."""
    argv, cwd = comando(trabalho)
    with conectar() as conn:
        conn.autocommit = True
        evento(conn, trabalho.id, f"$ {' '.join(argv)}  (em {cwd})")

    ambiente = dict(os.environ)
    # INFO, nunca DEBUG: ver o cabeçalho do módulo.
    ambiente.setdefault("PYTHONUNBUFFERED", "1")
    processo = subprocess.Popen(  # noqa: S603 — argv é montado por `comando`, nunca por shell
        argv,
        cwd=cwd,
        env=ambiente,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    try:
        _drenar(processo, trabalho.id)
    except BaseException:
        # Se o banco cair no meio da drenagem, o filho continuaria rodando contra o
        # Newcore sem ninguém para esperá-lo nem matá-lo — processo órfão consumindo
        # uma conexão de leitura por tempo indefinido. Matar é a escolha certa: o
        # trabalho já perdeu o log, e uma rodada cujo progresso ninguém vê é pior que
        # uma rodada que não aconteceu.
        processo.kill()
        processo.wait()
        raise
    return processo.wait()


def _ciclo() -> bool:
    """Um giro do laço. True se pegou algum trabalho."""
    with conectar() as conn:
        conn.autocommit = True
        bater_ponto(conn)
        trabalho = reivindicar(conn)
    if trabalho is None:
        return False

    log.info("trabalho %s (%s) reivindicado", trabalho.id, trabalho.tipo)
    try:
        codigo = executar_trabalho(trabalho)
    except ArgumentosInvalidos as e:
        # Argumento inválido é falha do PEDIDO, não da execução: o código 5 é o mesmo
        # que o runner usaria para parâmetro impossível, e a mensagem vai para a tela.
        with conectar() as conn:
            conn.autocommit = True
            evento(conn, trabalho.id, str(e), nivel="erro")
            concluir(conn, trabalho.id, codigo_saida=5)
        return True
    except FileNotFoundError as e:
        # Caso especial porque o genérico abaixo apagaria o diagnóstico. Sob o
        # agendador do macOS o PATH é mínimo (`/usr/bin:/bin:/usr/sbin:/sbin`), e um
        # `npm` de homebrew, nvm ou mise não está lá. A mensagem precisa NOMEAR o
        # executável: `argv[0]` é montado por `comando()`, nunca é dado do Newcore, e
        # sem ele a tela diria só "FileNotFoundError" — verdadeiro e inútil.
        faltando = getattr(e, "filename", None) or "o executável do comando"
        with conectar() as conn:
            conn.autocommit = True
            evento(
                conn,
                trabalho.id,
                f"{faltando} não foi encontrado no PATH deste processo. Se o "
                "trabalhador foi iniciado pelo agendador do sistema, o PATH dele é "
                "mínimo e não inclui gerenciadores de versão.",
                nivel="erro",
            )
            concluir(conn, trabalho.id, codigo_saida=1)
        log.error("trabalho %s: %s ausente do PATH", trabalho.id, faltando)
        return True
    except Exception as e:  # noqa: BLE001 — o laço não pode morrer por um trabalho ruim
        with conectar() as conn:
            conn.autocommit = True
            evento(conn, trabalho.id, f"falha ao executar: {type(e).__name__}", nivel="erro")
            concluir(conn, trabalho.id, codigo_saida=1)
        log.exception("trabalho %s falhou", trabalho.id)
        return True

    with conectar() as conn:
        conn.autocommit = True
        concluir(conn, trabalho.id, codigo_saida=codigo)
        evento(conn, trabalho.id, f"terminou com código {codigo}")
    return True


def main(argv: Sequence[str] | None = None) -> int:
    # Ambiente do `.env` do diretório CORRENTE — ver o docstring de config.ambiente.
    carregar_env()
    p = argparse.ArgumentParser(description="Executa os trabalhos que o console enfileira.")
    p.add_argument("--uma-vez", action="store_true", help="pega no máximo um trabalho e sai")
    p.add_argument("--intervalo", type=float, default=2.0, help="segundos entre sondagens")
    p.add_argument(
        "--enfileirar",
        metavar="TIPO",
        help="apenas enfileira um trabalho do tipo dado e sai (para operar sem o console)",
    )
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.enfileirar:
        with conectar() as conn:
            conn.autocommit = True
            log.info("trabalho %s enfileirado", criar(conn, args.enfileirar))
        return 0

    if args.uma_vez:
        _ciclo()
        return 0

    log.info("trabalhador no ar; sondando a cada %.1fs", args.intervalo)
    while True:
        try:
            if not _ciclo():
                time.sleep(args.intervalo)
        except KeyboardInterrupt:
            log.info("encerrando")
            return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
