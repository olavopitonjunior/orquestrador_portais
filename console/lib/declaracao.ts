// O exame de uma declaração de parâmetros vinda do formulário — PURO, sem servidor:
// as duas ações (`salvarParametros`, `verPrevia`) o chamam, e o teste também. Vive fora
// de `acoes.ts` porque um arquivo "use server" só pode exportar funções assíncronas.

import { validar } from "./toml";

export type Recusa =
  | { ok: false; problemas: { caminho: string; mensagem: string }[] }
  | { ok: false; erro: string };

/** O exame comum às duas ações: `por` limpo e os valores válidos. Exportado para o
 *  teste; não é ação de servidor (não é `async`). */
export function conferir(
  entradas: Record<string, string>,
  por: string,
): { valores: Map<string, string> } | Recusa {
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
  return { valores };
}
