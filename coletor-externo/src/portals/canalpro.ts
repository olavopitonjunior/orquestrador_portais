// Adapter do Canal Pro (Grupo OLX/ZAP) — STUB de bootstrap.
//
// Este arquivo é intencionalmente não funcional: a implementação real depende
// do RECONHECIMENTO do painel do Canal Pro (mapear a API interna, o header de
// sessão, os shapes de nota/visualizações e o código de amarração com o imóvel
// interno), que acontece com o operador logado uma vez no Chrome real. Até lá,
// todo método lança NotImplementedError — a coleta falha ruidosamente aqui, em
// vez de "ter sucesso" com zero anúncios.
//
// Ver docs/decisoes.md D-010 (transporte CDP) e o README deste diretório.

import { Page } from 'puppeteer-core';
import { Anuncio, NotImplementedError, Portal } from '../portal';

const ID = 'canalpro';

export const canalPro: Portal = {
  id: ID,
  host: 'canalpro.grupozap.com',
  panelUrl: 'https://canalpro.grupozap.com/',
  // Dimensões a confirmar no reconhecimento — placeholders declarados como pendência.
  shardDimensions: [],
  csvColumns: ['idPortal', 'codigoImovel', 'nota', 'visualizacoes', 'cliques', 'url'],

  async captureSessionId(_page: Page): Promise<string> {
    throw new NotImplementedError(ID, 'captureSessionId');
  },

  async probeList(_page: Page, _sessionId: string, _tokens: string[]): Promise<{ numberOfPostings: number; facets: unknown }> {
    throw new NotImplementedError(ID, 'probeList');
  },

  async collectShard(_page: Page, _sessionId: string, _tokens: string[], _limite?: number): Promise<Anuncio[]> {
    throw new NotImplementedError(ID, 'collectShard');
  },

  rowToCells(anuncio: Anuncio): unknown[] {
    // O mapeamento é trivial e determinístico; mantido implementado para o CsvWriter
    // ter contrato completo. A obtenção do `anuncio` é que depende do reconhecimento.
    return [anuncio.idPortal, anuncio.codigoImovel, anuncio.nota, anuncio.visualizacoes, anuncio.cliques, anuncio.url];
  },

  async readBlocked(_page: Page): Promise<boolean> {
    throw new NotImplementedError(ID, 'readBlocked');
  },
};
