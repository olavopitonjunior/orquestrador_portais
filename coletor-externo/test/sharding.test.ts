import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import { buildShards, codeBeforeComma, extractFacetBuckets, ListProbe } from '../src/core/sharding';

test('codeBeforeComma extrai o código antes da vírgula', () => {
  assert.equal(codeBeforeComma('V1-B-265, São Paulo'), 'V1-B-265');
  assert.equal(codeBeforeComma('2, Apartamento'), '2');
  assert.equal(codeBeforeComma('semvirgula'), 'semvirgula');
  assert.equal(codeBeforeComma('  espaco , x'), 'espaco');
});

test('extractFacetBuckets lê o facet de mesmo facetName (formato array)', () => {
  const facets = [
    { facetName: 'regiao', values: { 'R1, Centro': 100, 'R2, Sul': 50 } },
    { facetName: 'tipo', values: { '2, Apto': 30 } },
  ];
  const buckets = extractFacetBuckets(facets, 'regiao');
  assert.deepEqual(buckets, [
    { value: 'R1', count: 100 },
    { value: 'R2', count: 50 },
  ]);
});

test('extractFacetBuckets devolve vazio para dimensão ausente', () => {
  assert.deepEqual(extractFacetBuckets([{ facetName: 'regiao', values: { 'R1, x': 1 } }], 'cidade'), []);
  assert.deepEqual(extractFacetBuckets(null, 'regiao'), []);
});

test('buildShards não drilla quando a raiz já cabe em shardMax', async () => {
  const probe: ListProbe = async () => ({ numberOfPostings: 100, facets: [] });
  const shards = await buildShards(probe, ['regiao'], () => {});
  assert.equal(shards.length, 1);
  assert.equal(shards[0].estimated, 100);
  assert.deepEqual(shards[0].tokens, []);
});

test('buildShards drilla a dimensão quando a raiz excede shardMax', async () => {
  // raiz = 20000 (> 9500 default) → drilla regiao em dois buckets, cada um pequeno.
  const probe: ListProbe = async (tokens) => {
    if (tokens.length === 0) {
      return { numberOfPostings: 20000, facets: [{ facetName: 'regiao', values: { 'R1, a': 5000, 'R2, b': 4000 } }] };
    }
    return { numberOfPostings: tokens[0] === 'regiao:R1' ? 5000 : 4000, facets: [] };
  };
  const shards = await buildShards(probe, ['regiao'], () => {});
  assert.equal(shards.length, 2);
  // ordenado menor → maior
  assert.deepEqual(shards.map((s) => s.estimated), [4000, 5000]);
  assert.deepEqual(shards.map((s) => s.tokens[0]), ['regiao:R2', 'regiao:R1']);
});

test('extractFacetBuckets aceita facets no formato objeto-indexado', () => {
  const facets = { 0: { facetName: 'regiao', values: { 'R1, x': 7 } }, 1: { facetName: 'tipo', values: { '2, y': 3 } } };
  assert.deepEqual(extractFacetBuckets(facets, 'tipo'), [{ value: '2', count: 3 }]);
});

test('buildShards drilla em duas dimensões encadeadas', async () => {
  const probe: ListProbe = async (tokens) => {
    if (tokens.length === 0) {
      return { numberOfPostings: 30000, facets: [{ facetName: 'regiao', values: { 'R1, a': 20000 } }] };
    }
    if (tokens.length === 1) {
      // regiao:R1 ainda excede → drilla tipo
      return { numberOfPostings: 20000, facets: [{ facetName: 'tipo', values: { '2, apto': 5000, '3, casa': 4000 } }] };
    }
    return { numberOfPostings: tokens[1] === 'tipo:2' ? 5000 : 4000, facets: [] };
  };
  const shards = await buildShards(probe, ['regiao', 'tipo'], () => {});
  assert.equal(shards.length, 2);
  assert.deepEqual(shards.map((s) => s.tokens), [
    ['regiao:R1', 'tipo:3'],
    ['regiao:R1', 'tipo:2'],
  ]);
});

test('buildShards para de drillar quando esgota as dimensões, mesmo acima do teto', async () => {
  const probe: ListProbe = async () => ({ numberOfPostings: 50000, facets: [] });
  const shards = await buildShards(probe, ['regiao'], () => {});
  // sem buckets → cai para próxima dimensão → sem mais dimensões → aceita o shard grande
  assert.equal(shards.length, 1);
  assert.equal(shards[0].estimated, 50000);
});
