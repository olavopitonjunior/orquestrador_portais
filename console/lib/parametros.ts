// Os parâmetros de decisão e seu estado (fonte: a tabela do CLAUDE.md — D-004 / D-014 /
// D-017 / D-022 / D-025 / D-031 / D-034). É DADO DE REFERÊNCIA para o console mostrar o
// que ainda depende de você — os valores nulos permanecem nulos aqui, nada é inventado.
// Se a tabela do CLAUDE.md mudar, esta lista precisa acompanhar (é a única cópia; a
// fonte da verdade é o doc). `test/parametros.test.ts` executa esse contrato.
//
// Os nº 12 e nº 13 deixaram de existir (D-031): não estão aqui de propósito, e os
// números nunca são reaproveitados.

export type EstadoParametro = "pendente" | "definido";

export type Parametro = {
  numero: number;
  titulo: string;
  estado: EstadoParametro;
  nota?: string; // só quando definido: o valor/decisão
};

export const PARAMETROS: Parametro[] = [
  { numero: 1, titulo: "Evidência mínima por combinação de perfil", estado: "definido", nota: "N ≥ 3 (D-014)" },
  { numero: 2, titulo: "Forma de normalização de cada fator do ranking", estado: "pendente" },
  {
    numero: 3,
    titulo: "Descontos das três penalidades e decaimento da penalidade por janela",
    estado: "definido",
    nota: "20 / 5 / 10 pontos de 100; perdão de 50 % por semana (D-030, D-034)",
  },
  { numero: 4, titulo: "Tentativas e intervalo de repetição do Orquestrador", estado: "pendente" },
  {
    numero: 5,
    titulo: "Idade máxima aceitável da coleta externa de reserva",
    estado: "definido",
    nota: "2 dias (D-034)",
  },
  { numero: 6, titulo: "Limiar de variação de volume que dispara sinalização", estado: "pendente" },
  { numero: 7, titulo: "Limiar mínimo de taxa de amarração", estado: "definido", nota: "50 % (D-034)" },
  { numero: 8, titulo: "Horários exatos de execução na sexta e na segunda", estado: "pendente" },
  { numero: 9, titulo: "Política de retenção do Registro", estado: "pendente" },
  { numero: 10, titulo: "Prazo da aprovação tácita", estado: "pendente" },
  { numero: 11, titulo: "Prazo de atendimento de lead e limite de inatividade", estado: "pendente" },
  {
    numero: 14,
    titulo: "Resultado esperado por nível para a janela não ser penalizada (D-022)",
    estado: "pendente",
  },
  {
    numero: 15,
    titulo: 'Magnitude da "alteração relevante de preço" que dispara a saída da carga (D-025)',
    estado: "pendente",
  },
];

export const PARAMETROS_PENDENTES = PARAMETROS.filter((p) => p.estado === "pendente");
