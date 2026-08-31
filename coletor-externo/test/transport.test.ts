import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import type { Page } from 'puppeteer-core';
import { fetchInPage } from '../src/cdp/transport';

// Fake Page: executa a PAGE_FN localmente (ela roda `fetch` global), com um
// fetch stub que captura o `init` — trava a regressão de re-hardcodar credentials.
function fakePage(capture: (init: RequestInit) => void): Page {
  return {
    async evaluate(fn: (...a: unknown[]) => unknown, ...args: unknown[]) {
      const orig = (globalThis as { fetch?: unknown }).fetch;
      (globalThis as { fetch: unknown }).fetch = (_u: string, init: RequestInit) => {
        capture(init);
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: { get: () => 'application/json' },
          json: () => Promise.resolve({ ok: true }),
          text: () => Promise.resolve(''),
        });
      };
      try {
        return await (fn as (...a: unknown[]) => Promise<unknown>)(...args);
      } finally {
        (globalThis as { fetch: unknown }).fetch = orig;
      }
    },
  } as unknown as Page;
}

test('credentials default é include (compat com portais por cookie)', async () => {
  let init!: RequestInit;
  await fetchInPage(fakePage((i) => (init = i)), 'https://x/', {});
  assert.equal(init.credentials, 'include');
});

test('credentials omit chega ao RequestInit (Canal Pro / Bearer)', async () => {
  let init!: RequestInit;
  await fetchInPage(fakePage((i) => (init = i)), 'https://x/', {}, { credentials: 'omit' });
  assert.equal(init.credentials, 'omit');
});

test('method e body chegam ao RequestInit no POST', async () => {
  let init!: RequestInit;
  await fetchInPage(fakePage((i) => (init = i)), 'https://x/', {}, { method: 'POST', body: '{"q":1}', credentials: 'omit' });
  assert.equal(init.method, 'POST');
  assert.equal(init.body, '{"q":1}');
});
