// O que a página da rodada lê de cada aba da planilha: a ordem em que as exibe e
// quantas linhas de cada uma materializa.
//
// Vive fora de `page.tsx` para poder ser TESTADO. A regra que estes dois valores
// carregam não é verificável por tipo nem por build — só por teste sobre um artefato
// com a forma da rodada real —, e ela já falhou uma vez: ver `bug.md`.

import type { Aba, LimiteDeLinhas } from "./planilha";

// A ordem de LEITURA, explícita: limitações antes de qualquer número; depois o nível com
// disputa; depois o de folga; excluídos e relaxamento por último.
// A apuração NÃO entra aqui: são dezenas de milhares de linhas numa rodada inteira, e a
// tela não é o lugar de lê-las — ela ganha um cartão próprio no topo, com a contagem e o
// botão, e o arquivo se lê no Sheets.
export const ORDEM_DAS_ABAS: readonly Aba[] = [
  "parametros_e_limitacoes",
  "super_destaque",
  "destaque",
  "excluidos_por_regra",
  "relaxamento",
  "perfis",
];

export const LINHAS_NA_TELA = 300;

// A REGRA para mexer aqui: limite só é seguro em aba de que a página EXIBE linhas. Onde
// ela AGREGA sobre `Tabela.linhas` — conta, soma, filtra —, o limite corrompe o agregado
// sem sintoma nenhum: nem tipo, nem build, nem contagem de aba acusam. Por isso as duas
// exceções abaixo são nomeadas uma a uma, com o consumidor que as obriga.
//
// Os 94 % do custo estão em `apuracao` (14,7 MB) e `excluidos_por_regra` (2,1 MB), e
// nenhuma das duas tem agregado. A apuração nem exibida é: a tela mostra dela só a
// contagem, e `total` sai exato com zero linhas na memória.
export const LIMITES: LimiteDeLinhas = {
  ...Object.fromEntries(ORDEM_DAS_ABAS.map((a) => [a, LINHAS_NA_TELA])),
  apuracao: 0,
  // `page.tsx` conta `origem === "relaxamento"` sobre estas linhas. O relaxamento
  // preenche as ÚLTIMAS posições — a partir da 6.379 de 6.495 em 2026-09-06 —, então
  // qualquer prefixo daria ZERO e a tela mentiria sobre o mecanismo que a D-036 tornou o
  // modo ordinário de encher a cota.
  destaque: undefined,
  // `cedenciaDaAba` percorre estas linhas inteiras para montar os degraus da cedência.
  relaxamento: undefined,
};

/** As abas de que a página AGREGA (conta/percorre), e que por isso não podem ser
 *  limitadas. É a lista que o teste de regressão confere contra `LIMITES`. */
export const ABAS_COM_AGREGADO: readonly Aba[] = ["destaque", "relaxamento"];
