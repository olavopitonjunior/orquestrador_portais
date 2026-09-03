"use server";

// Casca fina: enfileira, e nada mais. Quem executa é o trabalhador, num processo
// separado — o console NUNCA executa processo. Disparar por `spawn` dentro de uma
// requisição daria um filho que morre no recarregamento do servidor e uma linha
// "executando" eterna, porque não haveria quem observasse a transição.

import { redirect } from "next/navigation";

import { TrabalhoEmVoo, criarTrabalho, ultimosParametros } from "@/lib/operacao";

export type RespostaDisparo = { ok: false; erro: string };

export async function dispararSexta(
  por: string,
  dryRun: boolean,
  declaracaoVista: number | null,
): Promise<RespostaDisparo> {
  const declaracao = await ultimosParametros();

  // A declaração que DISPARA precisa ser a que o dono VIU. A tela lê uma vez, no
  // servidor, e mostra "vai rodar com a declaração nº X"; sem esta conferência, a ação
  // lia de novo no clique e podia enfileirar a nº X+1 — submetida noutra aba, ou por
  // outra pessoa, no intervalo. A rodada citaria fielmente a nº X+1 como declarada, e a
  // aprovação humana que esta tela existe para capturar nunca teria acontecido para
  // AQUELE conteúdo. É o "peso inventado numa planilha aprovada", mudado de arquivo
  // para versão. Recusa, e não substitui em silêncio.
  if (declaracao !== null && declaracaoVista !== null && declaracao.id !== declaracaoVista) {
    return {
      ok: false,
      erro:
        `os parâmetros mudaram enquanto esta tela estava aberta: você viu a declaração ` +
        `nº ${declaracaoVista} e a mais recente agora é a nº ${declaracao.id}. Recarregue ` +
        `e confira antes de disparar.`,
    };
  }

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
