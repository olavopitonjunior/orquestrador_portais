// Interface do adapter de portal — a fronteira entre o núcleo genérico e tudo
// que é específico de um portal (endpoints, sessão, shapes, colunas, paginação).
// O núcleo (core/) e o transporte (cdp/) só falam com esta interface; trocar de
// portal é implementar outro Portal, sem tocar no núcleo.

import { Page } from 'puppeteer-core';

/**
 * Um anúncio já normalizado pelo adapter, no contrato de saída do produto
 * (Spec §5: nota, visualizações, cliques, URL, amarrado por imóvel).
 *
 * Invariante 3 (defesa em profundidade): este contrato carrega SÓ performance
 * de portal e a amarração — nunca endereço, geolocalização, imagens ou
 * identidade/contato de lead. O CSV alimenta o Analista de Perfil, que usa
 * modelo; não puxar dado pessoal na fonte é o que impede o vazamento a jusante.
 * As contagens de interação são agregadas por anúncio (não identidades).
 */
export interface Anuncio {
  /** identificador do anúncio no portal */
  idPortal: string;
  /** código de amarração com o imóvel interno do Newcore (externalId) */
  codigoImovel: string | null;
  /** nota do portal, CRUA (sem reescala — a normalização é o parâmetro pendente nº 2) */
  nota: number | null;
  /** nome/versão da nota do portal (ex.: "lqsBeta") */
  notaNome: string | null;
  /** nível de publicação no portal (ex.: STANDARD/PREMIUM) */
  nivel: string | null;
  /** situação do anúncio (ex.: ACTIVE) */
  situacao: string | null;
  /** preço anunciado, em reais */
  preco: number | null;
  /** portais em que o anúncio está (ex.: OLX, VIVAREAL, ZAP) */
  portais: string[] | null;
  /** data de criação do anúncio no portal, como o portal a devolve */
  criadoEm: string | null;
  /** visualizações agregadas */
  visualizacoes: number | null;
  // Cliques por TIPO, separados — não somar aqui: são intenções distintas, e a
  // combinação é decisão de quem calcula o fator "desempenho próprio" do ranking.
  cliqueContato: number | null;
  cliqueTelefone: number | null;
  cliqueProposta: number | null;
  cliqueWhatsapp: number | null;
  cliqueAgendamento: number | null;
  /** URL do anúncio no portal — não vem na listagem do Canal Pro (lacuna registrada) */
  url: string | null;
}

/**
 * Sessão do portal — OPACA ao núcleo. O núcleo a captura e a repassa a
 * probeList/collectShard/collectPage sem nunca inspecioná-la; cada adapter
 * define seu formato (o Canal Pro guarda um conjunto de headers de auth).
 * É segredo de sessão: nunca vai a log, status.json, checkpoint, CSV ou fixture.
 */
export type Sessao = unknown;

export interface Portal {
  /** identificador do adapter, ex.: "canalpro" */
  readonly id: string;
  /** fragmento de host para reconhecer a aba já aberta no Chrome real */
  readonly host: string;
  /** URL do painel autenticado */
  readonly panelUrl: string;
  /** dimensões de sharding, da mais separadora para a menos; vazio = paginação linear */
  readonly shardDimensions: string[];
  /** colunas do CSV de saída, na ordem de `rowToCells` */
  readonly csvColumns: string[];
  /** anúncios por página (paginação linear); ausente = modelo de shards por facets */
  readonly pageSize?: number;

  /** Captura a sessão a partir da página autenticada (tipo opaco definido pelo adapter). */
  captureSessionId(page: Page): Promise<Sessao>;

  /** Sonda uma listagem: tokens → contagem total + facets (para sharding e/ou total de páginas). */
  probeList(
    page: Page,
    sessao: Sessao,
    tokens: string[]
  ): Promise<{ numberOfPostings: number; facets: unknown }>;

  /**
   * Coleta uma fatia (um shard) e devolve os anúncios normalizados.
   * `limite` (opcional) para a coleta ao atingir N anúncios — usado pelo canário
   * como portão progressivo.
   */
  collectShard(page: Page, sessao: Sessao, tokens: string[], limite?: number): Promise<Anuncio[]>;

  /**
   * Coleta UMA página (paginação linear). Presente só em portais paginados;
   * quando existe, o `run.ts` faz checkpoint por página (retomada sem re-bater
   * o portal do início — condição anti-bot). `pageNumber` é 1-indexado.
   */
  collectPage?(page: Page, sessao: Sessao, pageNumber: number): Promise<Anuncio[]>;

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
