// Interface do adapter de portal — a fronteira entre o núcleo genérico e tudo
// que é específico de um portal (endpoints, header de sessão, shapes, colunas).
// O núcleo (core/) e o transporte (cdp/) só falam com esta interface; trocar de
// portal é implementar outro Portal, sem tocar no núcleo.

import { Page } from 'puppeteer-core';
import { InPageResponse } from './core/types';

/** Um anúncio já normalizado pelo adapter, no contrato de saída do produto. */
export interface Anuncio {
  /** identificador do anúncio no portal */
  idPortal: string;
  /** código de amarração com o imóvel interno do Newcore (Spec §5: "amarrada por imóvel") */
  codigoImovel: string | null;
  /** nota atribuída pelo portal (0–100 ou escala do portal) */
  nota: number | null;
  visualizacoes: number | null;
  cliques: number | null;
  url: string | null;
}

export interface Portal {
  /** identificador do adapter, ex.: "canalpro" */
  readonly id: string;
  /** fragmento de host para reconhecer a aba já aberta no Chrome real */
  readonly host: string;
  /** URL do painel autenticado */
  readonly panelUrl: string;
  /** dimensões de sharding, da mais separadora para a menos, ex.: ["regiao","tipo","cidade"] */
  readonly shardDimensions: string[];
  /** colunas do CSV de saída, na ordem de `rowToCells` */
  readonly csvColumns: string[];

  /** Captura o identificador de sessão a partir da página autenticada. */
  captureSessionId(page: Page): Promise<string>;

  /** Sonda uma listagem (para o sharding): tokens → contagem + facets. */
  probeList(page: Page, sessionId: string, tokens: string[]): Promise<{ numberOfPostings: number; facets: unknown }>;

  /**
   * Coleta uma fatia (um shard) e devolve os anúncios normalizados.
   * `limite` (opcional) para a coleta ao atingir N anúncios — usado pelo canário
   * como portão progressivo, sem baixar o shard inteiro a cada degrau.
   */
  collectShard(page: Page, sessionId: string, tokens: string[], limite?: number): Promise<Anuncio[]>;

  /** Serializa um anúncio nas células do CSV (mesma ordem de csvColumns). */
  rowToCells(anuncio: Anuncio): unknown[];

  /** Detecta bloqueio/desafio na página atual (marcadores do portal + Cloudflare). */
  readBlocked(page: Page): Promise<boolean>;
}

/** Lançada por adapters ainda não implementados — falha RUIDOSA, nunca resultado vazio. */
export class NotImplementedError extends Error {
  constructor(portalId: string, method: string) {
    super(
      `Portal "${portalId}": ${method} ainda não implementado. ` +
        `Este é um stub de bootstrap — o adapter real vem do reconhecimento do portal ` +
        `(ver README › Estado). Rodar a coleta agora deve falhar aqui, não devolver lista vazia.`
    );
    this.name = 'NotImplementedError';
  }
}

/** Contrato mínimo que o núcleo espera de qualquer resposta de listagem. */
export type ListResponse = InPageResponse<{ numberOfPostings: number; facets: unknown }>;
