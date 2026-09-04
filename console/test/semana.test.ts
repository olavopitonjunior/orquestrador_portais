import assert from "node:assert/strict";
import { test } from "node:test";

import { cadencia, diaCurto, quando } from "../lib/semana";

const ymd = (d: Date) => `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;

test("quinta 3/9/2026 → decisão sexta 4, acompanhamento segunda 7", () => {
  const c = cadencia(new Date(2026, 8, 3, 15, 30));
  assert.equal(ymd(c.decisao), "2026-9-4");
  assert.equal(ymd(c.acompanhamento), "2026-9-7");
  assert.equal(c.diasAteDecisao, 1);
});

test("sexta é hoje, não a próxima", () => {
  const c = cadencia(new Date(2026, 8, 4, 23, 59));
  assert.equal(ymd(c.decisao), "2026-9-4");
  assert.equal(c.diasAteDecisao, 0);
});

test("sábado pula para a sexta seguinte", () => {
  const c = cadencia(new Date(2026, 8, 5));
  assert.equal(ymd(c.decisao), "2026-9-11");
  assert.equal(c.diasAteDecisao, 6);
});

test("virada de mês e de ano", () => {
  assert.equal(ymd(cadencia(new Date(2026, 11, 30)).decisao), "2027-1-1");
  assert.equal(ymd(cadencia(new Date(2026, 11, 30)).acompanhamento), "2027-1-4");
});

test("rótulos", () => {
  assert.equal(diaCurto(new Date(2026, 8, 4)), "Sex 4");
  assert.equal(quando(0), "hoje");
  assert.equal(quando(1), "amanhã");
  assert.equal(quando(6), "em 6 dias");
});
