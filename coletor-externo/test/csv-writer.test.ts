import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import { mkdtemp, readFile, rm } from 'fs/promises';
import { tmpdir } from 'os';
import { join } from 'path';
import { cellsToLine, CsvWriter, escapeCell } from '../src/core/csv-writer';

test('escapeCell envolve em aspas e escapa aspas internas', () => {
  assert.equal(escapeCell('abc'), '"abc"');
  assert.equal(escapeCell('a"b'), '"a""b"');
  assert.equal(escapeCell(null), '""');
  assert.equal(escapeCell(undefined), '""');
  assert.equal(escapeCell(42), '"42"');
});

test('cellsToLine junta células escapadas com vírgula', () => {
  assert.equal(cellsToLine(['a', 'b,c', 'd"e']), '"a","b,c","d""e"');
});

test('CsvWriter escreve cabeçalho uma vez e anexa linhas (retomada não duplica header)', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'coletor-csv-'));
  const file = join(dir, 'out.csv');
  try {
    const w1 = new CsvWriter(file, ['id', 'nota']);
    await w1.init();
    await w1.appendRows([['a1', 10]]);

    // segundo writer sobre o MESMO arquivo (simula retomada): init não reescreve header
    const w2 = new CsvWriter(file, ['id', 'nota']);
    await w2.init();
    await w2.appendRows([['a2', 20]]);

    const content = await readFile(file, 'utf8');
    const lines = content.trimEnd().split('\r\n');
    assert.deepEqual(lines, ['"id","nota"', '"a1","10"', '"a2","20"']);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

test('appendRows com lista vazia não altera o arquivo', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'coletor-csv-'));
  const file = join(dir, 'out.csv');
  try {
    const w = new CsvWriter(file, ['id']);
    await w.init();
    await w.appendRows([]);
    const content = await readFile(file, 'utf8');
    assert.equal(content, '"id"\r\n');
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});
