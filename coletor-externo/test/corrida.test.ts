// Os testes que faltavam: a orquestração da corrida nunca teve nenhum, porque
// `run.ts` chama `void main()` na última linha e importá-lo dispararia uma coleta.
// É exatamente onde moravam os três defeitos do contrato de arquivo:
//
//   D1  o CSV acumulava entre execuções (dois canários ⇒ 2× as linhas)
//   D2  `--full` sobre checkpoint esgotado não coletava nada e se declarava "ok"
//   D3  `NEEDS_WARM.flag` nunca era removida, e o console prometia que sumia
//
// Nenhum destes testes toca navegador: o Portal é um duplo que ignora a `page`.

import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import { mkdtemp, readFile, rm, writeFile } from 'fs/promises';
import { existsSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import type { Page } from 'puppeteer-core';
import { AuthExpiredError, BlockedError } from '../src/core/block-detector';
import { NEEDS_WARM_FLAG } from '../src/core/config';
import { executarComTratamento, executarCorrida, nomeDoCsv, podeRetomar } from '../src/core/corrida';
import { CONTRATO_CHECKPOINT } from '../src/core/types';
import type { Anuncio, Portal } from '../src/portal';

const PAGINA = {} as Page;

function anuncio(id: string): Anuncio {
  return {
    idPortal: id, codigoImovel: id, nota: 1, notaNome: 'lqs', nivel: null, situacao: null,
    preco: null, portais: null, criadoEm: null, visualizacoes: null, cliqueContato: null,
    cliqueTelefone: null, cliqueProposta: null, cliqueWhatsapp: null, cliqueAgendamento: null,
    url: null,
  };
}

/** Portal falso. `pedidas` registra as páginas que a corrida realmente pediu — é o
 *  que separa "coletou" de "declarou que coletou". */
function portalFalso(opts: { total: number; porPagina: number; bloqueiaEm?: number }) {
  const pedidas: number[] = [];
  const portal: Portal = {
    id: 'falso',
    host: 'exemplo',
    panelUrl: 'https://exemplo',
    shardDimensions: [],
    csvColumns: ['idPortal', 'nota'],
    pageSize: opts.porPagina,
    captureSessionId: async () => 'sessao',
    probeList: async () => ({ numberOfPostings: opts.total, facets: {} }),
    collectShard: async (_p, _s, _t, limite) =>
      Array.from({ length: Math.min(limite ?? opts.total, opts.total) }, (_, i) => anuncio(`c${i}`)),
    collectPage: async (_p, _s, pg) => {
      if (opts.bloqueiaEm === pg) throw new BlockedError('desafio do portal');
      pedidas.push(pg);
      const restam = opts.total - (pg - 1) * opts.porPagina;
      return Array.from({ length: Math.max(0, Math.min(opts.porPagina, restam)) }, (_, i) =>
        anuncio(`p${pg}-${i}`)
      );
    },
    rowToCells: (a) => [a.idPortal, a.nota],
    readBlocked: async () => false,
  };
  return { portal, pedidas };
}

function deps(outDir: string) {
  return {
    conectar: async () => ({ browser: { disconnect: async () => {} }, page: PAGINA }),
    irAoPainel: async () => {},
    log: () => {},
    agora: () => new Date('2026-09-06T12:00:00.000Z'),
    outDir,
    degrausDoCanario: [1, 10, 100, 1000],
  };
}

async function comDiretorio(fn: (dir: string) => Promise<void>): Promise<void> {
  const dir = await mkdtemp(join(tmpdir(), 'coletor-corrida-'));
  try {
    await fn(dir);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
}

const linhas = async (f: string) => (await readFile(f, 'utf8')).trimEnd().split('\r\n');
const status = async (dir: string) => JSON.parse(await readFile(join(dir, 'status.json'), 'utf8'));

// ---- D1: o CSV não acumula ----

test('D1: dois canários seguidos deixam UMA corrida no arquivo, não duas', async () => {
  await comDiretorio(async (dir) => {
    const { portal } = portalFalso({ total: 3, porPagina: 10 });
    await executarCorrida(portal, 'canary', deps(dir));
    await executarCorrida(portal, 'canary', deps(dir));
    const l = await linhas(join(dir, 'falso.canario.csv'));
    assert.equal(l.length, 4, 'cabeçalho + 3 linhas — o segundo canário substitui o primeiro');
    assert.equal((await status(dir)).rows, 3);
  });
});

test('D1: canário e full escrevem em arquivos separados', async () => {
  await comDiretorio(async (dir) => {
    const { portal } = portalFalso({ total: 3, porPagina: 10 });
    await executarCorrida(portal, 'canary', deps(dir));
    assert.ok(existsSync(join(dir, 'falso.canario.csv')));
    assert.ok(!existsSync(join(dir, 'falso.csv')), 'o canário não pode tocar o arquivo do full');
    assert.equal(nomeDoCsv('falso', 'full'), 'falso.csv');
  });
});

test('D1: full novo descarta o CSV anterior', async () => {
  await comDiretorio(async (dir) => {
    const alvo = join(dir, 'falso.csv');
    await writeFile(alvo, '"idPortal","nota"\r\n"velho","9"\r\n', 'utf8');
    const { portal } = portalFalso({ total: 2, porPagina: 10 });
    await executarCorrida(portal, 'full', deps(dir));
    const l = await linhas(alvo);
    assert.ok(!l.some((x) => x.includes('velho')), 'linha da corrida anterior não pode sobreviver');
  });
});

test('a geração guardada é a de uma corrida CONCLUÍDA, com o conteúdo dela', async () => {
  await comDiretorio(async (dir) => {
    const alvo = join(dir, 'falso.csv');
    await writeFile(alvo, '"idPortal","nota"\r\n"completo","9"\r\n', 'utf8');
    await writeFile(
      join(dir, 'status.json'),
      JSON.stringify({ result: 'ok', mode: 'full', finishedAt: 'x', rows: 1 }),
      'utf8'
    );
    const { portal } = portalFalso({ total: 2, porPagina: 10 });
    await executarCorrida(portal, 'full', deps(dir));
    const guardado = await linhas(join(dir, 'falso.anterior.csv'));
    assert.ok(guardado.some((x) => x.includes('completo')), 'tem de guardar o CONTEÚDO, não um arquivo qualquer');
  });
});

test('um CSV parcial NÃO atropela a geração guardada', async () => {
  // `rename` sobrescreve em silêncio: sem a condição, uma corrida rebaixada
  // guardaria um parcial por cima do último full bom, e o nome prometeria o que o
  // arquivo não é.
  await comDiretorio(async (dir) => {
    await writeFile(join(dir, 'falso.anterior.csv'), '"idPortal","nota"\r\n"bom","9"\r\n', 'utf8');
    await writeFile(join(dir, 'falso.csv'), '"idPortal","nota"\r\n"parcial","1"\r\n', 'utf8');
    await writeFile(
      join(dir, 'status.json'),
      JSON.stringify({ result: 'error', mode: 'full', finishedAt: 'x' }),
      'utf8'
    );
    const { portal } = portalFalso({ total: 2, porPagina: 10 });
    await executarCorrida(portal, 'full', deps(dir));
    const guardado = await linhas(join(dir, 'falso.anterior.csv'));
    assert.ok(guardado.some((x) => x.includes('bom')), 'o último full bom tem de sobreviver');
    assert.ok(!guardado.some((x) => x.includes('parcial')));
  });
});

test('durante o full, o status declara `running` antes de truncar', async () => {
  // Um full leva horas e o status só era escrito no fim: quem lesse `out/` no meio
  // veria o CSV truncado ao lado do status da corrida ANTERIOR, com `finishedAt`
  // que a porta de idade aceita.
  await comDiretorio(async (dir) => {
    const vistos: string[] = [];
    const { portal } = portalFalso({ total: 2, porPagina: 1 });
    const espiao = {
      ...portal,
      collectPage: async (p: Parameters<NonNullable<Portal['collectPage']>>[0], sess: unknown, pg: number) => {
        vistos.push(JSON.parse(await readFile(join(dir, 'status.json'), 'utf8')).result);
        return portal.collectPage!(p, sess, pg);
      },
    } as Portal;
    await executarCorrida(espiao, 'full', deps(dir));
    assert.ok(vistos.includes('running'), `status durante a coleta: ${vistos.join(', ')}`);
    assert.equal((await status(dir)).result, 'ok', 'e no fim vira ok');
  });
});

// ---- D2: checkpoint esgotado não vira "ok" sem coletar ----

test('D2: full que conclui apaga o checkpoint', async () => {
  await comDiretorio(async (dir) => {
    const { portal } = portalFalso({ total: 2, porPagina: 10 });
    await executarCorrida(portal, 'full', deps(dir));
    assert.ok(!existsSync(join(dir, 'progress.json')), 'checkpoint imortal é o que produz o D2');
  });
});

test('D2: full sobre checkpoint ESGOTADO coleta de novo em vez de se declarar ok', async () => {
  await comDiretorio(async (dir) => {
    await writeFile(
      join(dir, 'progress.json'),
      JSON.stringify({
        startedAt: 'x', completedShards: [], seenCount: 0, rowsWritten: 999, lastUpdate: 'x',
        lastPage: 3, contrato: CONTRATO_CHECKPOINT, portal: 'falso', modo: 'full',
      }),
      'utf8'
    );
    await writeFile(join(dir, 'falso.csv'), '"idPortal","nota"\r\n"lixo","0"\r\n', 'utf8');
    const { portal, pedidas } = portalFalso({ total: 3, porPagina: 1 });
    const desfecho = await executarCorrida(portal, 'full', deps(dir));
    assert.deepEqual(pedidas, [1, 2, 3], 'tem de pedir as páginas, não pular o laço');
    assert.equal(desfecho.rows, 3, 'rows é o que se coletou agora, não o da corrida anterior');
    assert.equal((await status(dir)).rows, 3);
    const l = await linhas(join(dir, 'falso.csv'));
    assert.ok(!l.some((x) => x.includes('lixo')), 'o CSV velho não pode sobreviver');
  });
});

test('D2: checkpoint sem contrato é da versão antiga — corrida nova', () => {
  const antigo = { startedAt: 'x', completedShards: [], seenCount: 0, rowsWritten: 9, lastUpdate: 'x', lastPage: 5 };
  assert.equal(podeRetomar(antigo, 'falso', 'full', true).retoma, false);
  assert.match(podeRetomar(antigo, 'falso', 'full', true).porque, /contrato/);
});

test('D2: checkpoint de SHARDS não retoma num portal paginado', () => {
  // Sem esta condição o `lastPage` ausente virava `start = 1`, a rede de "esgotado"
  // não disparava e o CSV anterior era PRESERVADO enquanto tudo era recoletado por
  // cima — o acúmulo de volta, por dentro da guarda que existe para impedi-lo.
  const deShards = {
    startedAt: 'x', completedShards: ['sp|casa', 'sp|apto'], seenCount: 0, rowsWritten: 500,
    lastUpdate: 'x', contrato: CONTRATO_CHECKPOINT, portal: 'falso', modo: 'full' as const,
  };
  const v = podeRetomar(deShards, 'falso', 'full', true);
  assert.equal(v.retoma, false);
  assert.match(v.porque, /shards/);
});

test('D2: checkpoint de OUTRO portal ou de outro modo não retoma', () => {
  const base = {
    startedAt: 'x', completedShards: [], seenCount: 0, rowsWritten: 9, lastUpdate: 'x',
    lastPage: 1, contrato: CONTRATO_CHECKPOINT, modo: 'full' as const,
  };
  assert.equal(podeRetomar({ ...base, portal: 'outro' }, 'falso', 'full', true).retoma, false);
  assert.equal(podeRetomar({ ...base, portal: 'falso' }, 'falso', 'canary', true).retoma, false);
  assert.equal(podeRetomar({ ...base, portal: 'falso' }, 'falso', 'full', true).retoma, true);
});

test('D2: retomada LEGÍTIMA continua de onde parou e preserva o que já havia', async () => {
  await comDiretorio(async (dir) => {
    await writeFile(
      join(dir, 'progress.json'),
      JSON.stringify({
        startedAt: 'x', completedShards: [], seenCount: 0, rowsWritten: 1, lastUpdate: 'x',
        lastPage: 1, contrato: CONTRATO_CHECKPOINT, portal: 'falso', modo: 'full',
      }),
      'utf8'
    );
    await writeFile(join(dir, 'falso.csv'), '"idPortal","nota"\r\n"p1-0","1"\r\n', 'utf8');
    const { portal, pedidas } = portalFalso({ total: 3, porPagina: 1 });
    await executarCorrida(portal, 'full', deps(dir));
    assert.deepEqual(pedidas, [2, 3], 'não re-bate o portal do início');
    const l = await linhas(join(dir, 'falso.csv'));
    assert.ok(l.some((x) => x.includes('p1-0')), 'a página já coletada tem de sobreviver');
  });
});

// ---- D3: a flag de re-aquecimento ----

test('D3: corrida que autentica remove a flag pré-existente', async () => {
  await comDiretorio(async (dir) => {
    await writeFile(join(dir, NEEDS_WARM_FLAG), 'ontem', 'utf8');
    const { portal } = portalFalso({ total: 1, porPagina: 10 });
    await executarCorrida(portal, 'canary', deps(dir));
    assert.ok(!existsSync(join(dir, NEEDS_WARM_FLAG)), 'o console promete que ela some ao autenticar');
  });
});

test('D3: bloqueio no meio recria a flag e sai com código 2', async () => {
  await comDiretorio(async (dir) => {
    const { portal } = portalFalso({ total: 3, porPagina: 1, bloqueiaEm: 2 });
    const desfecho = await executarComTratamento(portal, 'full', deps(dir));
    assert.equal(desfecho.result, 'blocked');
    assert.equal(desfecho.exitCode, 2);
    assert.ok(existsSync(join(dir, NEEDS_WARM_FLAG)));
  });
});

// `mode` é a COSTURA entre o raspador e o leitor Python: é por ele que
// `_csv_do_modo` escolhe o arquivo. Sem asserção no caminho de sucesso, uma
// mutação que o removesse do `ok` passaria em toda a suíte, e todo canário
// passaria a ser lido como coleta completa — o defeito de origem, em silêncio.

test('status.json declara o modo no sucesso do CANÁRIO', async () => {
  await comDiretorio(async (dir) => {
    const { portal } = portalFalso({ total: 3, porPagina: 10 });
    await executarComTratamento(portal, 'canary', deps(dir));
    const st = await status(dir);
    assert.equal(st.result, 'ok');
    assert.equal(st.mode, 'canary');
  });
});

test('status.json declara o modo no sucesso do FULL', async () => {
  await comDiretorio(async (dir) => {
    const { portal } = portalFalso({ total: 3, porPagina: 1 });
    await executarComTratamento(portal, 'full', deps(dir));
    const st = await status(dir);
    assert.equal(st.result, 'ok');
    assert.equal(st.mode, 'full');
  });
});

test('status.json declara o modo no bloqueio e no erro genérico', async () => {
  await comDiretorio(async (dir) => {
    const { portal } = portalFalso({ total: 3, porPagina: 1, bloqueiaEm: 1 });
    await executarComTratamento(portal, 'full', deps(dir));
    assert.equal((await status(dir)).mode, 'full', 'quem escolhe o arquivo pelo modo ficaria cego na falha');
  });
  await comDiretorio(async (dir) => {
    const { portal } = portalFalso({ total: 3, porPagina: 10 });
    const quebra = { ...portal, collectShard: async () => { throw new Error('boom'); } } as Portal;
    const desfecho = await executarComTratamento(quebra, 'canary', deps(dir));
    assert.equal(desfecho.result, 'error');
    assert.equal((await status(dir)).mode, 'canary');
  });
});

test('401 é tratado como sessão caída: flag levantada e código 2', async () => {
  // O conserto de um 401 é re-logar, que é o que a flag comunica. Sem isto ele saía
  // como erro genérico e o console dizia "a coleta falhou" a quem só precisava
  // entrar no portal de novo.
  await comDiretorio(async (dir) => {
    const { portal } = portalFalso({ total: 3, porPagina: 10 });
    const expirado = {
      ...portal,
      collectShard: async () => { throw new AuthExpiredError('401'); },
    } as Portal;
    const desfecho = await executarComTratamento(expirado, 'canary', deps(dir));
    assert.equal(desfecho.result, 'blocked');
    assert.equal(desfecho.exitCode, 2);
    assert.ok(existsSync(join(dir, NEEDS_WARM_FLAG)));
  });
});

test('a flag SOBREVIVE a um 401: o alarme não cai antes de a sessão responder', async () => {
  // Regressão que a primeira versão desta fatia introduziu: remover a flag logo
  // após `captureSessionId` apagava o alarme antes de provar que o token vale.
  await comDiretorio(async (dir) => {
    await writeFile(join(dir, NEEDS_WARM_FLAG), 'ontem', 'utf8');
    const { portal } = portalFalso({ total: 3, porPagina: 10 });
    const expirado = {
      ...portal,
      collectShard: async () => { throw new AuthExpiredError('401'); },
    } as Portal;
    await executarComTratamento(expirado, 'canary', deps(dir));
    assert.ok(existsSync(join(dir, NEEDS_WARM_FLAG)), 'o operador precisa continuar sabendo que tem de re-logar');
  });
});
