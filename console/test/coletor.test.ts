import { strict as assert } from "node:assert";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { saudeColeta } from "../lib/coletor";

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
