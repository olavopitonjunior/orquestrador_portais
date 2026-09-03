"use server";

// Casca fina: enfileira, e nada mais. Quem executa é o trabalhador, num processo
// separado — o console NUNCA executa processo. Disparar por `spawn` dentro de uma
// requisição daria um filho que morre no recarregamento do servidor e uma linha
// "executando" eterna, porque não haveria quem observasse a transição.

import { redirect } from "next/navigation";

import { TrabalhoEmVoo, criarTrabalho, ultimosParametros } from "@/lib/operacao";

export type RespostaDisparo = { ok: false; erro: string };

export async function dispararSexta(por: string, dryRun: boolean): Promise<RespostaDisparo> {
  const declaracao = await ultimosParametros();
  if (declaracao === null) {
    return {
      ok: false,
      erro: "não há parâmetros declarados. Preencha o formulário antes — a rodada recusa "
        + "rodar sem eles, e isso é proteção: peso inventado numa planilha aprovada é invisível.",
    };
  }

  let id: number;
  try {
    // Vai o ID da declaração, não o caminho de um arquivo. O trabalhador materializa o
    // TOML na hora de rodar, e a `origem` que viaja para a planilha e para o Registro
    // passa a carregar o id do trabalho — reconstituível mesmo se o arquivo sumir, e
    // sobretudo quando a rodada ABORTA, que não deixa linha nenhuma no Registro.
    id = await criarTrabalho(
      "sexta",
      { parametros_declarados_id: declaracao.id, dry_run: dryRun },
      por || null,
    );
  } catch (e) {
    if (e instanceof TrabalhoEmVoo) return { ok: false, erro: e.message };
    console.error("[console] falha ao enfileirar a sexta:", e);
    return { ok: false, erro: "não foi possível enfileirar. Verifique se o Postgres está no ar." };
  }
  redirect(`/trabalho/${id}`);
}
