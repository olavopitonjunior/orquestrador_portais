# Documento de Requisitos de Produto: Curadoria Orquestrada da Vitrine de Destaques

**Versão**: 5.0
**Data**: 2026-08-28
**Autoria**: Sarah (Product Owner)
**Dono da decisão**: Olavo
**Score de qualidade dos requisitos**: 99/100

---

## Sumário executivo

A Newcore mantém contrato vigente com o Grupo OLX no plano Exclusivo, que cobre OLX, Zap e Viva Real, com 50.000 ofertas. O contrato é dimensionado para a base inteira de imóveis e já está pago independentemente do uso; dentro dele, 6.970 ofertas são posições de destaque e super destaque. A escolha de quais imóveis ocupam essas posições não segue critério objetivo, e o resultado é mensurável: de 59.653 janelas de destaque já registradas, 88% não geraram um único lead.

Este produto substitui essa escolha por uma cadeia de decisão orquestrada e executada sem intervenção. Sete agentes sob um orquestrador coletam dados internos do Newcore, raspam a performance externa no Canal Pro no dia da atualização do estoque, identificam os padrões de imóvel que convertem, aplicam critérios eliminatórios objetivos, ordenam os elegíveis com objetivos distintos por nível e entregam semanalmente uma planilha justificada. A carga é substituída manualmente a partir dela. Na segunda-feira seguinte, um ciclo de acompanhamento que lê apenas o banco produz o relatório da carga: os leads sem atendimento e sem contato originados de imóveis em posição paga, e o desempenho de cada posição.

O produto resolve dois problemas de sinal oposto. Nas 475 posições de super destaque há disputa real, com 4.852 candidatos e dez por vaga, e o ranking persegue valor esperado. Nas 6.495 posições de destaque a concorrência é baixa, com folga total de 48%, e o objetivo passa a ser não deixar benefício contratado sem uso.

O sistema não consulta a carga vigente e não confirma se a planilha foi aplicada. A planilha aprovada é o registro assumido do que está em vitrine.

---

## Problema

**Situação atual.** As posições de destaque são ocupadas sem critério comum. A marcação existente na interface, feita de forma distribuída pelos corretores, não define a carga e não tem efeito prático sobre a decisão comercial.

**Evidência.** Nas 59.653 janelas registradas, a média é de 0,21 lead por janela e 88% terminaram sem nenhum lead. A duração média observada é de 33 dias, contra os sete dias de ciclo de carga, o que indica que a vitrine não gira.

**Natureza econômica do desperdício.** O valor do contrato cobre o pacote completo de anúncios, que a base precisa de qualquer forma. Os destaques são benefício embutido, não item de custo separado. Portanto uma posição de destaque mal ocupada não gasta dinheiro adicional, e uma posição vazia não gera custo direto: ambas representam benefício contratado que deixou de ser extraído. Isso reduz o custo de preencher uma posição de destaque com um imóvel apenas razoável, já que a folga de 48% garante que nenhum imóvel melhor perde vaga por causa disso. No super destaque a lógica não vale, porque lá a posição é genuinamente escassa.

---

## Base factual

Levantamento direto nas fontes em 28/08/2026.

### Contrato vigente

Plano Exclusivo do Grupo OLX, cobrindo OLX, Zap e Viva Real, com gestão de leads, mini site, inteligência de mercado, loja oficial e Lead Certo.

| Item do contrato | Quantidade |
|---|---|
| Ofertas totais | 50.000 |
| Ofertas comuns | 43.035 |
| Destaques padrão | 6.255 |
| Destaques exclusivos | 240 |
| Super destaques | 470 |
| Topo VIP | 5 |

Valor de R$ 94.788, referente ao pacote completo. A periodicidade precisa ser confirmada.

**Agrupamento adotado no MVP.** Destaques padrão e exclusivos são tratados como Destaque; super destaques e Topo VIP como Super Destaque. A distinção entre subníveis fica para fase posterior.

| Nível | Posições |
|---|---|
| Destaque | 6.495 |
| Super Destaque | 475 |
| **Total** | **6.970** |

A configuração em `adsportalconfigs` registra 350 destaques e 1 super destaque, está inativa e desatualizada em quase vinte vezes. Não é fonte de cota.

### Bases de dados

- `newcore`: 418 tabelas, base transacional.
- `newcore_bi`: 53 tabelas, camada analítica com fatos já calculados.

### Desempenho histórico das janelas de destaque

| Leads gerados na janela | Janelas | Participação |
|---|---|---|
| Zero | 52.487 | 88,0% |
| 1 a 2 | 6.134 | 10,3% |
| 3 a 5 | 789 | 1,3% |
| Mais de 5 | 243 | 0,4% |

Média de 0,21 lead por janela, máximo de 72, duração média de 33 dias. Registrado em `adsrealtyextra_historic`, com `HighlightedAt`, `RemovedAt` e `QtyFacsGenerated`.

### Escala da operação

5.182 leads nos últimos 30 dias, 96% ligados a um imóvel, distribuídos por 3.453 imóveis, dos quais 2.608 receberam exatamente um lead.

### Volume do funil de conversão

| Sinal | Últimos 30 dias | Últimos 180 dias | Últimos 12 meses |
|---|---|---|---|
| Vendas assinadas | 25 | 176 | 546 |
| Propostas registradas | — | — | 3.940 |
| Visitas realizadas | — | — | 5.898 |
| Leads | 5.182 | — | cerca de 62.000 |

Esse volume é a restrição central da análise de perfil. As 176 vendas de seis meses se espalham por 66 distritos, 16 faixas de valor, 8 faixas de área, 7 variações de dormitórios e 11 tipos de imóvel, o que produz mais de seiscentas mil combinações possíveis. Cruzar cinco dimensões simultaneamente sobre essa base produziria coincidências com aparência de padrão.

### Nota interna de anúncio

`newcore.realty_score` pontua 376.856 imóveis de 0 a 100, média 68. Pesos: descrição (2), fotos (2), atualização (2), ano de construção (1), atributos (1), IPTU (1), condomínio (1).

### Ciclo de conversão

Sobre 6.545 propostas assinadas historicamente: 28% fecham em até 30 dias, 19% entre 31 e 90 dias e 52% acima de 90 dias. Média de 202 dias. O campo apresenta valores negativos e exige tratamento.

### Coleta externa

`webscraping_processing_grupo_zap` registra 105 execuções, com volume máximo de 36.420 anúncios. Das execuções, 40 processaram sem alterações, 37 com erros e 28 não processaram: cerca de 62% com problema.

A raspagem passa a rodar apenas no dia da atualização do estoque, uma vez por rodada semanal, e não mais diariamente. Ela serve exclusivamente para trazer nota do portal, visualizações e cliques por anúncio. Leads por imóvel, atendimento e conversão vêm do banco.

### Tabela central do produto

`newcore_bi.FT_RealtyRelation` (404.680 registros, um por imóvel) liga imóvel ao corretor gestor, distrito, zona de valor, bairro, status, tipo, preço, faixa de preço, faixa de área e dormitórios, e traz `Leads30D` e `Leads180D` por imóvel.

### Classificação de produtividade

`newcore_bi.productivityrating` classifica 2.094 corretores em Produtivo (193), Não Produtivo (1.146) e Ocioso Passível de Bloqueio (746), com captações por semana, vendas, data da última venda, conversão de compradores e visitas por semana.

### Demais fontes analíticas

| Tabela | Registros | Uso |
|---|---|---|
| `FT_Leads` | 942.368 | Leads por imóvel, canal, distrito, características e funil |
| `FT_LeadsVisits` | 84.823 | Visitas com feedback de imóvel e de preço |
| `FT_LeadsOffers` | 17.332 | Propostas com assinatura, valor, ciclo e características |
| `FT_LeadsAttendance` | 19.007 | Atendimento de leads |
| `FT_Districts` | 1.583 | Indicadores consolidados por distrito |
| `FT_Broker` | 16.691 | Perfil e desempenho de corretor |

### Defeitos de dado confirmados

- `realties.MarketingType_Id` é nulo em 96% dos ativos.
- `realtyaddresses.ValueZone_Id` é nulo em 98% dos imóveis ativos relevantes. A ligação com distrito vem de `FT_RealtyRelation`.
- `FT_LeadsOffers.DaysConversion` apresenta valores negativos.
- Cerca de 44% do estoque elegível não possui avaliação por categoria em `realty_score_category_score`.
- `realties` não expõe quantidade de vagas diretamente.
- Campos de placa e de impulsionamento estão integralmente vazios.
- `adswhitelist` está abandonada desde 2022. `adsblacklist` está viva com 12.155 imóveis, mas foi decidido ignorá-la.

---

## Critérios de decisão

### Estágio 1: elegibilidade

Regras eliminatórias, binárias, sem compensação entre si.

| Regra | Definição operacional |
|---|---|
| Base ativa | Status de publicação Ativo |
| Categoria | Casa, Casa de condomínio, Sobrado, Cobertura e Apartamento |
| Preço mínimo geral | Igual ou superior a R$ 300.000 |
| Preço mínimo de super destaque | Igual ou superior a R$ 700.000 |
| Fotos | Dez ou mais fotos |
| Cadastro atualizado | Atualizado nos últimos 90 dias |
| Cadastro completo | Nenhuma das sete categorias da nota interna com pontuação zero |
| Gestor produtivo | Corretor gestor captou ou vendeu nos últimos 30 dias |
| Capacidade do distrito | Distrito com dois ou mais corretores que captaram ou venderam nos últimos 30 dias |
| Status impeditivo | Vendido, reservado ou removido, com saída imediata fora do ciclo |

Definições que fecham ambiguidade:

- **Gestor, não captador.** O vínculo usado é o de gestão, disponível para todo o estoque.
- **Imóvel sem avaliação por categoria não é excluído.** Passa e recebe penalidade no ranking.
- **A lista de exclusão existente é ignorada.**
- **Preço contra referência de mercado não é regra de corte** nesta versão.

Permanecem as regras derivadas do diagnóstico de funil, que qualificam o motivo da exclusão:

| Sintoma observado | Diagnóstico | Encaminhamento |
|---|---|---|
| Poucas visualizações e nota interna baixa | Qualidade do anúncio | Pendência de cadastro |
| Boas visualizações e poucos cliques | Preço ou concorrência | Pendência de precificação |
| Muitos leads e poucas visitas | Atendimento, densidade de corretor ou falta de opção | Alerta operacional |

Poucas visualizações com nota interna alta não é motivo de exclusão. É o caso que o destaque resolve.

### Funil de elegibilidade medido

| Etapa acumulada | Imóveis |
|---|---|
| Ativos | 48.964 |
| Nas cinco categorias | 41.478 |
| Preço igual ou acima de R$ 300.000 | 35.560 |
| Após os cinco cortes restantes | 10.290 |

**Situação por nível:**

| Nível | Posições | Candidatos | Concorrência |
|---|---|---|---|
| Super Destaque | 475 | 4.852 acima de R$ 700.000 | 10,2 por vaga |
| Destaque | 6.495 | 9.815 restantes | 1,5 por vaga |
| Total | 6.970 | 10.290 | Folga de 48% |

### Custo de cada regra

Efeito de relaxar cada regra isoladamente. Medido com o mínimo de três corretores por distrito e mantido como referência de ordem de grandeza; os valores absolutos mudam com o mínimo de dois.

| Regra relaxada | Ganho aproximado |
|---|---|
| Dez ou mais fotos | +133 |
| Cadastro completo | +569 |
| Atualizado em 90 dias | +1.680 |
| Gestor produtivo | +1.747 |
| Capacidade do distrito | +5.686 |

A regra de fotos quase não filtra: 98,4% dos candidatos já têm dez fotos.

### Cobertura de território que vende

Das 176 vendas dos últimos 180 dias, 132 ocorreram em distritos que a regra de dois corretores ativos aceita, e 44 ficaram fora. Com o mínimo de três corretores, a cobertura seria de 109 vendas e 67 ficariam fora. A redução do mínimo de três para dois elevou a cobertura de 62% para 75% das vendas recentes, ampliou o universo elegível de 8.321 para 10.290 imóveis e aumentou os distritos elegíveis de 39 para 61, de um total de 126 com algum corretor ativo.

O quarto das vendas que permanece fora do universo elegível é indicador a acompanhar a cada rodada.

### Estágio 2: perfil de conversão

Constrói os padrões de imóvel que convertem a partir das **vendas assinadas dos últimos seis meses**, o que corresponde a 176 casos.

**Restrição de método, imposta pelo volume.** O perfil não cruza as cinco dimensões simultaneamente. Ele mede **uma ou duas dimensões por vez**, começando pelas que mais separam, e cada resultado é acompanhado do número de vendas que o sustenta. Combinações sustentadas por poucos casos são declaradas como frágeis e entram no ranking com peso reduzido ou não entram.

As dimensões disponíveis são região, faixa de preço, faixa de metragem, quantidade de dormitórios e quantidade de vagas.

Um imóvel pode ser priorizado por semelhança com um perfil vencedor mesmo sem desempenho próprio. Dado que 84% dos elegíveis não tiveram lead nos últimos 180 dias, este é o mecanismo que carrega a maior parte da decisão.

**Hipótese a testar na calibração.** O cruzamento entre frequência de lead e ticket sugere que o valor esperado cresce com o preço, ainda que a probabilidade de lead caia: a frequência cai de 22% na faixa de 400 a 500 mil para 5,5% na faixa de 2 a 2,5 milhões, enquanto o ticket cresce mais rápido. O indicador usado é proxy grosseiro e a hipótese precisa ser validada contra vendas antes de virar peso.

### Estágio 3: priorização

**Objetivos distintos por nível:**

| Nível | Objetivo do ranking |
|---|---|
| Super Destaque | Valor esperado, isto é, probabilidade de conversão ponderada pelo ticket |
| Destaque | Probabilidade de gerar lead |

**Fatores de ordenação e pesos iniciais**, com um conjunto por nível:

| Fator | Super Destaque | Destaque |
|---|---|---|
| Semelhança com perfil de conversão, ponderada pela evidência | 60 | 80 |
| Desempenho próprio observado, interno e externo | 25 | 10 |
| Produtividade do corretor gestor | 15 | 10 |
| **Soma** | **100** | **100** |

A diferença entre os níveis é deliberada. As 475 posições de super destaque são escassas e caras, e por isso favorecem o imóvel que já provou gerar lead: o desempenho próprio pesa dois anos e meio mais ali do que no destaque. No nível destaque a ordenação tem efeito limitado, porque 9.815 candidatos disputam 6.495 vagas e dois terços entram de qualquer forma.

Esses valores são iniciais e serão revistos depois da primeira lista produzida.

O fator de capacidade de distrito não participa do ranking, porque o distrito já atua como regra eliminatória.

**Penalidades descontadas:**

- Janela de destaque anterior sem resultado suficiente.
- Ausência de avaliação por categoria na nota interna.
- Ausência de qualquer lead nos últimos 180 dias, tratada como sinal negativo. Aplica-se a 84% dos elegíveis, o que converte o fator em bônus para a minoria com histórico recente.

Imóveis sem histórico de destaque não são penalizados por ausência de histórico. Toda penalidade aplicada é visível na justificativa.

### Estágio 4: alocação nas cotas

Preenche primeiro as 475 posições de super destaque, aplicando o piso de R$ 700.000 e o ranking de valor esperado. Depois preenche as 6.495 posições de destaque com o ranking de probabilidade de lead, entre os candidatos restantes. Nenhuma posição excedente é proposta.

### Estágio 5: relaxamento por falta de candidato

Se faltar imóvel apto, o sistema cede regras progressivamente até completar, **apenas nas posições de destaque**. As posições de super destaque nunca relaxam.

**Ordem de cedência:** fotos, cadastro completo, atualização em 90 dias, gestor produtivo e, por último, capacidade do distrito.

O relaxamento é executado pelo Decisor e obriga relatório próprio na planilha, indicando qual regra cedeu e quantas posições dependeram de cada cedência. Sem esse relatório a etapa não é considerada pronta.

### Rotação e penalidade

- A lista é recalculada integralmente a cada carga semanal.
- Venda, reserva, despublicação ou alteração relevante de preço provocam saída imediata, fora do ciclo.
- Resultado suficiente é proporcional ao tipo de posição: super destaque exige entrega superior à de destaque.
- A penalidade por resultado insuficiente decai ao longo dos ciclos.

Observação de desenho: com folga de 48% no nível destaque, a rotação real ali é baixa por construção. A rotação efetiva acontece no super destaque.

---

## Parâmetros de decisão

| Parâmetro | Natureza |
|---|---|
| Preço mínimo geral | R$ 300.000 |
| Preço mínimo de super destaque | R$ 700.000 |
| Categorias aceitas | Cinco categorias definidas |
| Número mínimo de fotos | 10 |
| Janela de atualização do cadastro | 90 dias |
| Definição de gestor produtivo | Captou ou vendeu em 30 dias |
| Mínimo de corretores ativos no distrito | 2 |
| Janela de vendas para o perfil | 180 dias |
| Número de dimensões por análise de perfil | Uma ou duas |
| Evidência mínima por combinação de perfil | A definir |
| Pesos no super destaque | 60 perfil, 25 desempenho, 15 gestor |
| Pesos no destaque | 80 perfil, 10 desempenho, 10 gestor |
| Intensidade das três penalidades | A definir |
| Decaimento da penalidade | A definir |
| Cotas por nível | 6.495 e 475 |
| Ordem de relaxamento | Definida |
| Tentativas e intervalo de repetição do Orquestrador | A definir |
| Idade máxima aceitável da coleta externa de reserva | A definir |
| Limiar de variação de volume que dispara sinalização | A definir |
| Prazo de atendimento de lead e limite de inatividade | A definir |

Toda alteração de parâmetro é registrada com data, autor e valor anterior.

---

## Agentes executores

Sete agentes mais um serviço compartilhado. O critério de separação adotado é o isolamento de falha: um agente existe quando pode falhar sozinho, com causa e conserto próprios.

### 1. Orquestrador

Dispara as duas rodadas fixas da semana em horário agendado, controla ordem e dependências, avalia os critérios de pronto e declara o estado final da rodada. A cadência é de dois momentos: sexta-feira para decisão e carga, segunda-feira para acompanhamento.

**Comportamento definido.** Quando uma etapa não fica pronta, ele repete a etapa algumas vezes antes de concluir que ela não vai completar. Só então decide entre seguir degradada ou abortar. O número de tentativas e o intervalo são parâmetros.

### 2. Coletor Interno

Lê o `newcore` e o `newcore_bi` e entrega o estoque elegível com atributos, leads, vendas, nota interna, produtividade do gestor e indicadores de distrito. Opera exclusivamente em leitura. É a única fonte sem a qual a rodada não acontece.

**Comportamento definido.** Quando o volume do estoque elegível varia muito em relação à semana anterior, ele entrega assim mesmo e sinaliza a variação na planilha, deixando o julgamento para o momento da aprovação. A rodada nunca é interrompida por variação de volume.

### 3. Coletor Externo

Raspa o Canal Pro no dia da atualização do estoque, amarra cada anúncio ao seu imóvel, mede a taxa de amarração e monta a planilha de raspagem com nota do portal, visualizações, cliques e a URL de cada anúncio. A URL é capturada durante a raspagem porque não existe em nenhuma tabela da base: o único endereço armazenado é o do site da própria Newcore.

A amarração entre anúncio e imóvel é responsabilidade dele, não de um agente separado, porque a consequência de uma amarração incompleta é limitada: o imóvel perde apenas essas três métricas externas e continua sendo avaliado pelo perfil, pelos leads internos, pela nota interna e pela produtividade do gestor.

A planilha de raspagem é **insumo interno**, consumida pelo Decisor e guardada no Registro. Não é entregável.

**Comportamento definido.** Se a raspagem da semana falhar, ele usa a última coleta bem-sucedida dentro de uma janela aceitável e informa a idade do dado. Como a raspagem passou a ser semanal, o dado de reserva terá tipicamente sete dias ou mais.

### 4. Analista de Perfil de Conversão

Constrói os perfis de imóvel que convertem a partir das vendas dos últimos seis meses, medindo uma ou duas dimensões por vez, com o número de vendas que sustenta cada resultado. Testa a hipótese de valor esperado contra as vendas.

É o único agente que produz conhecimento em vez de dado. Pode falhar sem quebrar a rodada: sem perfil, a priorização opera com os fatores restantes e isso fica registrado na justificativa.

### 5. Decisor

Aplica a elegibilidade, calcula os dois rankings, aloca nas cotas, executa o relaxamento e escreve a justificativa de cada escolha e o motivo de cada exclusão relevante.

Permanece íntegro por decisão explícita: suas etapas formam uma cadeia determinística que falha junto e se conserta junto, então separá-las criaria passagens de bastão sem ganho de isolamento.

O relaxamento fica dentro dele, com relatório obrigatório em seção própria da planilha. É a única etapa que desobedece deliberadamente ao critério, e por isso a auditoria dela é condição de pronto.

### 6. Redator da Entrega

Monta a planilha de decisão de sexta a partir do que o Decisor produziu e o relatório de acompanhamento de segunda a partir do que o Monitor produziu. Mantido como agente por decisão explícita, servindo aos dois ciclos com padrão único de formato.

### 7. Monitor Operacional

Roda na segunda-feira lendo apenas o banco, sem qualquer dependência de raspagem. Apura os leads entrados desde a carga de sexta, identifica os originados de posição paga a partir da planilha aprovada vigente, e produz duas listas: os leads sem atendimento e sem contato registrado, e todos os imóveis em posição paga com a contagem de leads que cada um gerou.

É o agente mais confiável do conjunto, e por isso o relatório de segunda existe mesmo em semanas em que a raspagem falhou por completo.

**Comportamento definido.** O relatório para no gestor da vitrine, nomeando corretor e gestor de distrito. O sistema não fala diretamente com essas pessoas. Não há alerta diário: a cadência semanal reconhece que o lead que não é atendido nas primeiras horas já está perdido, e o relatório serve para medir e cobrar padrão de comportamento, não para resgatar o lead individual.

### Registro

Serviço compartilhado, não agente. Persiste decisões, justificativas, cortes, relaxamentos, parâmetros vigentes, resultados por janela e o desfecho de cada rodada. Guarda apenas os imóveis escolhidos, cerca de sete mil por rodada, não os excluídos. Vive em **base própria do sistema**, separada do Newcore, sem exigir escrita na base de produção. A planilha de decisão é enviada por e-mail e arquivada no Drive do gestor da vitrine, como cópia de consulta humana.

Sem ele a penalidade não é calculável e a decisão não é auditável depois que a rodada aconteceu sem supervisão.

---

## Conceito de pronto por etapa

Nenhum agente entrega para o seguinte antes de cumprir suas condições de pronto.

### Coleta interna

**Pronto quando** todas as consultas retornaram, os campos obrigatórios estão presentes e o dado mais recente está dentro da janela de frescor.

**Sinaliza, sem impedir,** quando o volume do estoque diverge do esperado.

**Não está pronto se** campo obrigatório vier majoritariamente nulo ou o dado estiver desatualizado. Neste caso a rodada é abortada, porque sem estoque não há decisão.

### Coleta externa e amarração

**Pronto quando** a extração cobriu o conjunto esperado, os campos vieram preenchidos e a taxa de amarração entre anúncio e imóvel está acima do limiar.

**Não está pronto se** a sessão não autenticou, a cobertura ficou abaixo do esperado, ou a amarração ficou abaixo do limiar. Nesses casos aplica-se a última coleta válida, com a idade declarada, e a rodada segue.

### Perfil de conversão

**Pronto quando** ao menos um resultado foi produzido com evidência acima do mínimo e cada resultado carrega o número de vendas que o sustenta.

**Não está pronto se** nenhum resultado atingir o mínimo. A priorização opera sem esse fator e isso fica registrado.

### Decisão

**Pronto quando** todos os elegíveis passaram pelas regras, os dois rankings foram calculados com os pesos de cada nível, as cotas foram respeitadas sem excedente, cada item tem justificativa, cada exclusão relevante tem motivo, e todo relaxamento aplicado está no relatório com a regra que cedeu e a quantidade de posições dependentes.

### Entrega

**Pronto quando** a planilha contém as duas listas dentro das cotas, a justificativa por imóvel, o registro dos cortes, o relatório de relaxamento, as posições não preenchidas, os parâmetros vigentes, o estado da rodada e os avisos de variação de volume e de idade do dado externo.

### Rodada

**Completa quando** todas as etapas ficaram prontas.
**Degradada quando** alguma fonte falhou e a decisão prosseguiu com dado parcial, com a limitação declarada.
**Abortada quando** a coleta interna não fica pronta.

### Rodada de segunda-feira

**Pronto quando** os leads entrados desde a carga de sexta foram apurados, os originados de posição paga foram identificados a partir da planilha aprovada vigente, e as duas listas foram produzidas com responsável nomeado.

**Não está pronto se** não houver planilha aprovada vigente, porque sem ela não há como saber quais imóveis estavam em posição paga. Neste caso o relatório não é emitido e a ausência é declarada.

---

## Jornada do fluxo

### Rodada semanal

| Passo | Agente | Entrada | Saída |
|---|---|---|---|
| 1 | Orquestrador | Horário agendado e parâmetros vigentes | Rodada iniciada e registrada |
| 2 | Coletor Interno | Base transacional e analítica | Estoque elegível com todos os dados da decisão |
| 3 | Coletor Externo | Sessão autenticada no Canal Pro | Planilha de raspagem amarrada aos imóveis, com taxa de amarração |
| 4 | Analista de Perfil | Vendas dos últimos seis meses | Perfis por uma ou duas dimensões, com evidência de cada um |
| 5 | Decisor | Saídas dos passos 2, 3 e 4 e parâmetros | Lista de super destaque por valor esperado, lista de destaque por probabilidade de lead, justificativas, cortes e relatório de relaxamento |
| 6 | Redator | Saída do passo 5 | Planilha semanal |
| 7 | Registro | Saídas dos passos 5 e 6 | Decisão, justificativas e parâmetros persistidos |
| 8 | Dono da decisão | Planilha | Aprovação, remoção ou substituição |
| 9 | Operação | Planilha aprovada | Carga substituída manualmente no Newcore |

Na etapa 8, a remoção de um imóvel libera a posição, preenchida pelo próximo elegível do ranking daquele nível.

Entre a etapa 9 e a rodada seguinte não há verificação.

### Rodada de segunda-feira

| Passo | Agente | Entrada | Saída |
|---|---|---|---|
| 1 | Orquestrador | Horário agendado | Rodada iniciada |
| 2 | Monitor Operacional | Leads entrados desde a carga de sexta e planilha aprovada vigente | Leads dos imóveis em posição paga, identificados |
| 3 | Monitor Operacional | Dados de distribuição, atendimento e contato | Lista de leads sem atendimento e sem contato, e contagem de leads por imóvel em posição paga |
| 4 | Redator | Saída do passo 3 | Relatório de acompanhamento com responsáveis nomeados |
| 5 | Registro | Resultado da carga | Acumulação do resultado por janela de destaque |

O acumulado da etapa 5 alimenta a penalidade da rodada de sexta seguinte.

---

## Métricas de sucesso

**Métrica final.** Vendas atribuíveis a imóveis que estiveram em destaque, apuradas pela janela registrada cruzada com as propostas assinadas. Ciclo longo, com 52% das vendas fechando acima de 90 dias.

**Sinal intermediário semanal.** Leads e visitas gerados por posição paga durante e após a janela. Realimenta o ranking da semana seguinte. A linha de base é conhecida: 12% das janelas históricas geraram ao menos um lead.

**Indicador de aproveitamento.** Posições contratadas não preenchidas e posições preenchidas com regra relaxada, apurados por rodada.

**Indicador de território.** Proporção das vendas do período ocorridas fora do universo elegível. Hoje é de 25%.

**Validação inicial.** Calibração contra o histórico de janelas antes da primeira rodada agendada, incluindo o teste da hipótese de valor esperado.

---

## Personas

**Primária: gestor da vitrine.** Dono da decisão, aprova a carga de sexta, recebe o relatório de segunda e é quem cobra as pessoas. Nível técnico alto.

**Secundária: corretor.** Recebe e atende os leads gerados pela vitrine. Passa a ser avaliado quanto a tempo de atendimento. Não decide o que vai para destaque e não é notificado diretamente pelo sistema.

**Terciária: gestor de distrito.** Responde pela cobertura e performance dos corretores. É nomeado no relatório de segunda, mas a cobrança chega por meio do gestor da vitrine.

---

## Histórias de usuário e critérios de aceite

### História 1: receber a planilha semanal justificada

**Como** gestor da vitrine **quero** receber as duas listas com o motivo de cada imóvel ter entrado **para** aprovar com base em evidência.

- [x] As listas respeitam as cotas de 475 super destaques e 6.495 destaques.
- [x] Cada imóvel apresenta o critério que o classificou, o perfil com que casa, a evidência desse perfil e o resultado da sua última janela, quando houver.
- [x] Imóveis sem janela anterior são identificados como tal, sem penalização.
- [ ] A remoção de um imóvel libera a posição para o próximo elegível do mesmo nível.
- [ ] A rodada executa em horário agendado.
- [ ] Variação de volume, idade do dado externo e estado degradado aparecem de forma visível.

### História 2: excluir imóveis inviáveis antes da disputa

**Como** gestor da vitrine **quero** que imóveis inviáveis sejam eliminados antes do ranking **para** que a posição não seja gasta com imóvel que não converte por motivo conhecido.

- [x] O corte é binário e não admite compensação.
- [x] Cada exclusão registra o motivo.
- [ ] Imóvel fora de qualquer uma das nove regras não entra.
- [ ] Imóvel vendido, reservado ou removido sai imediatamente, fora do ciclo.

### História 3: descobrir o padrão que converte sem inventar padrão

**Como** gestor da vitrine **quero** saber quais características convertem **e** quanta evidência sustenta cada achado **para** não priorizar com base em coincidência.

- [x] A análise parte das vendas assinadas dos últimos seis meses.
- [x] O perfil mede uma ou duas dimensões por vez, nunca as cinco simultaneamente.
- [x] Cada resultado informa o número de vendas que o sustenta.
- [ ] Resultados abaixo da evidência mínima são declarados frágeis e não recebem peso pleno.
- [ ] A hipótese de valor esperado é testada contra vendas e o resultado é reportado.

### História 4: preencher o topo com valor e a base com volume

**Como** gestor da vitrine **quero** que os dois níveis sigam objetivos diferentes **para** que a posição escassa persiga receita e a abundante persiga contato.

- [ ] As 475 posições de super destaque exigem preço a partir de R$ 700.000 e são ordenadas por valor esperado.
- [ ] As 6.495 posições de destaque são ordenadas por probabilidade de lead.
- [ ] Cada nível usa seu próprio conjunto de pesos.
- [ ] A justificativa informa por qual objetivo o imóvel foi selecionado.

### História 5: não deixar benefício contratado sem uso

**Como** gestor da vitrine **quero** que o sistema ceda critério de forma controlada quando faltar imóvel **para** aproveitar posições já pagas.

- [x] O relaxamento se aplica apenas às posições de destaque.
- [x] As posições de super destaque nunca relaxam.
- [x] A ordem de cedência é fotos, cadastro, atualização, gestor e distrito.
- [x] Cada regra relaxada é registrada com a quantidade de posições que dependeram dela.
- [x] Se ainda faltar imóvel, a planilha informa quantas posições ficaram vazias.

### História 6: medir o que a carga produziu e cobrar o padrão

**Como** gestor da vitrine **quero** um relatório na segunda-feira **para** saber o que a carga de sexta produziu e quem deixou lead morrer.

- [x] O relatório cobre os leads entrados desde a carga de sexta.
- [x] Identifica os leads originados de imóveis em destaque e super destaque a partir da planilha aprovada vigente.
- [x] Lista os leads que não tiveram atendimento nem contato registrado, com corretor e gestor de distrito nomeados.
- [x] Lista todos os imóveis em destaque e super destaque com a quantidade de leads que cada um gerou, inclusive os que geraram zero.
- [x] Nenhuma notificação é enviada diretamente a corretor ou gestor de distrito.
- [x] Não existe alerta diário.
- [ ] A rodada de segunda executa em horário agendado e independe da raspagem.

---

## Fora de escopo

- Escrita automática em qualquer tabela de produção.
- Leitura da carga vigente como insumo da decisão.
- Confirmação de que a planilha aprovada foi aplicada.
- Aplicação automática da carga.
- Distinção entre destaque padrão, destaque exclusivo, super destaque e Topo VIP.
- Notificação direta a corretores e gestores de distrito.
- Correção automática de cadastro ou de precificação.
- Redistribuição automática de leads.
- Substituição da marcação de destaque feita por corretores na interface atual.
- Uso da lista de exclusão existente.
- Preço contra referência de mercado como critério.
- Definição de metas numéricas por métrica.

---

## Restrições técnicas

**Acesso a dados.** Leitura apenas sobre o Newcore. A escrita ocorre somente na base própria do Registro. A aplicação da carga é manual.

**Coleta externa.** O Canal Pro exige sessão autenticada. O portal apresentou aviso de instabilidade durante a varredura e a página de performance renderizou com elementos sem rótulo acessível. Com a raspagem passando a ser semanal, há uma única tentativa por rodada e o dado de reserva é o da semana anterior.

**Qualidade da coleta existente.** Cerca de 62% das execuções históricas terminaram com erro ou sem processar. A rodada degradada é estado previsto, não exceção.

**Volume de evidência.** As 176 vendas de seis meses limitam estruturalmente o que a análise de perfil pode afirmar. Essa é restrição de negócio, não de tecnologia, e não se resolve com ferramenta.

**Defeitos de dado.** Catalogados na base factual.

**Volume de dados.** As maiores tabelas relevantes são `realtyattributes` (4,2 milhões), `brokerneighborhoods` (6,1 milhões) e `userbrokerrelationshipshistoric` (7,5 milhões).

---

## Fases

### Fase 1: MVP

- Contrato vigente do Grupo OLX, com dois níveis agrupados.
- Elegibilidade com nove regras, perfil de conversão com evidência declarada, dois rankings, alocação, relaxamento e rotação.
- Planilha semanal com as duas listas, justificativas, cortes e relatório de relaxamento.
- Relatório de segunda com as duas listas, parando no gestor da vitrine.
- Execução agendada das duas rodadas.
- Registro persistente em base própria.
- Calibração contra o histórico, incluindo o teste da hipótese de valor esperado.

**Definição de MVP.** O menor conjunto que permite aprovar uma carga semanal com justificativa auditável, aproveitar as posições contratadas e acompanhar diariamente o que aquela carga produziu.

### Fase 2

- Dissecação dos subníveis do contrato.
- Estabilização ou substituição da coleta no Canal Pro.
- Notificação direta a gestores de distrito.
- Escrita direta após aprovação, com trilha de auditoria.
- Detecção por inferência de que a planilha provavelmente não foi aplicada.
- Preço contra referência de mercado como critério.

### Considerações futuras

- Ajuste automático dos pesos a partir do resultado observado.
- Regra de diversificação por distrito.
- Realocação automática de leads parados.
- Recuperação do território que vende e hoje está fora do universo elegível.

---

## Riscos

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Perfil de conversão produzir padrão a partir de coincidência | Alta | Alto | Apenas 176 vendas em seis meses. Análise limitada a uma ou duas dimensões por vez, com número de casos declarado e resultados frágeis sem peso pleno |
| Planilha aplicada parcialmente, com troca de itens ou com atraso | Alta | Alto | Risco assumido por decisão explícita. Sem verificação, o relatório de segunda atribui resultado a posições possivelmente inexistentes e a penalidade seguinte pode punir imóvel que nunca esteve em vitrine. Degradação silenciosa e cumulativa. Mitigação em aberto |
| Coleta externa falhar sem redundância | Alta | Médio | Com raspagem semanal há uma única tentativa por rodada. Uso da última coleta válida, com idade declarada. O impacto é limitado a três métricas de refinamento |
| Território que vende ficar fora do universo elegível | Alta | Alto | 25% das vendas dos últimos seis meses ocorreram em distritos que a regra exclui, mesmo após reduzir o mínimo para dois corretores. Acompanhado como indicador a cada rodada |
| Amarração ligar anúncio ao imóvel errado | Média | Médio | Taxa de amarração medida e reportada. Impacto limitado a nota do portal, visualizações e cliques |
| Hipótese de valor esperado não se confirmar | Média | Alto | Testada na calibração. Se falhar, o ranking de super destaque volta a perseguir probabilidade de conversão |
| Defeitos de dado tratados como critério | Alta | Alto | Catalogados; a coleta interna verifica preenchimento antes de declarar pronto |
| Concentração em poucos gestores | Alta | Médio | Universo elegível concentrado em poucas centenas de gestores. Distribuição monitorada desde o MVP |
| Penalidade por ausência de avaliação recair sobre metade dos candidatos | Alta | Médio | Cerca de 44% do estoque elegível não tem avaliação por categoria. Investigar a causa antes de calibrar a intensidade |
| Execução automática com critério não calibrado | Média | Médio | Calibração precede a primeira rodada agendada; a planilha continua exigindo aprovação |

---

## Dependências e decisões

**Dependências**

- Acesso de leitura estável ao `newcore` e ao `newcore_bi`.
- Provisionamento da base própria do Registro.
- Sessão autenticada no Canal Pro.
- Confirmação da periodicidade do valor contratual.
- Confirmação da localização do campo de vagas.

**Decisões tomadas com risco assumido**

- O sistema não confirma a aplicação da planilha.
- Ambas as rodadas executam de forma agendada desde o MVP.
- O corte de distrito é mantido, agora com mínimo de dois corretores, deixando 25% das vendas recentes fora do universo elegível.

**Decisões em aberto**

- Evidência mínima por combinação de perfil.
- Intensidade e decaimento das três penalidades.
- Tentativas e intervalo de repetição do Orquestrador.
- Idade máxima aceitável da coleta externa de reserva.
- Limiar de variação de volume que dispara sinalização.
- Limiar mínimo de taxa de amarração.
- Prazo de atendimento de lead e limite de inatividade.

- Horários de execução de cada rodada.
- Por que 44% do estoque elegível não possui avaliação por categoria.
- Valores-alvo das métricas de sucesso.

---

## Glossário

- **Carga semanal**: publicação periódica de anúncios, com sete dias de duração.
- **Destaque e super destaque**: posições de maior visibilidade no portal. No MVP, destaque agrupa destaque padrão e exclusivo; super destaque agrupa super destaque e Topo VIP.
- **Elegibilidade**: conjunto de nove regras eliminatórias, binárias e sem compensação, aplicadas antes do ranking.
- **Perfil de conversão**: combinação de características de imóvel que demonstradamente gera venda no período analisado, sempre acompanhada do número de casos que a sustenta.
- **Valor esperado**: probabilidade de conversão ponderada pelo ticket do imóvel. Objetivo do ranking de super destaque.
- **Janela de destaque**: intervalo em que um imóvel ocupou posição paga.
- **Distrito**: unidade territorial de organização comercial do Newcore.
- **Amarração**: correspondência entre o anúncio no portal e o imóvel no Newcore, responsabilidade do Coletor Externo.
- **Planilha de raspagem**: insumo interno com nota do portal, visualizações e cliques por imóvel. Não é entregável.
- **Relaxamento**: cedência controlada de regras de elegibilidade, apenas nas posições de destaque, com relatório obrigatório.
- **Planilha de decisão**: entrega semanal com as duas listas, justificativas, cortes e relaxamentos. Insumo da substituição manual e registro assumido do que está em vitrine.
- **Rodada completa, degradada e abortada**: estados possíveis de uma execução.
- **Pronto**: conjunto de condições verificáveis que uma etapa cumpre antes de entregar para a seguinte.

---

*Documento produzido por levantamento interativo de requisitos com pontuação de qualidade, apoiado em varredura direta das fontes de dados e no contrato vigente com o Grupo OLX, em 28 de agosto de 2026.*
