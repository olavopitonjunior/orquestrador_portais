// Entrypoint do coletor: canário (portão) e full (com checkpoints).
// Orquestra o núcleo genérico sobre um Portal escolhido. O adapter Canal Pro
// é um stub que lança (ver src/portals/canalpro.ts) — rodar `full` hoje falha
// ruidosamente no primeiro método não implementado, por desenho.

import { writeFile, mkdir } from 'fs/promises';
import { join } from 'path';
import { config, NEEDS_WARM_FLAG } from './core/config';
import { CsvWriter, loadCheckpoint, saveCheckpoint } from './core/csv-writer';
import { buildShards } from './core/sharding';
import { BlockedError } from './core/block-detector';
import { Checkpoint, Shard } from './core/types';
import { connectRealChrome, gotoPanel } from './cdp/browser';
import { Portal } from './portal';
import { canalPro } from './portals/canalpro';

const PORTALS: Record<string, Portal> = { canalpro: canalPro };

function log(msg: string): void {
  process.stdout.write(`[coletor] ${new Date().toISOString()} ${msg}\n`);
}

async function writeStatus(result: string, extra: Record<string, unknown>): Promise<void> {
  await mkdir(config.outDir, { recursive: true });
  await writeFile(
    join(config.outDir, 'status.json'),
    JSON.stringify({ result, finishedAt: new Date().toISOString(), ...extra }, null, 2),
    'utf8'
  );
}

async function raiseNeedsWarm(): Promise<void> {
  await mkdir(config.outDir, { recursive: true });
  await writeFile(join(config.outDir, NEEDS_WARM_FLAG), new Date().toISOString(), 'utf8');
}

async function run(portal: Portal, mode: 'canary' | 'full'): Promise<void> {
  const { browser, page } = await connectRealChrome(portal);
  try {
    await gotoPanel(page, portal, log);
    const sessionId = await portal.captureSessionId(page);
    log(`Sessão capturada no portal "${portal.id}".`);

    const csv = new CsvWriter(join(config.outDir, `${portal.id}.csv`), portal.csvColumns);
    await csv.init();

    if (mode === 'canary') {
      // Portão progressivo: coleta ATÉ o maior degrau uma única vez (limite),
      // e reporta os cortes intermediários. Qualquer bloqueio aborta cedo (o
      // collectShort lança BlockedError). Sem baixar o shard inteiro e sem
      // regravar linhas a cada degrau.
      const steps = config.canarySteps.length ? config.canarySteps : [1];
      const maior = Math.max(...steps);
      const anuncios = await portal.collectShard(page, sessionId, [], maior);
      for (const step of steps) {
        log(`Canário ${step}: ${Math.min(step, anuncios.length)} de ${anuncios.length} coletados sem bloqueio.`);
      }
      await csv.appendRows(anuncios.map((a) => portal.rowToCells(a)));
      log(`Canário concluído: ${anuncios.length} anúncios gravados.`);
      await writeStatus('ok', { mode, portal: portal.id, rows: anuncios.length });
      return;
    }

    // full: sharding + coleta por shard com checkpoint.
    const shards: Shard[] = await buildShards(
      (tokens) => portal.probeList(page, sessionId, tokens),
      portal.shardDimensions,
      log
    );
    const cp: Checkpoint = (await loadCheckpoint()) || {
      startedAt: new Date().toISOString(),
      completedShards: [],
      seenCount: 0,
      rowsWritten: 0,
      lastUpdate: new Date().toISOString(),
    };
    const done = new Set(cp.completedShards);
    for (const shard of shards) {
      if (done.has(shard.label)) continue;
      const anuncios = await portal.collectShard(page, sessionId, shard.tokens);
      await csv.appendRows(anuncios.map((a) => portal.rowToCells(a)));
      cp.completedShards.push(shard.label);
      cp.rowsWritten += anuncios.length;
      cp.lastUpdate = new Date().toISOString();
      await saveCheckpoint(cp);
      log(`Shard [${shard.label}]: ${anuncios.length} anúncios (total ${cp.rowsWritten}).`);
    }
    await writeStatus('ok', { mode, portal: portal.id, rows: cp.rowsWritten });
  } finally {
    // NUNCA browser.close(): é o Chrome do operador.
    await browser.disconnect();
  }
}

async function main(): Promise<void> {
  const mode = process.argv.includes('--full') ? 'full' : 'canary';
  const portalId = (process.argv.find((a) => a.startsWith('--portal='))?.split('=')[1] || 'canalpro').trim();
  const portal = PORTALS[portalId];
  if (!portal) {
    throw new Error(`Portal desconhecido: "${portalId}". Disponíveis: ${Object.keys(PORTALS).join(', ')}.`);
  }
  log(`Iniciando coletor: portal=${portal.id} modo=${mode}.`);
  try {
    await run(portal, mode);
    log('Concluído.');
  } catch (e) {
    if (e instanceof BlockedError) {
      await raiseNeedsWarm();
      await writeStatus('blocked', { portal: portalId, message: e.message });
      log(`BLOQUEADO: ${e.message} — flag ${NEEDS_WARM_FLAG} criada; re-logue no portal.`);
      process.exitCode = 2;
      return;
    }
    await writeStatus('error', { portal: portalId, message: e instanceof Error ? e.message : String(e) });
    log(`ERRO: ${e instanceof Error ? e.message : String(e)}`);
    process.exitCode = 1;
  }
}

void main();
