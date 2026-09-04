import { strict as assert } from "node:assert";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";
import { PARAMETROS, PARAMETROS_PENDENTES } from "../lib/parametros";

// O cabeçalho de `lib/parametros.ts` declara um contrato: "se a tabela do CLAUDE.md
// mudar, esta lista precisa acompanhar (é a única cópia; a fonte da verdade é o doc)".
// Até aqui isso era comentário, e a lista dessincronizou três vezes — a terceira
// acrescentou o nº 15 ao doc e deixou o painel exibindo catorze. Estes testes
// executam o contrato em vez de descrevê-lo.

const CLAUDE_MD = join(import.meta.dirname, "..", "..", "CLAUDE.md");

/** Linhas `| N | ... | valor |` da tabela de parâmetros do CLAUDE.md. */
function tabelaDoDocumento(): { numero: number; valor: string }[] {
  const linhas = readFileSync(CLAUDE_MD, "utf-8").split("\n");
  const casadas = linhas.map((l) => /^\|\s*(\d+)\s*\|(.*)\|(.*)\|\s*$/.exec(l)).filter((m) => m !== null);
  return casadas.map((m) => ({ numero: Number(m[1]), valor: m[3].trim() }));
}

test("a tabela do CLAUDE.md é encontrada e não está vazia", () => {
  // Guarda da própria guarda: se a regex parar de casar (a tabela mudou de forma),
  // os testes abaixo passariam por vacuidade, comparando duas listas vazias.
  // 13 desde a D-031 (nº 12 e nº 13 deixaram de existir).
  assert.ok(tabelaDoDocumento().length >= 13, "regex não casou a tabela do CLAUDE.md");
});

test("a lista do console tem os MESMOS números da tabela do CLAUDE.md", () => {
  assert.deepEqual(
    PARAMETROS.map((p) => p.numero),
    tabelaDoDocumento().map((l) => l.numero),
  );
});

test("numeração contígua a partir de 1, sem duplicata — só os buracos DECLARADOS", () => {
  // D-031: nº 12 e nº 13 deixaram de existir e os números nunca são reaproveitados.
  // Qualquer outro buraco é erro de cópia.
  const DISSOLVIDOS = new Set([12, 13]);
  const esperado = Array.from({ length: PARAMETROS.length + DISSOLVIDOS.size }, (_, i) => i + 1)
    .filter((n) => !DISSOLVIDOS.has(n));
  assert.deepEqual(
    PARAMETROS.map((p) => p.numero),
    esperado,
  );
});

test("quem o documento diz nulo, o console diz pendente", () => {
  // É o invariante que importa para o dono: o painel não pode dar por decidido
  // um parâmetro que o documento mantém nulo — nem o contrário.
  const nulosNoDoc = tabelaDoDocumento()
    .filter((l) => l.valor.toLowerCase().startsWith("nulo"))
    .map((l) => l.numero);
  assert.deepEqual(PARAMETROS_PENDENTES.map((p) => p.numero), nulosNoDoc);
});
