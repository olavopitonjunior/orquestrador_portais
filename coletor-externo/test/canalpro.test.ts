import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { canalPro, classificarResposta, paraAnuncio } from '../src/portals/canalpro';
import { AuthExpiredError, BlockedError, TransientError } from '../src/core/block-detector';

const __dir = dirname(fileURLToPath(import.meta.url));
const fixture = JSON.parse(readFileSync(join(__dir, 'fixtures', 'canalpro-listings.json'), 'utf8'));
const listings = fixture.data.listings.listListing;

test('paraAnuncio mapeia nota, amarração e as métricas de performance', () => {
  const a = paraAnuncio(listings[0]);
  assert.equal(a.idPortal, '9000000001');
  assert.equal(a.codigoImovel, 'IMOVEL-0001'); // amarração = externalId
  assert.equal(a.nota, 8442.5); // score CRU, sem reescala
  assert.equal(a.notaNome, 'lqsBeta');
  assert.equal(a.nivel, 'PREMIUM');
  assert.equal(a.preco, 850000);
  assert.deepEqual(a.portais, ['OLX', 'VIVAREAL', 'ZAP']);
  assert.equal(a.visualizacoes, 128);
  assert.equal(a.url, null); // não vem na listagem
});

test('cliques ficam em campos separados por tipo (não somados)', () => {
  const a = paraAnuncio(listings[0]);
  assert.equal(a.cliqueContato, 4);
  assert.equal(a.cliqueTelefone, 9);
  assert.equal(a.cliqueProposta, 2);
  assert.equal(a.cliqueWhatsapp, 15);
  assert.equal(a.cliqueAgendamento, 1);
});

test('campos ausentes viram null, não zero nem erro', () => {
  const a = paraAnuncio(listings[2]); // externalId null, score null, pricingInfos vazio
  assert.equal(a.codigoImovel, null);
  assert.equal(a.nota, null);
  assert.equal(a.preco, null);
  assert.deepEqual(a.portais, []);
  assert.equal(a.visualizacoes, 3);
  assert.equal(a.cliqueContato, null); // leads.contactForm ausente
});

test('preço prefere SALE quando há múltiplos pricingInfos', () => {
  const raw = { id: '1', pricingInfos: [{ price: 1000, businessType: 'RENTAL' }, { price: 500000, businessType: 'SALE' }] };
  assert.equal(paraAnuncio(raw).preco, 500000);
});

test('rowToCells segue a ordem de csvColumns e serializa portais com pipe', () => {
  const a = paraAnuncio(listings[0]);
  const cells = canalPro.rowToCells(a);
  assert.equal(cells.length, canalPro.csvColumns.length);
  assert.equal(cells[canalPro.csvColumns.indexOf('portais')], 'OLX|VIVAREAL|ZAP');
  assert.equal(cells[canalPro.csvColumns.indexOf('nota')], 8442.5);
});

// --- Invariante 3: a query NÃO pode pedir dado pessoal na fonte ---

test('a query listings NÃO pede endereço, geo, imagens nem contato de lead', () => {
  // Extrai a string QUERY do fonte (só a seleção GraphQL, ignorando comentários)
  // e confere que é mínima.
  const src = readFileSync(join(__dir, '..', 'src', 'portals', 'canalpro.ts'), 'utf8');
  const m = src.match(/const QUERY = `([\s\S]*?)`;/);
  assert.ok(m, 'não localizei a string QUERY no adapter');
  const query = m![1];
  const proibidos = ['address', 'street', 'streetNumber', 'point', 'lat', 'lon', 'zipCode', 'images', 'imageUrl', 'neighborhood', 'originalAddress'];
  for (const termo of proibidos) {
    assert.ok(!new RegExp(`\\b${termo}\\b`).test(query), `a query não pode pedir "${termo}" (invariante 3)`);
  }
  // e DEVE pedir o essencial de performance
  for (const termo of ['externalId', 'score', 'views', 'clickWhatsapp']) {
    assert.ok(query.includes(termo), `a query deve pedir "${termo}"`);
  }
});

// --- Tratamento de falha: bloqueio NUNCA vira "lista vazia com ok" ---

function resp(p: Partial<{ ok: boolean; status: number; contentType: string; bodySnippet: string | null; json: unknown }>) {
  return { ok: true, status: 200, contentType: 'application/json', bodySnippet: null, json: null, ...p } as Parameters<typeof classificarResposta>[0];
}

test('resposta 200 válida devolve listings e total', () => {
  const r = classificarResposta(resp({ json: fixture }));
  assert.equal(r.listings.length, 3);
  assert.equal(r.totalResults, 33);
});

test('bloqueio do Cloudflare lança BlockedError (dispara NEEDS_WARM), não lista vazia', () => {
  const cf = resp({ status: 200, contentType: 'text/html', bodySnippet: 'Just a moment...' });
  assert.throws(() => classificarResposta(cf), BlockedError);
  const forbidden = resp({ status: 403, contentType: 'text/html', bodySnippet: 'access denied' });
  assert.throws(() => classificarResposta(forbidden), BlockedError);
});

test('401 lança AuthExpiredError', () => {
  assert.throws(() => classificarResposta(resp({ status: 401, json: null })), AuthExpiredError);
});

test('erro GraphQL e resposta anômala lançam, nunca devolvem vazio silencioso', () => {
  assert.throws(() => classificarResposta(resp({ json: { errors: [{ message: 'x' }] } })), /GraphQL errors/);
  assert.throws(() => classificarResposta(resp({ status: 500, json: null })), /resposta inesperada/);
  assert.throws(() => classificarResposta(resp({ status: 200, json: { data: {} } })), /resposta inesperada/);
});

// --- Repetível × definitivo: o que vale nova tentativa e o que não vale ---
//
// O caso de origem: 06/09, HTTP 200 e o gateway dizendo no CORPO que não alcançava
// o backend dele. Dez segundos de soluço mataram treze minutos de coleta, numa
// rodada de tentativa única.

test('erro de GraphQL "não alcança a API" (200) é TransientError, não erro genérico', () => {
  const observado = resp({ json: { errors: [{ message: 'Can not reach the API' }] } });
  assert.throws(() => classificarResposta(observado), TransientError);
  // A mensagem observada em 06/09, literal, sem normalização nenhuma antes.
  assert.throws(() => classificarResposta(observado), /não alcançou a API/);
});

test('erro de GraphQL de CONSULTA continua definitivo — repeti-lo gastaria a tentativa da sexta', () => {
  for (const message of [
    'Cannot query field "score" on type "Listing"',
    'Variable $timeout of required type Int! was not provided',
    'Syntax Error: Expected Name, found }',
  ]) {
    const r = resp({ json: { errors: [{ message }] } });
    assert.throws(() => classificarResposta(r), /GraphQL errors/, `"${message}" deve ser definitivo`);
    // A guarda que importa: erro de código NUNCA pode virar repetível. `timeout`
    // como palavra solta casaria a segunda mensagem — por isso o padrão casa frase.
    assert.doesNotThrow(() => {
      try {
        classificarResposta(r);
      } catch (e) {
        if (e instanceof TransientError) throw new Error(`"${message}" foi classificado como repetível`);
      }
    });
  }
});

test('PRECEDÊNCIA: 503 com desafio do Cloudflare é bloqueio, não soluço', () => {
  // Um 503 servindo desafio casa `isTransient` (pelo status) E `isBlockResponse`
  // (pelo marcador). Se o transitório vencesse, a NEEDS_WARM.flag não seria criada
  // e o operador nunca seria mandado re-logar — falha silenciosa.
  const desafio = resp({ status: 503, contentType: 'text/html', bodySnippet: 'Just a moment...', json: null });
  assert.throws(() => classificarResposta(desafio), BlockedError);
  // Sem marcador, o MESMO status é soluço de infraestrutura e vale nova tentativa.
  const soluco = resp({ status: 503, contentType: 'text/html', bodySnippet: 'upstream error', json: null });
  assert.throws(() => classificarResposta(soluco), TransientError);
});

test('429 e falha de rede são repetíveis — `isTransient` deixa de ser código morto', () => {
  assert.throws(() => classificarResposta(resp({ status: 429, json: null })), TransientError);
  assert.throws(() => classificarResposta(resp({ status: -1, contentType: '', json: null })), TransientError);
  // 500 NÃO está na lista: pode ser defeito de consulta do lado deles, e a casa não
  // inventa marcador não observado. Continua definitivo.
  assert.throws(() => classificarResposta(resp({ status: 500, json: null })), /resposta inesperada/);
  // Corpo declarado JSON que não parseou: `r.json()` rejeitou no transporte, o que só
  // acontece por corpo truncado ou malformado do lado deles.
  assert.throws(
    () => classificarResposta(resp({ status: 200, contentType: 'application/json', json: null })),
    TransientError
  );
});

test('"too many requests" NÃO é marcador: casaria limite de complexidade, que é erro de consulta', () => {
  // Recusado na revisão desta fatia. O 429 de verdade chega por status HTTP e
  // `isTransient` já o cobre; como marcador de CORPO, a frase descreve limite em
  // geral e não inalcançabilidade — e repetir um erro de consulta gasta a tentativa
  // única que a sexta tem.
  const complexidade = resp({
    json: { errors: [{ message: 'Query complexity limit exceeded: too many requests in batch, max 10 allowed' }] },
  });
  assert.throws(() => classificarResposta(complexidade), /GraphQL errors/);
  try {
    classificarResposta(complexidade);
  } catch (e) {
    assert.ok(!(e instanceof TransientError), 'limite de complexidade é defeito de consulta, não soluço');
  }
});

test('paginação usa chave IMUTÁVEL (CREATED_AT) para retomada estável', () => {
  const src = readFileSync(join(__dir, '..', 'src', 'portals', 'canalpro.ts'), 'utf8');
  assert.ok(src.includes("orderBy: 'CREATED_AT'"), 'ordenação deve ser por CREATED_AT (imutável)');
  assert.ok(!src.includes("orderBy: 'UPDATED_AT'"), 'UPDATED_AT muda durante a coleta e quebra a retomada');
});

test('o adapter passa credentials omit — o Canal Pro autentica por Bearer, não cookie', () => {
  // O canário provou: credentials include → CORS status 0; omit → 200.
  // Trava a regressão de alguém re-hardcodar include ou remover o omit.
  const src = readFileSync(join(__dir, '..', 'src', 'portals', 'canalpro.ts'), 'utf8');
  assert.ok(/credentials:\s*'omit'/.test(src), "canalpro deve passar credentials: 'omit' na chamada");
});

test('csvColumns cobre exatamente os campos do Anuncio de performance', () => {
  assert.equal(canalPro.csvColumns.length, 16);
  assert.ok(canalPro.csvColumns.includes('codigoImovel'));
  assert.ok(canalPro.csvColumns.includes('nota'));
  assert.ok(canalPro.csvColumns.includes('visualizacoes'));
});

test('captureSessionId tolera contexto destruído por navegação tardia do SPA', async () => {
  let chamadas = 0;
  const page = {
    evaluateOnNewDocument: async () => undefined,
    goto: async () => undefined,
    evaluate: async () => {
      // 1ª chamada: readBlocked (retorna false). 2ª: contexto morto. 3ª: sessão capturada.
      chamadas++;
      if (chamadas === 1) return false;
      if (chamadas === 2) throw new Error('Execution context was destroyed, most likely because of a navigation.');
      return { authorization: 'Bearer x', 'x-domain': 'canalpro' };
    },
  } as unknown as import('puppeteer-core').Page;
  const s = await canalPro.captureSessionId(page);
  assert.equal((s as Record<string, string>).authorization, 'Bearer x');
  assert.equal(chamadas, 3);
});

test('captureSessionId NÃO engole outros erros do evaluate', async () => {
  let chamadas = 0;
  const page = {
    evaluateOnNewDocument: async () => undefined,
    goto: async () => undefined,
    evaluate: async () => {
      chamadas++;
      if (chamadas === 1) return false;
      throw new Error('ReferenceError: window is not defined');
    },
  } as unknown as import('puppeteer-core').Page;
  await assert.rejects(canalPro.captureSessionId(page), /ReferenceError/);
});
