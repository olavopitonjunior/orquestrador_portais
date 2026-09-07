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

/** Transiente (vale nova tentativa): 429, 503, erro de rede (-1), ou 200 não-JSON
 *  SEM marcador CF.
 *
 *  Consultado por `classificarResposta` DEPOIS do 401 e DEPOIS de `isBlockResponse`
 *  — a ordem é regra, e o porquê está lá. Até 06/09 esta função era código MORTO:
 *  existia, tinha teste, e nenhum caminho de produção a chamava; 429 e 503 saíam
 *  como "resposta inesperada", indistinguíveis de um defeito de consulta. */
export function isTransient(resp: InPageResponse): boolean {
  if (resp.status === 429 || resp.status === 503 || resp.status === -1) return true;
  // 200 cujo corpo NÃO virou objeto. Dois caminhos chegam aqui, e ambos são soluço:
  // o corpo não era JSON (interstitial), ou foi DECLARADO `application/json` e não
  // parseou — em `cdp/transport.ts` isso é exatamente `r.json()` rejeitando, ou seja
  // corpo truncado. Uma consulta nossa não pode produzir corpo malformado do lado
  // deles. A exclusão do content-type que havia aqui deixava de fora justamente o
  // corpo truncado, que é a forma mais literal do soluço que esta classificação
  // existe para pegar. Marcador do Cloudflare continua vencendo: é bloqueio, não
  // soluço (e nesse caminho `bodySnippet` vem preenchido, no outro vem null).
  if (resp.status === 200 && resp.json === null) {
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

/** Lançada quando a falha é do tipo que uma NOVA TENTATIVA resolve — o portal
 *  soluçou, o código está certo.
 *
 *  O que esta classe NÃO faz: repetir. Quantas vezes tentar e com que intervalo é o
 *  **parâmetro nº 4, que segue NULO** — do dono da decisão, não do código. Aqui só
 *  se afirma o que a resposta é; quem repete hoje é o operador, avisado pelo console.
 *  Quando o parâmetro ganhar valor, é este tipo que a política vai consultar.
 *
 *  Por que ela existe: em 06/09 a coleta completa morreu em 10 s com o gateway do
 *  portal respondendo 200 e dizendo no corpo que não alcançava o backend dele. Não
 *  houve segunda tentativa, e a segunda — manual, um minuto depois — levou 13
 *  minutos e trouxe 55.162 anúncios. A sexta tem tentativa única por rodada. */
export class TransientError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'TransientError';
  }
}
