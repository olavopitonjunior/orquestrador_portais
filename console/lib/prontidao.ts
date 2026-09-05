// As condições da rodada de decisão e o veredito que a tela dá sobre elas. Função
// PURA sobre leituras que a página já faz (saúde da coleta, Chrome, trabalhador,
// parâmetros pendentes) — testável sem I/O, como `acoes.ts`.
//
// Regra de honestidade: leitura que falhou (`null`) NUNCA vira condição "ok". Vira
// "bad" com o texto dizendo o que não deu para ler.

import type { SaudeChrome } from "./chrome";
import type { SaudeColeta } from "./coletor";

export type Nivel = "ok" | "warn" | "bad";

export type Condicao = {
  titulo: "Coleta do portal" | "Sessão do Canal Pro" | "Trabalhador" | "Parâmetros";
  nivel: Nivel;
  texto: string;
  href?: string;
  rotulo?: string;
};

export type Veredito = {
  classe: string;
  texto: "não roda" | "sairá degradada" | "roda com provisórios" | "pronta";
  explicacao: string;
};

export function condicoes(
  saude: SaudeColeta | null,
  chrome: SaudeChrome | null,
  vivo: boolean | null,
  pendentes: number,
  totalParametros: number,
  formatarData: (iso: string) => string,
): Condicao[] {
  const coleta: Condicao = !saude
    ? { titulo: "Coleta do portal", nivel: "bad", texto: "Não foi possível ler os arquivos do coletor." }
    : saude.estado === "ok"
      ? {
          titulo: "Coleta do portal",
          nivel: "ok",
          texto: `${saude.coletadoEm ? `Coletada ${formatarData(saude.coletadoEm)}` : "Sem data de coleta"}${
            saude.idadeDias !== null ? ` · ${saude.idadeDias} dia(s)` : ""
          }${saude.linhas !== null ? ` · ${saude.linhas.toLocaleString("pt-BR")} anúncios` : ""}.`,
        }
      : saude.estado === "ausente"
        ? {
            titulo: "Coleta do portal",
            nivel: "warn",
            texto:
              "Nenhuma coleta em disco. Sem ela a nota do anúncio não ordena a lista e a rodada sai degradada.",
            href: "/coleta",
            rotulo: "Coletar",
          }
        : {
            titulo: "Coleta do portal",
            nivel: "bad",
            texto:
              saude.estado === "blocked"
                ? "A sessão do raspador caiu (Cloudflare). Refaça o login antes de coletar."
                : saude.estado === "error"
                  ? "A última coleta terminou em erro. Veja o log do raspador."
                  : "A última coleta ficou pela metade: o status está ilegível.",
            href: "/coleta",
            rotulo: "Abrir a coleta",
          };

  // O que dá para saber sem raspar: porta responde, aba do painel aberta, sem flag de
  // re-login. Só o canário prova autenticação — o texto do "ok" diz isso.
  const sessao: Condicao = !chrome
    ? { titulo: "Sessão do Canal Pro", nivel: "bad", texto: "Não foi possível consultar o Chrome de depuração." }
    : !chrome.noAr
      ? {
          titulo: "Sessão do Canal Pro",
          nivel: "bad",
          texto: "O Chrome de depuração está fora do ar. A raspagem se anexa a ele e não tem login próprio.",
          href: "/coleta",
          rotulo: "Como abrir",
        }
      : chrome.abaDoPainel === null
        ? {
            titulo: "Sessão do Canal Pro",
            nivel: "bad",
            texto: "O Chrome respondeu, mas não deixou listar as abas: não dá para saber se o painel está aberto.",
          }
        : chrome.abaDoPainel === false
          ? {
              titulo: "Sessão do Canal Pro",
              nivel: "warn",
              texto: "Chrome no ar, mas sem aba do painel do Canal Pro aberta. Abra e faça o login.",
            }
          : saude?.needsWarm
            ? {
                titulo: "Sessão do Canal Pro",
                nivel: "bad",
                texto: "A sessão pediu re-login (NEEDS_WARM).",
                href: "/coleta",
                rotulo: "Refazer login",
              }
            : {
                titulo: "Sessão do Canal Pro",
                nivel: "ok",
                texto:
                  "Chrome de depuração no ar com a aba do painel aberta. Só o canário prova que está autenticada.",
              };

  const trabalhador: Condicao =
    vivo === null
      ? { titulo: "Trabalhador", nivel: "bad", texto: "Não foi possível ler o batimento do trabalhador." }
      : vivo
        ? { titulo: "Trabalhador", nivel: "ok", texto: "Batendo ponto. É ele quem executa o que você dispara aqui." }
        : {
            titulo: "Trabalhador",
            nivel: "bad",
            texto: "Sem trabalhador no ar: nada que você disparar vai rodar até subir o rodada-trabalhador.",
          };

  const parametros: Condicao =
    pendentes === 0
      ? { titulo: "Parâmetros", nivel: "ok", texto: "Todos definidos por você." }
      : {
          titulo: "Parâmetros",
          nivel: "warn",
          texto: `${pendentes} de ${totalParametros} ainda sem valor. A rodada usa provisórios rotulados; nada é inventado.`,
          href: "/parametros",
          rotulo: "Definir",
        };

  return [coleta, sessao, trabalhador, parametros];
}

/** Sem trabalhador nada executa; qualquer fonte externa fora → degradada; só
 *  parâmetros pendentes → roda com provisórios (a planilha os rotula); tudo ok → pronta. */
export function veredito(cs: Condicao[]): Veredito {
  const prontas = cs.filter((c) => c.nivel === "ok").length;
  const contagem = `${prontas} de ${cs.length} condições prontas`;
  const trabalhador = cs.find((c) => c.titulo === "Trabalhador");
  if (trabalhador && trabalhador.nivel !== "ok")
    return { classe: "pill pill-bad", texto: "não roda", explicacao: `${contagem} · sem trabalhador, nada executa` };
  if (cs.some((c) => c.titulo !== "Parâmetros" && c.nivel !== "ok"))
    return {
      classe: "pill pill-warn",
      texto: "sairá degradada",
      explicacao: `${contagem} · a rodada corre, mas declara limitações`,
    };
  if (cs.some((c) => c.nivel !== "ok"))
    return {
      classe: "pill pill-warn",
      texto: "roda com provisórios",
      explicacao: `${contagem} · a planilha rotula os valores provisórios`,
    };
  return { classe: "pill pill-ok", texto: "pronta", explicacao: contagem };
}
