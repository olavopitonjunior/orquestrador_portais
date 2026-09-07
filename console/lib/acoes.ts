import type { SaudeColeta } from "./coletor";
import type { RodadaResumo } from "./registro";

// Deriva a "caixa de ações" — o que precisa da sua atenção agora — a partir do
// estado já lido (saúde da coleta, rodadas sem aprovação, parâmetros pendentes).
// Função PURA: quem busca os dados é a página; aqui só se compõe (testável sem I/O).

export type Severidade = "acao" | "aviso" | "info";

export type Acao = {
  id: string;
  severidade: Severidade;
  titulo: string;
  descricao: string;
  detalhe?: string; // passos, quando houver (ex.: runbook de login)
  href?: string; // para onde o botão leva; sem href, a ação é só aviso
  rotulo?: string; // o texto do botão
};

const PASSOS_LOGIN =
  "1. Feche o Chrome. 2. Reabra com --remote-debugging-port=9222 e as flags anti-throttling. " +
  "3. Faça login no Canal Pro (resolve o Cloudflare como humano). 4. Rode o coletor de novo. " +
  "A flag NEEDS_WARM some quando a próxima coleta autentica.";

export function montarAcoes(
  saude: SaudeColeta,
  aguardando: RodadaResumo[],
  parametrosPendentes: number,
): Acao[] {
  const acoes: Acao[] = [];

  // `needsWarm` já implica estado "blocked" (ver coletor.ts) — a fonte única da
  // verdade é o estado. Cada falha da coleta vira UMA ação, nunca fica muda: é o
  // propósito da caixa (o operador não pode deixar de saber que algo trava a sexta).
  if (saude.estado === "blocked") {
    acoes.push({
      id: "login-portal",
      severidade: "acao",
      titulo: "Refaça o login no Canal Pro",
      descricao:
        "A sessão do raspador caiu (Cloudflare). Sem re-login, a rodada de sexta fica " +
        "sem desempenho de portal e degrada.",
      detalhe: PASSOS_LOGIN,
      href: "/coleta",
      rotulo: "Abrir a coleta",
    });
  } else if (saude.estado === "error" && saude.repetivel) {
    // Falha repetível é a ÚNICA cuja resposta é simplesmente rodar de novo, e mandar
    // essa pessoa ler log é mandá-la ao lugar errado. Em 06/09 a coleta completa
    // morreu em 10 s por um soluço do portal; a segunda tentativa, um minuto depois,
    // levou 13 minutos e trouxe 55.162 anúncios. A sexta tem tentativa única.
    acoes.push({
      id: "coleta-repetivel",
      severidade: "acao",
      titulo: "A coleta esbarrou num soluço do portal — rode de novo",
      descricao:
        "O Canal Pro respondeu de um jeito que costuma passar na tentativa seguinte: " +
        "não alcançou a própria API, recusou por excesso de requisições ou entregou " +
        "resposta pela metade. Não é bloqueio de sessão nem defeito do raspador. O " +
        "sistema não repete sozinho — quantas vezes tentar e com que intervalo é " +
        "decisão sua (parâmetro nº 4, ainda sem valor).",
      href: "/coleta",
      rotulo: "Abrir a coleta",
    });
  } else if (saude.estado === "error") {
    acoes.push({
      id: "coleta-erro",
      severidade: "acao",
      titulo: "A coleta externa falhou",
      descricao:
        "A última coleta terminou em erro (não é bloqueio de sessão). Veja os logs do " +
        "raspador antes da rodada de sexta — sem coleta, a rodada degrada.",
      href: "/coleta",
      rotulo: "Abrir a coleta",
    });
  } else if (saude.estado === "em_curso") {
    acoes.push({
      id: "coleta-em-curso",
      severidade: "aviso",
      titulo: "A coleta completa está rodando",
      descricao:
        "O raspador declarou uma coleta completa em andamento. O CSV está sendo " +
        "reescrito: uma rodada disparada agora leria dado pela metade, então espere " +
        "ela fechar antes da sexta.",
      href: "/coleta",
      rotulo: "Abrir a coleta",
    });
  } else if (saude.estado === "corrompido") {
    acoes.push({
      id: "coleta-corrompida",
      severidade: "acao",
      titulo: "A coleta externa terminou pela metade",
      descricao:
        "O status da última coleta está ilegível (o raspador rodou e não fechou o " +
        "arquivo). Rode a coleta de novo antes da sexta.",
      href: "/coleta",
      rotulo: "Abrir a coleta",
    });
  }

  for (const r of aguardando) {
    acoes.push({
      id: `aprovar-${r.id}`,
      severidade: "acao",
      titulo: `Aprove a rodada ${r.id}`,
      descricao:
        // `?? ""` é defesa de tipo: o chamador (rodadasAguardandoAprovacao) já
        // filtra estado IN ('completa','degradada'), mas o tipo admite null.
        `Rodada de decisão ${r.estado ?? ""} aguardando sua aprovação (D-001). ` +
        "Enquanto não aprovada, a carga não deve ser aplicada.",
      href: `/rodada/${r.id}`,
      rotulo: "Ver a rodada",
    });
  }

  if (parametrosPendentes > 0) {
    acoes.push({
      id: "parametros-pendentes",
      severidade: "info",
      titulo: `${parametrosPendentes} parâmetros aguardam sua decisão`,
      descricao:
        "Parâmetros de decisão ainda nulos (nunca preenchidos com valor inventado). " +
        "A rodada roda com provisórios rotulados até você defini-los.",
      href: "/parametros",
      rotulo: "Definir",
    });
  }

  return acoes;
}
