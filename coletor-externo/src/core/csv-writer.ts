// Escrita de CSV com checkpoint — genérica. Portado de imovelweb-ativos/src/csv-writer.ts.
// O núcleo escreve células escapadas e linhas; o mapeamento anúncio→célula é do
// adapter do portal (Portal.csvColumns + Portal.rowToCells).

import { appendFile, writeFile, mkdir, readFile } from 'fs/promises';
import { existsSync } from 'fs';
import { dirname, join } from 'path';
import { config } from './config';
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

  /** Cria o arquivo com cabeçalho só se ele ainda não existe — retomada não duplica header. */
  async init(): Promise<void> {
    await mkdir(dirname(this.filePath), { recursive: true });
    if (!existsSync(this.filePath)) {
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

export function checkpointPath(): string {
  return join(config.outDir, 'progress.json');
}

export async function loadCheckpoint(): Promise<Checkpoint | null> {
  const p = checkpointPath();
  if (!existsSync(p)) return null;
  try {
    return JSON.parse(await readFile(p, 'utf8')) as Checkpoint;
  } catch {
    return null;
  }
}

export async function saveCheckpoint(cp: Checkpoint): Promise<void> {
  await mkdir(config.outDir, { recursive: true });
  await writeFile(checkpointPath(), JSON.stringify(cp, null, 2), 'utf8');
}
