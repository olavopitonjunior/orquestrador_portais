import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import { TETO_BYTES, ZipGrandeDemais, crc32, zipStore } from "../lib/zip";

const enc = new TextEncoder();

test("crc32 bate com os valores de referência", () => {
  assert.equal(crc32(new Uint8Array(0)), 0);
  assert.equal(crc32(enc.encode("abc")), 0x352441c2);
  assert.equal(crc32(enc.encode("123456789")), 0xcbf43926); // vetor de teste clássico
});

test("estrutura: assinaturas, contagem no fim e deslocamentos do diretório central", () => {
  const z = zipStore(
    [
      { nome: "a.csv", dados: enc.encode("x,y\r\n1,2\r\n") },
      { nome: "b.csv", dados: enc.encode("(sem linhas nesta rodada)") },
    ],
    new Date(2026, 8, 3, 21, 12, 0),
  );
  const dv = new DataView(z.buffer, z.byteOffset, z.byteLength);
  assert.equal(dv.getUint32(0, true), 0x04034b50);
  const fim = z.length - 22;
  assert.equal(dv.getUint32(fim, true), 0x06054b50);
  assert.equal(dv.getUint16(fim + 10, true), 2);
  const inicioCentral = dv.getUint32(fim + 16, true);
  assert.equal(dv.getUint32(inicioCentral, true), 0x02014b50);
  // o segundo cabeçalho central aponta para o segundo local: 30 + 5 + 10
  const segundo = inicioCentral + 46 + 5;
  assert.equal(dv.getUint32(segundo + 42, true), 30 + 5 + 10);
  assert.equal(dv.getUint32(30 + 5 + 10, true), 0x04034b50);
});

test("um leitor de verdade abre o zip e recupera cada arquivo byte a byte", (t) => {
  const py = spawnSync("python3", ["-c", "import zipfile"], { encoding: "utf-8" });
  if (py.status !== 0) return t.skip("sem python3 para conferir com zipfile");
  const dir = mkdtempSync(join(tmpdir(), "zip-"));
  const caminho = join(dir, "t.zip");
  const conteudo = "coluna,ação\r\n1,\"vírgula, dentro\"\r\n";
  writeFileSync(caminho, zipStore([{ nome: "ação.csv", dados: enc.encode(conteudo) }], new Date(2026, 8, 3)));
  const r = spawnSync(
    "python3",
    [
      "-c",
      "import sys, zipfile\n" +
        "z = zipfile.ZipFile(sys.argv[1]); assert z.testzip() is None\n" +
        "print(z.namelist()[0]); sys.stdout.write(z.read(z.namelist()[0]).decode('utf-8'))",
      caminho,
    ],
    { encoding: "utf-8" },
  );
  assert.equal(r.status, 0, r.stderr);
  assert.equal(r.stdout, `ação.csv\n${conteudo}`);
});

test("mesmo conteúdo e mesma data → mesmos bytes (o carimbo é parâmetro, não relógio)", () => {
  const e = [{ nome: "a.csv", dados: enc.encode("x\r\n") }];
  const d = new Date(2026, 8, 3);
  assert.deepEqual(zipStore(e, d), zipStore(e, d));
  assert.notDeepEqual(zipStore(e, d), zipStore(e, new Date(2026, 8, 4)));
});

test("acima do teto, falha antes de escrever um byte", () => {
  // Não aloca 256 MiB de verdade: um Uint8Array com `length` forjado basta para a
  // conta do teto, que só lê `dados.length` antes de copiar.
  const gigante = { nome: "g.csv", dados: { length: TETO_BYTES } as unknown as Uint8Array };
  assert.throws(() => zipStore([gigante], new Date(2026, 8, 3)), ZipGrandeDemais);
});
