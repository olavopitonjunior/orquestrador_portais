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

/** Versão do contrato de checkpoint. Um checkpoint SEM este campo foi escrito pela
 *  versão que não apagava o progresso ao concluir: retomá-lo é o defeito, não a
 *  intenção. Quem lê trata a ausência como "corrida nova". */
export const CONTRATO_CHECKPOINT = 2;

/** Estado de retomada de uma coleta full, persistido por shard concluído.
 *
 *  `contrato`, `portal` e `modo` existem para que a retomada só aconteça sobre a
 *  MESMA coisa. O caminho do arquivo é `out/progress.json`, sem o portal no nome:
 *  sem estes campos, um `--portal=x` retomaria o progresso de um `--portal=y`. */
export interface Checkpoint {
  startedAt: string;
  completedShards: string[];
  seenCount: number;
  rowsWritten: number;
  lastUpdate: string;
  /** última página COMPLETA (paginação linear) — retomada continua de lastPage+1 */
  lastPage?: number;
  /** ausente ⇒ escrito pela versão antiga; ver CONTRATO_CHECKPOINT */
  contrato?: number;
  portal?: string;
  modo?: 'full';
}

/** Um bucket de facet: o valor da dimensão e sua contagem. */
export interface FacetBucket {
  value: string;
  count: number;
}
