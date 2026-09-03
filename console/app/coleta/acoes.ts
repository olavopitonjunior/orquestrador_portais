"use server";

// Casca fina: enfileira, e nada mais — quem raspa é o trabalhador, que roda
// `npm run canary|full` em `coletor-externo/`. O console nunca executa processo.

import { redirect } from "next/navigation";

import { TrabalhoEmVoo, criarTrabalho } from "@/lib/operacao";

export type RespostaColeta = { ok: false; erro: string };

// Mesma gramática que o trabalhador aceita para CANARY_STEPS: inteiros separados
// por vírgula. Validado AQUI e LÁ: aqui para a mensagem chegar a quem clicou, lá
// porque `argumentos` também pode ser escrito à mão.
const PASSOS_VALIDOS = /^\d+(,\d+)*$/;

export async function dispararColeta(
  tipo: "canario" | "full",
  passos: string,
  por: string,
): Promise<RespostaColeta> {
  if (tipo !== "canario" && tipo !== "full") {
    return { ok: false, erro: "tipo de coleta desconhecido." };
  }
  const argumentos: Record<string, unknown> = {};
  if (tipo === "canario") {
    // Server action é chamável com qualquer payload: string é pré-condição, não tipo.
    const p = typeof passos === "string" ? passos.replace(/\s/g, "") : "";
    if (!PASSOS_VALIDOS.test(p)) {
      return {
        ok: false,
        erro: "os passos do canário precisam ser inteiros separados por vírgula, ex.: 1,10,100.",
      };
    }
    argumentos.canary_steps = p;
  }
  let id: number;
  try {
    id = await criarTrabalho(tipo, argumentos, por || null);
  } catch (e) {
    if (e instanceof TrabalhoEmVoo) return { ok: false, erro: e.message };
    console.error("[console] falha ao enfileirar a coleta:", e);
    return { ok: false, erro: "não foi possível enfileirar. Verifique se o Postgres está no ar." };
  }
  redirect(`/trabalho/${id}`);
}
