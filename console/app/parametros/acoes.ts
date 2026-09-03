"use server";

// Casca fina. Toda a lógica mora em `lib/toml.ts` (pura) e `lib/operacao.ts` (com
// executor injetável), que são testáveis sem servidor e sem banco — o mesmo idioma
// que o lado Python usa com `Fontes` e `conectar_registro`.

import { revalidatePath } from "next/cache";

import { guardarParametros } from "@/lib/operacao";
import { paraToml, validar } from "@/lib/toml";

export type Resposta =
  | { ok: true; id: number }
  | { ok: false; problemas: { caminho: string; mensagem: string }[] }
  | { ok: false; erro: string };

export async function salvarParametros(
  entradas: Record<string, string>,
  por: string,
): Promise<Resposta> {
  const valores = new Map(Object.entries(entradas));

  // `por` NÃO vem do contrato, então não passa por `validar()` — e era o único dado
  // que chegava aqui ao lado do formulário em vez de dentro dele. Ele vira comentário
  // no TOML, e comentário termina na quebra de linha: sem esta guarda, um nome com
  // `\n[resultado_esperado]` definia o parâmetro nº 14, que a D-022 declara nulo.
  // `paraToml` também limpa, por contrato próprio; aqui a recusa é explícita para o
  // dono VER o problema em vez de ter o nome dele silenciosamente encurtado.
  // Qualquer caractere de controle, não só quebra de linha: a gramática do TOML os
  // proíbe dentro de comentário, e um `\x01` faz o arquivo inteiro deixar de parsear.
  // `paraToml` também os remove, por contrato próprio; aqui a recusa é explícita para
  // o dono VER o problema em vez de ter o nome silenciosamente alterado.
  if (/[\u0000-\u001F\u007F]/.test(por)) {
    return {
      ok: false,
      problemas: [
        { caminho: "por", mensagem: "não pode conter quebra de linha nem caractere de controle" },
      ],
    };
  }
  if (por.length > 200) {
    return { ok: false, problemas: [{ caminho: "por", mensagem: "no máximo 200 caracteres" }] };
  }

  // Revalida no SERVIDOR, mesmo o cliente já tendo validado. O cliente é conveniência
  // para o dono corrigir enquanto digita; ele não é garantia, porque quem chama a
  // ação não é obrigado a ser o formulário.
  const problemas = validar(valores);
  if (problemas.length > 0) return { ok: false, problemas };

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
