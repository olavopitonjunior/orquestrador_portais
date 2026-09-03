import { strict as assert } from "node:assert";
import { test } from "node:test";
import { saudeChrome } from "../lib/chrome";

function fetchFalso(respostas: Record<string, unknown | Error>): typeof fetch {
  return (async (entrada: string | URL | Request) => {
    const url = String(entrada);
    const chave = Object.keys(respostas).find((k) => url.endsWith(k));
    if (chave === undefined) throw new Error("conexão recusada");
    const r = respostas[chave];
    if (r instanceof Error) throw r;
    return { ok: true, json: async () => r } as Response;
  }) as typeof fetch;
}

test("porta fechada → fora do ar, aba desconhecida", async () => {
  const s = await saudeChrome(fetchFalso({}));
  assert.deepEqual(s, { noAr: false, abaDoPainel: null });
});

test("no ar com aba do painel → os dois booleanos, e nenhuma URL sai", async () => {
  const s = await saudeChrome(
    fetchFalso({
      "/json/version": { Browser: "Chrome/128" },
      "/json/list": [
        { url: "https://canal-pro.grupozap.com/anuncios?session=SEGREDO" },
        { url: "https://outro.exemplo/" },
      ],
    }),
  );
  assert.deepEqual(s, { noAr: true, abaDoPainel: true });
  assert.ok(!JSON.stringify(s).includes("SEGREDO"));
});

test("no ar sem aba do painel → abaDoPainel false", async () => {
  const s = await saudeChrome(
    fetchFalso({ "/json/version": {}, "/json/list": [{ url: "https://outro.exemplo/" }] }),
  );
  assert.deepEqual(s, { noAr: true, abaDoPainel: false });
});

test("subdomínio parecido NÃO conta como painel", async () => {
  const s = await saudeChrome(
    fetchFalso({
      "/json/version": {},
      "/json/list": [{ url: "https://canal-pro.grupozap.com.evil.example/" }],
    }),
  );
  assert.equal(s.abaDoPainel, false);
});

test("/json/list quebrado → no ar, aba desconhecida (não false)", async () => {
  const s = await saudeChrome(
    fetchFalso({ "/json/version": {}, "/json/list": new Error("timeout") }),
  );
  assert.deepEqual(s, { noAr: true, abaDoPainel: null });
  const s2 = await saudeChrome(fetchFalso({ "/json/version": {}, "/json/list": { nao: "lista" } }));
  assert.deepEqual(s2, { noAr: true, abaDoPainel: null });
});
