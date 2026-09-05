"use server";

// Casca fina. Toda a lógica mora em `lib/toml.ts` (pura) e `lib/operacao.ts` (com
// executor injetável), que são testáveis sem servidor e sem banco — o mesmo idioma
// que o lado Python usa com `Fontes` e `conectar_registro`.

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { TrabalhoEmVoo, criarTrabalho, guardarParametros, listarTrabalhos } from "@/lib/operacao";
import { conferir } from "@/lib/declaracao";
import { previaEmVoo } from "@/lib/previa";
import { paraToml } from "@/lib/toml";

export type Resposta =
  | { ok: true; id: number }
  | { ok: false; problemas: { caminho: string; mensagem: string }[] }
  | { ok: false; erro: string; emVoo?: number };

export async function salvarParametros(
  entradas: Record<string, string>,
  por: string,
): Promise<Resposta> {
  const exame = conferir(entradas, por);
  if ("ok" in exame) return exame;
  const { valores } = exame;

  try {
    const id = await guardarParametros(
      paraToml(valores, `declarado no console${por ? ` por ${por}` : ""}`),
      por || null,
    );
    revalidatePath("/parametros");
    return { ok: true, id };
  } catch (e) {
    // Detalhe (que pode conter host) só no log do servidor; a tela mostra o genérico.
    console.error("[console] falha ao guardar parâmetros:", e);
    return { ok: false, erro: "não foi possível guardar. Verifique se o Postgres está no ar." };
  }
}

/** Guarda a declaração E enfileira a prévia sobre ela — o elo entre definir e rodar.
 *  Uma declaração VAZIA é legítima: a prévia responde com os adotados (D-034). */
export async function verPrevia(entradas: Record<string, string>, por: string): Promise<Resposta> {
  const exame = conferir(entradas, por);
  if ("ok" in exame) return exame;
  const { valores } = exame;

  let id: number;
  try {
    // Antes de gravar: o duplo-clique e a segunda aba são o caso NORMAL, e cada um
    // deixaria uma declaração órfã (append-only) se a fila só recusasse depois. A
    // guarda de verdade continua sendo o índice do banco; esta é a que evita o lixo.
    const jaEmVoo = previaEmVoo(await listarTrabalhos(50));
    if (jaEmVoo !== null) {
      return {
        ok: false,
        erro: "já há uma prévia sendo calculada. Acompanhe a que está em curso.",
        emVoo: jaEmVoo,
      };
    }
    const declaracao = await guardarParametros(
      paraToml(valores, `prévia pedida no console${por ? ` por ${por}` : ""}`),
      por || null,
    );
    id = await criarTrabalho("previa", { parametros_declarados_id: declaracao }, por || null);
    revalidatePath("/parametros");
  } catch (e) {
    if (e instanceof TrabalhoEmVoo) {
      // Não é erro do dono: é o duplo-clique, ou uma prévia de outra aba. A tela aponta
      // para a que já corre em vez de mostrar a razão técnica da unicidade.
      const emVoo = await listarTrabalhos(50)
        .then(previaEmVoo)
        .catch(() => null);
      return {
        ok: false,
        erro: "já há uma prévia sendo calculada. Acompanhe a que está em curso.",
        emVoo: emVoo ?? undefined,
      };
    }
    console.error("[console] falha ao pedir a prévia:", e);
    return { ok: false, erro: "não foi possível enfileirar. Verifique se o Postgres está no ar." };
  }
  // Fora do try: `redirect` lança, e o catch genérico o engoliria.
  redirect(`/trabalho/${id}`);
}
