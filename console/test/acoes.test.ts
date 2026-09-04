import { strict as assert } from "node:assert";
import { test } from "node:test";
import { montarAcoes } from "../lib/acoes";
import type { SaudeColeta } from "../lib/coletor";
import type { RodadaResumo } from "../lib/registro";

function saude(p: Partial<SaudeColeta> = {}): SaudeColeta {
  return {
    estado: "ok",
    needsWarm: false,
    coletadoEm: "2026-09-01T06:00:00Z",
    idadeDias: 0,
    linhas: 100,
    ...p,
  };
}

function rodada(id: number, p: Partial<RodadaResumo> = {}): RodadaResumo {
  return {
    id,
    tipo: "decisao",
    estado: "degradada",
    inicio: "2026-09-01T09:00:00Z",
    fim: null,
    aprovadaEm: null,
    aprovadaPor: null,
    motivoDegradacao: null,
    posicoesVaziasDestaque: 0,
    superDestaque: 475,
    destaque: 6495,
    amostral: false,
    ...p,
  };
}

test("coleta saudável e nada pendente → sem ações de ação, só info de params", () => {
  const acoes = montarAcoes(saude(), [], 0);
  assert.equal(acoes.length, 0);
});

test("NEEDS_WARM → ação de login com passos do runbook", () => {
  const acoes = montarAcoes(saude({ needsWarm: true, estado: "blocked" }), [], 0);
  const login = acoes.find((a) => a.id === "login-portal");
  assert.ok(login, "deve haver a ação de login");
  assert.equal(login!.severidade, "acao");
  assert.match(login!.detalhe ?? "", /9222/); // passo do runbook
});

test("estado blocked sem flag também dispara login", () => {
  const acoes = montarAcoes(saude({ estado: "blocked" }), [], 0);
  assert.ok(acoes.some((a) => a.id === "login-portal"));
});

test("coleta em erro NÃO fica muda: vira ação", () => {
  const acoes = montarAcoes(saude({ estado: "error" }), [], 0);
  const erro = acoes.find((a) => a.id === "coleta-erro");
  assert.ok(erro, "falha de coleta precisa aparecer na caixa de ações");
  assert.equal(erro!.severidade, "acao");
  assert.equal(
    acoes.some((a) => a.id === "login-portal"),
    false, // erro não é bloqueio de sessão: não manda relogar
  );
});

test("coleta corrompida vira ação própria", () => {
  const acoes = montarAcoes(saude({ estado: "corrompido" }), [], 0);
  const c = acoes.find((a) => a.id === "coleta-corrompida");
  assert.ok(c);
  assert.equal(c!.severidade, "acao");
});

test("coleta ausente não vira ação (o raspador só não rodou ainda)", () => {
  const acoes = montarAcoes(saude({ estado: "ausente", coletadoEm: null, idadeDias: null }), [], 0);
  assert.equal(acoes.length, 0);
});

test("uma ação por rodada aguardando aprovação", () => {
  const acoes = montarAcoes(saude(), [rodada(24), rodada(23)], 0);
  assert.deepEqual(
    acoes.filter((a) => a.id.startsWith("aprovar-")).map((a) => a.id),
    ["aprovar-24", "aprovar-23"],
  );
});

test("parâmetros pendentes viram uma ação info agregada", () => {
  const acoes = montarAcoes(saude(), [], 12);
  const p = acoes.find((a) => a.id === "parametros-pendentes");
  assert.ok(p);
  assert.equal(p!.severidade, "info");
  assert.match(p!.titulo, /12/);
});

test("zero parâmetros pendentes → sem card de parâmetros", () => {
  const acoes = montarAcoes(saude(), [], 0);
  assert.equal(
    acoes.some((a) => a.id === "parametros-pendentes"),
    false,
  );
});
