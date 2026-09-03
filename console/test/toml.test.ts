// O validador do formulário adianta a recusa que o Python faria — e não pode divergir
// dela. Estes testes derivam TUDO do contrato: uma lista paralela aqui seria a mesma
// duplicação que o contrato existe para evitar.

import assert from "node:assert/strict";
import { test } from "node:test";

import { CAMPOS, POR_CAMINHO, REGRAS, campoAtivo } from "../lib/contrato";
import { paraToml, validar } from "../lib/toml";

/** Um preenchimento válido, montado A PARTIR DO CONTRATO. */
function preenchimentoValido(forma = "visualizacoes"): Map<string, string> {
  const v = new Map<string, string>([["externo.desempenho.forma", forma]]);
  for (const c of CAMPOS) {
    if (!c.obrigatorio || v.has(c.caminho)) continue;
    if (!campoAtivo(c, v)) continue;
    if (c.tipo === "escolha") {
      v.set(c.caminho, (c.escolhas ?? [])[0]);
    } else if (c.caminho.startsWith("pesos.")) {
      v.set(c.caminho, "25"); // os quatro somam 100
    } else if (c.tipo === "inteiro") {
      v.set(c.caminho, String(c.minimo ?? 1));
    } else {
      const min = c.minimo ?? 0;
      const max = c.maximo ?? min + 2;
      v.set(c.caminho, String((min + max) / 2));
    }
  }
  // Campos condicionais dependem da forma escolhida — segunda passada.
  for (const c of CAMPOS) {
    if (c.obrigatorio && campoAtivo(c, v) && !v.has(c.caminho)) {
      v.set(c.caminho, c.tipo === "escolha" ? (c.escolhas ?? [])[0] : "1");
    }
  }
  return v;
}

test("há contrato a conferir", () => {
  assert.ok(CAMPOS.length >= 20, `contrato encolheu: ${CAMPOS.length}`);
  assert.ok(REGRAS.length >= 4, `regras encolheram: ${REGRAS.length}`);
});

test("um preenchimento válido não produz problema nenhum", () => {
  for (const forma of POR_CAMINHO.get("externo.desempenho.forma")!.escolhas ?? []) {
    assert.deepEqual(validar(preenchimentoValido(forma)), [], `forma ${forma}`);
  }
});

test("campo obrigatório vazio é cobrado, e só ele", () => {
  const v = preenchimentoValido();
  v.delete("intensidades.sem_lead_180d");
  const p = validar(v);
  assert.equal(p.length, 1);
  assert.equal(p[0].caminho, "intensidades.sem_lead_180d");
});

test("espaço em branco conta como vazio", () => {
  // Sem isto, `Number(" ")` vira 0 — um valor que ninguém escolheu, entrando numa
  // rodada que decide 6.970 posições pagas.
  const v = preenchimentoValido();
  v.set("intensidades.sem_lead_180d", "   ");
  assert.equal(validar(v).length, 1);
});

test("inteiro com casa decimal é RECUSADO", () => {
  // A distinção que o JavaScript não faz e o validador Python faz. Sem ela, um
  // formulário perfeitamente preenchido produz um TOML que a rodada rejeita.
  const v = preenchimentoValido();
  v.set("externo.idade_maxima_dias", "8.5");
  const p = validar(v);
  assert.equal(p.length, 1);
  assert.match(p[0].mensagem, /inteiro/);
});

test("o limite ABERTO recusa o próprio limite; o fechado aceita", () => {
  const v = preenchimentoValido();
  v.set("semelhanca.decaimento", "0"); // (0, 1] — zero é fora
  assert.equal(validar(v).length, 1);
  v.set("semelhanca.decaimento", "0.5");
  v.set("semelhanca.desconto_fragil", "0"); // [0, 1] — zero é dentro
  assert.deepEqual(validar(v), []);
});

test("valor acima do teto é recusado", () => {
  const v = preenchimentoValido();
  v.set("externo.limiar_amarracao", "1.5");
  assert.equal(validar(v).length, 1);
});

test("escolha fora da lista é recusada", () => {
  const v = preenchimentoValido();
  v.set("decaimento_janela.forma", "sem_decaimento");
  assert.equal(validar(v).length, 1);
});

test("os pesos precisam somar exatamente 100, por nível", () => {
  const v = preenchimentoValido();
  v.set("pesos.super_destaque.semelhanca_perfil", "26");
  const p = validar(v);
  assert.equal(p.length, 1);
  assert.match(p[0].mensagem, /Somam 101/);
});

test("a seção opcional é indivisível: os dois níveis, ou nenhum", () => {
  const v = preenchimentoValido();
  assert.deepEqual(validar(v), [], "sem a seção, nada é cobrado");
  v.set("resultado_esperado.super_destaque", "3");
  const p = validar(v);
  assert.ok(p.length >= 1, "meio-declarada precisa ser cobrada");
  v.set("resultado_esperado.destaque", "1");
  assert.deepEqual(validar(v), [], "os dois declarados passa");
});

test("resultado_esperado exige super MAIOR que destaque", () => {
  const v = preenchimentoValido();
  v.set("resultado_esperado.super_destaque", "1");
  v.set("resultado_esperado.destaque", "1");
  const p = validar(v);
  assert.ok(p.some((x) => /MAIOR/.test(x.mensagem)));
});

test("campo condicional inativo NÃO é cobrado", () => {
  // `quando_ausente` só existe quando a forma é `nota`. Cobrá-lo sempre faria o
  // formulário exigir do dono um valor que a rodada nem lê.
  const v = preenchimentoValido("visualizacoes");
  assert.ok(!v.has("externo.desempenho.quando_ausente"));
  assert.deepEqual(validar(v), []);
});

test("o TOML sai com inteiro SEM casa decimal", () => {
  const toml = paraToml(preenchimentoValido(), "teste");
  assert.match(toml, /semelhanca_perfil = 25\b/);
  assert.doesNotMatch(toml, /= 25\.0/);
});

test("a seção opcional não declarada NÃO aparece no TOML", () => {
  // Omitir é o que declara o limiar como nulo. Emitir a seção vazia — ou pior, com
  // zero — desligaria a penalidade em silêncio, que é o que a D-022 proíbe.
  const toml = paraToml(preenchimentoValido(), "teste");
  assert.doesNotMatch(toml, /\[resultado_esperado\]/);
});

test("campo condicional inativo não vaza para o TOML", () => {
  const toml = paraToml(preenchimentoValido("visualizacoes"), "teste");
  assert.doesNotMatch(toml, /quando_ausente/);
  assert.doesNotMatch(toml, /^tipo = /m);
});

test("o TOML declara que os valores são PROVISÓRIOS", () => {
  const toml = paraToml(preenchimentoValido(), "trabalho 7");
  assert.match(toml, /PROVISÓRIO/);
  assert.match(toml, /trabalho 7/);
});

test("toda seção esperada aparece quando preenchida", () => {
  const toml = paraToml(preenchimentoValido("cliques_do_tipo"), "teste");
  for (const secao of ["semelhanca", "intensidades", "decaimento_janela", "externo"]) {
    assert.match(toml, new RegExp(`\\[${secao}\\]`), `faltou [${secao}]`);
  }
  assert.match(toml, /\[externo\.desempenho\]/);
  assert.match(toml, /^tipo = "clique/m);
});

test("o problema DO CAMPO vem antes do problema de REGRA", () => {
  // A ordem não é estética: a tela mostra o primeiro problema de cada campo, e um
  // peso com casa decimal produz DOIS — "precisa ser inteiro" e "os quatro somam
  // 100.5". Se o de regra viesse primeiro, o dono veria a soma errada sem ver a causa.
  const v = preenchimentoValido();
  v.set("pesos.super_destaque.semelhanca_perfil", "40.5");
  const doCampo = validar(v).filter((p) => p.caminho === "pesos.super_destaque.semelhanca_perfil");
  assert.ok(doCampo.length >= 2, "esperava o erro do campo E o da regra");
  assert.match(doCampo[0].mensagem, /inteiro/, "o erro do campo precisa vir primeiro");
});

test("a procedência NÃO pode escapar do comentário e virar TOML", () => {
  // Reproduzido em 03/09/2026: o campo livre "quem está declarando" entrava cru no
  // comentário, e comentário termina na quebra de linha. Um nome com
  // "\n[resultado_esperado]\nsuper_destaque = 3\ndestaque = 1" produzia um arquivo
  // VÁLIDO que definia o parâmetro nº 14 — o que a D-022 declara nulo, e exatamente o
  // que esta tela existe para impedir.
  const toml = paraToml(
    preenchimentoValido(),
    "olavo\n[resultado_esperado]\nsuper_destaque = 3\ndestaque = 1",
  );
  // A asserção é sobre ESTRUTURA, não sobre presença do texto: o mesmo texto dentro
  // de um comentário é inofensivo, e checar presença faria o teste falhar por um
  // arquivo correto. O que faz uma seção é começar a linha.
  const linhas = toml.split("\n");
  const secoes = linhas.filter((l) => /^\[/.test(l));
  const atribuicoes = linhas.filter((l) => /^[a-z_]+ = /.test(l));
  assert.ok(!secoes.some((l) => l.includes("resultado_esperado")), `seção injetada: ${secoes}`);
  assert.ok(!atribuicoes.some((l) => l.startsWith("super_destaque")), "atribuição injetada");
  // E o nome continua legível, numa linha de comentário só.
  assert.ok(linhas.filter((l) => l.startsWith("#")).some((l) => l.includes("olavo")));
});

test("a procedência é truncada, não deixada crescer sem limite", () => {
  const toml = paraToml(preenchimentoValido(), "x".repeat(5000));
  const linha = toml.split("\n").find((l) => l.includes("xxx"))!;
  assert.ok(linha.length < 260, `comentário de ${linha.length} caracteres`);
});

test("inteiro grande demais é RECUSADO em vez de virar notação científica", () => {
  // `String(1e21)` emite "1e+21", que o TOML lê como FLOAT e o validador recusa —
  // formulário verde produzindo arquivo que a rodada rejeita. E acima do inteiro
  // seguro o JavaScript perde precisão em silêncio.
  const v = preenchimentoValido();
  v.set("externo.idade_maxima_dias", "1000000000000000000000");
  const p = validar(v);
  assert.equal(p.length, 1);
  assert.match(p[0].mensagem, /grande demais/);
});
