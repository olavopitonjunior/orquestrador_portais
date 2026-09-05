import assert from "node:assert/strict";
import { test } from "node:test";

import { desfechoDe } from "../lib/desfecho";
import type { Trabalho } from "../lib/operacao";
import { conferir } from "../lib/declaracao";
import {
  fraseDaPrevia,
  grupoDoCaminho,
  lerPrevia,
  previaEmVoo,
  valoresEmOrdem,
  type Previa,
} from "../lib/previa";

function previa(p: Partial<Previa> = {}): Previa {
  return {
    hoje: "2026-09-04",
    candidatos: 48_964,
    funil: [
      {
        regra: "status_ativo",
        rotulo: "publicação ativa",
        grupo: "quem_entra_imovel",
        sobram: 48_964,
        cortou: 0,
      },
      {
        regra: "perfil_de_conversao",
        rotulo: "parece com o que vendeu",
        grupo: "quem_entra_perfil",
        sobram: 8_230,
        cortou: 1_600,
      },
    ],
    reprovados_por_regra: { perfil_de_conversao: 1_600 },
    elegiveis: 8_230,
    candidatos_super_destaque: 3_715,
    posicoes: { super_destaque: 475, destaque: 6_495, total: 6_970 },
    projecao: {
      super_destaque_preenchido: 475,
      destaque_preenchido: 6_495,
      vazias_super_destaque: 0,
      vazias_destaque: 0,
      vazias_total: 0,
    },
    relaxamento: {
      recuperaveis: 0,
      travados_pelo_login: 0,
      por_degrau: [],
      vazias_destaque_depois: 0,
    },
    perfil: {
      perfis: 187,
      robustos: 187,
      que_contam: 120,
      exigencia: "faixa_preco",
      sem_dimensoes: 0,
      filtro_incide: true,
    },
    degradacoes: [],
    parametros: {
      origem: "adotados (D-034)",
      efetivo: {},
      procedencia: {},
      declarados_diferentes_do_adotado: [],
    },
    ...p,
  };
}

function trabalho(id: number, tipo: string, estado: string): Trabalho {
  return {
    id,
    tipo,
    estado,
    pedido_em: "2026-09-04T10:00:00Z",
    pedido_por: null,
    codigo_saida: null,
    rodada_id: null,
  };
}

test("lerPrevia aceita a forma do módulo Python e recusa o resto", () => {
  assert.ok(lerPrevia(previa()));
  assert.equal(lerPrevia(undefined), null);
  assert.equal(lerPrevia(null), null);
  assert.equal(lerPrevia({ elegiveis: 3 }), null, "sem funil não é prévia");
  assert.equal(
    lerPrevia({ ...previa(), funil: [{ regra: "x" }] }),
    null,
    "linha sem contagem",
  );
  assert.equal(
    lerPrevia({ ...previa(), elegiveis: "muitos" }),
    null,
    "contagem que não é número",
  );
});

test("lerPrevia confere TUDO que a tela dereferencia", () => {
  const base = previa();
  const sem = (chave: keyof Previa) => {
    const copia: Record<string, unknown> = { ...base };
    delete copia[chave];
    return copia;
  };
  for (const chave of ["parametros", "relaxamento", "perfil", "projecao", "posicoes", "degradacoes"] as const) {
    assert.equal(lerPrevia(sem(chave)), null, `sem ${chave} não é prévia`);
  }
  assert.equal(lerPrevia({ ...base, relaxamento: { ...base.relaxamento, por_degrau: [{ regra: "x" }] } }), null);
  assert.equal(lerPrevia({ ...base, parametros: { ...base.parametros, efetivo: "x" } }), null);
  assert.equal(lerPrevia({ ...base, perfil: { ...base.perfil, filtro_incide: "sim" } }), null);
});

test("cada seção do TOML aponta para o grupo da tela onde o campo mora", () => {
  assert.equal(grupoDoCaminho("conversao.janela_dias"), "quem_entra_perfil");
  assert.equal(grupoDoCaminho("corretor.minimo_no_distrito"), "quem_entra_corretor");
  assert.equal(grupoDoCaminho("portal.peso_nota"), "em_que_ordem_portal");
  assert.equal(grupoDoCaminho("desconto.perdao_por_semana"), "em_que_ordem_descontos");
  assert.equal(grupoDoCaminho("resultado_esperado.destaque"), "quantos");
  assert.equal(grupoDoCaminho("outra.coisa"), "operacao");
});

test("conferir: nome com controle ou longo demais é recusado; declaração vazia passa", () => {
  const ruim = conferir({}, "ol\u0001avo");
  assert.ok("ok" in ruim && ruim.ok === false);
  const longo = conferir({}, "x".repeat(201));
  assert.ok("ok" in longo && longo.ok === false);
  const vazio = conferir({}, "");
  assert.ok("valores" in vazio && vazio.valores.size === 0, "a declaração vazia é válida (adotados)");
  const invalido = conferir({ "portal.peso_nota": "80" }, "olavo");
  assert.ok("ok" in invalido && "problemas" in invalido, "soma 110 com os adotados é recusada");
});

test("a frase diz quantos sobram e, cheio, que tudo ficou preenchido", () => {
  const f = fraseDaPrevia(previa());
  assert.match(f, /sobram 8\.230 imóveis para as 6\.970 posições/);
  assert.match(f, /todas preenchidas/);
});

test("a frase diz o que falta em cada nível, e o que a cedência recuperaria", () => {
  const f = fraseDaPrevia(
    previa({
      elegiveis: 5_000,
      candidatos_super_destaque: 300,
      projecao: {
        super_destaque_preenchido: 300,
        destaque_preenchido: 4_700,
        vazias_super_destaque: 175,
        vazias_destaque: 1_795,
        vazias_total: 1_970,
      },
      relaxamento: {
        recuperaveis: 1_200,
        travados_pelo_login: 105,
        por_degrau: [],
        vazias_destaque_depois: 595,
      },
    }),
  );
  assert.match(
    f,
    /300 das 475 de super destaque \(175 vazias — o super destaque nunca relaxa\)/,
  );
  assert.match(
    f,
    /4\.700 das 6\.495 de destaque \(1\.795 vazias; a cedência de regras recuperaria até 1\.200, sobrando 595 vazias\)/,
  );
});

test("quando a cedência cobre todas as vazias, a frase diz que encheria — não 'sobrando 0'", () => {
  const f = fraseDaPrevia(
    previa({
      projecao: {
        super_destaque_preenchido: 475,
        destaque_preenchido: 874,
        vazias_super_destaque: 0,
        vazias_destaque: 5_621,
        vazias_total: 5_621,
      },
      relaxamento: {
        recuperaveis: 6_997,
        travados_pelo_login: 169,
        por_degrau: [],
        vazias_destaque_depois: 0,
      },
    }),
  );
  assert.match(f, /encheria todas — há 6\.997 recuperáveis/);
  assert.doesNotMatch(f, /sobrando 0/);
});

test("os valores efetivos saem na ordem das seções, e alfabéticos dentro delas", () => {
  const ordem = valoresEmOrdem({
    "portal.peso_nota": 70,
    "desconto.sem_lead_180d": 10,
    "corretor.minimo_no_distrito": 2,
    "conversao.janela_dias": 180,
    "corretor.login_janela_dias": 30,
  }).map(([c]) => c);
  assert.deepEqual(ordem, [
    "conversao.janela_dias",
    "corretor.login_janela_dias",
    "corretor.minimo_no_distrito",
    "portal.peso_nota",
    "desconto.sem_lead_180d",
  ]);
});

test("sem ninguém a recuperar, a frase diz isso em vez de omitir", () => {
  const f = fraseDaPrevia(
    previa({
      projecao: {
        super_destaque_preenchido: 475,
        destaque_preenchido: 6_000,
        vazias_super_destaque: 0,
        vazias_destaque: 495,
        vazias_total: 495,
      },
      relaxamento: {
        recuperaveis: 0,
        travados_pelo_login: 0,
        por_degrau: [],
        vazias_destaque_depois: 495,
      },
    }),
  );
  assert.match(f, /as 475 de super destaque preenchidas/);
  assert.match(f, /não recuperaria ninguém/);
});

test("previaEmVoo acha só a prévia pendente ou executando", () => {
  assert.equal(previaEmVoo([]), null);
  assert.equal(
    previaEmVoo([
      trabalho(1, "sexta", "pendente"),
      trabalho(2, "previa", "ok"),
    ]),
    null,
  );
  assert.equal(previaEmVoo([trabalho(3, "previa", "executando")]), 3);
  assert.equal(previaEmVoo([trabalho(4, "previa", "pendente")]), 4);
});

test("os códigos da prévia são traduzidos, e não com o texto da sexta", () => {
  const ok = desfechoDe("previa", 0)!;
  const fonte = desfechoDe("previa", 3)!;
  const params = desfechoDe("previa", 5)!;
  assert.equal(ok.grave, false);
  assert.doesNotMatch(
    ok.explicacao,
    /planilha|Registro/,
    "a prévia não entrega planilha",
  );
  assert.equal(fonte.grave, true);
  assert.equal(params.grave, false);
  assert.equal(desfechoDe("previa", 1)?.grave, true);
  assert.equal(desfechoDe("previa", 2)?.grave, true);
  assert.equal(desfechoDe("previa", 4)?.titulo, "Código 4");
});
