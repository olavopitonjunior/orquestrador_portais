import assert from "node:assert/strict";
import { test } from "node:test";

import { desfechoDe } from "../lib/desfecho";

test("sem código não há desfecho — o trabalho ainda está em curso", () => {
  assert.equal(desfechoDe(null), null);
});

test("os seis códigos da rodada são traduzidos", () => {
  for (const c of [0, 1, 2, 3, 4, 5, 6]) {
    const d = desfechoDe(c);
    assert.ok(d && d.titulo && d.explicacao, `código ${c} sem tradução`);
  }
});

test("os DOIS abortos são distinguidos, e só um é grave", () => {
  // A distinção é a razão de o código 6 existir separado do 4: estoque vazio é ausência
  // de insumo; veto do crivo é violação de invariante. Sob um código só, a violação
  // chegaria ao monitoramento com a mesma cara de "não havia imóvel", e ninguém olharia.
  const semEstoque = desfechoDe(4)!;
  const veto = desfechoDe(6)!;
  assert.equal(semEstoque.grave, false);
  assert.equal(veto.grave, true);
  assert.notEqual(semEstoque.titulo, veto.titulo);
});

test("falha de escrita e falha de fonte não se confundem", () => {
  // Na de escrita houve decisão e ela se perdeu na saída; na de fonte não houve
  // decisão. Ações opostas de quem opera.
  assert.match(desfechoDe(1)!.titulo, /ESCREVER/);
  assert.match(desfechoDe(3)!.titulo, /FONTE/);
});

test("código desconhecido é traduzido como GRAVE, não ignorado", () => {
  // Um código novo que o console não conhece é motivo para olhar, não para assumir bem.
  const d = desfechoDe(99)!;
  assert.equal(d.grave, true);
  assert.match(d.titulo, /99/);
});
