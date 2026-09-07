import { strict as assert } from "node:assert";
import { test } from "node:test";
import type { Amarracao, SaudeColeta } from "../lib/coletor";
import { motivoParaNaoRodarFull } from "../lib/portao-da-coleta";

function saude(p: Partial<SaudeColeta> = {}): SaudeColeta {
  return {
    estado: "ok",
    needsWarm: false,
    coletadoEm: "2026-09-06T15:19:00Z",
    idadeDias: 0,
    linhas: 1000,
    repetivel: false,
    ...p,
  };
}

const amarracao: Amarracao = {
  linhas: 1000,
  noFormato: 1000,
  vazios: 0,
  foraDoFormato: 0,
  exemplos: ["123a"],
};

const tudoPronto = { chromeNoAr: true, saude: saude(), canarioOk: {}, amarracao };

test("tudo pronto → portão liberado", () => {
  assert.equal(motivoParaNaoRodarFull(tudoPronto), null);
});

test("soluço do portal tem motivo PRÓPRIO: dispare de novo, não conserte nada", () => {
  // Esta página é o destino de `acoes.ts` e de `prontidao.ts`, que acabaram de dizer
  // "rode de novo". Mostrar aqui o estado cru `error` mandaria a mesma pessoa
  // procurar defeito onde não há.
  const m = motivoParaNaoRodarFull({ ...tudoPronto, saude: saude({ estado: "error", repetivel: true }) });
  assert.match(m ?? "", /soluço do portal/);
  assert.match(m ?? "", /de novo/);
  assert.doesNotMatch(m ?? "", /'error'/, "o estado cru não pode vazar para o operador");
});

test("erro definitivo continua mostrando o estado cru", () => {
  const m = motivoParaNaoRodarFull({ ...tudoPronto, saude: saude({ estado: "error", repetivel: false }) });
  assert.match(m ?? "", /'error'/);
  assert.doesNotMatch(m ?? "", /soluço/);
});

test("Chrome fora do ar vence o soluço: sem navegador não há o que disparar", () => {
  // A ordem é regra: oferecer "dispare de novo" a quem não tem Chrome no ar é
  // mandar a pessoa clicar num botão que não vai funcionar.
  const m = motivoParaNaoRodarFull({
    ...tudoPronto,
    chromeNoAr: false,
    saude: saude({ estado: "error", repetivel: true }),
  });
  assert.match(m ?? "", /Chrome de depuração/);
});

test("bloqueio NÃO vira soluço, mesmo com repetivel indevidamente ligado", () => {
  // `saudeColeta` já trava `repetivel` em `estado === "error"`; esta é a segunda
  // linha de defesa, porque o conserto do bloqueio é re-logar, não repetir.
  const m = motivoParaNaoRodarFull({ ...tudoPronto, saude: saude({ estado: "blocked", repetivel: true }) });
  assert.match(m ?? "", /'blocked'/);
});

test("os demais degraus do portão seguem na ordem", () => {
  assert.match(motivoParaNaoRodarFull({ ...tudoPronto, canarioOk: null }) ?? "", /nenhum canário/);
  assert.match(motivoParaNaoRodarFull({ ...tudoPronto, amarracao: null }) ?? "", /não há CSV/);
  assert.match(
    motivoParaNaoRodarFull({ ...tudoPronto, amarracao: { ...amarracao, noFormato: 0 } }) ?? "",
    /raspar em volume não conserta/,
  );
});
