// O que cada código de saída da rodada significa, em português, para quem opera.
//
// Função PURA, e separada da tela de propósito: é a tradução mais consequente do
// console — a diferença entre "não havia imóvel para decidir" e "a auditoria vetou por
// violação de invariante" é a diferença entre não fazer nada e investigar. Os códigos
// são o contrato de `src/executar/sexta.py`, e o CI os exercita um a um.

export type Desfecho = { titulo: string; explicacao: string; grave: boolean };

const POR_CODIGO: Record<number, Desfecho> = {
  0: {
    titulo: "Entregou",
    explicacao:
      "A rodada completou. Pode ter saído DEGRADADA — com alguma fonte ausente e a " +
      "limitação declarada na planilha —, e isso ainda é entrega: veja o estado da rodada.",
    grave: false,
  },
  1: {
    titulo: "Falha ao ESCREVER",
    explicacao:
      "A decisão foi tomada, mas não foi possível gravá-la (Registro ou planilha). " +
      "Diferente de falha de fonte: aqui houve resultado, e ele se perdeu na saída.",
    grave: true,
  },
  2: {
    titulo: "Argumento inválido",
    explicacao: "O comando foi montado com um argumento que a rodada recusa.",
    grave: true,
  },
  3: {
    titulo: "Falha de FONTE",
    explicacao:
      "Não foi possível coletar ou decidir — o Newcore fora do ar, a saída do raspador " +
      "ilegível, ou incoerência na rodada. Nada foi escrito.",
    grave: true,
  },
  4: {
    titulo: "ABORTADA — sem estoque",
    explicacao:
      "A coleta interna veio vazia: sem estoque não há decisão possível. É ausência de " +
      "insumo, não defeito. A rodada abortada NÃO deixa linha no Registro.",
    grave: false,
  },
  5: {
    titulo: "Parâmetros recusados",
    explicacao:
      "Falta um parâmetro, ou um valor está fora da faixa. Nada rodou e nada foi tocado " +
      "— é o arquivo de quem opera, corrigível em segundos.",
    grave: false,
  },
  6: {
    titulo: "ABORTADA — o crivo VETOU",
    explicacao:
      "A auditoria apanhou violação de cota, de piso ou de relaxamento em super destaque " +
      "— os invariantes 6 e 7. Código próprio de propósito: sob um código só, isto " +
      "chegaria ao monitoramento com a mesma cara de 'não havia imóvel para decidir', e " +
      "ninguém iria olhar. ISTO precisa ser investigado.",
    grave: true,
  },
};

export function desfechoDe(codigo: number | null): Desfecho | null {
  if (codigo === null) return null;
  return (
    POR_CODIGO[codigo] ?? {
      titulo: `Código ${codigo}`,
      explicacao: "Código de saída que o console ainda não sabe traduzir.",
      grave: true,
    }
  );
}
