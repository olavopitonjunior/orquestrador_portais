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

test("status error com `retryable` → repetível: o soluço do portal se distingue da falha", async () => {
  // O caso de 06/09: HTTP 200 e o gateway dizendo no corpo que não alcançava a
  // própria API. Dez segundos de soluço mataram treze minutos de coleta.
  comOut({
    "status.json": JSON.stringify({
      result: "error",
      finishedAt: "2026-09-06T15:19:00Z",
      message: "Canal Pro não alcançou a API: Can not reach the API",
      retryable: true,
    }),
  });
  const s = await saudeColeta();
  // O ESTADO não muda — é contrato de três componentes, e mexer nele é o defeito
  // que esta série já registrou três vezes. O sinal é aditivo.
  assert.equal(s.estado, "error");
  assert.equal(s.repetivel, true);
});

test("status error sem `retryable` → não repetível: sem o campo, nada se afirma", async () => {
  comOut({
    "status.json": JSON.stringify({ result: "error", finishedAt: "2026-09-06T15:19:00Z" }),
  });
  const s = await saudeColeta();
  assert.equal(s.estado, "error");
  assert.equal(s.repetivel, false, "todo status anterior a 06/09 não tem o campo");
});

test("`retryable` num status que não é erro é ignorado", async () => {
  // Um `ok` ou um bloqueio nunca é "rode de novo": o conserto do bloqueio é
  // re-logar, e oferecer as duas ações ao mesmo tempo é ruído no único alarme
  // que o operador não pode aprender a ignorar.
  comOut({
    "status.json": JSON.stringify({ result: "blocked", finishedAt: "2026-09-06T15:19:00Z", retryable: true }),
  });
  const s = await saudeColeta();
  assert.equal(s.estado, "blocked");
  assert.equal(s.repetivel, false);
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
    "canalpro.canario.csv": csv([
      ["idPortal", "codigoImovel", "nota"],
      ["1", "431347A", "8000"], // o formato real: {Id}{letra}
      ["2", "IMOVEL-0001", "8000"],
      ["3", "", ""],
      ["4", "7890", ""],
      ["5", "7890", ""], // repetido: exemplo não duplica
      ["6", "431347a", ""], // minúscula: fora do formato, como na rodada
    ]),
  });
  const a = await amarracaoDoCsv();
  assert.ok(a);
  assert.equal(a.linhas, 6);
  assert.equal(a.noFormato, 3);
  assert.equal(a.vazios, 1);
  assert.equal(a.foraDoFormato, 2);
  assert.deepEqual(a.exemplos, ["431347A", "IMOVEL-0001", "7890"]);
});

test("amarração: sem CSV → null; CSV só com cabeçalho → zeros", async () => {
  comOut({});
  assert.equal(await amarracaoDoCsv(), null);
  comOut({ "canalpro.canario.csv": csv([["idPortal", "codigoImovel"]]) });
  assert.deepEqual(await amarracaoDoCsv(), {
    linhas: 0, noFormato: 0, vazios: 0, foraDoFormato: 0, exemplos: [],
  });
});

test("amarração: aspas escapadas e vírgula dentro da célula não deslocam a coluna", async () => {
  comOut({
    "canalpro.canario.csv": csv([
      ["idPortal", "notaNome", "codigoImovel"],
      ["1", 'x "y", z', "42"],
    ]),
  });
  const a = await amarracaoDoCsv();
  assert.ok(a);
  assert.equal(a.noFormato, 1);
  assert.deepEqual(a.exemplos, ["42"]);
});

test("amarração: sem a coluna codigoImovel, tudo conta como não numérico", async () => {
  comOut({ "canalpro.canario.csv": csv([["idPortal"], ["1"], ["2"]]) });
  const a = await amarracaoDoCsv();
  assert.ok(a);
  assert.equal(a.linhas, 2);
  assert.equal(a.foraDoFormato, 2);
});

test("amarracaoDoCsv NÃO cai para o arquivo da coleta completa", async () => {
  // A sonda mede o último canário. Se ela lesse `canalpro.csv`, mediria o estoque
  // e chamaria de sonda — a contaminação por outro nome.
  comOut({ "canalpro.csv": csv([["idPortal", "codigoImovel"], ["1", "431347A"]]) });
  assert.equal(await amarracaoDoCsv(), null);
});
