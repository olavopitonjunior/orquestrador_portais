"use server";

// Casca fina: enfileira, e nada mais. Quem executa é o trabalhador, num processo
// separado — o console NUNCA executa processo. Disparar por `spawn` dentro de uma
// requisição daria um filho que morre no recarregamento do servidor e uma linha
// "executando" eterna, porque não haveria quem observasse a transição.

import { redirect } from "next/navigation";

import { TrabalhoEmVoo, criarTrabalho, listarTrabalhos, ultimosParametros } from "@/lib/operacao";

export type RespostaDisparo = { ok: false; erro: string };

// Onde o raspador escreve, RELATIVO À RAIZ do repositório — que é o `cwd` que o
// trabalhador fixa para a rodada. É o mesmo diretório que `lib/coletor.ts` lê pelo
// caminho do console; os dois apontam para `coletor-externo/out` NAS CONFIGURAÇÕES
// PADRÃO. Há duas variáveis de sobrescrita que esta string ignora (`OUT_DIR` no
// raspador, `COLETOR_OUT_DIR` no console): quem definir uma delas passa a ter a tela
// olhando um diretório e a rodada lendo outro. Declarado; unificar é fatia própria.
const SAIDA_DO_RASPADOR = "coletor-externo/out";

export type ModoDisparo = "seco" | "real" | "completa";

async function declaracaoConferida(
  declaracaoVista: number | null,
): Promise<{ id: number } | RespostaDisparo> {
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
  return { id: declaracao.id };
}

const PASSOS_VALIDOS = /^\d+(,\d+)*$/;

export async function dispararSexta(
  por: string,
  modo: ModoDisparo,
  declaracaoVista: number | null,
  usarColeta: boolean,
  passosDoCanario: string,
): Promise<RespostaDisparo> {
  const conferida = await declaracaoConferida(declaracaoVista);
  if ("ok" in conferida) return conferida;

  // Vai o ID da declaração, não o caminho de um arquivo. O trabalhador materializa o
  // TOML na hora de rodar, e a `origem` que viaja para a planilha e para o Registro
  // passa a carregar o id do trabalho — reconstituível mesmo se o arquivo sumir, e
  // sobretudo quando a rodada ABORTA, que não deixa linha nenhuma no Registro.
  const base: Record<string, unknown> = { parametros_declarados_id: conferida.id };

  let id: number;
  try {
    if (modo === "completa") {
      // Um clique: raspa e, SE a raspagem terminar com 0, o trabalhador enfileira a
      // decisão apontando para o `out/`, recortada pela raspagem (rodada AMOSTRAL —
      // declarada, nunca COMPLETA, nunca aprovável). Se a raspagem falhar, a decisão
      // não roda e o log do canário diz por quê.
      //
      // A dedup do índice só protege o CANÁRIO neste clique; uma sexta já em voo só
      // colidiria horas depois, como evento de erro no pai. Lê a fila antes.
      const emVoo = (await listarTrabalhos(50)).find(
        (t) => t.tipo === "sexta" && (t.estado === "pendente" || t.estado === "executando"),
      );
      if (emVoo) {
        return {
          ok: false,
          erro: `já existe a rodada de decisão nº ${emVoo.id} ${emVoo.estado}: a rodada completa ` +
            "enfileiraria outra ao fim do canário. Espere ela terminar.",
        };
      }
      const p = typeof passosDoCanario === "string" ? passosDoCanario.replace(/\s/g, "") : "";
      if (!PASSOS_VALIDOS.test(p)) {
        return { ok: false, erro: "os passos do canário precisam ser inteiros separados por vírgula." };
      }
      id = await criarTrabalho(
        "canario",
        {
          canary_steps: p,
          encadear: {
            tipo: "sexta",
            argumentos: { ...base, externo: SAIDA_DO_RASPADOR, recorte_pela_raspagem: true, dry_run: false },
          },
        },
        por || null,
      );
    } else {
      const argumentos: Record<string, unknown> = { ...base, dry_run: modo === "seco" };
      if (usarColeta) argumentos.externo = SAIDA_DO_RASPADOR;
      id = await criarTrabalho("sexta", argumentos, por || null);
    }
  } catch (e) {
    if (e instanceof TrabalhoEmVoo) return { ok: false, erro: e.message };
    console.error("[console] falha ao enfileirar:", e);
    return { ok: false, erro: "não foi possível enfileirar. Verifique se o Postgres está no ar." };
  }
  redirect(`/trabalho/${id}`);
}
