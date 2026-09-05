import assert from "node:assert/strict";
import { test } from "node:test";

import type { SaudeChrome } from "../lib/chrome";
import type { SaudeColeta } from "../lib/coletor";
import { condicoes, veredito } from "../lib/prontidao";

const data = (iso: string) => `@${iso}`;

function saude(p: Partial<SaudeColeta> = {}): SaudeColeta {
  return { estado: "ok", needsWarm: false, coletadoEm: "2026-09-03T21:12:00Z", idadeDias: 0, linhas: 300, ...p };
}
function chrome(p: Partial<SaudeChrome> = {}): SaudeChrome {
  return { noAr: true, abaDoPainel: true, ...p };
}
const por = (cs: ReturnType<typeof condicoes>, t: string) => cs.find((c) => c.titulo === t)!;

test("tudo no ar e nenhum pendente → pronta", () => {
  const cs = condicoes(saude(), chrome(), true, 0, 15, data);
  assert.deepEqual(cs.map((c) => c.nivel), ["ok", "ok", "ok", "ok"]);
  assert.equal(veredito(cs).texto, "pronta");
});

test("só parâmetros pendentes → roda com provisórios, e o texto conta N de total", () => {
  const cs = condicoes(saude(), chrome(), true, 14, 15, data);
  assert.equal(por(cs, "Parâmetros").nivel, "warn");
  assert.match(por(cs, "Parâmetros").texto, /14 de 15/);
  assert.equal(veredito(cs).texto, "roda com provisórios");
});

test("trabalhador parado → não roda, mesmo com tudo o mais ok", () => {
  assert.equal(veredito(condicoes(saude(), chrome(), false, 0, 15, data)).texto, "não roda");
  // leitura do batimento falhou: também não é "ok"
  assert.equal(veredito(condicoes(saude(), chrome(), null, 0, 15, data)).texto, "não roda");
});

test("coleta ausente → sairá degradada (a nota do anúncio não ordena)", () => {
  const cs = condicoes(saude({ estado: "ausente", coletadoEm: null, linhas: null, idadeDias: null }), chrome(), true, 0, 15, data);
  assert.equal(por(cs, "Coleta do portal").nivel, "warn");
  assert.equal(veredito(cs).texto, "sairá degradada");
});

test("leitura que falhou NUNCA vira ok", () => {
  // Chrome respondeu mas não listou abas: não dá para afirmar que o painel está aberto.
  const semAbas = condicoes(saude(), chrome({ abaDoPainel: null }), true, 0, 15, data);
  assert.equal(por(semAbas, "Sessão do Canal Pro").nivel, "bad");
  assert.match(por(semAbas, "Sessão do Canal Pro").texto, /não deixou listar/);
  // Sem leitura nenhuma da coleta ou do Chrome
  const nada = condicoes(null, null, true, 0, 15, data);
  assert.equal(por(nada, "Coleta do portal").nivel, "bad");
  assert.equal(por(nada, "Sessão do Canal Pro").nivel, "bad");
});

test("sessão: Chrome fora → bad; sem aba → warn; NEEDS_WARM → bad; ok nunca afirma autenticação", () => {
  assert.equal(por(condicoes(saude(), chrome({ noAr: false, abaDoPainel: null }), true, 0, 15, data), "Sessão do Canal Pro").nivel, "bad");
  assert.equal(por(condicoes(saude(), chrome({ abaDoPainel: false }), true, 0, 15, data), "Sessão do Canal Pro").nivel, "warn");
  assert.equal(por(condicoes(saude({ needsWarm: true, estado: "blocked" }), chrome(), true, 0, 15, data), "Sessão do Canal Pro").nivel, "bad");
  const ok = por(condicoes(saude(), chrome(), true, 0, 15, data), "Sessão do Canal Pro");
  assert.equal(ok.nivel, "ok");
  assert.match(ok.texto, /Só o canário prova/);
});

test("a coleta ok mostra data, idade e linhas com o formatador injetado", () => {
  const c = por(condicoes(saude(), chrome(), true, 0, 15, data), "Coleta do portal");
  assert.equal(c.texto, "Coletada @2026-09-03T21:12:00Z · 0 dia(s) · 300 anúncios.");
});
