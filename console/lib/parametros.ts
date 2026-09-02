// Os quatorze parâmetros de decisão e seu estado (fonte: CLAUDE.md / D-004 / D-014 /
// D-017). É DADO DE REFERÊNCIA para o console mostrar o que ainda depende de você —
// os valores nulos permanecem nulos aqui, nada é inventado. Se a tabela do CLAUDE.md
// mudar, esta lista precisa acompanhar (é a única cópia; a fonte da verdade é o doc).

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
  { numero: 3, titulo: "Intensidade das três penalidades e decaimento da penalidade por janela", estado: "pendente" },
  { numero: 4, titulo: "Tentativas e intervalo de repetição do Orquestrador", estado: "pendente" },
  { numero: 5, titulo: "Idade máxima aceitável da coleta externa de reserva", estado: "pendente" },
  { numero: 6, titulo: "Limiar de variação de volume que dispara sinalização", estado: "pendente" },
  { numero: 7, titulo: "Limiar mínimo de taxa de amarração", estado: "pendente" },
  { numero: 8, titulo: "Horários exatos de execução na sexta e na segunda", estado: "pendente" },
  { numero: 9, titulo: "Política de retenção do Registro", estado: "pendente" },
  { numero: 10, titulo: "Prazo da aprovação tácita", estado: "pendente" },
  { numero: 11, titulo: "Prazo de atendimento de lead e limite de inatividade", estado: "pendente" },
  { numero: 12, titulo: "Pesos dos quatro fatores do ranking por nível (D-017)", estado: "pendente" },
  { numero: 13, titulo: "Decaimento do peso por dimensão do F1 (D-017)", estado: "pendente" },
  {
    numero: 14,
    titulo: "Resultado esperado por nível para a janela não ser penalizada (D-022)",
    estado: "pendente",
  },
];

export const PARAMETROS_PENDENTES = PARAMETROS.filter((p) => p.estado === "pendente");
