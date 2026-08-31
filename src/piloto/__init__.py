"""Orquestração da planilha-piloto: rodada de TESTE fora do ciclo semanal.

Encadeia as funções puras do domínio (elegibilidade → perfil → penalidades →
ranking → alocação → relaxamento) com os parâmetros provisórios INJETADOS
run-local — nunca em src/config, nunca como parâmetro adotado (D-014). Não é o
grafo de produção (src/grafo) nem a entrega (src/entrega): é o teste de
realidade dos critérios antes de qualquer automação.
"""
