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
  assert.ok(tabelaDoDocumento().length >= 14, "regex não casou a tabela do CLAUDE.md");
});

test("a lista do console tem os MESMOS números da tabela do CLAUDE.md", () => {
  assert.deepEqual(
    PARAMETROS.map((p) => p.numero),
    tabelaDoDocumento().map((l) => l.numero),
  );
});

test("numeração contígua a partir de 1, sem buraco nem duplicata", () => {
  assert.deepEqual(
    PARAMETROS.map((p) => p.numero),
    Array.from({ length: PARAMETROS.length }, (_, i) => i + 1),
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
