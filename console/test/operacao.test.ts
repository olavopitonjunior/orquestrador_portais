// A camada de escrita do console, com o executor injetado — sem banco.
//
// O que se prova aqui é o CONTRATO com o Postgres: qual SQL sai, com quais parâmetros,
// e como a violação de unicidade vira erro que a tela sabe explicar. O que o banco faz
// com esse SQL é provado do lado Python, contra um Postgres real (`tests/test_operacao.py`).

import assert from "node:assert/strict";
import { test } from "node:test";

import {
  TrabalhoEmVoo,
  criarTrabalho,
  guardarParametros,
  listarTrabalhos,
  trabalhadorVivo,
  ultimosParametros,
  type Consulta,
} from "../lib/operacao";

function espiao(resposta: unknown[] = [{ id: "7" }]) {
  const chamadas: { sql: string; params?: unknown[] }[] = [];
  const exec = (async (sql: string, params?: unknown[]) => {
    chamadas.push({ sql, params });
    return { rows: resposta };
  }) as Consulta;
  return { exec, chamadas };
}

test("guardarParametros insere o TOML verbatim e devolve o id", async () => {
  const { exec, chamadas } = espiao();
  const id = await guardarParametros("razao = 0.5\n", "olavo", exec);
  assert.equal(id, 7);
  assert.match(chamadas[0].sql, /INSERT INTO operacao\.parametros_declarados/);
  assert.deepEqual(chamadas[0].params, ["razao = 0.5\n", "olavo"]);
});

test("guardarParametros NÃO escreve em registro.alteracao_parametro", () => {
  // Aquela tabela é a trilha de parâmetro ADOTADO; o que sai do formulário é
  // PROVISÓRIO. Misturar destruiria a distinção que o projeto inteiro sustenta.
  const { exec, chamadas } = espiao();
  return guardarParametros("x = 1\n", null, exec).then(() => {
    assert.doesNotMatch(chamadas[0].sql, /alteracao_parametro/);
    assert.doesNotMatch(chamadas[0].sql, /\bregistro\./);
  });
});

test("criarTrabalho enfileira com os argumentos em JSON", async () => {
  const { exec, chamadas } = espiao();
  const id = await criarTrabalho("sexta", { parametros: "/tmp/p.toml" }, "olavo", exec);
  assert.equal(id, 7);
  assert.match(chamadas[0].sql, /INSERT INTO operacao\.trabalho/);
  assert.deepEqual(chamadas[0].params, ["sexta", "olavo", '{"parametros":"/tmp/p.toml"}']);
});

test("violação de unicidade vira TrabalhoEmVoo, com a razão escrita", async () => {
  // A tela precisa dizer "já está rodando" em vez de mostrar um erro de banco. E a
  // mensagem carrega o PORQUÊ: sem chave natural de dedup, o segundo pedido criaria
  // uma rodada duplicada e indistinguível.
  const exec = (async () => {
    throw Object.assign(new Error("duplicate key"), { code: "23505" });
  }) as Consulta;
  await assert.rejects(() => criarTrabalho("sexta", {}, null, exec), TrabalhoEmVoo);
  await assert.rejects(() => criarTrabalho("sexta", {}, null, exec), /rodada duplicada/);
});

test("outro erro de banco NÃO vira TrabalhoEmVoo", async () => {
  // Engolir uma queda de conexão como "já está rodando" mandaria o dono esperar por
  // um trabalho que não existe.
  const exec = (async () => {
    throw Object.assign(new Error("connection refused"), { code: "08006" });
  }) as Consulta;
  await assert.rejects(() => criarTrabalho("sexta", {}, null, exec), /connection refused/);
});

test("ultimosParametros devolve null quando não há nenhum", async () => {
  const { exec } = espiao([]);
  assert.equal(await ultimosParametros(exec), null);
});

test("ultimosParametros normaliza id e data", async () => {
  const { exec } = espiao([
    { id: "12", toml: "x = 1\n", criado_em: new Date("2026-09-04T10:00:00Z"), por: "olavo" },
  ]);
  const p = await ultimosParametros(exec);
  assert.equal(p?.id, 12);
  assert.equal(p?.criado_em, "2026-09-04T10:00:00.000Z");
});

test("listarTrabalhos normaliza o bigint que o driver devolve como string", async () => {
  const { exec } = espiao([
    {
      id: "9",
      tipo: "sexta",
      estado: "ok",
      pedido_em: new Date("2026-09-04T10:00:00Z"),
      pedido_por: "olavo",
      codigo_saida: 0,
      rodada_id: null,
    },
  ]);
  const [t] = await listarTrabalhos(20, exec);
  assert.equal(t.id, 9);
  assert.equal(typeof t.id, "number");
});

test("trabalhadorVivo é falso quando não há batimento", async () => {
  const { exec } = espiao([]);
  assert.equal(await trabalhadorVivo(30, exec), false);
});

test("trabalhadorVivo repassa a janela em segundos", async () => {
  const { exec, chamadas } = espiao([{ vivo: true }]);
  assert.equal(await trabalhadorVivo(45, exec), true);
  assert.deepEqual(chamadas[0].params, [45]);
});
