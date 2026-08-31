// Conexão CDP ao Chrome real — genérica. Portado de imovelweb-ativos/src/cdp/browser.ts.
// NÃO lança Chrome via chromedriver (que o Cloudflare detecta): anexa a um Chrome
// já aberto pelo operador com --remote-debugging-port, herdando o perfil real
// (sessão + cf_clearance já presentes). Nunca chama browser.close() — é o Chrome
// do usuário; ao final, apenas browser.disconnect().

import puppeteer, { Browser, Page } from 'puppeteer-core';
import { config } from '../core/config';
import { Portal } from '../portal';

export async function connectRealChrome(portal: Portal): Promise<{ browser: Browser; page: Page }> {
  const browserURL = `http://127.0.0.1:${config.cdpPort}`;
  let browser: Browser;
  try {
    browser = await puppeteer.connect({ browserURL, defaultViewport: null });
  } catch (e) {
    throw new Error(
      `Não consegui conectar ao Chrome em ${browserURL}. ` +
        `Feche o Chrome e reabra com --remote-debugging-port=${config.cdpPort} ` +
        `(ver README › "Fluxo do operador"). Detalhe: ${e instanceof Error ? e.message : String(e)}`
    );
  }

  // Reusa uma aba já no portal, se houver; senão abre uma nova.
  const pages = await browser.pages();
  let page = pages.find((p) => p.url().includes(portal.host)) || null;
  if (!page) {
    page = await browser.newPage();
  }
  return { browser, page };
}

export async function gotoPanel(page: Page, portal: Portal, log: (msg: string) => void = () => {}): Promise<void> {
  if (!page.url().startsWith(portal.panelUrl)) {
    await page.goto(portal.panelUrl, { waitUntil: 'networkidle2', timeout: 60_000 }).catch((e) => {
      // Não aborta aqui: a captura de sessão a seguir dá o erro definitivo,
      // mas registra o motivo para o diagnóstico não ficar cego.
      log(`Aviso: navegação ao painel falhou (${e instanceof Error ? e.message : String(e)}).`);
    });
  }
}

export function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}
