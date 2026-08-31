import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import { isAuthExpired, isBlockResponse, isTransient } from '../src/core/block-detector';
import { InPageResponse } from '../src/core/types';

function resp(p: Partial<InPageResponse>): InPageResponse {
  return { ok: false, status: 200, contentType: 'application/json', json: {}, bodySnippet: null, ...p };
}

test('403 é bloqueio duro', () => {
  assert.equal(isBlockResponse(resp({ status: 403 })), true);
  assert.equal(isTransient(resp({ status: 403 })), false);
});

test('HTML de desafio Cloudflare é bloqueio duro', () => {
  const r = resp({ status: 200, contentType: 'text/html', json: null, bodySnippet: 'Just a moment...' });
  assert.equal(isBlockResponse(r), true);
  assert.equal(isTransient(r), false);
});

test('429 e 503 são transientes, não bloqueio', () => {
  for (const status of [429, 503]) {
    assert.equal(isTransient(resp({ status })), true);
    assert.equal(isBlockResponse(resp({ status })), false);
  }
});

test('erro de rede (-1) é transiente', () => {
  assert.equal(isTransient(resp({ status: -1, contentType: '', json: null })), true);
});

test('200 não-JSON SEM marcador CF é transiente, não bloqueio', () => {
  const r = resp({ status: 200, contentType: 'text/html', json: null, bodySnippet: '<html>manutenção</html>' });
  assert.equal(isTransient(r), true);
  assert.equal(isBlockResponse(r), false);
});

test('200 JSON normal não é bloqueio nem transiente', () => {
  const r = resp({ ok: true, status: 200, json: { numberOfPostings: 10 } });
  assert.equal(isBlockResponse(r), false);
  assert.equal(isTransient(r), false);
  assert.equal(isAuthExpired(r), false);
});

test('401 é sessão expirada, não bloqueio nem transiente', () => {
  const r = resp({ status: 401, json: null });
  assert.equal(isAuthExpired(r), true);
  assert.equal(isBlockResponse(r), false);
  assert.equal(isTransient(r), false);
});
