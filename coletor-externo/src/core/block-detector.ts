// Classificadores de bloqueio — puros, agnósticos de portal.
// Cloudflare é Cloudflare em qualquer portal; a classificação opera só sobre
// o envelope InPageResponse. Portado de imovelweb-ativos/src/block-detector.ts
// (ver README › Proveniência), removido o caminho Selenium (screenshot/WebDriver).

import { InPageResponse } from './types';

const CF_MARKERS = /just a moment|cf-browser-verification|challenge-form|cloudflare|verify you are human/i;

/** Bloqueio duro do Cloudflare (não adianta retry): 403 ou HTML de desafio. */
export function isBlockResponse(resp: InPageResponse): boolean {
  if (resp.status === 403) return true;
  // Qualquer resposta com marcador de desafio (403 já coberto; 200 não-JSON
  // interstitial; etc.). Sem marcador, não é bloqueio duro.
  return !!(resp.bodySnippet && CF_MARKERS.test(resp.bodySnippet));
}

/** Transiente (vale retry com backoff): 429, 503, erro de rede (-1), ou 200 não-JSON SEM marcador CF. */
export function isTransient(resp: InPageResponse): boolean {
  if (resp.status === 429 || resp.status === 503 || resp.status === -1) return true;
  if (resp.status === 200 && resp.json === null && !resp.contentType.includes('application/json')) {
    return !(resp.bodySnippet && CF_MARKERS.test(resp.bodySnippet));
  }
  return false;
}

/** Sessão expirada — dispara recaptura do identificador de sessão. */
export function isAuthExpired(resp: InPageResponse): boolean {
  return resp.status === 401;
}

/** Lançada quando um bloqueio duro é detectado: o operador precisa re-aquecer o perfil. */
export class BlockedError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'BlockedError';
  }
}

/** Lançada quando a sessão expira e a recaptura esgota as tentativas. */
export class AuthExpiredError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'AuthExpiredError';
  }
}
