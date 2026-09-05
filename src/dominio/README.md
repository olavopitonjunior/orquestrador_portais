# src/dominio

Regras de negócio puras e determinísticas: elegibilidade (oito regras gerais mais o perfil de conversão, a nona desde a D-027; o piso de nível do super destaque fica na alocação, D-002/D-003), ranking (a nota do portal em pontos de 100, D-028), descontos (três), alocação nas cotas e relaxamento (ordem de cedência com o perfil primeiro).

Invariante: nenhuma chamada a modelo de linguagem neste pacote, em nenhuma circunstância. A mesma entrada, com os mesmos parâmetros, produz a mesma lista.

`elegibilidade.py`: as nove regras eliminatórias como funções puras — as oito gerais (D-002/D-003) mais o perfil de conversão (D-027), cujo veredito vem da costura e cujo `None` NÃO reprova —, o piso de nível do super destaque e a ordem de cedência do relaxamento. Testes em `tests/test_elegibilidade.py`, com valores-limite da Spec §6.1.
