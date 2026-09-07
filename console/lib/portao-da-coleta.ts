import type { Amarracao, SaudeColeta } from "./coletor";

// O PORTÃO da coleta completa, extraído de `app/coleta/page.tsx` para poder ser
// testado. Um full são horas de raspagem sobre um login manual; se o CSV que sair
// dali não amarrar com o Newcore, o custo é a semana inteira. O canário custa
// segundos e decide isso antes.
//
// Por que virou módulo: na fatia anterior um agregado escondido dentro de
// `page.tsx` produziu "0 por relaxamento" em vez de 116, e a lição registrada foi
// que lógica dentro de página não tem teste e por isso não tem rede. Este portão é
// decisão de verdade — diz quando NÃO raspar —, então mora onde se prova.

/** Por que a coleta completa está barrada, ou `null` se está liberada.
 *
 *  A ORDEM importa: cada motivo pressupõe que os anteriores foram vencidos, e o
 *  primeiro que casar é o que o operador lê. O soluço vem logo depois do Chrome
 *  porque é o único motivo cuja resposta é "dispare de novo" em vez de "conserte
 *  algo" — e esta página é o destino para onde a caixa de ações e a prontidão
 *  mandam quem acabou de ler exatamente isso. */
export function motivoParaNaoRodarFull(entrada: {
  chromeNoAr: boolean;
  saude: SaudeColeta | null;
  canarioOk: unknown | null;
  amarracao: Amarracao | null;
}): string | null {
  const { chromeNoAr, saude, canarioOk, amarracao } = entrada;
  if (!chromeNoAr) return "o Chrome de depuração não está no ar.";
  if (saude?.estado === "error" && saude.repetivel) {
    // Repetir aqui o estado cru `error` mandaria o operador procurar defeito onde
    // não há: o portal soluçou, e a resposta é disparar de novo.
    return "a última coleta esbarrou num soluço do portal. Dispare o canário de novo: costuma passar na tentativa seguinte.";
  }
  // `status.json` é reescrito por cada coleta, então "ok" é o da ÚLTIMA: um bloqueio
  // posterior a um canário bom derruba o portão, e deve mesmo.
  if (saude?.estado !== "ok") return `a última coleta está '${saude?.estado ?? "?"}', não 'ok'.`;
  if (canarioOk === null) return "nenhum canário disparado pelo console terminou com sucesso ainda.";
  if (amarracao === null) return "não há CSV em out/ para medir a amarração.";
  if (amarracao.noFormato === 0) {
    return "o CSV em out/ não tem nenhum codigoImovel no formato {Id}{letra}: raspar em volume não conserta isso.";
  }
  return null;
}
