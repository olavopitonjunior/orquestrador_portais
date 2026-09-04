import assert from "node:assert/strict";
import { test } from "node:test";

import { cotasDe, cotasDoRegistro } from "../lib/cotas";

// O texto exato que `pg_get_constraintdef` devolve para a restrição do 001_registro.sql.
const DEF =
  "CHECK ((((nivel = 'super_destaque'::text) AND ((posicao_ranking >= 1) AND (posicao_ranking <= 475))) " +
  "OR ((nivel = 'destaque'::text) AND ((posicao_ranking >= 1) AND (posicao_ranking <= 6495)))))";

test("lê as duas cotas do texto da restrição", () => {
  assert.deepEqual(cotasDe(DEF), { superDestaque: 475, destaque: 6495 });
});

test("a cota de destaque não é confundida com a de super_destaque", () => {
  // Ordem invertida na definição: cada nível tem de achar o SEU limite.
  const invertida =
    "CHECK ((((nivel = 'destaque'::text) AND ((posicao_ranking >= 1) AND (posicao_ranking <= 6495))) " +
    "OR ((nivel = 'super_destaque'::text) AND ((posicao_ranking >= 1) AND (posicao_ranking <= 475)))))";
  assert.deepEqual(cotasDe(invertida), { superDestaque: 475, destaque: 6495 });
});

test("metade de uma cota não é cota: falta um nível → null", () => {
  assert.equal(cotasDe("CHECK (((nivel = 'destaque'::text) AND (posicao_ranking <= 6495)))"), null);
  assert.equal(cotasDe(""), null);
});

test("cotasDoRegistro: restrição ausente → null, nunca um número inventado", async () => {
  const vazio = async () => ({ rows: [] });
  assert.equal(await cotasDoRegistro(vazio as never), null);
  const cheio = async () => ({ rows: [{ def: DEF }] });
  assert.deepEqual(await cotasDoRegistro(cheio as never), { superDestaque: 475, destaque: 6495 });
});
