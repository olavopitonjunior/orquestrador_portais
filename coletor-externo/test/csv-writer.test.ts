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

// Os dois testes abaixo são um PAR, e é o par que expressa a correção. O append-only
// nunca foi errado — errado era não haver escolha: `init()` inferia do disco, então
// duas corridas independentes empilhavam no mesmo arquivo. Agora a retomada continua
// preservando (é o que a paginação por `lastPage` exige) e a corrida nova descarta.

test('init de RETOMADA (truncar ausente) preserva o conteúdo e não duplica o cabeçalho', async () => {
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

test('init de CORRIDA NOVA (truncar) descarta o conteúdo e reescreve o cabeçalho', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'coletor-csv-'));
  const file = join(dir, 'out.csv');
  try {
    const w1 = new CsvWriter(file, ['id', 'nota']);
    await w1.init();
    await w1.appendRows([['a1', 10]]);

    const w2 = new CsvWriter(file, ['id', 'nota']);
    await w2.init({ truncar: true });
    await w2.appendRows([['a2', 20]]);

    const content = await readFile(file, 'utf8');
    const lines = content.trimEnd().split('\r\n');
    assert.deepEqual(lines, ['"id","nota"', '"a2","20"'], 'a linha da corrida anterior não pode sobreviver');
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

test('truncar num arquivo inexistente é idêntico a criar', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'coletor-csv-'));
  try {
    const a = join(dir, 'a.csv');
    const b = join(dir, 'b.csv');
    await new CsvWriter(a, ['id']).init();
    await new CsvWriter(b, ['id']).init({ truncar: true });
    assert.equal(await readFile(a, 'utf8'), await readFile(b, 'utf8'));
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
