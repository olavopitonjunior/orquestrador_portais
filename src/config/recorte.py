"""Recortes de decisão que mais de um ponto de entrada precisa — e que não podem
existir em duas cópias.

Existe por um defeito concreto: a medição dos números de referência precisava da
mesma definição de "corretor ativo no distrito" que a rodada de sexta usa, e a
primeira versão a repetiu como literal. Repetição de constante que carrega DECISÃO é
o pior tipo: revista a D-015, a sexta mudaria e a medição passaria a medir outro
funil em silêncio, reportando a diferença como deriva da base.

A segunda tentativa foi importar de `executar.sexta`. Também errado, por dois
motivos que o portão de código mediu: arrasta LangGraph, psycopg e a cadeia inteira
do grafo para uma ferramenta que lê um markdown e conta imóveis (575 ms dos 630 ms
de import), e — o que importa mais — faz qualquer efeito colateral futuro no nível
de módulo da sexta virar efeito colateral da medição, em silêncio. Ponto de entrada
é topo de pilha: ninguém espera que alguém importe dele.

Aqui é o lugar: `src/config` é onde o CLAUDE.md põe parâmetros de decisão.
"""

from __future__ import annotations

from dados.coletor_interno import DefinicaoAtivoDistrito

# D-015 fixou a definição de gestor ativo do distrito usada na elegibilidade.
# Constante nomeada e não argumento de linha de comando: trocá-la muda a regra de
# decisão, e regra se muda por decisão registrada, não por flag de invocação.
DEFINICAO_ATIVO = DefinicaoAtivoDistrito.PRODUTIVOS
