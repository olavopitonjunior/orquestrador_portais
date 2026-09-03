import { strict as assert } from "node:assert";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { amarracaoDoCsv, saudeColeta } from "../lib/coletor";

function comOut(arquivos: Record<string, string>): string {
  const dir = mkdtempSync(join(tmpdir(), "console-coletor-"));
  for (const [nome, conteudo] of Object.entries(arquivos)) {
    writeFileSync(join(dir, nome), conteudo, "utf-8");
  }
  process.env.COLETOR_OUT_DIR = dir;
  return dir;
}

test("status ok → estado ok, idade e linhas", async () => {
  comOut({
    "status.json": JSON.stringify({ result: "ok", finishedAt: "2026-09-01T06:00:00Z", rows: 54210 }),
  });
  const s = await saudeColeta();
  assert.equal(s.estado, "ok");
  assert.equal(s.needsWarm, false);
  assert.equal(s.linhas, 54210);
  assert.ok(s.idadeDias !== null && s.idadeDias >= 0);
});

test("NEEDS_WARM.flag → blocked + needsWarm", async () => {
  comOut({
    "status.json": JSON.stringify({ result: "ok", finishedAt: "2026-09-01T06:00:00Z" }),
    "NEEDS_WARM.flag": "2026-09-01T07:00:00Z",
  });
  const s = await saudeColeta();
  assert.equal(s.estado, "blocked");
  assert.equal(s.needsWarm, true);
});

test("status blocked → blocked", async () => {
  comOut({ "status.json": JSON.stringify({ result: "blocked", finishedAt: "2026-09-01T06:00:00Z" }) });
  assert.equal((await saudeColeta()).estado, "blocked");
});

test("sem arquivos → ausente", async () => {
  comOut({});
  const s = await saudeColeta();
  assert.equal(s.estado, "ausente");
  assert.equal(s.coletadoEm, null);
  assert.equal(s.idadeDias, null);
});

test("status.json malformado → corrompido (rodou e não fechou), não lança", async () => {
  comOut({ "status.json": "{ isto não é json" });
  const s = await saudeColeta();
  assert.equal(s.estado, "corrompido"); // ≠ "ausente": o raspador RODOU
  assert.equal(s.coletadoEm, null);
});

test("status error → estado error", async () => {
  comOut({
    "status.json": JSON.stringify({ result: "error", finishedAt: "2026-09-01T06:00:00Z" }),
  });
  assert.equal((await saudeColeta()).estado, "error");
});

test("finishedAt inválido → sem data e sem idade (nunca NaN na UI)", async () => {
  comOut({ "status.json": JSON.stringify({ result: "ok", finishedAt: "não é data", rows: 10 }) });
  const s = await saudeColeta();
  assert.equal(s.estado, "ok");
  assert.equal(s.coletadoEm, null);
  assert.equal(s.idadeDias, null); // não NaN
  assert.equal(s.linhas, 10);
});

function csv(linhas: string[][]): string {
  const cel = (v: string) => '"' + v.replace(/"/g, '""') + '"';
  return linhas.map((l) => l.map(cel).join(",")).join("\r\n") + "\r\n";
}

test("amarração: conta numéricos, vazios e não numéricos, com exemplos", async () => {
  comOut({
    "canalpro.csv": csv([
      ["idPortal", "codigoImovel", "nota"],
      ["1", "123456", "8000"],
      ["2", "IMOVEL-0001", "8000"],
      ["3", "", ""],
      ["4", "7890", ""],
      ["5", "7890", ""], // repetido: exemplo não duplica
    ]),
  });
  const a = await amarracaoDoCsv();
  assert.ok(a);
  assert.equal(a.linhas, 5);
  assert.equal(a.numericos, 3);
  assert.equal(a.vazios, 1);
  assert.equal(a.naoNumericos, 1);
  assert.deepEqual(a.exemplos, ["123456", "IMOVEL-0001", "7890"]);
});

test("amarração: sem CSV → null; CSV só com cabeçalho → zeros", async () => {
  comOut({});
  assert.equal(await amarracaoDoCsv(), null);
  comOut({ "canalpro.csv": csv([["idPortal", "codigoImovel"]]) });
  assert.deepEqual(await amarracaoDoCsv(), {
    linhas: 0, numericos: 0, vazios: 0, naoNumericos: 0, exemplos: [],
  });
});

test("amarração: aspas escapadas e vírgula dentro da célula não deslocam a coluna", async () => {
  comOut({
    "canalpro.csv": csv([
      ["idPortal", "notaNome", "codigoImovel"],
      ["1", 'x "y", z', "42"],
    ]),
  });
  const a = await amarracaoDoCsv();
  assert.ok(a);
  assert.equal(a.numericos, 1);
  assert.deepEqual(a.exemplos, ["42"]);
});

test("amarração: sem a coluna codigoImovel, tudo conta como não numérico", async () => {
  comOut({ "canalpro.csv": csv([["idPortal"], ["1"], ["2"]]) });
  const a = await amarracaoDoCsv();
  assert.ok(a);
  assert.equal(a.linhas, 2);
  assert.equal(a.naoNumericos, 2);
});
