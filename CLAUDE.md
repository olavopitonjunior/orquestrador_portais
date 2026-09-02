# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## O que é o projeto

Sistema de curadoria automatizada da vitrine de destaques de imóveis da Newcore. O contrato vigente com o Grupo OLX (plano Exclusivo: OLX, Zap e Viva Real) inclui 6.970 posições de destaque já pagas — 475 de super destaque e 6.495 de destaque — e hoje a escolha de quais imóveis as ocupam não segue critério objetivo. O desperdício é medido: das 59.653 janelas de destaque já registradas, 88% não geraram um único lead.

O sistema substitui essa escolha por uma cadeia de decisão orquestrada: sete agentes do produto, sob um orquestrador, coletam dados internos do Newcore, raspam a performance externa no Canal Pro, identificam os padrões de imóvel que convertem, aplicam critérios eliminatórios objetivos, ordenam os elegíveis e entregam semanalmente uma planilha justificada. A carga é aplicada manualmente por uma pessoa a partir da planilha; o sistema não publica nada.

Os dois níveis têm problemas de sinal oposto e por isso objetivos de ranking distintos. No super destaque há disputa real — 4.852 candidatos para 475 vagas, mais de dez por posição — e o ranking persegue valor esperado (probabilidade de conversão ponderada pelo ticket). No destaque a folga é de 48% e o objetivo é não deixar benefício contratado sem uso: o ranking persegue probabilidade de gerar lead, e regras podem ser relaxadas para preencher posições.

## Cadência

Dois momentos fixos por semana. **Não existe execução diária.**

| Momento | Rodada | Produto |
|---|---|---|
| Sexta-feira | Decisão | Planilha de decisão, aprovada e aplicada manualmente na carga |
| Segunda-feira | Acompanhamento | Relatório do que a carga produziu desde sexta |

A rodada de sexta é a única que raspa o portal (uma única tentativa por rodada). A rodada de segunda lê apenas o banco e independe de fonte externa.

## Stack

- **Python** com **LangGraph** para a orquestração: estado explícito, critério de pronto por etapa, repetição antes de desistir, estados completa/degradada/abortada e pausa para aprovação humana.
- **Um único PostgreSQL** servindo o checkpointer do grafo e o Registro, em esquemas separados.
- **Leitura direta do MySQL do Newcore** (`newcore` e `newcore_bi`) pelos nós de código. O MCP de MySQL serve para exploração fora da rodada, nunca dentro dela.
- **Automação de navegador** para a raspagem do Canal Pro, com dois caminhos: determinístico por seletores primeiro; modelo interpretando a página quando falha. Mesma sessão autenticada nos dois.
- **Um provedor comercial de modelo por API** — ainda não escolhido; o critério é qualidade em navegação por visão, comparada contra o portal real. Apenas três agentes usam modelo: Coletor Externo (caminho de erro), Analista de Perfil e Redator (só no resumo da rodada).
- Agendador do sistema operacional; entregáveis como planilha do Google no Drive com link por e-mail; hospedagem na máquina física do gestor da vitrine.

## Invariantes

Estes sete itens não podem ser violados por nenhuma implementação futura.

1. O Newcore é somente leitura. Nenhuma escrita em nenhuma tabela dele, em nenhuma circunstância.
2. Toda escrita do sistema acontece no PostgreSQL próprio.
3. Nenhum dado pessoal de lead, comprador ou corretor é enviado a modelo de linguagem. A análise de perfil recebe apenas características de imóvel, com identidades removidas antes do envio.
4. O caminho da decisão é determinístico. Elegibilidade, ranking, penalidades, alocação e relaxamento são cálculo, não julgamento de modelo. Nenhuma chamada a modelo de linguagem nesse caminho.
5. A mesma entrada, com os mesmos parâmetros, produz a mesma lista.
6. Nenhuma posição além da cota contratada é proposta: 475 super destaques e 6.495 destaques.
7. O relaxamento de regras aplica-se apenas às posições de destaque. As posições de super destaque nunca relaxam.

## Estrutura de pastas

```
docs/            fonte da verdade: PRD, spec, ferramentas, mapa de dados
src/grafo/       nós do LangGraph e definição do fluxo
src/dominio/     regras de elegibilidade, ranking, penalidades, alocação, relaxamento
src/dados/       leitura do Newcore (MySQL) e acesso ao Registro (Postgres)
src/entrega/     geração da planilha e do relatório
src/executar/    pontos de entrada das rodadas (`python -m executar.segunda`)
src/config/      parâmetros de decisão
tests/           testes (estratégia ainda não definida)
.claude/agents/  subagentes de DESENVOLVIMENTO (nunca rodam em produção)
.claude/skills/  skills de DESENVOLVIMENTO
CHANGELOG.md     trilha de mudanças, obrigatória para regra de decisão
bug.md           registro de defeitos
```

## Hierarquia dos documentos

`docs/vitrine-destaque-prd.md` **>** `docs/vitrine-destaque-spec.md` **>** `docs/vitrine-destaque-ferramentas.md` **>** código.

Divergência entre código e documento é **bug do código** até prova em contrário. Se dois documentos divergirem entre si, o de hierarquia superior prevalece — e a divergência deve ser apontada, não resolvida em silêncio.

`docs/mapa-de-dados.md` é referência derivada do PRD: consulte-o antes de depender de qualquer campo do banco.

`docs/decisoes.md` registra as resoluções do dono da decisão para divergências entre os documentos. Uma decisão registrada lá prevalece sobre o trecho divergente até que uma revisão dos documentos a incorpore.

`docs/perguntas-abertas.md` é o ÍNDICE de tudo que aguarda o dono — parâmetros nulos, divergências, fatos e atos —, com o que cada resposta destrava. É índice, não fonte: o texto integral continua em `docs/decisoes.md` e na tabela abaixo. Quem registrar pendência nova acrescenta a linha lá na mesma mudança; `tests/test_perguntas_abertas.py` falha se os arquivos divergirem.

## Glossário mínimo

- **Agente do produto**: um dos sete — Orquestrador, Coletor Interno, Coletor Externo, Analista de Perfil de Conversão, Decisor, Redator da Entrega, Monitor Operacional. São nós do grafo LangGraph, escritos em Python, executados em produção às sextas e segundas. **Nunca viram arquivos em `.claude/agents/`.**
- **Subagente de desenvolvimento**: vive em `.claude/agents/`, existe apenas para ajudar a construir este projeto e **nunca roda em produção**. Nenhum subagente pode ter o nome de um agente do produto. O mesmo vale para skills: `.claude/skills/` é ferramenta de desenvolvimento; as competências dos agentes do produto viram código Python.
- **Elegibilidade**: conjunto de **oito** regras eliminatórias gerais, binárias e sem compensação, aplicadas antes do ranking; reprovar em uma basta para excluir. O piso de R$ 700.000 é condição de nível do super destaque aplicada na alocação, e o status impeditivo é regra de saída imediata — não regras de elegibilidade (decisões D-002 e D-003; onde os documentos dizem "nove regras", leia-se assim).
- **Perfil de conversão**: combinação de características de imóvel que demonstradamente gera venda no período analisado (vendas assinadas em 180 dias), sempre acompanhada do número de casos que a sustenta. Analisa uma ou duas dimensões por vez, nunca as cinco simultaneamente.
- **Janela de destaque**: intervalo em que um imóvel ocupou posição paga. Histórico que alimenta a penalidade por janela anterior sem resultado.
- **Relaxamento**: cedência controlada de regras de elegibilidade, apenas nas posições de destaque, com relatório obrigatório. Ordem de cedência: fotos, cadastro completo, atualização em 90 dias, gestor produtivo, capacidade do distrito.
- **Rodada degradada**: estado da rodada em que alguma fonte falhou e a decisão prosseguiu com dado parcial, com a limitação declarada de forma visível na planilha. Os outros estados são completa (todas as etapas prontas) e abortada (a coleta interna não ficou pronta; sem estoque não há decisão).
- **Pronto**: conjunto de condições verificáveis que uma etapa cumpre antes de entregar para a seguinte. Nenhum agente entrega para o próximo sem estar pronto.

## Parâmetros ainda sem valor

Quatorze parâmetros. Os onze primeiros foram consolidados pela decisão D-004 a partir de Spec §8, Ferramentas §6 e da tabela de parâmetros do PRD, que divergiam entre si; a **D-017** acrescentou o nº 12 e o nº 13, que a Spec §6.3 dava como **definidos** e o redesenho do ranking tornou nulos; a **D-022** acrescentou o nº 14, que a Spec §6.4 exige ("o resultado esperado **para o nível**") e nenhum documento jamais quantificou. O nº 1 foi resolvido pelo dono em 2026-08-31 (D-014); os outros **treze seguem pendentes**. **Nenhum pendente pode ser preenchido com valor inventado** — permanecem explicitamente nulos até serem definidos pelo dono da decisão. Os provisórios da planilha-piloto (nº 2, nº 3, nº 12 e nº 13) são run-local, rotulados PROVISÓRIO na própria planilha e **não adotados**: seguem nulos aqui e nunca entram em `src/config`.

| # | Parâmetro | Valor |
|---|---|---|
| 1 | Evidência mínima por combinação de perfil | **N ≥ 3** (D-014, 2026-08-31) |
| 2 | Forma de normalização de cada fator do ranking | nulo |
| 3 | Intensidade das três penalidades e decaimento da penalidade por janela | nulo |
| 4 | Tentativas e intervalo de repetição do Orquestrador | nulo |
| 5 | Idade máxima aceitável da coleta externa de reserva | nulo |
| 6 | Limiar de variação de volume que dispara sinalização | nulo |
| 7 | Limiar mínimo de taxa de amarração | nulo |
| 8 | Horários exatos de execução na sexta e na segunda | nulo |
| 9 | Política de retenção do Registro | nulo |
| 10 | Prazo da aprovação tácita | nulo |
| 11 | Prazo de atendimento de lead e limite de inatividade | nulo |
| 12 | Pesos dos quatro fatores do ranking por nível (semelhança, leads, desempenho, produtividade) — antes definidos na Spec §6.3 | nulo (D-017) |
| 13 | Decaimento do peso por dimensão do F1 (magnitude da queda na ordem preço > localização > metragem > dormitórios > vagas; a ordem é adotada, a magnitude é nula) | nulo (D-017) |
| 14 | Resultado esperado por nível para a janela não ser penalizada (§6.4) — **dois** valores, super destaque e destaque | nulo (D-022) |

## Antes de commitar

Regra global do usuário: antes de qualquer `git commit`, `git merge`, `gh pr merge`, push para branch compartilhada ou abertura de PR, invocar o agente `orchestrator` e seguir o veredito. REPROVADO/BLOQUEADO = não executar.

Toda mudança em regra de decisão — elegibilidade, pesos, penalidades, cotas, ordem de relaxamento — exige entrada no `CHANGELOG.md`.
