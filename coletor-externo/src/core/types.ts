// Tipos genéricos do núcleo do coletor — agnósticos de portal.
// Os shapes de resposta de cada portal (cartão de anúncio, qualidade, stats)
// vivem no adapter do portal, nunca aqui.

/** Resposta padronizada de um fetch feito DENTRO da página autenticada (CDP). */
export interface InPageResponse<T = unknown> {
  ok: boolean;
  status: number;
  contentType: string;
  json: T | null;
  /** primeiros ~200 chars do corpo quando não-JSON — insumo da classificação de bloqueio */
  bodySnippet: string | null;
}

/** Um shard = um conjunto de tokens de busca que produz uma fatia raspável (≤ shardMax). */
export interface Shard {
  /** rótulo legível, ex.: "regiao:R1;tipo:2" */
  label: string;
  /** tokens além do filtro-base, ex.: ["regiao:R1", "tipo:2"] */
  tokens: string[];
  /** contagem estimada via facets (pode capar no teto do portal antes do drill) */
  estimated: number;
}

/** Estado de retomada de uma coleta full, persistido por shard concluído. */
export interface Checkpoint {
  startedAt: string;
  completedShards: string[];
  seenCount: number;
  rowsWritten: number;
  lastUpdate: string;
}

/** Um bucket de facet: o valor da dimensão e sua contagem. */
export interface FacetBucket {
  value: string;
  count: number;
}
