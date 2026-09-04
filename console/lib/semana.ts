// A cadência semanal (CLAUDE.md, "Cadência"): decisão na sexta, acompanhamento na
// segunda seguinte. Só datas — a HORA é o parâmetro nº 8, ainda nulo, e não aparece.
// Função pura sobre o dia local do servidor (a máquina do gestor, em São Paulo).

export type Cadencia = {
  decisao: Date; // a próxima sexta (hoje, se hoje for sexta)
  acompanhamento: Date; // a segunda depois dessa sexta
  diasAteDecisao: number; // 0 = hoje, 1 = amanhã
};

const SEXTA = 5;

function somaDias(d: Date, n: number): Date {
  const r = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  r.setDate(r.getDate() + n);
  return r;
}

export function cadencia(hoje: Date): Cadencia {
  const dia = new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate());
  const ate = (SEXTA - dia.getDay() + 7) % 7;
  const decisao = somaDias(dia, ate);
  return { decisao, acompanhamento: somaDias(decisao, 3), diasAteDecisao: ate };
}

const DIA_SEMANA = new Intl.DateTimeFormat("pt-BR", { weekday: "short" });
const DIA_MES = new Intl.DateTimeFormat("pt-BR", { day: "numeric" });
const LONGA = new Intl.DateTimeFormat("pt-BR", { weekday: "long", day: "numeric", month: "long" });

/** "Sex 4" — rótulo curto para a coluna da semana. */
export function diaCurto(d: Date): string {
  const s = DIA_SEMANA.format(d).replace(".", "");
  return `${s.charAt(0).toUpperCase()}${s.slice(1)} ${DIA_MES.format(d)}`;
}

/** "quinta-feira, 3 de setembro" com a inicial maiúscula. */
export function diaLongo(d: Date): string {
  const s = LONGA.format(d);
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** "hoje", "amanhã", "em N dias". */
export function quando(dias: number): string {
  if (dias === 0) return "hoje";
  if (dias === 1) return "amanhã";
  return `em ${dias} dias`;
}


