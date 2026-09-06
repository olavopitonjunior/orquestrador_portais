// O limite de linhas da página da rodada, e a armadilha que ele cria.
//
// Estes testes existem por causa de um defeito real: a primeira versão da correção
// limitou `destaque` a 300 linhas, e o painel passou a dizer "6.495 pelo ranking + 0 por
// relaxamento" em vez de "6.379 + 116". Nada acusou — tipo, build, testes e a contagem
// da aba continuaram certos, porque `total` continua exato. O que quebra em silêncio é
// AGREGADO sobre `Tabela.linhas`. Ver `bug.md`.

import { strict as assert } from "node:assert";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { ABAS_COM_AGREGADO, LIMITES, LINHAS_NA_TELA, ORDEM_DAS_ABAS } from "../lib/abas-da-rodada";
import { lerPlanilha } from "../lib/planilha";

test("nenhuma aba de que a página AGREGA pode ter limite", () => {
  for (const aba of ABAS_COM_AGREGADO) {
    assert.equal(
      LIMITES[aba],
      undefined,
      `${aba}: a página conta/percorre estas linhas, então limitá-la corrompe o número em silêncio`,
    );
  }
});

test("a apuração não materializa linha nenhuma: a tela mostra só a contagem", () => {
  assert.equal(LIMITES.apuracao, 0);
  assert.equal(ORDEM_DAS_ABAS.includes("apuracao"), false, "a apuração não é exibida");
});

// A forma da rodada 30417: 6.495 posições de destaque, os 116 relaxados nas ÚLTIMAS.
function destaqueComoNaRodadaReal(): string {
  const total = 6495;
  const relaxados = 116;
  const linhas = Array.from({ length: total }, (_, i) => {
    const origem = i >= total - relaxados ? "relaxamento" : "ranking";
    return `${i + 1},${1000 + i},${origem}`;
  });
  return "posicao,imovel_id,origem\r\n" + linhas.join("\r\n") + "\r\n";
}

test("os relaxados são contados inteiros — eles ficam no FIM da lista, fora de qualquer prefixo", async () => {
  const raiz = mkdtempSync(join(tmpdir(), "console-abas-"));
  mkdirSync(join(raiz, "2026-09-06"));
  writeFileSync(join(raiz, "2026-09-06", "destaque.csv"), destaqueComoNaRodadaReal());
  process.env.SAIDA_SEXTA_DIR = raiz;

  const p = await lerPlanilha("2026-09-06", LIMITES);
  assert.ok(p);
  const aba = p.abas.destaque;
  assert.ok(aba);
  const iOrigem = aba.colunas.indexOf("origem");
  const relaxados = aba.linhas.filter((l) => l[iOrigem] === "relaxamento").length;

  assert.equal(aba.total, 6495, "o total da aba");
  assert.equal(relaxados, 116, "é este número que o painel publica ao lado de 'por relaxamento'");

  // E a prova de que o prefixo NÃO serve: com o limite da tela, a mesma conta dá zero.
  // É a forma exata do defeito, guardada aqui para que ninguém o reintroduza por engano.
  const noPrefixo = aba.linhas
    .slice(0, LINHAS_NA_TELA)
    .filter((l) => l[iOrigem] === "relaxamento").length;
  assert.equal(noPrefixo, 0, "as 300 primeiras posições não têm um relaxado sequer");
});
