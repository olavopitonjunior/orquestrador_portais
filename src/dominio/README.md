# src/dominio

Regras de negócio puras e determinísticas: elegibilidade (oito regras gerais + piso de nível do super destaque — decisões D-002/D-003 em docs/decisoes.md), ranking (dois conjuntos de pesos), penalidades (três), alocação nas cotas e relaxamento (ordem de cedência).

Invariante: nenhuma chamada a modelo de linguagem neste pacote, em nenhuma circunstância. A mesma entrada, com os mesmos parâmetros, produz a mesma lista.

Vazio por decisão: nenhum código de produto é escrito antes da fase de implementação.
