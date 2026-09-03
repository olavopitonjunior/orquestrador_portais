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
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import psycopg

from config.ambiente import carregar_env
from dados.operacao import (
    TIPOS,
    Trabalho,
    TrabalhoEmVoo,
    bater_ponto,
    concluir,
    criar,
    evento,
    ler_parametros,
    ligar_declaracao,
    reivindicar,
)
from dados.registro.conexao import conectar

log = logging.getLogger("trabalhador")

# A raiz do repositório, deduzida deste arquivo. O `cwd` do filho é fixado aqui em vez
# de herdado: `carregar_env` procura o `.env` no diretório CORRENTE, e um trabalhador
# iniciado pelo agendador do sistema (cujo cwd é qualquer um) faria a rodada falhar com
# "variável ausente" — diagnóstico errado para "rodei do lugar errado".
# Dois períodos, e a distinção importa. A sondagem precisa ser curta para o progresso
# parecer ao vivo; o batimento não — ele só precisa caber com folga no prazo que a tela
# usa para declarar o trabalhador morto (30s). Iguais, uma raspagem de horas faria
# ~7.200 escritas por hora numa linha só, com o autovacuum girando por nada.
SONDAGEM = 0.5
BATIMENTO = 5.0

RAIZ = Path(__file__).resolve().parent.parent.parent
COLETOR = RAIZ / "coletor-externo"


# Onde ficam os artefatos de uma execução: FORA de `saida/`, que é do produto.
#
# A primeira versão dizia isto no comentário e punha a constante dentro de `saida/`
# — comentário e código afirmando o oposto, que neste projeto é bug do código. E o
# incômodo era legítimo: `saida/sexta/` guarda a planilha, que é o entregável
# contratual, e um expurgo de operação por glob alcançaria justamente ela.
#
# Mover agora custa uma linha de `.gitignore`; depois da primeira sexta real custaria
# mover artefato vivo que o console lê por caminho.
EXECUCOES = RAIZ / "var" / "execucoes"


def eventos_de(trabalho_id: int) -> Path:
    return EXECUCOES / f"trabalho-{trabalho_id}.ndjson"


def resultado_de(trabalho_id: int) -> Path:
    return EXECUCOES / f"trabalho-{trabalho_id}.json"


def ler_resultado(trabalho_id: int) -> dict[str, Any]:
    """O desfecho que o runner declarou. Vazio quando o arquivo não existe — o que é
    normal para tipos que não o escrevem (raspagem, aprovação) e para um processo
    morto antes de chegar ao fim."""
    caminho = resultado_de(trabalho_id)
    if not caminho.is_file():
        return {}
    try:
        return dict(json.loads(caminho.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        # Arquivo ilegível não pode derrubar a conclusão do trabalho: o código de
        # saída do processo continua sendo a verdade sobre o desfecho.
        return {}


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
            if a.get("recorte_pela_raspagem"):
                argv.append("--recorte-pela-raspagem")
            # Os dois arquivos de contrato da execução, em caminhos derivados do id
            # do trabalho: o de eventos alimenta a tela ao vivo, e o de resultado é
            # por onde o `rodada_id` chega até aqui. Parsear a prosa do log seria a
            # alternativa, e aí uma mudança de redação viraria defeito de integração.
            #
            # Só a SEXTA: a segunda não tem estas opções, e passá-las a ela faria o
            # argparse recusar o comando inteiro. Quando a segunda as ganhar, esta
            # linha sobe um nível — e o teste de `comando()` para a segunda é o que
            # obriga a lembrar disso.
            argv += [
                "--eventos",
                str(eventos_de(trabalho.id)),
                "--resultado",
                str(resultado_de(trabalho.id)),
            ]
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


def _acompanhar(caminho: Path | None, trabalho_id: int, parar: threading.Event) -> None:
    """Bate o ponto e lê o progresso ENQUANTO a rodada corre. Uma thread, duas tarefas.

    **O batimento precisa acontecer aqui, e não só no começo do ciclo.** Ele era dado
    uma vez, antes de a rodada começar; uma sexta real leva MINUTOS, e a tela considera
    morto um trabalhador sem batimento há 30 segundos. Resultado medido: em toda rodada
    de verdade, meio minuto depois, o acompanhamento passaria a dizer "o trabalhador
    não está no ar" — falso, e justamente na tela feita para tranquilizar quem acabou de
    disparar. E o alarme falso é o que mais provavelmente faria alguém matar o processo
    no meio, o que arrisca a rodada duplicada que a fila existe para impedir.

    Vale para TODO tipo de trabalho, com ou sem arquivo de progresso: a raspagem também
    leva minutos, e o batimento não é do NDJSON, é do processo.

    Precisa ser concorrente. A alternativa — ler o arquivo ao fim — daria o mesmo
    conteúdo e nenhuma serventia: a tela de acompanhamento existe para mostrar em que
    etapa a rodada está AGORA, e um progresso que só aparece depois de terminar é um
    relatório, não um acompanhamento.

    Sondagem, não notificação de sistema de arquivos: a rodada leva minutos e emite
    oito linhas: meio segundo de latência é imperceptível, e depender de `inotify` ou
    `FSEvents` traria uma dependência por plataforma para resolver o que uma leitura
    barata resolve.

    Falha aqui NÃO derruba a rodada. Progresso é conveniência; a rodada é o trabalho.
    """
    lidas = 0
    falhas = 0
    ultimo_ponto = 0.0
    conn: psycopg.Connection | None = None
    try:
        while True:
            terminou = parar.wait(SONDAGEM)
            try:
                # A conexão nasce e RENASCE dentro do try. Estava aberta fora dele, e
                # isso produzia duas versões do mesmo defeito que este acompanhamento
                # existe para evitar: se `conectar()` falhasse no arranque, a thread
                # morria calada e a rodada inteira ficava SEM batimento — o alarme falso
                # de "trabalhador morto" pelo tempo todo; e se a conexão morresse no
                # meio, o psycopg não reconecta, então todo comando seguinte levantava e
                # o laço girava falhando até o fim. O CHANGELOG dizia resistir a "um
                # soluço na conexão", e o teste provava só o caso leve, com a conexão
                # viva. Agora resiste ao que a frase nomeia.
                if conn is None or conn.closed:
                    conn = conectar()
                    conn.autocommit = True

                agora = time.monotonic()
                if agora - ultimo_ponto >= BATIMENTO:
                    # Período PRÓPRIO, maior que o da sondagem. Batendo a cada meia
                    # segundo seriam ~7.200 escritas por hora numa linha só — e a
                    # raspagem dura horas. O prazo que a tela usa é de 30s; 5s dá
                    # margem de seis vezes com 1/10 da escrita.
                    bater_ponto(conn)
                    ultimo_ponto = agora

                if caminho is not None and caminho.is_file():
                    linhas = caminho.read_text(encoding="utf-8").splitlines()
                    novas = linhas[lidas:]
                    for posicao, linha in enumerate(novas):
                        try:
                            dado = json.loads(linha)
                        except ValueError:
                            if posicao == len(novas) - 1:
                                # ÚLTIMA linha da leitura: o escritor pode estar no meio
                                # dela. Não avança o cursor, e a próxima volta relê.
                                break
                            # No MEIO do arquivo é outra coisa — escrita truncada, um
                            # glitch — e parar aqui travaria o seguidor no mesmo ponto
                            # para sempre, fazendo TODAS as etapas seguintes sumirem em
                            # silêncio. Avança e avisa.
                            log.warning("linha ilegível no progresso do trabalho %s", trabalho_id)
                            lidas += 1
                            continue
                        evento(
                            conn,
                            trabalho_id,
                            f"etapa concluída: {dado.get('no', '?')}",
                            no_grafo=str(dado.get("no") or ""),
                            resumo=dado.get("resumo")
                            if isinstance(dado.get("resumo"), dict)
                            else None,
                        )
                        lidas += 1
            except Exception:  # noqa: BLE001 — acompanhar é conveniência; a rodada é o trabalho
                # `OSError` sozinho não bastava: `evento()` levanta `psycopg.Error`, que
                # não é `OSError`, e a thread morria calada — as etapas paravam sem uma
                # palavra na tela. "Não derruba a rodada" não é o mesmo que "avisa".
                #
                # E desistir na primeira falha era compromisso mais forte do que a
                # intenção pedia: um soluço momentâneo na conexão congelaria o painel
                # pelo resto de uma rodada de minutos, com o batimento junto — e aí a
                # tela passaria a mentir que o trabalhador morreu. Segue tentando; só
                # desiste quando o processo termina.
                falhas += 1
                if falhas in (1, 10, 100):
                    log.warning(
                        "acompanhamento do trabalho %s falhou (%dª vez)",
                        trabalho_id,
                        falhas,
                        exc_info=True,
                    )
            if terminou:
                return
    finally:
        if conn is not None and not conn.closed:
            conn.close()


# Gramática de CANARY_STEPS: inteiros separados por vírgula. É a mesma que o console
# valida antes de enfileirar; aqui de novo porque `argumentos` também pode ser escrito
# à mão em SQL, e o que vai para o ambiente de um processo filho não pode ser texto
# livre.
# `[0-9]` e `fullmatch`, não `\d` e `$`: `\d` casa dígito Unicode (`١`, `１`) e `$`
# casa antes de um `\n` final — o console recusa os dois, e "a mesma gramática" tem
# de ser verdade, não intenção.
_PASSOS_DO_CANARIO = re.compile(r"[0-9]+(,[0-9]+)*")


def ambiente_do_trabalho(trabalho: Trabalho) -> dict[str, str]:
    """As variáveis de ambiente que um trabalho pode acrescentar ao filho. FUNÇÃO PURA.

    Lista BRANCA, não passagem: só `canary_steps` (→ `CANARY_STEPS`, só no canário) é
    aceito. Deixar `argumentos` virar ambiente livre seria dar a quem escreve na fila
    controle sobre `PATH`, `OUT_DIR` ou `CDP_PORT` do raspador.
    """
    a: Mapping[str, Any] = trabalho.argumentos
    passos = a.get("canary_steps")
    if passos is None:
        return {}
    if trabalho.tipo != "canario":
        raise ArgumentosInvalidos("`canary_steps` só faz sentido no canário")
    if not isinstance(passos, str) or not _PASSOS_DO_CANARIO.fullmatch(passos):
        raise ArgumentosInvalidos(
            f"`canary_steps` precisa ser inteiros separados por vírgula, veio {passos!r}"
        )
    return {"CANARY_STEPS": passos}


def proximo_encadeado(trabalho: Trabalho) -> tuple[str, dict[str, Any]] | None:
    """O trabalho que este deve enfileirar ao terminar BEM. FUNÇÃO PURA.

    `argumentos.encadear = {"tipo": ..., "argumentos": {...}}` é o "um clique" do
    console: raspar e, se a raspagem terminar com 0, decidir apontando para o `out/`.
    Validado ANTES de o pai rodar: um encadeado malformado descoberto depois de horas
    de raspagem seria a pior hora de descobrir. Um só nível — o encadeado não pode
    encadear outro, senão um pedido escrito à mão poderia programar a fila inteira.
    """
    enc = trabalho.argumentos.get("encadear")
    if enc is None:
        return None
    if not isinstance(enc, Mapping) or not isinstance(enc.get("tipo"), str):
        raise ArgumentosInvalidos("`encadear` precisa ser {tipo: str, argumentos: {...}}")
    tipo = enc["tipo"]
    if tipo not in TIPOS:
        raise ArgumentosInvalidos(f"`encadear.tipo` desconhecido: {tipo!r}")
    argumentos = enc.get("argumentos")
    if argumentos is None:
        argumentos = {}
    elif not isinstance(argumentos, Mapping):
        raise ArgumentosInvalidos("`encadear.argumentos` precisa ser um objeto")
    if "encadear" in argumentos:
        raise ArgumentosInvalidos("encadeamento tem um nível só: o encadeado não encadeia")
    return tipo, dict(argumentos)


def encadear(conn: psycopg.Connection, trabalho: Trabalho, codigo: int) -> int | None:
    """Enfileira o encadeado se o pai terminou com 0; senão, diz por que não.

    Chamado DEPOIS de `concluir` do pai, na mesma conexão: o encadeado nasce com o
    pai já terminal, então nunca disputa o índice de "um por tipo em voo" com ele.
    `TrabalhoEmVoo` (já há um do tipo encadeado) vira evento de erro no pai, não
    exceção — o pai terminou bem, e isso não muda.
    """
    try:
        proximo = proximo_encadeado(trabalho)
    except ArgumentosInvalidos as e:
        # Chamado de DENTRO de um `except` do laço: levantar aqui mataria o trabalhador
        # inteiro por um pedido malformado. O pai já está terminal; só se diz por quê.
        evento(conn, trabalho.id, f"encadeamento inválido, ignorado: {e}", nivel="erro")
        return None
    if proximo is None:
        return None
    tipo, argumentos = proximo
    if codigo != 0:
        evento(
            conn,
            trabalho.id,
            f"encadeamento CANCELADO: este trabalho terminou com código {codigo}, então o "
            f"'{tipo}' encadeado não foi enfileirado",
            nivel="aviso",
        )
        return None
    try:
        # Quem clicou continua no rastro do filho; o pai vai junto, para o log dizer
        # de onde o pedido veio.
        novo = criar(
            conn,
            tipo,
            pedido_por=f"{trabalho.pedido_por or '?'} (via trabalho {trabalho.id})",
            argumentos=argumentos,
        )
    except TrabalhoEmVoo as e:
        evento(conn, trabalho.id, f"encadeamento não enfileirado: {e}", nivel="erro")
        return None
    evento(conn, trabalho.id, f"enfileirou o trabalho {novo} ({tipo}) encadeado")
    return novo


def executar_trabalho(trabalho: Trabalho) -> int:
    """Roda o trabalho e devolve o código de saída do processo filho."""
    argv, cwd = comando(trabalho)
    # Antes do evento que grava o comando: um argumento recusado aqui não pode deixar no
    # log um "$ npm run canary" que nunca rodou.
    extra = ambiente_do_trabalho(trabalho)
    with conectar() as conn:
        conn.autocommit = True
        evento(conn, trabalho.id, f"$ {' '.join(argv)}  (em {cwd})")

    ambiente = dict(os.environ)
    ambiente.update(extra)
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
    # O seguidor do NDJSON roda em paralelo com a drenagem da saída: são duas fontes
    # independentes (o arquivo traz os nós do grafo, a saída traz o log humano), e
    # esperar uma para ler a outra perderia a razão de existir de ambas.
    parar = threading.Event()
    eventos = trabalho.argumentos.get("eventos_ndjson")
    # SEMPRE, e não só quando há progresso a ler: o batimento é do processo, não do
    # arquivo, e sem ele a tela declara morto um trabalhador que está trabalhando.
    seguidor = threading.Thread(
        target=_acompanhar,
        args=(Path(str(eventos)) if eventos else None, trabalho.id, parar),
        daemon=True,
    )
    seguidor.start()

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
    finally:
        # Sinaliza DEPOIS da drenagem: o seguidor faz mais uma passada antes de sair,
        # senão as últimas etapas — justamente as que dizem como terminou — ficariam
        # de fora por uma corrida de meio segundo.
        parar.set()
        seguidor.join(timeout=5)
        if seguidor.is_alive():
            # Só acontece com a conexão do acompanhamento pendurada. É `daemon`, então
            # não segura a saída do processo — mas fica com uma conexão aberta, e sem
            # esta linha a única pista seria o número de conexões subindo.
            log.warning("o acompanhamento do trabalho %s não encerrou em 5s", trabalho.id)
    return processo.wait()


def materializar_parametros(trabalho: Trabalho) -> Trabalho:
    """Escreve em disco o TOML que o console declarou, e devolve o trabalho apontando
    para ele.

    O console guarda TEXTO no banco, não caminho — e é o certo: `origem` viaja para a
    planilha e para o Registro, então ela precisa dizer de QUAL declaração a rodada
    saiu, não de um arquivo qualquer que alguém pode ter mexido. O nome carrega o id do
    trabalho pela mesma razão.

    Quem já manda `parametros` direto (a linha de comando, o teste de fumaça) não passa
    por aqui: os dois caminhos convivem, e o do console é o que precisa da tradução.
    """
    declaracao = trabalho.argumentos.get("parametros_declarados_id")
    if declaracao is None:
        return trabalho
    with conectar() as conn:
        conn.autocommit = True
        toml = ler_parametros(conn, int(declaracao))
        if toml is None:
            raise ArgumentosInvalidos(
                f"a declaração de parâmetros {declaracao} não existe — o trabalho foi "
                "enfileirado apontando para algo que sumiu do Registro de operação"
            )
        ligar_declaracao(conn, int(declaracao), trabalho.id)
    destino = EXECUCOES / f"rodada-{trabalho.id}.toml"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(toml, encoding="utf-8")
    return replace(trabalho, argumentos={**trabalho.argumentos, "parametros": str(destino)})


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
        pronto = materializar_parametros(trabalho)
        # O caminho do NDJSON é o mesmo que `comando()` passa à rodada — declarado aqui
        # para o seguidor não ter de recalculá-lo e as duas metades não divergirem.
        if pronto.tipo == "sexta":
            pronto = replace(
                pronto,
                argumentos={**pronto.argumentos, "eventos_ndjson": str(eventos_de(pronto.id))},
            )
        # Falha rápido: um encadeado malformado descoberto DEPOIS de horas de raspagem
        # seria a pior hora de descobrir.
        proximo_encadeado(pronto)
        codigo = executar_trabalho(pronto)
    except ArgumentosInvalidos as e:
        # Argumento inválido é falha do PEDIDO, não da execução: o código 5 é o mesmo
        # que o runner usaria para parâmetro impossível, e a mensagem vai para a tela.
        with conectar() as conn:
            conn.autocommit = True
            evento(conn, trabalho.id, str(e), nivel="erro")
            concluir(conn, trabalho.id, codigo_saida=5)
            encadear(conn, trabalho, 5)
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
            encadear(conn, trabalho, 1)
        log.error("trabalho %s: %s ausente do PATH", trabalho.id, faltando)
        return True
    except Exception as e:  # noqa: BLE001 — o laço não pode morrer por um trabalho ruim
        with conectar() as conn:
            conn.autocommit = True
            evento(conn, trabalho.id, f"falha ao executar: {type(e).__name__}", nivel="erro")
            concluir(conn, trabalho.id, codigo_saida=1)
            encadear(conn, trabalho, 1)
        log.exception("trabalho %s falhou", trabalho.id)
        return True

    # Fecha o defeito registrado em bug.md: a coluna existia, com chave estrangeira,
    # e ninguém a preenchia — o acervo do console nunca ligaria execução a rodada.
    declarado = ler_resultado(trabalho.id)
    rodada_id = declarado.get("rodada_id")
    with conectar() as conn:
        conn.autocommit = True
        concluir(conn, trabalho.id, codigo_saida=codigo, rodada_id=rodada_id)
        if rodada_id is not None:
            evento(conn, trabalho.id, f"rodada {rodada_id} gravada no Registro")
        evento(conn, trabalho.id, f"terminou com código {codigo}")
        # O "um clique" do console: só depois de o pai estar terminal, na mesma conexão.
        encadear(conn, trabalho, codigo)
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
