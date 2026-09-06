// Escrita de CSV com checkpoint — genérica. Portado de imovelweb-ativos/src/csv-writer.ts.
// O núcleo escreve células escapadas e linhas; o mapeamento anúncio→célula é do
// adapter do portal (Portal.csvColumns + Portal.rowToCells).

import { appendFile, writeFile, mkdir, readFile, rm } from 'fs/promises';
import { existsSync } from 'fs';
import { dirname, join } from 'path';
import { Checkpoint } from './types';

/** Escapa uma célula para CSV: aspas duplas com escape `""`. */
export function escapeCell(v: unknown): string {
  const s = v == null ? '' : String(v);
  return `"${s.replace(/"/g, '""')}"`;
}

/** Serializa uma linha (array de células cruas) em texto CSV, CRLF sem terminador. */
export function cellsToLine(cells: unknown[]): string {
  return cells.map(escapeCell).join(',');
}

export class CsvWriter {
  private readonly headerLine: string;

  constructor(
    private readonly filePath: string,
    columns: string[]
  ) {
    this.headerLine = cellsToLine(columns);
  }

  /** Prepara o arquivo para receber linhas.
   *
   *  `truncar` é a INTENÇÃO DO CHAMADOR, não uma inferência sobre o disco — e é a
   *  correção do defeito que fazia duas corridas empilharem no mesmo CSV. Sem ele,
   *  o cabeçalho só era escrito quando o arquivo não existia, e todo `appendRows`
   *  seguinte anexava ao que estivesse lá, de qualquer corrida anterior.
   *
   *  - `truncar: true`  → corrida NOVA: descarta o que havia e reescreve o cabeçalho.
   *  - ausente ou false → RETOMADA: preserva o conteúdo e não duplica o cabeçalho. */
  async init(opts?: { truncar?: boolean }): Promise<void> {
    await mkdir(dirname(this.filePath), { recursive: true });
    if (opts?.truncar || !existsSync(this.filePath)) {
      await writeFile(this.filePath, this.headerLine + '\r\n', 'utf8');
    }
  }

  /** Anexa linhas já serializadas (cada uma vinda de cellsToLine). Append-only. */
  async appendLines(lines: string[]): Promise<void> {
    if (!lines.length) return;
    await appendFile(this.filePath, lines.join('\r\n') + '\r\n', 'utf8');
  }

  /** Anexa linhas a partir de arrays de células. */
  async appendRows(rows: unknown[][]): Promise<void> {
    await this.appendLines(rows.map(cellsToLine));
  }
}

// ---- Checkpoint ----

export function checkpointPath(outDir: string): string {
  return join(outDir, 'progress.json');
}

export async function loadCheckpoint(outDir: string): Promise<Checkpoint | null> {
  const p = checkpointPath(outDir);
  if (!existsSync(p)) return null;
  try {
    return JSON.parse(await readFile(p, 'utf8')) as Checkpoint;
  } catch {
    return null;
  }
}

export async function saveCheckpoint(cp: Checkpoint, outDir: string): Promise<void> {
  await mkdir(outDir, { recursive: true });
  await writeFile(checkpointPath(outDir), JSON.stringify(cp, null, 2), 'utf8');
}

/** Apaga o checkpoint. Chamado ao CONCLUIR a coleta, antes de declarar `ok`.
 *
 *  `outDir` é obrigatório de propósito: com default, uma chamada sem argumento num
 *  teste apagaria o `progress.json` real do operador.
 *
 *  Sem isto o checkpoint sobrevive com `lastPage = totalPages`, e a corrida
 *  seguinte não itera nenhuma página e mesmo assim escreve `result: "ok"` com um
 *  `finishedAt` novo — dado velho entrando como fresco na porta de idade. */
export async function clearCheckpoint(outDir: string): Promise<void> {
  await rm(checkpointPath(outDir), { force: true });
}
