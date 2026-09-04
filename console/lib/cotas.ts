// As cotas contratuais (invariante 6), lidas de onde o Registro as IMPÕE: a restrição
// `posicao_dentro_da_cota` de `registro.decisao_imovel` (001_registro.sql). O console
// não redeclara 475/6.495 em TypeScript — seria uma segunda fonte da verdade para uma
// quantidade governada por invariante, o mesmo motivo pelo qual `contrato.ts` importa
// um JSON gerado em vez de digitar faixas. Enquanto não existe `registro.contrato`
// (fatia B2 do plano), o teto que o banco recusa ultrapassar é a leitura honesta.

import { db } from "./db";
import type { Consulta } from "./operacao";

export type Cotas = { superDestaque: number; destaque: number };

const padrao: Consulta = async (sql, params) => {
  const r = await db().query(sql, params as never[]);
  return { rows: r.rows as never[] };
};

/** Extrai as cotas do texto da restrição, como o Postgres o devolve:
 *  `(nivel = 'super_destaque'::text) AND ((posicao_ranking >= 1) AND (posicao_ranking <= 475))`.
 *  Pura, para ser testável sem banco. `null` se o texto não tiver as DUAS cotas —
 *  metade de uma cota não é cota. */
export function cotasDe(definicao: string): Cotas | null {
  const cota = (nivel: string): number | null => {
    const re = new RegExp(
      `nivel = '${nivel}'::text\\)[^)]*\\)?[^<]*posicao_ranking <= ([0-9]+)`,
    );
    const m = re.exec(definicao);
    return m ? Number(m[1]) : null;
  };
  const superDestaque = cota("super_destaque");
  const destaque = cota("destaque");
  if (superDestaque === null || destaque === null) return null;
  return { superDestaque, destaque };
}

/** As cotas vigentes no Registro; `null` se a restrição não existir ou não parsear —
 *  a tela diz "sem cota lida", nunca inventa. */
export async function cotasDoRegistro(exec: Consulta = padrao): Promise<Cotas | null> {
  const { rows } = await exec<{ def: string }>(
    "SELECT pg_get_constraintdef(c.oid) AS def FROM pg_constraint c " +
      "JOIN pg_class t ON t.oid = c.conrelid JOIN pg_namespace n ON n.oid = t.relnamespace " +
      "WHERE n.nspname = 'registro' AND t.relname = 'decisao_imovel' " +
      "AND c.conname = 'posicao_dentro_da_cota'",
  );
  return rows.length ? cotasDe(rows[0].def) : null;
}
