// Os tipos do contrato dos parâmetros da rodada, e a leitura da cópia commitada.
//
// A fonte da verdade é `src/config/contrato.py`, no lado Python — é lá que moram as
// faixas, os tipos e as escolhas fechadas, derivadas dos mesmos validadores que a
// rodada usa. Este arquivo NÃO redeclara nada disso: importa o JSON gerado por
// `uv run rodada-contrato`, que um passo de CI compara byte a byte com a saída atual.
//
// Duplicar o contrato em TypeScript garantiria divergência silenciosa, e o modo de
// divergir é o pior possível: o formulário passaria a proibir um valor que a rodada
// aceita — ou a aceitar um que ela recusa —, e o dono só descobriria ao submeter.

import contratoJson from "./contrato-parametros.json";

export type TipoCampo = "inteiro" | "numero" | "escolha";

export type Campo = {
  caminho: string;
  tipo: TipoCampo;
  ajuda: string;
  obrigatorio: boolean;
  minimo: number | null;
  maximo: number | null;
  /** `true` quando o mínimo é EXCLUSIVO. A diferença importa: `decaimento` em (0,1]
   *  recusa zero, `desconto_fragil` em [0,1] aceita. Um formulário que trate as duas
   *  como "entre 0 e 1" deixa passar valor que o carregador recusa. */
  minimo_aberto: boolean;
  escolhas: string[] | null;
  /** `[caminho, valor]`: o campo só existe quando aquele outro tiver aquele valor. */
  exige: [string, string] | null;
  /** Rótulo do parâmetro pendente, para o dono saber que decisão está respondendo. */
  pendencia: string | null;
};

export type TipoRegra = "soma_igual" | "todos_ou_nenhum" | "maior_que";

export type RegraCruzada = {
  tipo: TipoRegra;
  descricao: string;
  campos: string[];
  valor: number | null;
};

export const CAMPOS: Campo[] = contratoJson.campos as Campo[];
export const REGRAS: RegraCruzada[] = contratoJson.regras as RegraCruzada[];

export const POR_CAMINHO: ReadonlyMap<string, Campo> = new Map(
  CAMPOS.map((c) => [c.caminho, c]),
);

/** A seção a que o campo pertence, para agrupar o formulário. `pesos.super_destaque`
 *  e `pesos.destaque` são seções distintas de propósito: os dois níveis perseguem
 *  objetivos diferentes, e essa assimetria é a parte do modelo que o dono precisa
 *  preservar ao decidir. */
export function secaoDe(campo: Campo | string): string {
  const caminho = typeof campo === "string" ? campo : campo.caminho;
  const partes = caminho.split(".");
  return partes.length > 2 ? partes.slice(0, 2).join(".") : partes[0];
}

/** A ÚNICA noção de igualdade para valor de escolha.
 *
 *  Existe porque havia duas, e a divergência era explorável: `validar` comparava com
 *  `.trim()` e `campoAtivo` comparava cru. Um valor com espaço à direita —
 *  `"cliques_do_tipo "` — era ACEITO pela validação e, ao mesmo tempo, desativava o
 *  campo condicional que ele governa. O campo deixava de ser exigido, não era
 *  serializado, o console dizia "Guardado", e a rodada morria com "falta
 *  externo.desempenho.tipo" — na única tentativa da semana, depois de o dono já ter
 *  visto sucesso na tela. Duas noções de igualdade para o mesmo par é o defeito; a
 *  função é a correção. */
export function normalizarEscolha(valor: string | undefined): string {
  return (valor ?? "").trim();
}

/** Um campo condicional só entra quando o campo que o governa tem o valor esperado. */
export function campoAtivo(campo: Campo, valores: ReadonlyMap<string, string>): boolean {
  if (campo.exige === null) return true;
  const [alvo, esperado] = campo.exige;
  return normalizarEscolha(valores.get(alvo)) === esperado;
}
