// Adapter do Canal Pro (Grupo OLX/ZAP) — implementação real.
//
// A API interna do painel é GraphQL: POST https://gandalf-api.grupozap.com/,
// operationName "listings", paginação linear por pageNumber. Autentica por um
// conjunto de headers (Authorization Bearer + x-*), capturado da sessão do
// operador logado. Cada anúncio traz nota (LQS), visualizações e cliques
// agregados, e o externalId que amarra ao imóvel interno.
//
// Reconhecido com o operador logado (docs/coletor: CANALPRO_SCRAPE_RECIPE.md).
// Ver docs/decisoes.md D-010 (transporte CDP) e D-012 (publicação aberta).

import { Page } from 'puppeteer-core';
import { Anuncio, Portal, Sessao } from '../portal';
import { fetchInPage } from '../cdp/transport';
import { AuthExpiredError, BlockedError, isBlockResponse } from '../core/block-detector';
import { InPageResponse } from '../core/types';

const ID = 'canalpro';
const ENDPOINT = 'https://gandalf-api.grupozap.com/';
// 100/página (o máximo que o canário validou): com ~55 mil anúncios, são ~551
// requisições em vez de ~1.836 a 30/página — 3× menos batidas no portal
// (superfície anti-bot). O checkpoint por página continua igual.
const PAGE_SIZE = 100;

// Sessão do Canal Pro: os headers de auth capturados de uma XHR real.
// Opaca ao núcleo; NUNCA logada, persistida ou impressa (segredo de sessão).
type CanalProSession = Record<string, string>;

// Nomes dos headers de auth/contexto que a query listings exige. Só NOMES aqui;
// os valores vêm da sessão do operador em runtime e nunca são embutidos.
const HEADERS_AUTH = [
  'authorization',
  'x-publisherid',
  'x-contractid',
  'x-odinid',
  'x-clientid',
  'x-company',
  'x-appversion',
  'x-publishercontracttype',
];

// Query GraphQL MÍNIMA (invariante 3): só performance de portal + amarração.
// Deliberadamente SEM address/street/point(geo)/images/originalAddress — o
// cruzamento de características é do Coletor Interno; o Externo só traz
// performance. `leads{}` são contagens agregadas, não identidades.
const QUERY = `query listings($listingStatus: [ListingStatusEnumType], $publicationType: [PublicationTypeEnumType], $businessType: [BusinessEnumType], $contractType: ContractEnumType, $pageSize: Int, $pageNumber: Int, $orderBy: ListingOrderByEnumType, $orderDesc: Boolean) {
  listings(listingStatus: $listingStatus, publicationType: $publicationType, businessType: $businessType, contractType: $contractType, pageSize: $pageSize, pageNumber: $pageNumber, orderBy: $orderBy, orderDesc: $orderDesc) {
    listListing {
      externalId
      id
      score
      scoreName
      publicationType
      status
      createdAt
      portals
      pricingInfos { price businessType }
      leads { views contactForm phoneView clickProposal clickWhatsapp clickSchedule }
    }
    pageNumber
    pageSize
    totalPages
    totalResults
  }
}`;

interface ListingsResp {
  listings?: {
    listListing?: RawListing[];
    totalResults?: number;
    totalPages?: number;
  };
}

interface RawListing {
  externalId?: string;
  id?: string;
  score?: number;
  scoreName?: string;
  publicationType?: string;
  status?: string;
  createdAt?: string;
  portals?: string[];
  pricingInfos?: Array<{ price?: number; businessType?: string }>;
  leads?: {
    views?: number;
    contactForm?: number;
    phoneView?: number;
    clickProposal?: number;
    clickWhatsapp?: number;
    clickSchedule?: number;
  };
}

function variables(pageNumber: number) {
  return {
    listingStatus: [],
    publicationType: [],
    businessType: [],
    contractType: 'REAL_ESTATE',
    pageSize: PAGE_SIZE,
    pageNumber,
    orderBy: 'CREATED_AT',
    orderDesc: true, // chave IMUTÁVEL: a retomada por página não pula nem duplica
  };
}

function num(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

/** Converte um anúncio cru da API no contrato de saída do produto. */
export function paraAnuncio(raw: RawListing): Anuncio {
  const preco = raw.pricingInfos?.find((p) => p.businessType === 'SALE') ?? raw.pricingInfos?.[0];
  const l = raw.leads ?? {};
  return {
    idPortal: String(raw.id ?? ''),
    codigoImovel: raw.externalId != null ? String(raw.externalId) : null,
    nota: num(raw.score),
    notaNome: raw.scoreName ?? null,
    nivel: raw.publicationType ?? null,
    situacao: raw.status ?? null,
    preco: num(preco?.price),
    portais: Array.isArray(raw.portals) ? raw.portals : null,
    criadoEm: raw.createdAt ?? null,
    visualizacoes: num(l.views),
    cliqueContato: num(l.contactForm),
    cliqueTelefone: num(l.phoneView),
    cliqueProposta: num(l.clickProposal),
    cliqueWhatsapp: num(l.clickWhatsapp),
    cliqueAgendamento: num(l.clickSchedule),
    url: null, // não vem na listagem do Canal Pro
  };
}

async function postListings(
  page: Page,
  sessao: CanalProSession,
  pageNumber: number
): Promise<{ listings: RawListing[]; totalResults: number }> {
  const headers = { ...sessao, accept: 'application/json', 'content-type': 'application/json' };
  const body = JSON.stringify({ operationName: 'listings', query: QUERY, variables: variables(pageNumber) });
  const resp = await fetchInPage<{ data?: ListingsResp; errors?: Array<{ message: string }> }>(
    page,
    ENDPOINT,
    headers,
    // credentials 'omit' EXPLÍCITO: o Canal Pro autentica por Bearer no header,
    // não por cookie; com credenciais o preflight CORS rejeita (canário 31/08).
    { method: 'POST', body, credentials: 'omit' }
  );
  return classificarResposta(resp);
}

/**
 * Classifica a resposta ANTES de ler dados — pura, testável sem browser.
 * Uma resposta bloqueada ou não-JSON NUNCA pode ser confundida com "lista
 * vazia" (isso viraria coleta parcial marcada como sucesso, indo ao Analista
 * de Perfil como completa). Bloqueio duro → BlockedError (dispara NEEDS_WARM);
 * 401 → AuthExpiredError; qualquer outra anomalia → Error explícito.
 */
export function classificarResposta(
  resp: InPageResponse<{ data?: ListingsResp; errors?: Array<{ message: string }> }>
): { listings: RawListing[]; totalResults: number } {
  if (resp.status === 401) {
    throw new AuthExpiredError(`Canal Pro respondeu 401 — sessão expirada.`);
  }
  if (isBlockResponse(resp)) {
    throw new BlockedError(`Canal Pro bloqueou (status ${resp.status}) — re-aqueça o perfil (login).`);
  }
  if (resp.json?.errors?.length) {
    throw new Error(`Canal Pro GraphQL errors: ${resp.json.errors.map((e) => e.message).join('; ')}`);
  }
  if (resp.status !== 200 || resp.json?.data?.listings == null) {
    throw new Error(`Canal Pro: resposta inesperada (status ${resp.status}, sem data.listings).`);
  }
  const data = resp.json.data.listings;
  return { listings: data.listListing ?? [], totalResults: data.totalResults ?? 0 };
}

export const canalPro: Portal = {
  id: ID,
  host: 'canal-pro.grupozap.com',
  panelUrl: 'https://canal-pro.grupozap.com/',
  shardDimensions: [], // paginação linear — sem sharding por facets
  pageSize: PAGE_SIZE,
  csvColumns: [
    'idPortal',
    'codigoImovel',
    'nota',
    'notaNome',
    'nivel',
    'situacao',
    'preco',
    'portais',
    'criadoEm',
    'visualizacoes',
    'cliqueContato',
    'cliqueTelefone',
    'cliqueProposta',
    'cliqueWhatsapp',
    'cliqueAgendamento',
    'url',
  ],

  async captureSessionId(page: Page): Promise<Sessao> {
    // Instala, antes de navegar, um hook que grava em window.__CP os headers de
    // auth da próxima XHR listings; depois navega ao painel (que a dispara).
    // Shim do `__name`: o tsx/esbuild anota funções com o helper `__name`, e o puppeteer
    // serializa a função para o navegador, onde o helper não existe — "__name is not
    // defined" (medido em 03/09/2026, logo após a captura de sessão). Identidade em
    // cada documento novo e no atual; inofensivo quando o helper não é injetado.
    const shim = () => {
      const g = globalThis as unknown as { __name?: (f: unknown, n?: string) => unknown };
      if (typeof g.__name !== 'function') g.__name = (f: unknown) => f;
    };
    await page.evaluateOnNewDocument(shim);
    await page.evaluate(shim).catch(() => undefined);
    await page.evaluateOnNewDocument((nomes: string[]) => {
      const w = window as unknown as { __CP?: Record<string, string> };
      const orig = window.fetch;
      window.fetch = function (input: RequestInfo | URL, init?: RequestInit) {
        try {
          const url = typeof input === 'string' ? input : (input as Request).url || '';
          if (url.includes('gandalf-api') && init && typeof init.body === 'string' && init.body.includes('listings')) {
            const out: Record<string, string> = {};
            const h = init.headers as Record<string, string> | Headers | undefined;
            const want = new Set(nomes.map((n) => n.toLowerCase()));
            if (h instanceof Headers) h.forEach((v, k) => { if (want.has(k.toLowerCase())) out[k] = v; });
            else if (h) for (const k of Object.keys(h)) { if (want.has(k.toLowerCase())) out[k] = (h as Record<string, string>)[k]; }
            if (Object.keys(out).length) w.__CP = out;
          }
        } catch { /* ignore */ }
        return orig.apply(this, arguments as unknown as [RequestInfo | URL, RequestInit?]);
      };
    }, HEADERS_AUTH);

    await page.goto(`${this.panelUrl}`, { waitUntil: 'networkidle2', timeout: 60_000 }).catch(() => undefined);
    if (await this.readBlocked(page)) {
      throw new BlockedError('Cloudflare detectado no Canal Pro. Re-aqueça o perfil (login) e rode de novo.');
    }
    for (let i = 0; i < 40; i++) {
      let s: Record<string, string> | null = null;
      try {
        s = await page.evaluate(() => (window as unknown as { __CP?: Record<string, string> }).__CP || null);
      } catch (e) {
        // O SPA do painel navega de novo DEPOIS de o goto resolver (medido em 03/09/2026:
        // duas corridas mortas aos ~3 s com "Execution context was destroyed"). Contexto
        // destruído durante a espera é benigno — o hook de `evaluateOnNewDocument` é
        // reinstalado a cada documento novo, então basta esperar e olhar de novo.
        // "Target closed" NÃO entra: é a aba/Chrome que morreu, e esperar 20 s para dizer
        // "abra a lista de anúncios" seria o diagnóstico errado. Sobe na hora.
        if (!/Execution context was destroyed|Cannot find context/i.test(String(e))) throw e;
      }
      if (s && Object.keys(s).length) return s as CanalProSession;
      await new Promise((r) => setTimeout(r, 500));
    }
    throw new Error('Não capturei os headers de sessão do Canal Pro (nenhuma XHR listings). Abra a lista de anúncios e rode de novo.');
  },

  async probeList(page, sessao, _tokens): Promise<{ numberOfPostings: number; facets: unknown }> {
    const { totalResults } = await postListings(page, sessao as CanalProSession, 1);
    return { numberOfPostings: totalResults, facets: {} };
  },

  async collectPage(page, sessao, pageNumber): Promise<Anuncio[]> {
    const { listings } = await postListings(page, sessao as CanalProSession, pageNumber);
    return listings.map(paraAnuncio);
  },

  async collectShard(page, sessao, _tokens, limite): Promise<Anuncio[]> {
    // Sem sharding: pagina do início até o limite (canário) ou até esgotar.
    const s = sessao as CanalProSession;
    const total = (await this.probeList(page, s, [])).numberOfPostings;
    const totalPages = Math.ceil(total / PAGE_SIZE);
    const acc: Anuncio[] = [];
    for (let pg = 1; pg <= totalPages; pg++) {
      const anuncios = await this.collectPage!(page, s, pg);
      acc.push(...anuncios);
      if (limite != null && acc.length >= limite) return acc.slice(0, limite);
      if (!anuncios.length) break;
    }
    return acc;
  },

  rowToCells(a: Anuncio): unknown[] {
    return [
      a.idPortal,
      a.codigoImovel,
      a.nota,
      a.notaNome,
      a.nivel,
      a.situacao,
      a.preco,
      a.portais ? a.portais.join('|') : null,
      a.criadoEm,
      a.visualizacoes,
      a.cliqueContato,
      a.cliqueTelefone,
      a.cliqueProposta,
      a.cliqueWhatsapp,
      a.cliqueAgendamento,
      a.url,
    ];
  },

  async readBlocked(page: Page): Promise<boolean> {
    try {
      return await page.evaluate(() => {
        const t = (document.body?.innerText || '').toLowerCase();
        const title = (document.title || '').toLowerCase();
        return (
          !!document.querySelector('#challenge-form, .cf-browser-verification, input[name="cf_captcha_kind"]') ||
          title.includes('just a moment') ||
          title.includes('cloudflare') ||
          t.includes('verificando se você é humano') ||
          t.includes('verify you are human')
        );
      });
    } catch {
      return false;
    }
  },
};
