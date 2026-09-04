import assert from "node:assert/strict";
import { test } from "node:test";

import { abaDoArquivo, responderDownload, type Leituras } from "../lib/download";
import { TETO_BYTES } from "../lib/zip";

const enc = new TextEncoder();
const SENTINELA = "(sem linhas nesta rodada)\r\n";

function leituras(p: Partial<Leituras> = {}): Leituras {
  return {
    dataDaRodada: async (id) => (id === 15474 ? "2026-09-03" : null),
    bytesDaAba: async (data, aba) => {
      if (data !== "2026-09-03") return null;
      if (aba === "super_destaque") return enc.encode("posicao,imovel_id\r\n1,\"a, b\"\r\n");
      if (aba === "relaxamento") return enc.encode(SENTINELA);
      if (aba === "destaque") return new Uint8Array(0);
      return null;
    },
    ...p,
  };
}

test("abaDoArquivo: só `<aba>.csv` exato, com a aba na lista fechada", () => {
  assert.equal(abaDoArquivo("super_destaque.csv"), "super_destaque");
  for (const ruim of [
    "Super_destaque.csv",
    "super_destaque.csv.csv",
    "super_destaque.CSV",
    "../super_destaque.csv",
    "x/super_destaque.csv",
    "outra.csv",
    "super_destaque",
    "",
  ])
    assert.equal(abaDoArquivo(ruim), null, ruim);
});

test("sucesso: bytes crus, anexo com o nome da rodada e da aba, sem cache", async () => {
  const r = await responderDownload("15474", "super_destaque.csv", leituras());
  assert.equal(r.status, 200);
  assert.equal(r.headers.get("content-type"), "text/csv; charset=utf-8");
  assert.equal(r.headers.get("content-disposition"), 'attachment; filename="rodada-15474-super_destaque.csv"');
  assert.equal(r.headers.get("cache-control"), "no-store");
  assert.equal(r.headers.get("x-content-type-options"), "nosniff");
  assert.equal(await r.text(), 'posicao,imovel_id\r\n1,"a, b"\r\n');
});

test("a sentinela de aba vazia é conteúdo legítimo: sai byte a byte", async () => {
  const r = await responderDownload("15474", "relaxamento.csv", leituras());
  assert.equal(r.status, 200);
  assert.equal(await r.text(), SENTINELA);
});

test("arquivo de 0 bytes é 404 com a razão — não um CSV vazio", async () => {
  const r = await responderDownload("15474", "destaque.csv", leituras());
  assert.equal(r.status, 404);
  assert.match(await r.text(), /0 bytes/);
  assert.equal(r.headers.get("cache-control"), "no-store");
});

test("id não numérico, arquivo fora da lista, aba ausente, rodada sem data → 404 em texto", async () => {
  const casos: [string, string, RegExp][] = [
    ["abc", "super_destaque.csv", /rodada inválida/],
    ["15474", "outra.csv", /arquivo desconhecido/],
    ["15474", "excluidos_por_regra.csv", /sem excluidos_por_regra\.csv em disco para 2026-09-03/],
    ["9", "super_destaque.csv", /não gravou data de referência/],
  ];
  for (const [id, arq, re] of casos) {
    const r = await responderDownload(id, arq, leituras());
    assert.equal(r.status, 404, `${id}/${arq}`);
    assert.equal(r.headers.get("content-type"), "text/plain; charset=utf-8");
    assert.match(await r.text(), re);
  }
});

test("banco fora não vira 'rodada sem data': 503 genérico e o erro vai para o log", async () => {
  const registrados: string[] = [];
  const r = await responderDownload("15474", "super_destaque.csv", leituras({
    dataDaRodada: async () => {
      throw new Error("ECONNREFUSED 127.0.0.1:5432");
    },
    registrar: (m) => registrados.push(m),
  }));
  assert.equal(r.status, 503);
  const corpo = await r.text();
  assert.doesNotMatch(corpo, /5432|ECONNREFUSED/);
  assert.match(corpo, /log do servidor/);
  assert.equal(registrados.length, 1);
});

test("a resposta nunca cita caminho do servidor", async () => {
  for (const [id, arq] of [["15474", "excluidos_por_regra.csv"], ["15474", "destaque.csv"]]) {
    const r = await responderDownload(id, arq, leituras());
    assert.doesNotMatch(await r.text(), /\/Users|\/home|saida\/sexta/);
  }
});

test("todas.zip: empacota só as abas com conteúdo, com nome carimbado pela data", async () => {
  const r = await responderDownload("15474", "todas.zip", leituras());
  assert.equal(r.status, 200);
  assert.equal(r.headers.get("content-type"), "application/zip");
  assert.equal(r.headers.get("content-disposition"), 'attachment; filename="rodada-15474-planilha-2026-09-03.zip"');
  const z = new Uint8Array(await r.arrayBuffer());
  const dv = new DataView(z.buffer);
  assert.equal(dv.getUint32(0, true), 0x04034b50);
  // duas entradas: super_destaque e relaxamento (destaque tem 0 bytes; as outras faltam)
  assert.equal(dv.getUint16(z.length - 22 + 10, true), 2);
  const texto = new TextDecoder().decode(z);
  assert.match(texto, /super_destaque\.csv/);
  assert.match(texto, /relaxamento\.csv/);
  // "destaque.csv" só aparece como sufixo de "super_destaque.csv"
  assert.doesNotMatch(texto, /(^|[^_])destaque\.csv/);
});

test("todas.zip com nenhuma aba em disco → 404, não um zip vazio", async () => {
  const r = await responderDownload("15474", "todas.zip", leituras({ bytesDaAba: async () => null }));
  assert.equal(r.status, 404);
  assert.match(await r.text(), /sem planilha em disco/);
});

test("todas.zip é determinístico para o mesmo conteúdo", async () => {
  const a = new Uint8Array(await (await responderDownload("15474", "todas.zip", leituras())).arrayBuffer());
  const b = new Uint8Array(await (await responderDownload("15474", "todas.zip", leituras())).arrayBuffer());
  assert.deepEqual(a, b);
});

test("o 404 de arquivo desconhecido cita todas.zip", async () => {
  const r = await responderDownload("15474", "outra.csv", leituras());
  assert.match(await r.text(), /todas\.zip/);
});

test("todas.zip acima do teto → 413 com o erro no log e sem detalhe no corpo", async () => {
  const registrados: string[] = [];
  // `length` forjado: a conta do teto lê só `dados.length`, e falha antes de copiar.
  const gigante = { length: TETO_BYTES } as unknown as Uint8Array;
  const r = await responderDownload("15474", "todas.zip", leituras({
    bytesDaAba: async (_d, aba) => (aba === "super_destaque" ? gigante : null),
    registrar: (m) => registrados.push(m),
  }));
  assert.equal(r.status, 413);
  assert.equal(r.headers.get("cache-control"), "no-store");
  const corpo = await r.text();
  assert.match(corpo, /aba por aba/);
  assert.doesNotMatch(corpo, /\/Users|TETO|bytes/);
  assert.equal(registrados.length, 1);
  assert.match(registrados[0], /acima do teto/);
});
