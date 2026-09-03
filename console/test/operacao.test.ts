// A camada de escrita do console, com o executor injetado — sem banco.
//
// O que se prova aqui é o CONTRATO com o Postgres: qual SQL sai, com quais parâmetros,
// e como a violação de unicidade vira erro que a tela sabe explicar. O que o banco faz
// com esse SQL é provado do lado Python, contra um Postgres real (`tests/test_operacao.py`).

import assert from "node:assert/strict";
import { test } from "node:test";

import {
  ETAPAS,
  TrabalhoEmVoo,
  criarTrabalho,
  etapasConcluidas,
  eventosDoTrabalho,
  lerTrabalho,
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

test("lerTrabalho devolve null quando não existe", async () => {
  const { exec } = espiao([]);
  assert.equal(await lerTrabalho(1, exec), null);
});

test("eventosDoTrabalho corta o COMEÇO, não o fim", async () => {
  // O desfecho está no fim. Cortar por `LIMIT` sobre a ordem crescente perderia
  // justamente a linha que diz como a rodada terminou.
  const { exec, chamadas } = espiao([]);
  await eventosDoTrabalho(7, 50, exec);
  assert.match(chamadas[0].sql, /ORDER BY id DESC LIMIT \$2/);
  assert.match(chamadas[0].sql, /\) ultimos ORDER BY id/);
  assert.deepEqual(chamadas[0].params, [7, 50]);
});

test("as etapas de apresentação são sete e começam pela coleta", () => {
  // Ordem de LEITURA, não topologia: `analista_perfil` e `coletor_externo` correm em
  // paralelo, e listá-los em sequência é escolha de apresentação. O `registrar` fica
  // de fora porque é sink, não etapa da decisão.
  assert.equal(ETAPAS.length, 7);
  assert.equal(ETAPAS[0], "coletor_interno");
  assert.equal(ETAPAS[ETAPAS.length - 1], "finalizar");
  assert.ok(!ETAPAS.includes("registrar" as never));
});

test("a contagem de etapas ignora nós que não são etapa da decisão", () => {
  // A rodada também emite `registrar`, que é sink. Contá-lo produzia "8 de 7
  // anunciadas" na tela — número que não quer dizer nada, e que nenhum teste via
  // porque a contagem morava no componente.
  const anunciados = new Set([...ETAPAS, "registrar"]);
  const contadas = ETAPAS.filter((e) => anunciados.has(e));
  assert.equal(contadas.length, ETAPAS.length);
  assert.ok(contadas.length < anunciados.size, "a fixture precisa ter um nó a mais");
});

test("as etapas vêm de consulta PRÓPRIA, imune ao tamanho do log", async () => {
  // Derivar do log estaria errado: `eventosDoTrabalho` corta em 300 linhas pelo COMEÇO
  // — certo para o log, onde o desfecho está no fim; errado para a contagem. Numa
  // rodada que imprime muito, as primeiras etapas sairiam da janela e a lista apagaria
  // PARA TRÁS. Em modo seco a rodada fala pouco e isso nunca apareceria.
  const { exec, chamadas } = espiao([{ no_grafo: "decisor" }]);
  assert.deepEqual(await etapasConcluidas(7, exec), ["decisor"]);
  assert.match(chamadas[0].sql, /SELECT DISTINCT no_grafo/);
  assert.doesNotMatch(chamadas[0].sql, /LIMIT/);
});
