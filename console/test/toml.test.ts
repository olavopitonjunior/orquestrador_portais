// O validador do formulário adianta a recusa que o Python faria — e não pode divergir
// dela. Estes testes derivam TUDO do contrato: uma lista paralela aqui seria a mesma
// duplicação que o contrato existe para evitar.

import assert from "node:assert/strict";
import { test } from "node:test";

import { CAMPOS, POR_CAMINHO, REGRAS, campoAtivo } from "../lib/contrato";
import { paraToml, validar } from "../lib/toml";

// Os três pesos do portal somam 100 — assimétricos, para uma troca de campo não passar.
const PESOS: Record<string, string> = {
  "portal.peso_nota": "70",
  "portal.peso_cliques": "30",
  "portal.peso_visualizacoes": "0",
};

/** Um preenchimento válido, montado A PARTIR DO CONTRATO. */
function preenchimentoValido(): Map<string, string> {
  const v = new Map<string, string>();
  for (const c of CAMPOS) {
    if (!c.obrigatorio || v.has(c.caminho)) continue;
    if (!campoAtivo(c, v)) continue;
    if (c.tipo === "escolha") {
      v.set(c.caminho, (c.escolhas ?? [])[0]);
    } else if (c.caminho in PESOS) {
      v.set(c.caminho, PESOS[c.caminho]);
    } else if (c.tipo === "inteiro") {
      v.set(c.caminho, String(c.minimo ?? 1));
    } else {
      const min = c.minimo ?? 0;
      const max = c.maximo ?? min + 2;
      v.set(c.caminho, String((min + max) / 2));
    }
  }
  return v;
}

test("há contrato a conferir", () => {
  assert.ok(CAMPOS.length >= 16, `contrato encolheu: ${CAMPOS.length}`);
  assert.ok(REGRAS.length >= 3, `regras encolheram: ${REGRAS.length}`);
  for (const caminho of Object.keys(PESOS)) {
    assert.ok(POR_CAMINHO.has(caminho), `o contrato perdeu ${caminho}`);
  }
});

test("um preenchimento válido não produz problema nenhum", () => {
  assert.deepEqual(validar(preenchimentoValido()), []);
});

test("campo obrigatório vazio é cobrado, e só ele", () => {
  const v = preenchimentoValido();
  v.delete("desconto.sem_lead_180d");
  const p = validar(v);
  assert.equal(p.length, 1);
  assert.equal(p[0].caminho, "desconto.sem_lead_180d");
});

test("espaço em branco conta como vazio", () => {
  // Sem isto, `Number(" ")` vira 0 — um valor que ninguém escolheu, entrando numa
  // rodada que decide 6.970 posições pagas.
  const v = preenchimentoValido();
  v.set("desconto.sem_lead_180d", "   ");
  assert.equal(validar(v).length, 1);
});

test("inteiro com casa decimal é RECUSADO", () => {
  // A distinção que o JavaScript não faz e o validador Python faz. Sem ela, um
  // formulário perfeitamente preenchido produz um TOML que a rodada rejeita.
  const v = preenchimentoValido();
  v.set("portal.idade_maxima_dias", "8.5");
  const p = validar(v);
  assert.equal(p.length, 1);
  assert.match(p[0].mensagem, /inteiro/);
});

test("o limite FECHADO aceita o próprio limite, dos dois lados", () => {
  // Pontos de 100 e por cento são faixas fechadas [0, 100]: zero é um valor legítimo
  // (visualizações pesam 0 por medição) e 100 também (perdão total).
  const v = preenchimentoValido();
  v.set("portal.cobertura_minima", "0");
  v.set("desconto.perdao_por_semana", "100");
  assert.deepEqual(validar(v), []);
});

test("valor acima do teto é recusado", () => {
  const v = preenchimentoValido();
  v.set("portal.cobertura_minima", "150");
  assert.equal(validar(v).length, 1);
});

test("valor abaixo do piso é recusado", () => {
  const v = preenchimentoValido();
  v.set("corretor.minimo_no_distrito", "0"); // piso 1
  assert.equal(validar(v).length, 1);
});

test("escolha fora da lista é recusada", () => {
  const v = preenchimentoValido();
  v.set("portal.sem_anuncio", "zero");
  assert.equal(validar(v).length, 1);
});

test("os três pesos do portal precisam somar exatamente 100", () => {
  const v = preenchimentoValido();
  v.set("portal.peso_nota", "71");
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

test("o TOML sai com inteiro SEM casa decimal", () => {
  const toml = paraToml(preenchimentoValido(), "teste");
  assert.match(toml, /^peso_nota = 70$/m);
  assert.doesNotMatch(toml, /= 70\.0/);
});

test("a seção opcional não declarada NÃO aparece no TOML", () => {
  // Omitir é o que declara o limiar como nulo. Emitir a seção vazia — ou pior, com
  // zero — desligaria a penalidade em silêncio, que é o que a D-022 proíbe.
  const toml = paraToml(preenchimentoValido(), "teste");
  assert.doesNotMatch(toml, /\[resultado_esperado\]/);
});

test("o TOML declara que os valores são PROVISÓRIOS", () => {
  const toml = paraToml(preenchimentoValido(), "trabalho 7");
  assert.match(toml, /PROVISÓRIO/);
  assert.match(toml, /trabalho 7/);
});

test("toda seção esperada aparece quando preenchida", () => {
  const toml = paraToml(preenchimentoValido(), "teste");
  for (const secao of ["conversao", "corretor", "portal", "desconto"]) {
    assert.match(toml, new RegExp(`^\\[${secao}\\]$`, "m"), `faltou [${secao}]`);
  }
  assert.match(toml, /^sem_anuncio = "fim_da_fila"$/m, "escolha sai entre aspas");
});

test("o problema DO CAMPO vem antes do problema de REGRA", () => {
  // A ordem não é estética: a tela mostra o primeiro problema de cada campo, e um
  // peso com casa decimal produz DOIS — "precisa ser inteiro" e "os três somam
  // 100.5". Se o de regra viesse primeiro, o dono veria a soma errada sem ver a causa.
  const v = preenchimentoValido();
  v.set("portal.peso_nota", "70.5");
  const doCampo = validar(v).filter((p) => p.caminho === "portal.peso_nota");
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
  v.set("portal.idade_maxima_dias", "1000000000000000000000");
  const p = validar(v);
  assert.equal(p.length, 1);
  assert.match(p[0].mensagem, /grande demais/);
});

test("escolha com espaço supérfluo NÃO desativa o campo que ela governa", () => {
  // Havia DUAS noções de igualdade: `validar` comparava com trim, `campoAtivo` cru.
  // Uma escolha com espaço no fim era aceita pela validação E desativava o campo
  // condicional, que então não era exigido nem serializado — o console dizia
  // "Guardado", e a rodada morria com "falta ...", na única tentativa da semana.
  // O contrato de hoje não tem campo condicional; a garantia fica num campo
  // sintético, para o dia em que voltar a ter.
  const governante = POR_CAMINHO.get("portal.sem_anuncio")!;
  const condicional = {
    ...governante,
    caminho: "portal.x",
    quando: ["portal.sem_anuncio", "mediana"] as [string, string],
  };
  const v = preenchimentoValido();
  v.set("portal.sem_anuncio", "mediana ");
  assert.ok(campoAtivo(condicional, v), "o campo condicional foi desativado por um espaço");
  assert.deepEqual(validar(v), [], "e continua válido");
  assert.match(paraToml(v, "t"), /^sem_anuncio = "mediana"$/m, "e a escolha sai limpa");
});

test("caractere de controle na procedência não quebra o TOML", () => {
  // A gramática do TOML proíbe controle dentro de comentário: um caractere de controle
  // no nome fazia o arquivo INTEIRO deixar de parsear, e a rodada morria antes de ler
  // um parâmetro — com o console tendo dito "Guardado". Mesma classe da injeção, por um
  // caractere que a primeira correção não cobria.
  const toml = paraToml(preenchimentoValido(), "ol\u0001a\u007Fvo");
  assert.doesNotMatch(toml, /[\u0000-\u0008\u000B-\u001F\u007F]/);
  assert.ok(toml.split("\n").some((l) => l.startsWith("#") && l.includes("olavo")));
});
