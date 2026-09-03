// Saúde do Chrome de depuração remota — a pré-condição da raspagem (D-010).
//
// O raspador não tem login próprio: ele se anexa, por CDP, a um Chrome REAL em que o
// operador logou no Canal Pro. Esta leitura confere o que dá para conferir sem raspar:
// a porta de depuração responde? há uma aba do painel aberta? São dois booleanos, e
// só eles saem daqui — a lista de abas traz URLs completas, que podem carregar
// identificador de sessão, e a UI nunca as recebe.
//
// O que isto NÃO prova: que a sessão está autenticada. Só uma requisição ao portal
// prova isso, e é o canário quem a faz. A tela diz a diferença.

export type SaudeChrome = {
  noAr: boolean; // a porta de depuração respondeu a /json/version
  abaDoPainel: boolean | null; // há aba no host do painel; null = não deu para listar
};

// Cópia de `coletor-externo/src/portals/canalpro.ts` (`panelUrl`): os dois pacotes não
// se importam. Comparação por hostname EXATO — subdomínio parecido e `user@host` não casam.
const HOST_DO_PAINEL = "canal-pro.grupozap.com";
const TEMPO_LIMITE_MS = 1500;

/** A porta de depuração que o raspador usa (`CDP_PORT`, default 9222) — a mesma que
 *  a tela manda o operador abrir. */
export function portaCdp(): number {
  const p = Number(process.env.CDP_PORT);
  return Number.isInteger(p) && p > 0 ? p : 9222;
}

function hostDe(url: unknown): string | null {
  if (typeof url !== "string") return null;
  try {
    return new URL(url).hostname;
  } catch {
    return null;
  }
}

/** Nunca lança: Chrome fora do ar é um estado, não um erro. `fetchFn` é injetável
 *  para o teste não precisar de um Chrome. */
export async function saudeChrome(fetchFn: typeof fetch = fetch): Promise<SaudeChrome> {
  const base = `http://127.0.0.1:${portaCdp()}`;
  try {
    const v = await fetchFn(`${base}/json/version`, { signal: AbortSignal.timeout(TEMPO_LIMITE_MS) });
    if (!v.ok) return { noAr: false, abaDoPainel: null };
  } catch {
    return { noAr: false, abaDoPainel: null };
  }
  try {
    const l = await fetchFn(`${base}/json/list`, { signal: AbortSignal.timeout(TEMPO_LIMITE_MS) });
    const abas = (await l.json()) as unknown;
    if (!Array.isArray(abas)) return { noAr: true, abaDoPainel: null };
    const tem = abas.some((a) => hostDe((a as { url?: unknown })?.url) === HOST_DO_PAINEL);
    return { noAr: true, abaDoPainel: tem };
  } catch {
    return { noAr: true, abaDoPainel: null };
  }
}
