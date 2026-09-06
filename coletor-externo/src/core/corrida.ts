// A CORRIDA: uma execução do coletor, do login ao `status.json`.
//
// Por que este módulo existe, e não vive em `run.ts`. O entrypoint termina com
// `void main()`: qualquer teste que o importasse DISPARARIA uma coleta de verdade.
// É por isso que a orquestração — modo, checkpoint, que arquivo escrever, o que
// apagar — nunca teve teste, e é onde moravam os três defeitos do contrato de
// arquivo. Aqui as dependências de mundo (conectar ao Chrome, ir ao painel, o
// relógio, o diretório) entram por parâmetro, e um teste roda a corrida inteira
// com um Portal falso, sem navegador.
//
// O que este módulo NÃO faz: não importa `cdp/`. Quem constrói a conexão real é
// `run.ts`; aqui só existe a forma dela.

import { writeFile, mkdir, readFile, rm, rename } from 'fs/promises';
import { existsSync } from 'fs';
import { join } from 'path';
import type { Page } from 'puppeteer-core';
import { NEEDS_WARM_FLAG } from './config';
import { CsvWriter, clearCheckpoint, loadCheckpoint, saveCheckpoint } from './csv-writer';
import { buildShards } from './sharding';
import { AuthExpiredError, BlockedError } from './block-detector';
import { Checkpoint, CONTRATO_CHECKPOINT, Shard } from './types';
import { Portal } from '../portal';

export type Modo = 'canary' | 'full';

/** A conexão como a corrida a enxerga. Tipo estreito de propósito: o teste passa um
 *  duplo sem precisar de um Browser inteiro do puppeteer. */
export interface Conexao {
  browser: { disconnect(): Promise<void> };
  page: Page;
}

export interface DepsCorrida {
  conectar: (portal: Portal) => Promise<Conexao>;
  irAoPainel: (page: Page, portal: Portal, log: (msg: string) => void) => Promise<void>;
  log: (msg: string) => void;
  agora: () => Date;
  outDir: string;
  /** degraus do canário; o maior define quanto ele coleta. Injetado como o resto do
   *  mundo externo — era a única leitura de `config` que sobrava neste módulo, e não
   *  é só log: define volume. */
  degrausDoCanario: number[];
}

export interface Desfecho {
  result: 'ok' | 'blocked' | 'error';
  rows: number;
  exitCode: 0 | 1 | 2;
}

/** O arquivo que cada modo escreve.
 *
 *  Canário e full têm arquivos SEPARADOS porque medem coisas diferentes: o canário
 *  é a sonda que o console lê para decidir se libera a coleta completa; o full é o
 *  estoque. Compartilhando o mesmo arquivo, uma sonda de 1.000 linhas ficava
 *  indistinguível da cauda de um full de 55 mil, e o console media o acúmulo. */
export function nomeDoCsv(portalId: string, modo: Modo): string {
  return modo === 'canary' ? `${portalId}.canario.csv` : `${portalId}.csv`;
}

/** Esta corrida pode retomar o checkpoint que está no disco?
 *
 *  Retomar é a exceção, não o padrão. Só vale sobre a MESMA coisa: mesmo portal,
 *  mesmo modo, contrato atual, e com página já concluída. Um checkpoint sem
 *  `contrato` foi escrito pela versão que nunca o apagava ao concluir — retomá-lo
 *  é exatamente o defeito que fazia a corrida seguinte não coletar nada e ainda
 *  assim se declarar `ok`. */
export function podeRetomar(
  cp: Checkpoint | null,
  portalId: string,
  modo: Modo,
  /** o portal pagina linearmente (tem `collectPage`) ou coleta por shards */
  paginado: boolean
): { retoma: boolean; porque: string } {
  if (cp == null) return { retoma: false, porque: 'não há checkpoint' };
  if (cp.contrato !== CONTRATO_CHECKPOINT) {
    return { retoma: false, porque: `checkpoint de contrato ${cp.contrato ?? 'ausente'} (atual: ${CONTRATO_CHECKPOINT})` };
  }
  if (cp.portal !== portalId) return { retoma: false, porque: `checkpoint é do portal "${cp.portal}"` };
  if (cp.modo !== modo) return { retoma: false, porque: `checkpoint é do modo "${cp.modo}"` };
  // O progresso tem de ser do MODELO que esta corrida vai usar. Um checkpoint de
  // shards sobre um portal paginado passaria com `lastPage` ausente: `start` viraria
  // 1, a rede de "esgotado" não dispararia, e o CSV anterior seria PRESERVADO
  // enquanto o laço recoleta tudo por cima — o defeito do acúmulo de volta, por
  // dentro da guarda que existe para impedi-lo. O contrato não protege disso: o
  // formato errado é do contrato atual.
  const temPagina = (cp.lastPage ?? 0) > 0;
  const temShards = cp.completedShards.length > 0;
  // A incoerência de MODELO vem primeiro: é o diagnóstico mais informativo para
  // quem lê o log, e "sem página" descreveria mal um checkpoint que tem shards.
  if (paginado && temShards) return { retoma: false, porque: 'checkpoint é de shards, e o portal pagina' };
  if (!paginado && temPagina) return { retoma: false, porque: 'checkpoint é paginado, e o portal usa shards' };
  // LACUNA DECLARADA: não há condição de IDADE. Um checkpoint legítimo de semanas
  // atrás retoma, e o CSV fica com duas gerações coladas sob um `finishedAt` de
  // hoje, que a porta de idade da rodada aceita. O limite é um número, e número
  // vira parâmetro do dono — registrado como [P-24]. Enquanto ele não vier, a
  // guarda não é inventada aqui.
  if (paginado && !temPagina) return { retoma: false, porque: 'checkpoint sem página concluída' };
  if (!paginado && !temShards) return { retoma: false, porque: 'checkpoint sem shard concluído' };
  return { retoma: true, porque: 'mesmo portal, mesmo modo, contrato atual, progresso coerente' };
}

/** Nome do status POR MODO. Existe porque `status.json` sozinho é "a última
 *  corrida", e a última corrida apaga o registro da outra: um canário de segundos
 *  rodado depois de uma coleta completa de horas sobrescrevia o status, e a partir
 *  daí o CSV do full ficava inalcançável para a rodada — com o `finishedAt` do
 *  canário passando na porta de idade. A sequência não é hipotética: é a que o
 *  console prescreve, porque o canário é o portão que libera o full. */
export function nomeDoStatus(modo: Modo): string {
  return `status.${modo}.json`;
}

async function escreverStatus(
  outDir: string,
  agora: () => Date,
  modo: Modo,
  result: 'ok' | 'blocked' | 'error' | 'running',
  extra: Record<string, unknown>
): Promise<void> {
  await mkdir(outDir, { recursive: true });
  const corpo = JSON.stringify(
    { result, finishedAt: agora().toISOString(), mode: modo, ...extra },
    null,
    2
  );
  // `status.json` continua sendo "a última corrida", que é o que o card do console
  // mostra; `status.<modo>.json` é o registro que ninguém sobrescreve por acidente.
  await writeFile(join(outDir, 'status.json'), corpo, 'utf8');
  await writeFile(join(outDir, nomeDoStatus(modo)), corpo, 'utf8');
}

async function levantarNeedsWarm(outDir: string, agora: () => Date): Promise<void> {
  await mkdir(outDir, { recursive: true });
  await writeFile(join(outDir, NEEDS_WARM_FLAG), agora().toISOString(), 'utf8');
}

/** Guarda uma geração do CSV do full antes de truncá-lo — só se ela for COMPLETA.
 *
 *  Um full são horas de raspagem. Até esta correção, o operador tinha um backup
 *  ACIDENTAL: as linhas velhas ficavam no arquivo, misturadas, que era o defeito.
 *  Trocamos o acidente por uma cópia declarada, que ninguém lê.
 *
 *  A condição existe porque `rename` sobrescreve em silêncio: sem ela, uma corrida
 *  rebaixada guardaria um CSV PARCIAL por cima do último full bom, e o nome
 *  prometeria o que o arquivo não é. Só guarda quando o `status.json` vigente diz
 *  que a corrida que produziu aquele arquivo concluiu. */
async function guardarGeracaoAnterior(caminho: string, outDir: string): Promise<void> {
  if (!existsSync(caminho)) return;
  let concluida = false;
  try {
    // Lê o status DO FULL, não o da última corrida: um canário entre dois fulls
    // sobrescrevia `status.json` e fazia esta condição recusar preservar a última
    // geração boa — derrotando esta função exatamente no caso para o qual ela existe.
    const st = JSON.parse(await readFile(join(outDir, nomeDoStatus('full')), 'utf8')) as {
      result?: string;
    };
    concluida = st.result === 'ok';
  } catch {
    concluida = false; // sem status legível, não afirmamos nada sobre o arquivo
  }
  if (!concluida) return;
  await rename(caminho, caminho.replace(/\.csv$/, '.anterior.csv'));
}

export async function executarCorrida(
  portal: Portal,
  modo: Modo,
  deps: DepsCorrida
): Promise<Desfecho> {
  const { conectar, irAoPainel, log, agora, outDir, degrausDoCanario } = deps;
  const { browser, page } = await conectar(portal);
  try {
    await irAoPainel(page, portal, log);
    const sessionId = await portal.captureSessionId(page);
    log(`Sessão capturada no portal "${portal.id}".`);

    // A flag só cai quando uma requisição AUTENTICADA responde — ver `provouSessao`.
    // `captureSessionId` prova que a SPA DISPAROU uma XHR e de onde vieram os
    // cabeçalhos — não prova que o portal ACEITA o token, que pode estar expirado.
    // Quem prova é a primeira requisição autenticada que responde. Apagar a flag
    // antes disso é apagar o alarme certo: o 401 seguinte sai como erro genérico e
    // o operador que esqueceu de re-logar fica sem diagnóstico.
    let sessaoProvada = false;
    const provouSessao = async (): Promise<void> => {
      if (sessaoProvada) return;
      sessaoProvada = true;
      await rm(join(outDir, NEEDS_WARM_FLAG), { force: true });
    };

    const caminhoCsv = join(outDir, nomeDoCsv(portal.id, modo));
    const csv = new CsvWriter(caminhoCsv, portal.csvColumns);

    if (modo === 'canary') {
      // Portão progressivo: coleta ATÉ o maior degrau uma única vez (limite),
      // e reporta os cortes intermediários. Qualquer bloqueio aborta cedo (o
      // collectShort lança BlockedError). Sem baixar o shard inteiro e sem
      // regravar linhas a cada degrau.
      const steps = degrausDoCanario.length ? degrausDoCanario : [1];
      const maior = Math.max(...steps);
      const anuncios = await portal.collectShard(page, sessionId, [], maior);
      await provouSessao();
      for (const step of steps) {
        log(`Canário ${step}: ${Math.min(step, anuncios.length)} de ${anuncios.length} coletados sem bloqueio.`);
      }
      // Canário é SEMPRE corrida nova: é uma sonda do estado atual do portal, e
      // acumular sondas de dias diferentes é o defeito, não a intenção. Trunca só
      // depois de ter o que gravar — um canário que morre no login não destrói a
      // sonda anterior.
      await csv.init({ truncar: true });
      await csv.appendRows(anuncios.map((a) => portal.rowToCells(a)));
      log(`Canário concluído: ${anuncios.length} anúncios gravados.`);
      await escreverStatus(outDir, agora, modo, 'ok', { portal: portal.id, rows: anuncios.length });
      return { result: 'ok', rows: anuncios.length, exitCode: 0 };
    }

    const noDisco = await loadCheckpoint(outDir);
    const veredito = podeRetomar(noDisco, portal.id, modo, portal.collectPage != null);
    let retomando = veredito.retoma;
    log(retomando ? `Retomando: ${veredito.porque}.` : `Corrida nova: ${veredito.porque}.`);
    const cp: Checkpoint = retomando && noDisco
      ? noDisco
      : {
          startedAt: agora().toISOString(),
          completedShards: [],
          seenCount: 0,
          rowsWritten: 0,
          lastUpdate: agora().toISOString(),
          contrato: CONTRATO_CHECKPOINT,
          portal: portal.id,
          modo: 'full',
        };

    if (portal.collectPage) {
      // Paginação linear com checkpoint POR PÁGINA: se a coleta morrer no meio,
      // a retomada continua de lastPage+1 em vez de re-bater o portal do início
      // (condição anti-bot). Um "shard" único não daria essa granularidade.
      const size = portal.pageSize ?? 30;
      const total = (await portal.probeList(page, sessionId, [])).numberOfPostings;
      await provouSessao();
      const totalPages = Math.max(1, Math.ceil(total / size));
      let start = (cp.lastPage ?? 0) + 1;
      // Rede de segurança para o checkpoint que sobrevive esgotado. NÃO cobre "morrer
      // entre o clearCheckpoint e o status": ali o disco fica SEM checkpoint e a
      // corrida seguinte já é nova. Cobre dois casos reais: a listagem encolheu
      // (`totalPages` caiu abaixo de `lastPage`) e o `clearCheckpoint` falhou por
      // outro motivo que não a ausência do arquivo. Sem ela o laço não itera e a
      // corrida se declara `ok` com os números da anterior e um `finishedAt` novo.
      // O checkpoint pode ser coerente consigo mesmo e mentir sobre o disco. Apagar
      // o CSV à mão era o que o próprio console ensinava até esta fatia ("apague o
      // arquivo antes de disparar o canário") — e apagar o CSV não apaga o
      // `progress.json`. Retomar sobre um arquivo que não existe produz coleta
      // parcial declarada `ok`, com `rows` prometendo o que não está lá.
      if (retomando && !existsSync(caminhoCsv)) {
        log(`Checkpoint diz retomar, mas ${nomeDoCsv(portal.id, modo)} não existe: rebaixando para corrida nova.`);
        retomando = false;
        cp.lastPage = 0;
        cp.rowsWritten = 0;
        cp.startedAt = agora().toISOString();
      }
      if (retomando && start > totalPages) {
        log(
          `Checkpoint aponta a página ${cp.lastPage} e a listagem tem ${totalPages}: ` +
            `esgotado ou encolhido — rebaixando para corrida nova.`
        );
        retomando = false;
        cp.lastPage = 0;
        cp.rowsWritten = 0;
        // O `startedAt` é da corrida ANTERIOR; mantê-lo faria o arquivo mentir sobre
        // quando esta começou — e é o campo que uma guarda de idade leria.
        cp.startedAt = agora().toISOString();
      }
      // Um ponto só de verdade para o `start`: qualquer um dos dois rebaixamentos
      // acima faz a corrida recomeçar da primeira página.
      if (!retomando) start = 1;
      // Guardar ANTES de declarar `running`: a decisão de guardar lê o status do
      // full anterior — sobrescrevê-lo primeiro apagaria a única evidência de que
      // aquele CSV veio de uma corrida concluída.
      if (!retomando) await guardarGeracaoAnterior(caminhoCsv, outDir);
      // `running` vale nos DOIS casos: uma retomada também está em curso, e enquanto
      // ela apende horas de linhas o status vigente continuaria dizendo `ok` com o
      // `rows` da corrida anterior — o defeito de origem por uma porta nova.
      await escreverStatus(outDir, agora, modo, 'running', { portal: portal.id });
      await csv.init({ truncar: !retomando });
      log(`Paginação linear: ${total} anúncios, ${totalPages} páginas; retomando da página ${start}.`);
      for (let pg = start; pg <= totalPages; pg++) {
        const anuncios = await portal.collectPage(page, sessionId, pg);
        // Guard de sub-coleta: uma página NÃO-final com menos que pageSize
        // significa que o servidor limitou o page size — o totalPages calculado
        // ficou grande demais e a coleta terminaria incompleta marcada "ok".
        // Aborta ruidosamente em vez de sub-coletar em silêncio.
        if (pg < totalPages && anuncios.length > 0 && anuncios.length < size) {
          throw new Error(
            `Sub-coleta: página ${pg}/${totalPages} veio com ${anuncios.length} < pageSize ${size} — ` +
              `o servidor limitou o page size. Reduza pageSize no adapter.`
          );
        }
        await csv.appendRows(anuncios.map((a) => portal.rowToCells(a)));
        cp.lastPage = pg;
        cp.rowsWritten += anuncios.length;
        cp.lastUpdate = agora().toISOString();
        await saveCheckpoint(cp, outDir);
        log(`Página ${pg}/${totalPages}: ${anuncios.length} anúncios (total ${cp.rowsWritten}).`);
      }
      // ANTES do status: morrer entre os dois perde a retomada, o que é seguro;
      // o inverso deixa um checkpoint completo, que é o defeito.
      await clearCheckpoint(outDir);
      await escreverStatus(outDir, agora, modo, 'ok', { portal: portal.id, rows: cp.rowsWritten });
      return { result: 'ok', rows: cp.rowsWritten, exitCode: 0 };
    }

    // Modelo de shards por facets (portais sem paginação linear).
    const shards: Shard[] = await buildShards(
      (tokens) => portal.probeList(page, sessionId, tokens),
      portal.shardDimensions,
      log
    );
    await provouSessao();
    const done = new Set(cp.completedShards);
    // Rebaixa se o checkpoint já cobre tudo OU se guarda rótulo que não existe mais:
    // os facets mudam entre corridas, e um rótulo órfão significa que o mapa de
    // shards mudou — retomar sobre ele recoletaria tudo preservando o CSV anterior.
    if (retomando && !existsSync(caminhoCsv)) {
      log(`Checkpoint diz retomar, mas ${nomeDoCsv(portal.id, modo)} não existe: rebaixando para corrida nova.`);
      retomando = false;
      cp.completedShards = [];
      cp.rowsWritten = 0;
      cp.startedAt = agora().toISOString();
      done.clear();
    }
    const orfaos = [...done].filter((r) => !shards.some((s) => s.label === r));
    const cobreTudo = shards.length > 0 && shards.every((s) => done.has(s.label));
    if (retomando && (cobreTudo || orfaos.length > 0)) {
      log(
        cobreTudo
          ? `Checkpoint já cobre os ${shards.length} shards: rebaixando para corrida nova.`
          : `Checkpoint guarda ${orfaos.length} shard(s) que não existem mais: rebaixando para corrida nova.`
      );
      retomando = false;
      cp.completedShards = [];
      cp.rowsWritten = 0;
      cp.startedAt = agora().toISOString();
      done.clear();
    }
    if (!retomando) await guardarGeracaoAnterior(caminhoCsv, outDir);
    await escreverStatus(outDir, agora, modo, 'running', { portal: portal.id });
    await csv.init({ truncar: !retomando });
    for (const shard of shards) {
      if (done.has(shard.label)) continue;
      const anuncios = await portal.collectShard(page, sessionId, shard.tokens);
      await csv.appendRows(anuncios.map((a) => portal.rowToCells(a)));
      cp.completedShards.push(shard.label);
      cp.rowsWritten += anuncios.length;
      cp.lastUpdate = agora().toISOString();
      await saveCheckpoint(cp, outDir);
      log(`Shard [${shard.label}]: ${anuncios.length} anúncios (total ${cp.rowsWritten}).`);
    }
    await clearCheckpoint(outDir);
    await escreverStatus(outDir, agora, modo, 'ok', { portal: portal.id, rows: cp.rowsWritten });
    return { result: 'ok', rows: cp.rowsWritten, exitCode: 0 };
  } finally {
    // NUNCA browser.close(): é o Chrome do operador.
    await browser.disconnect();
  }
}

/** Roda a corrida e traduz a falha no contrato de arquivo + código de saída.
 *
 *  `mode` vai no status em TODOS os caminhos, inclusive nos de falha — quem escolhe
 *  o arquivo pelo modo ficaria cego justamente quando a coleta quebra. */
export async function executarComTratamento(
  portal: Portal,
  modo: Modo,
  deps: DepsCorrida
): Promise<Desfecho> {
  const { log, agora, outDir } = deps;
  try {
    const desfecho = await executarCorrida(portal, modo, deps);
    log('Concluído.');
    return desfecho;
  } catch (e) {
    // AuthExpiredError entra aqui junto com BlockedError porque o CONSERTO é o
    // mesmo — re-logar —, e é o conserto que a flag comunica. Sem isto, um 401 sai
    // como erro genérico e o console diz "a coleta falhou" a quem só precisa entrar
    // no portal de novo.
    if (e instanceof BlockedError || e instanceof AuthExpiredError) {
      await levantarNeedsWarm(outDir, agora);
      await escreverStatus(outDir, agora, modo, 'blocked', { portal: portal.id, message: e.message });
      log(`SESSÃO CAÍDA: ${e.message} — flag ${NEEDS_WARM_FLAG} criada; re-logue no portal.`);
      return { result: 'blocked', rows: 0, exitCode: 2 };
    }
    const msg = e instanceof Error ? e.message : String(e);
    await escreverStatus(outDir, agora, modo, 'error', { portal: portal.id, message: msg });
    log(`ERRO: ${msg}`);
    return { result: 'error', rows: 0, exitCode: 1 };
  }
}
