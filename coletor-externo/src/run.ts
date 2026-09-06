// Entrypoint do coletor: canário (portão) e full (com checkpoints).
// Aqui só ficam o registro de portais, o parse de argv e o código de saída — a
// orquestração da corrida vive em `core/corrida.ts`, que é testável sem navegador
// (este arquivo chama `void main()` na última linha: importá-lo dispara a coleta).

import { config } from './core/config';
import { executarComTratamento, Modo } from './core/corrida';
import { connectRealChrome, gotoPanel } from './cdp/browser';
import { Portal } from './portal';
import { canalPro } from './portals/canalpro';

const PORTALS: Record<string, Portal> = { canalpro: canalPro };

function log(msg: string): void {
  process.stdout.write(`[coletor] ${new Date().toISOString()} ${msg}\n`);
}

async function main(): Promise<void> {
  const mode: Modo = process.argv.includes('--full') ? 'full' : 'canary';
  const portalId = (process.argv.find((a) => a.startsWith('--portal='))?.split('=')[1] || 'canalpro').trim();
  const portal = PORTALS[portalId];
  if (!portal) {
    throw new Error(`Portal desconhecido: "${portalId}". Disponíveis: ${Object.keys(PORTALS).join(', ')}.`);
  }
  log(`Iniciando coletor: portal=${portal.id} modo=${mode}.`);
  const { exitCode } = await executarComTratamento(portal, mode, {
    conectar: connectRealChrome,
    irAoPainel: gotoPanel,
    log,
    agora: () => new Date(),
    outDir: config.outDir,
    degrausDoCanario: config.canarySteps,
  });
  if (exitCode !== 0) process.exitCode = exitCode;
}

void main();
