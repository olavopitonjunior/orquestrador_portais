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

/** Os códigos da PRÉVIA (`executar/previa.py`): três, e nenhum fala de planilha ou
 *  Registro, porque a prévia não escreve em lugar nenhum. */
const PREVIA_POR_CODIGO: Record<number, Desfecho> = {
  1: {
    titulo: "Falha ao MONTAR a prévia",
    explicacao:
      "O Newcore foi lido, mas o cálculo ou a gravação do resultado falhou. É defeito, não " +
      "dado: o log abaixo diz o tipo do erro.",
    grave: true,
  },
  2: {
    titulo: "Argumento inválido",
    explicacao: "O comando foi montado com um argumento que a prévia recusa (data no futuro).",
    grave: true,
  },
  0: {
    titulo: "Prévia pronta",
    explicacao: "O funil foi calculado com os valores declarados. O resultado está abaixo.",
    grave: false,
  },
  3: {
    titulo: "Falha de FONTE",
    explicacao:
      "Não foi possível ler o Newcore (candidatos, vendas ou dimensões). Nada foi calculado; " +
      "tente de novo quando a fonte responder.",
    grave: true,
  },
  5: {
    titulo: "Parâmetros recusados",
    explicacao:
      "Um valor está fora da faixa, uma chave é desconhecida, ou a régua de resultado foi " +
      "declarada pela metade. Corrija em /parametros e peça a prévia de novo.",
    grave: false,
  },
};

/** A tradução vale para a SEXTA e para a PRÉVIA, e o tipo é exigido por isso.
 *
 *  Os códigos são o contrato de `executar/sexta.py`, e outros tipos os reusam com
 *  significados DIFERENTES: em `executar/segunda.py` o código 4 quer dizer "sem carga
 *  aprovada desde a sexta", nada a ver com "a coleta interna veio vazia". Traduzir sem
 *  olhar o tipo faria a tela afirmar, com confiança e por escrito, algo simplesmente
 *  falso — e a raspagem, cujo código vem do `npm`, passaria pela mesma tabela.
 *
 *  Para os demais tipos devolve-se o código cru: não saber é melhor que inventar. */
export function desfechoDe(tipo: string, codigo: number | null): Desfecho | null {
  if (codigo === null) return null;
  if (tipo === "previa") {
    return (
      PREVIA_POR_CODIGO[codigo] ?? {
        titulo: `Código ${codigo}`,
        explicacao: "Código de saída que o console ainda não sabe traduzir para a prévia.",
        grave: true,
      }
    );
  }
  if (tipo !== "sexta") {
    return {
      titulo: `Código ${codigo}`,
      explicacao:
        `O console só traduz os códigos da rodada de sexta. Para um trabalho do tipo ` +
        `'${tipo}', o significado é o do comando que ele executa.`,
      grave: codigo !== 0,
    };
  }
  return (
    POR_CODIGO[codigo] ?? {
      titulo: `Código ${codigo}`,
      explicacao: "Código de saída que o console ainda não sabe traduzir.",
      grave: true,
    }
  );
}
