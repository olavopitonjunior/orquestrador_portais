import assert from "node:assert/strict";
import { test } from "node:test";

import { efetivosDe, proseDaDeclaracao, valoresDoToml } from "../lib/declaracao";
import { paraToml } from "../lib/toml";

test("o TOML que o console gera é lido de volta sem perda", () => {
  const v = new Map([
    ["portal.peso_nota", "80"],
    ["portal.peso_cliques", "20"],
    ["portal.sem_anuncio", "mediana"],
    ["conversao.janela_dias", "90"],
  ]);
  const lido = valoresDoToml(paraToml(v, "olavo"));
  assert.deepEqual([...lido.entries()].sort(), [...v.entries()].sort());
});

test("comentários, linhas soltas e valor fora de seção são ignorados", () => {
  const lido = valoresDoToml("# x\nsolto = 1\n[portal]\npeso_nota = 70\n\n# fim\n");
  assert.deepEqual([...lido.entries()], [["portal.peso_nota", "70"]]);
});

test("efetivosDe: vazio cai no adotado, declarado fica marcado, o nº 14 só entra declarado", () => {
  const e = efetivosDe(new Map([["portal.peso_nota", "80"]]));
  const por = new Map(e.map((x) => [x.caminho, x]));
  assert.equal(por.get("portal.peso_nota")?.valor, "80");
  assert.equal(por.get("portal.peso_nota")?.procedencia, "declarado");
  assert.equal(por.get("portal.peso_cliques")?.valor, "30");
  assert.equal(por.get("portal.peso_cliques")?.procedencia, "adotado");
  assert.ok(!por.has("resultado_esperado.destaque"), "sem adotado e sem declaração: fora");
  assert.equal(e.filter((x) => x.procedencia === "declarado").length, 1);
  const com = efetivosDe(
    new Map([
      ["resultado_esperado.super_destaque", "3"],
      ["resultado_esperado.destaque", "1"],
    ]),
  );
  assert.ok(com.some((x) => x.caminho === "resultado_esperado.destaque" && x.valor === "1"));
});

test("a prosa tem os três blocos, cada número ligado ao parâmetro, com unidade", () => {
  const frases = proseDaDeclaracao(efetivosDe(new Map([["conversao.janela_dias", "90"]])), {
    superDestaque: 475,
    destaque: 6495,
  });
  assert.deepEqual(
    frases.map((f) => f.bloco),
    ["quem-entra", "em-que-ordem", "quantos"],
  );
  const valores = frases.flatMap((f) => f.trechos).filter((t) => "v" in t);
  const janela = valores.find((t) => "caminho" in t && t.caminho === "conversao.janela_dias")!;
  assert.ok("v" in janela && janela.v === "90 dias" && janela.procedencia === "declarado");
  const cobertura = valores.find((t) => "caminho" in t && t.caminho === "portal.cobertura_minima")!;
  assert.ok("v" in cobertura && cobertura.v === "50 %" && cobertura.procedencia === "adotado");
  const semAnuncio = valores.find((t) => "caminho" in t && t.caminho === "portal.sem_anuncio")!;
  assert.ok("v" in semAnuncio && semAnuncio.v === "vai para o fim da fila", "escolha vira prosa");
  const texto = frases
    .flatMap((f) => f.trechos)
    .map((t) => ("t" in t ? t.t : t.v))
    .join("");
  assert.match(texto, /475 super destaques acima de R\$ 700\.000 e 6\.495 destaques/);
  assert.doesNotMatch(texto, /F1|F3|0 a 1/, "nem sigla nem escala abstrata");
  assert.doesNotMatch(texto, /régua de resultado desta rodada/, "o nº 14 não declarado não aparece");
});

test("sem cotas lidas do Registro, a prosa não inventa 475 nem 6.495", () => {
  const texto = proseDaDeclaracao(efetivosDe(new Map()), null)
    .flatMap((f) => f.trechos)
    .map((t) => ("t" in t ? t.t : t.v))
    .join("");
  assert.doesNotMatch(texto, /475|6\.495/);
});

test("comentário em linha e aspas com escape não corrompem o valor", () => {
  const lido = valoresDoToml(
    '[portal]\npeso_nota = 75  # ajustado à mão\nsem_anuncio = "mediana" # nota\n[x]\ny = "va\\"lue"\n',
  );
  assert.equal(lido.get("portal.peso_nota"), "75");
  assert.equal(lido.get("portal.sem_anuncio"), "mediana");
  assert.equal(lido.get("x.y"), 'va"lue');
});

test("declarado IGUAL ao adotado conta como adotado, como o carregador Python", () => {
  const e = efetivosDe(new Map([["portal.peso_nota", "70"], ["portal.sem_anuncio", "fim_da_fila"], ["portal.cobertura_minima", "50.0"]]));
  const por = new Map(e.map((x) => [x.caminho, x.procedencia]));
  assert.equal(por.get("portal.peso_nota"), "adotado");
  assert.equal(por.get("portal.sem_anuncio"), "adotado");
  assert.equal(por.get("portal.cobertura_minima"), "adotado", "50.0 é o mesmo número que 50");
});

test("a régua nº 14 meio-declarada não aparece, e nenhum '?' vaza para a prosa", () => {
  const texto = proseDaDeclaracao(efetivosDe(new Map([["resultado_esperado.super_destaque", "3"]])), null)
    .flatMap((f) => f.trechos)
    .map((t) => ("t" in t ? t.t : t.v))
    .join("");
  assert.doesNotMatch(texto, /régua de resultado desta rodada|\?/);
});

test("a prosa contrai a preposição: 'vem dos leads', não 'vem de os leads'", () => {
  const texto = proseDaDeclaracao(efetivosDe(new Map()), null)
    .flatMap((f) => f.trechos)
    .map((t) => ("t" in t ? t.t : t.v))
    .join("");
  assert.match(texto, /a ordem vem dos leads em 180 dias/);
  assert.doesNotMatch(texto, /vem de os|vem de a /);
});
