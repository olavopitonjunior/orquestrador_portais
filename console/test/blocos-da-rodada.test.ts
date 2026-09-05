import assert from "node:assert/strict";
import { test } from "node:test";

import { blocosPreenchidos, cedenciaDaAba, montarBlocos } from "../lib/blocos-da-rodada";
import { ORDEM_RELAXAMENTO, REGRAS_LEGIVEIS } from "../lib/regras";

const RESUMOS = new Map<string, Record<string, unknown>>([
  ["coletor_interno", { candidatos: 48_964, penalizaveis: 48_964, com_dimensoes: 48_900, recorte_amostral: null, degradacoes: [] }],
  ["analista_perfil", { perfis: 187, frageis: 40, degradacoes: [] }],
  ["coletor_externo", { entrou_no_ranking: true, taxa_amarracao: 0.734, idade_dias: 0, imoveis_com_anuncio: 300, degradacoes: [] }],
  [
    "decisor",
    {
      elegiveis: 8_230,
      reprovados: 40_734,
      reprovados_por_regra: { capacidade_distrito: 5_000, fotos: 900, perfil_de_conversao: 1_600, status_ativo: 0 },
      super_destaque: 475,
      destaque: 6_375, // pelo ranking; o resumo traz os recuperados à parte
      recuperados_por_relaxamento: 120,
      posicoes_vazias: 0,
      degradacoes: ["forma de normalização (parâmetro nº 2) = min-max"],
    },
  ],
  ["crivo", { passou: true, violacoes: [], degradacoes: [] }],
]);

const EFETIVO = {
  "portal.cobertura_minima": 50,
  "portal.idade_maxima_dias": 2,
  "portal.peso_nota": 70,
  "portal.peso_cliques": 30,
  "portal.peso_visualizacoes": 0,
  "portal.sem_anuncio": "fim_da_fila",
  "portal.ordem_quando_nao_entra": "leads_180d",
};

test("os três blocos saem dos resumos, com as regras na ordem do funil e só as que reprovaram", () => {
  const b = montarBlocos({ resumos: RESUMOS, efetivo: EFETIVO, contagens: null, relaxamento: [] });
  assert.equal(b.quemEntrou.candidatos, 48_964);
  assert.equal(b.quemEntrou.elegiveis, 8_230);
  assert.deepEqual(
    b.quemEntrou.porRegra.map((r) => r.regra),
    ["fotos", "perfil_de_conversao", "capacidade_distrito"],
  );
  assert.equal(b.quemEntrou.porRegra[1].grupo, "quem_entra_perfil");
  assert.equal(b.emQueOrdem.portalEntrou, true);
  assert.equal(b.emQueOrdem.coberturaAtingida, 73.4);
  assert.equal(b.emQueOrdem.coberturaMinima, 50);
  assert.deepEqual(b.emQueOrdem.pesos, { nota: 70, cliques: 30, visualizacoes: 0 });
  assert.equal(b.quantos.superDestaque, 475);
  assert.equal(b.quantos.destaque, 6_495, "ranking + cedência, como o Registro conta");
  assert.equal(b.quantos.recuperados, 120);
  assert.equal(b.quantos.crivoPassou, true);
  assert.deepEqual(b.quantos.degradacoes, ["forma de normalização (parâmetro nº 2) = min-max"]);
  assert.equal(blocosPreenchidos(b), 3);
});

test("o que ainda não chegou é null, nunca zero — e a contagem de blocos reflete isso", () => {
  const b = montarBlocos({
    resumos: new Map([["coletor_interno", { candidatos: 10 }]]),
    efetivo: null,
    contagens: null,
    relaxamento: [],
  });
  assert.equal(b.quemEntrou.candidatos, 10);
  assert.equal(b.quemEntrou.elegiveis, null);
  assert.equal(b.emQueOrdem.portalEntrou, null);
  assert.equal(b.emQueOrdem.coberturaMinima, null);
  assert.equal(b.quantos.destaque, null);
  assert.equal(blocosPreenchidos(b), 0);
});

test("as contagens do Registro prevalecem sobre o resumo, e a cedência vem da aba na ordem certa", () => {
  const b = montarBlocos({
    resumos: RESUMOS,
    efetivo: EFETIVO,
    contagens: { superDestaque: 400, destaque: 6_000, vaziasDestaque: 495 },
    relaxamento: cedenciaDaAba(
      ["ordem", "regra_cedida", "posicoes_dependentes", "posicoes_vazias"],
      [
        ["2", "fotos", "30", "0"],
        ["1", "perfil_de_conversao", "90", "0"],
        ["", "POSIÇÕES AINDA VAZIAS (nenhum grau cobriu)", "495", "495"], // resíduo, não degrau
      ],
    ),
  });
  assert.equal(b.quantos.superDestaque, 400);
  assert.equal(b.quantos.vaziasDestaque, 495);
  assert.deepEqual(
    b.quantos.cedencia.map((c) => [c.regra, c.n]),
    [
      ["perfil_de_conversao", 90],
      ["fotos", 30],
    ],
  );
  assert.match(b.quantos.cedencia[0].rotulo, /parece com o que vendeu/);
});

test("cedenciaDaAba sem as colunas devolve vazio em vez de inventar", () => {
  assert.deepEqual(cedenciaDaAba(["x"], [["1"]]), []);
});

test("as nove regras legíveis batem com o domínio, e a ordem de cedência tem seis", () => {
  assert.equal(REGRAS_LEGIVEIS.length, 9);
  assert.equal(new Set(REGRAS_LEGIVEIS.map((r) => r.regra)).size, 9);
  assert.deepEqual(ORDEM_RELAXAMENTO, [
    "perfil_de_conversao",
    "fotos",
    "cadastro_completo",
    "atualizacao_90d",
    "gestor_produtivo",
    "capacidade_distrito",
  ]);
  for (const r of REGRAS_LEGIVEIS) assert.doesNotMatch(r.rotulo, /_|F[0-9]/);
});
