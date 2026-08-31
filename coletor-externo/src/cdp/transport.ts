// Transporte in-page genérico — o mecanismo, não a receita de um portal.
// Portado de imovelweb-ativos/src/cdp/transport.ts, extraído o que era genérico:
// a captura de sessão por monkey-patch de setRequestHeader e o fetch dentro da
// página autenticada (herda cookies + cf_clearance + fingerprint). O NOME do
// header de sessão, o header de portal, os endpoints e a projeção de campos são
// do adapter (src/portal.ts) — nunca deste arquivo.

import { Page } from 'puppeteer-core';
import { config } from '../core/config';
import { InPageResponse } from '../core/types';

/**
 * Instala, ANTES da navegação, um hook que grava em window.__SID o valor do
 * header de sessão (cujo nome é do portal) quando a SPA o envia numa XHR.
 * Chame antes de page.goto(panel). Depois leia com readCapturedSessionId.
 */
export async function installSessionCapture(page: Page, sessionHeaderName: string): Promise<void> {
  await page.evaluateOnNewDocument((headerName: string) => {
    const w = window as unknown as { __SID?: string };
    const target = String(headerName).toLowerCase();
    const orig = XMLHttpRequest.prototype.setRequestHeader;
    XMLHttpRequest.prototype.setRequestHeader = function (k: string, v: string) {
      try {
        if (String(k).toLowerCase() === target) w.__SID = v;
      } catch {
        /* ignore */
      }
      return orig.apply(this, arguments as unknown as [string, string]);
    };
  }, sessionHeaderName);
}

/** Lê o valor de sessão capturado pelo hook, ou null se ainda não veio. */
export async function readCapturedSessionId(page: Page): Promise<string | null> {
  return page.evaluate(() => (window as unknown as { __SID?: string }).__SID || null);
}

/**
 * Faz um GET JSON DENTRO da página autenticada. `headers` é montado pelo adapter
 * (inclui o header de portal e o de sessão, ambos com nomes do portal). Devolve
 * o envelope InPageResponse padronizado para a classificação de bloqueio/401.
 */
export async function fetchInPage<T = unknown>(
  page: Page,
  url: string,
  headers: Record<string, string>
): Promise<InPageResponse<T>> {
  const PAGE_FN = function (u: string, h: Record<string, string>): Promise<InPageResponse> {
    function mk(ok: boolean, status: number, ct: string, json: unknown, snip: string | null): InPageResponse {
      return { ok: ok, status: status, contentType: ct, json: json, bodySnippet: snip };
    }
    return fetch(u, { headers: h, credentials: 'include' })
      .then(function (r): Promise<InPageResponse> {
        const ct = r.headers.get('content-type') || '';
        if (ct.indexOf('application/json') >= 0) {
          return r.json().then(
            (j: unknown) => mk(r.ok, r.status, ct, j, null),
            () => mk(r.ok, r.status, ct, null, null)
          );
        }
        return r.text().then((t: string) => mk(r.ok, r.status, ct, null, String(t).slice(0, 200)));
      })
      .catch((e: { message?: string }) => mk(false, -1, '', null, String((e && e.message) || e)));
  };
  return (await page.evaluate(PAGE_FN, url, headers)) as InPageResponse<T>;
}

export function sessionOverride(): string {
  return config.sessionIdOverride;
}
