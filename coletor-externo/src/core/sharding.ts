// Sharding recursivo — genérico. Portado de imovelweb-ativos/src/sharding.ts.
// O portal só existe atrás do `probe`: dado um conjunto de tokens, o probe
// devolve a contagem e os facets; este módulo não conhece endpoint nem shape.

import { config } from './config';
import { FacetBucket, Shard } from './types';

interface FacetEntry {
  facetName?: string;
  values?: Record<string, number>;
}

/** Probe agnóstico de transporte: tokens → contagem + facets da listagem. */
export type ListProbe = (tokens: string[]) => Promise<{ numberOfPostings: number; facets: unknown }>;

/**
 * Extrai o código antes da vírgula de uma chave de facet.
 * Muitos painéis rotulam o bucket como "CÓDIGO, Rótulo legível" e o filtro usa
 * só o código. Se não houver vírgula, devolve a chave inteira (já é o código).
 */
export function codeBeforeComma(key: string): string {
  const i = key.indexOf(',');
  return (i >= 0 ? key.slice(0, i) : key).trim();
}

/**
 * Extrai os buckets de uma dimensão a partir do facet de mesmo `facetName`.
 * Aceita facets como array de {facetName, values} ou como objeto indexado.
 * O formato exato de cada portal é responsabilidade do adapter; este é o
 * formato comum (confirme no reconhecimento de cada portal novo).
 */
export function extractFacetBuckets(facets: unknown, dimension: string): FacetBucket[] {
  const entries: FacetEntry[] = Array.isArray(facets)
    ? (facets as FacetEntry[])
    : (Object.values((facets as Record<string, unknown>) || {}) as FacetEntry[]);

  const entry = entries.find((e) => e && e.facetName === dimension && e.values);
  if (!entry || !entry.values) return [];

  return Object.entries(entry.values)
    .map(([key, count]) => ({ value: codeBeforeComma(key), count: Number(count) }))
    .filter((b) => b.value && Number.isFinite(b.count));
}

/**
 * Constrói shards recursivamente: enquanto o shard estimado > shardMax, drilla
 * a próxima dimensão. `probe` abstrai o transporte; `dimensions` vem do adapter
 * do portal (ex.: região → tipo → cidade).
 */
export async function buildShards(
  probe: ListProbe,
  dimensions: string[],
  log: (msg: string) => void
): Promise<Shard[]> {
  const shards: Shard[] = [];
  let loggedRawFacets = false;

  async function recurse(tokens: string[], dimIndex: number): Promise<void> {
    const disc = await probe(tokens);
    const est = disc.numberOfPostings;
    const label = tokens.length ? tokens.join(';') : '(raiz)';

    if (!loggedRawFacets) {
      loggedRawFacets = true;
      log(`Facets crus (confira o mapeamento de dimensões): ${JSON.stringify(disc.facets).slice(0, 1500)}`);
    }

    if (est <= config.shardMax) {
      shards.push({ label, tokens: [...tokens], estimated: est });
      log(`Shard OK [${label}] estimado=${est}`);
      return;
    }

    if (dimIndex >= dimensions.length) {
      shards.push({ label, tokens: [...tokens], estimated: est });
      log(`ATENÇÃO: shard [${label}] estimado=${est} > shardMax e sem mais dimensões — pode truncar.`);
      return;
    }

    const dim = dimensions[dimIndex];
    const buckets = extractFacetBuckets(disc.facets, dim);
    if (!buckets.length) {
      log(`Sem buckets para "${dim}" em [${label}] — tentando próxima dimensão.`);
      await recurse(tokens, dimIndex + 1);
      return;
    }

    log(`Drillando [${label}] por "${dim}": ${buckets.length} buckets.`);
    for (const b of buckets) {
      await recurse([...tokens, `${dim}:${b.value}`], dimIndex + 1);
    }
  }

  await recurse([], 0);
  log(`Total de shards: ${shards.length}`);
  // Menor → maior: o CSV cresce cedo e o shard gigante fica por último.
  // Desempate por label para ordem total (CSV byte-idêntico entre execuções).
  return shards.sort((a, b) => a.estimated - b.estimated || a.label.localeCompare(b.label));
}
