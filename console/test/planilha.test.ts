import { strict as assert } from "node:assert";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import {
  SENTINELA_VAZIA,
  arquivoDaAba,
  datasComPlanilha,
  lerPlanilha,
  parsearCsv,
  tabelaDe,
} from "../lib/planilha";
import { limitacoesDe } from "../lib/registro";

test("parseia o dialeto do csv do Python: aspas mínimas, escape, vírgula e quebra dentro da célula", () => {
  const texto = 'a,b,c\r\n1,"x, y","diz ""oi""\r\nsegunda linha"\r\n2,,\r\n';
  assert.deepEqual(parsearCsv(texto), [
    ["a", "b", "c"],
    ["1", "x, y", 'diz "oi"\r\nsegunda linha'],
    ["2", "", ""],
  ]);
});

test("última linha sem terminador ainda conta", () => {
  assert.deepEqual(parsearCsv("a,b\n1,2"), [["a", "b"], ["1", "2"]]);
});

test("a sentinela sem cabeçalho vira tabela VAZIA, não erro nem linha", () => {
  const t = tabelaDe(SENTINELA_VAZIA + "\n");
  assert.deepEqual(t, { colunas: [], linhas: [], vazia: true, semConteudo: false });
});

test("arquivo de 0 bytes é SEM CONTEÚDO, não 'sem linhas'", () => {
  assert.deepEqual(tabelaDe(""), { colunas: [], linhas: [], vazia: false, semConteudo: true });
});

test("aspa no meio de célula não quotada é texto, como no csv do Python", () => {
  assert.deepEqual(parsearCsv('x"y,z\r\n1,2\r\n'), [["x\"y", "z"], ["1", "2"]]);
  assert.deepEqual(parsearCsv("a\rb,c\n"), [["a"], ["b", "c"]]); // \r solto termina a linha
});

test("limitacoesDe divide por LINHA; '; ' dentro da limitação não parte nada", () => {
  const m = "gestor ativo = X (D-015): cobertura de 45,9% da base; imóveis fora ficam de fora\nHISTÓRICO vazio";
  assert.deepEqual(limitacoesDe(m), [
    "gestor ativo = X (D-015): cobertura de 45,9% da base; imóveis fora ficam de fora",
    "HISTÓRICO vazio",
  ]);
  // rodada antiga, juntada por "; " — bloco único, não contagem errada
  assert.equal(limitacoesDe("a; b; c").length, 1);
  assert.deepEqual(limitacoesDe(null), []);
});

test("cabeçalho vira colunas e o resto vira linhas", () => {
  const t = tabelaDe("posicao,imovel_id\r\n1,101\r\n2,202\r\n");
  assert.deepEqual(t.colunas, ["posicao", "imovel_id"]);
  assert.equal(t.linhas.length, 2);
  assert.equal(t.vazia, false);
});

function saida(datas: Record<string, Record<string, string>>): string {
  const raiz = mkdtempSync(join(tmpdir(), "console-planilha-"));
  for (const [data, arquivos] of Object.entries(datas)) {
    mkdirSync(join(raiz, data));
    for (const [nome, conteudo] of Object.entries(arquivos)) writeFileSync(join(raiz, data, nome), conteudo);
  }
  process.env.SAIDA_SEXTA_DIR = raiz;
  return raiz;
}

test("lê as cinco abas de uma data e lista as ausentes", async () => {
  saida({
    "2026-09-05": {
      "super_destaque.csv": "posicao,imovel_id\r\n1,101\r\n",
      "destaque.csv": SENTINELA_VAZIA + "\n",
      "relaxamento.csv": "ordem,regra_cedida\r\n",
    },
  });
  const p = await lerPlanilha("2026-09-05");
  assert.ok(p);
  assert.equal(p.abas.super_destaque?.linhas.length, 1);
  assert.equal(p.abas.destaque?.vazia, true);
  assert.equal(p.abas.relaxamento?.semConteudo, false);
  assert.deepEqual(p.ausentes, ["excluidos_por_regra", "parametros_e_limitacoes"]);
});

test("datas mais recentes primeiro; nome fora do padrão é ignorado e nunca vira caminho", async () => {
  saida({ "2026-09-01": {}, "2026-09-05": {}, "lixo": {} });
  assert.deepEqual(await datasComPlanilha(), ["2026-09-05", "2026-09-01"]);
  assert.equal(await lerPlanilha("../../etc"), null);
  assert.equal(await lerPlanilha("2026-09-09"), null);
});

// --- arquivoDaAba: os bytes crus, com as mesmas guardas de lerPlanilha ---------------

function raizComPlanilha(): string {
  const raiz = mkdtempSync(join(tmpdir(), "saida-"));
  mkdirSync(join(raiz, "2026-09-03"));
  writeFileSync(join(raiz, "2026-09-03", "super_destaque.csv"), "imovel_id,nota\r\n1,\"a, b\"\r\n");
  writeFileSync(join(raiz, "2026-09-03", "destaque.csv"), "");
  mkdirSync(join(raiz, "fora"));
  writeFileSync(join(raiz, "fora", "super_destaque.csv"), "não deve ser alcançado");
  return raiz;
}

test("arquivoDaAba devolve os bytes como estão em disco, sem reescrever", async () => {
  process.env.SAIDA_SEXTA_DIR = raizComPlanilha();
  const b = await arquivoDaAba("2026-09-03", "super_destaque");
  assert.ok(b);
  assert.equal(b.toString("utf-8"), "imovel_id,nota\r\n1,\"a, b\"\r\n");
});

test("arquivo de 0 bytes volta como Buffer vazio, não como null — o chamador distingue", async () => {
  process.env.SAIDA_SEXTA_DIR = raizComPlanilha();
  const b = await arquivoDaAba("2026-09-03", "destaque");
  assert.ok(b);
  assert.equal(b.length, 0);
});

test("arquivoDaAba: data fora do formato, aba fora da lista e arquivo ausente → null", async () => {
  process.env.SAIDA_SEXTA_DIR = raizComPlanilha();
  assert.equal(await arquivoDaAba("fora", "super_destaque"), null);
  assert.equal(await arquivoDaAba("../2026-09-03", "super_destaque"), null);
  assert.equal(await arquivoDaAba("2026-09-03", "../fora/super_destaque"), null);
  assert.equal(await arquivoDaAba("2026-09-03", "outra_aba"), null);
  assert.equal(await arquivoDaAba("2026-09-03", "relaxamento"), null);
  assert.equal(await arquivoDaAba("2026-09-04", "super_destaque"), null);
});
