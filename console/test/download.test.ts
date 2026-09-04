import assert from "node:assert/strict";
import { test } from "node:test";

import { abaDoArquivo, responderDownload, type Leituras } from "../lib/download";

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
