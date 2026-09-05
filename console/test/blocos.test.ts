import assert from "node:assert/strict";
import { test } from "node:test";

import { BLOCOS } from "../lib/blocos";
import { GRUPOS } from "../lib/contrato";

test("todo grupo do contrato tem bloco, e nenhum bloco cita grupo inexistente", () => {
  // Nos DOIS sentidos, como o teste de rótulos do lado Python: um grupo novo no
  // contrato sumiria da tela em silêncio, e o dono declararia menos sem perceber.
  assert.deepEqual(new Set(BLOCOS.flatMap((b) => b.grupos)), new Set(GRUPOS.map((g) => g.id)));
  const citados = BLOCOS.flatMap((b) => b.grupos);
  assert.equal(new Set(citados).size, citados.length, "grupo citado em dois blocos");
});

test("os três blocos têm a ordem da decisão e uma tese cada", () => {
  assert.deepEqual(
    BLOCOS.map((b) => b.titulo),
    ["Quem entra", "Em que ordem", "Quantos"],
  );
  for (const b of BLOCOS) assert.ok(b.tese.length > 20, `${b.id} sem tese`);
});
