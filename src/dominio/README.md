# src/dominio

Regras de negócio puras e determinísticas: elegibilidade (oito regras gerais + piso de nível do super destaque — decisões D-002/D-003 em docs/decisoes.md), ranking (dois conjuntos de pesos), penalidades (três), alocação nas cotas e relaxamento (ordem de cedência).

Invariante: nenhuma chamada a modelo de linguagem neste pacote, em nenhuma circunstância. A mesma entrada, com os mesmos parâmetros, produz a mesma lista.

`elegibilidade.py`: as oito regras eliminatórias gerais (D-002/D-003) como funções puras, o piso de nível do super destaque, e a ordem de cedência do relaxamento. Testes em `tests/test_elegibilidade.py`, com valores-limite da Spec §6.1. Ranking, penalidades, alocação e relaxamento vêm em etapas seguintes.
