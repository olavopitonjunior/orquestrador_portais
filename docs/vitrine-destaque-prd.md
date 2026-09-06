# Documento de Requisitos de Produto: Curadoria Orquestrada da Vitrine de Destaques

**Versão**: 6.0
**Data**: 2026-08-28 · **Revisão 6.0**: 2026-09-05, autorizada pelo dono da decisão ([P-23]), incorporando as decisões D-001 a D-034 de `docs/decisoes.md` — com efeito maior das **D-002/D-003** (o piso de R$ 700.000 e o status impeditivo deixam de ser regras de elegibilidade), **D-011** (o Console do Operador), **D-014** (evidência mínima N ≥ 3), **D-021/D-023** (só a última janela é julgada), **D-027** (o perfil de conversão vira a nona regra e o primeiro degrau da cedência), **D-028** (o banco manda, o portal classifica: a nota é do anúncio, em pontos de 100), **D-029** (o login do gestor trava o relaxamento), **D-030/D-034** (descontos em pontos e a parametrização adotada) e **D-031** (dois parâmetros dissolvidos sem valor).
**O que esta revisão não faz**: não preenche nenhum dos nove parâmetros que seguem nulos, não resolve nenhuma pergunta aberta de `docs/perguntas-abertas.md`, e não alinha o PRD ao código nos pontos em que o código é que diverge — esses ficam declarados como divergência. Onde esta revisão e uma decisão registrada divergirem, a decisão prevalece (regra do topo de `docs/decisoes.md`).
**Autoria**: Sarah (Product Owner)
**Dono da decisão**: Olavo
**Score de qualidade dos requisitos**: 99/100

---

## Sumário executivo

A Newcore mantém contrato vigente com o Grupo OLX no plano Exclusivo, que cobre OLX, Zap e Viva Real, com 50.000 ofertas. O contrato é dimensionado para a base inteira de imóveis e já está pago independentemente do uso; dentro dele, 6.970 ofertas são posições de destaque e super destaque. A escolha de quais imóveis ocupam essas posições não segue critério objetivo, e o resultado é mensurável: de 59.653 janelas de destaque já registradas, 88% não geraram um único lead.

Este produto substitui essa escolha por uma cadeia de decisão orquestrada e executada sem intervenção. Sete agentes sob um orquestrador coletam dados internos do Newcore, raspam a performance externa no Canal Pro no dia da atualização do estoque, identificam os padrões de imóvel que convertem, aplicam critérios eliminatórios objetivos, ordenam os elegíveis e entregam semanalmente uma planilha justificada. A ordenação é uma só, e o que separa os dois níveis é o piso de preço aplicado na alocação (D-028); os objetivos distintos por nível sobrevivem como intenção do critério, não como duas contas. A carga é substituída manualmente a partir dela. Na segunda-feira seguinte, um ciclo de acompanhamento que lê apenas o banco produz o relatório da carga: os leads sem atendimento e sem contato originados de imóveis em posição paga, e o desempenho de cada posição.

O produto resolve dois problemas de sinal oposto. Nas 475 posições de super destaque há disputa real — **2.389 candidatos acima do piso, cinco por vaga** (06/09/2026) — e o ranking persegue valor esperado. Nas 6.495 posições de destaque não há disputa, e o objetivo é não deixar benefício contratado sem uso.

**A folga do destaque acabou, e isso muda o papel do relaxamento.** A versão anterior deste documento registrava folga de 48%: sobravam imóveis aprovados para as posições contratadas. Medido em 06/09/2026, **faltam 116**. O relaxamento foi desenhado como plano B para uma semana ruim e passa a ser o mecanismo ordinário de encher a cota **do destaque** — cedendo, primeiro, o próprio filtro de perfil. O super destaque nunca relaxa. **O dono decidiu manter esse desenho** (D-036), diante da alternativa de deixar vazia a posição que nenhum imóvel aprovado preencha. A planilha declara cada cedência, imóvel por imóvel, com a regra que cedeu.

**Como estes números foram obtidos.** Medidos em 06/09/2026 pelo próprio pipeline da rodada, não por consulta exploratória — a série completa, os cortes regra a regra e a causa da queda estão em `docs/mapa-de-dados.md`, seção "O funil pelo pipeline". A leitura de fundação, de 28/08/2026, dava 10.290 elegíveis, 4.852 candidatos ao super destaque e folga de 48%; ela precede o coletor interno e **não é comparável diretamente** — e, principalmente, a base andou. O patamar do pipeline foi de 7.801 (02/09) a 8.230 (04/09) e 8.197 (06/09) na contagem sem o filtro de perfil, que é a comparável com aqueles 10.290: degrau, não oscilação diária. A causa está medida e é comercial, não técnica — os distritos com dois ou mais corretores produtivos caíram de **61 para 46**, e com três ou mais de 39 para 18, na mesma coluna e com o mesmo predicado. Os parágrafos históricos abaixo preservam a medição de fundação, sempre datada.

O sistema não consulta a carga vigente e não confirma se a planilha foi aplicada. A planilha aprovada é o registro assumido do que está em vitrine.

---

## Problema

**Situação atual.** As posições de destaque são ocupadas sem critério comum. A marcação existente na interface, feita de forma distribuída pelos corretores, não define a carga e não tem efeito prático sobre a decisão comercial.

**Evidência.** Nas 59.653 janelas registradas, a média é de 0,21 lead por janela e 88% terminaram sem nenhum lead. A duração média observada é de 33 dias, contra os sete dias de ciclo de carga, o que indica que a vitrine não gira.

**Natureza econômica do desperdício.** O valor do contrato cobre o pacote completo de anúncios, que a base precisa de qualquer forma. Os destaques são benefício embutido, não item de custo separado. Portanto uma posição de destaque mal ocupada não gasta dinheiro adicional, e uma posição vazia não gera custo direto: ambas representam benefício contratado que deixou de ser extraído. Isso reduz o custo de preencher uma posição de destaque com um imóvel apenas razoável, já que não há fila: com 0,98 candidato por vaga no destaque (06/09/2026), nenhum imóvel melhor perde posição por causa disso — e o mesmo vale, com mais força, quando faltam candidatos. No super destaque a lógica não vale, porque lá a posição é genuinamente escassa.

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
- Cerca de 44% do estoque elegível não possui avaliação por categoria em `realty_score_category_score` — **medido em 56,3 % entre os elegíveis da rodada 30417** (06/09/2026). **Cuidado com a base, porque ela decide o veredito.** A tabela de riscos (§ Riscos) dá como Alta a probabilidade de a penalidade "recair sobre metade dos **candidatos**" — e entre os 48.812 candidatos a taxa medida é **35,3 %**, cerca de um terço. Na base em que foi escrita, a previsão **não se confirmou**; passa de metade só no recorte mais estreito dos elegíveis. Ressalva de método: a medição **não separa** deriva do estoque de composição do conjunto elegível — os 35,3 % estão *abaixo* dos 44 % de 28/08, então quem produz os 56 % é a filtragem do funil, **não necessariamente** o acúmulo de estoque novo, e a definição de "elegível" mudou no período (a D-027 acrescentou a nona regra).
- `realties` não expõe quantidade de vagas diretamente.
- Campos de placa e de impulsionamento estão integralmente vazios.
- `adswhitelist` está abandonada desde 2022. `adsblacklist` está viva com 12.155 imóveis, mas foi decidido ignorá-la.

---

## Critérios de decisão

### Estágio 1: elegibilidade

**Nove** regras eliminatórias, binárias, sem compensação entre si. Reprovar em uma basta para excluir. Oito são gerais e fixas; a nona é o perfil de conversão, definido no Estágio 2 (D-027).

| Regra | Definição operacional |
|---|---|
| Base ativa | Status de publicação Ativo |
| Categoria | Casa, Casa de condomínio, Sobrado, Cobertura e Apartamento |
| Preço mínimo geral | Igual ou superior a R$ 300.000 |
| Fotos | Dez ou mais fotos |
| Cadastro atualizado | Atualizado nos últimos 90 dias |
| Cadastro completo | Nenhuma das sete categorias da nota interna com pontuação zero |
| Gestor produtivo | Corretor gestor captou ou vendeu nos últimos 30 dias |
| Capacidade do distrito | Distrito com corretores que captaram ou venderam nos últimos 30 dias em número igual ou superior ao mínimo declarado (adotado: dois) |
| Perfil de conversão | Casa ao menos um perfil que conta (Estágio 2). Quando nenhum perfil conta, ou o candidato não tem dimensões na coleta, a regra não é avaliada: o imóvel não é reprovado por ela e a rodada declara a limitação |

Duas condições que **este documento já tratou como regra e não são**:

- **O piso de R$ 700.000 do super destaque é condição de nível**, aplicada na alocação (Estágio 4), não regra de elegibilidade (D-002). Tratá-lo como regra geral excluiria o estoque inteiro do destaque.
- **O status impeditivo — vendido, reservado, despublicado — é regra de saída imediata** (Rotação), não filtro de entrada (D-003).

Definições que fecham ambiguidade:

- **Gestor, não captador.** O vínculo usado é o de gestão, disponível para todo o estoque.
- **Imóvel sem avaliação por categoria não é excluído.** Passa e recebe desconto no ranking.
- **O login do gestor não exclui ninguém.** Medido em 04/09/2026, "sem login em 30 dias" é subconjunto estrito de "gestor não produtivo": como regra de entrada não excluiria nada além do que a regra de gestor produtivo já exclui. Ele age no relaxamento, como trava (Estágio 5, D-029).
- **A lista de exclusão existente é ignorada.**
- **Preço contra referência de mercado não é regra de corte** nesta versão.

Permanecem as regras derivadas do diagnóstico de funil, que qualificam o motivo da exclusão:

| Sintoma observado | Diagnóstico | Encaminhamento |
|---|---|---|
| Poucas visualizações e nota interna baixa | Qualidade do anúncio | Pendência de cadastro |
| Boas visualizações e poucos cliques | Preço ou concorrência | Pendência de precificação |
| Muitos leads e poucas visitas | Atendimento, densidade de corretor ou falta de opção | Alerta operacional |

Poucas visualizações com nota interna alta não é motivo de exclusão. É o caso que o destaque resolve.

### Funil de elegibilidade medido em 06/09/2026

Pelo pipeline da rodada, com as **nove** regras. Cada linha é o que sobra depois da regra.

| Etapa acumulada | Imóveis | Corta |
|---|---:|---:|
| Recorte ativo lido | 48.812 | — |
| Publicação ativa | 48.806 | 6 |
| Nas cinco categorias | 41.312 | 7.494 |
| Preço igual ou acima de R$ 300.000 | 35.451 | 5.861 |
| Dez ou mais fotos | 34.389 | 1.062 |
| Cadastro completo | 26.877 | 7.512 |
| Atualizado nos últimos 90 dias | 19.271 | 7.606 |
| **Casa um perfil de conversão** | 15.287 | 3.984 |
| Gestor produtivo | 11.218 | 4.069 |
| Capacidade do distrito | **6.854** | 4.364 |

Para comparar com o histórico, o mesmo funil **sem** a regra de perfil termina em 8.197 — é essa a grandeza que se compara aos 10.290 de 28/08/2026.

As três primeiras etapas variaram 0,3 a 0,4% em nove dias: o estoque está estável. A queda está nas duas regras de corretor, e a causa está medida no mapa de dados.

**Situação por nível:**

| Nível | Posições | Candidatos | Concorrência |
|---|---|---|---|
| Super Destaque | 475 | 2.389 acima de R$ 700.000 | 5,0 por vaga |
| Destaque | 6.495 | 6.379 restantes | 0,98 por vaga |
| Total | 6.970 | 6.854 | **Déficit de 116** |

Medição de 06/09/2026, com as nove regras. **A comparação com 28/08 exige cuidado**: aqueles 4.852 candidatos ao super e 10,2 por vaga são anteriores ao filtro de perfil, e o comparável de hoje é **3.732 / 7,9 por vaga**; os 2.389 / 5,0 da tabela têm uma regra a mais. Do mesmo modo, os 10.290 do total comparam-se com 8.197, não com 6.854. A série completa está no mapa de dados. **Um único instante já foi medido abaixo da cota**; duas leituras não estabelecem frequência, e a de 05/09 dava 39 imóveis de sobra.

### Custo de cada regra

Efeito de relaxar cada regra isoladamente. Medido com o mínimo de três corretores por distrito e mantido como referência de ordem de grandeza; os valores absolutos mudam com o mínimo de dois. **Falta o primeiro degrau**: o ganho de ceder o perfil de conversão não foi medido nesta data, porque a regra é de 04/09/2026 — a prévia do console o mede a cada pedido.

| Regra relaxada | Ganho aproximado |
|---|---|
| Dez ou mais fotos | +133 |
| Cadastro completo | +569 |
| Atualizado em 90 dias | +1.680 |
| Gestor produtivo | +1.747 |
| Capacidade do distrito | +5.686 |

A regra de fotos quase não filtra: 98,4% dos candidatos já têm dez fotos.

### Cobertura de território que vende

Das 176 vendas dos últimos 180 dias (leitura de 28/08/2026; a contagem canônica é **177** — assinadas no período, incluídas as posteriormente canceladas, D-013 — e mediram-se **184** em 04/09/2026), 132 ocorreram em distritos que a regra de dois corretores ativos aceita, e 44 ficaram fora. Com o mínimo de três corretores, a cobertura seria de 109 vendas e 67 ficariam fora. A redução do mínimo de três para dois elevou a cobertura de 62% para 75% das vendas recentes, ampliou o universo elegível de 8.321 para 10.290 imóveis e aumentou os distritos elegíveis de 39 para 61, de um total de 126 com algum corretor ativo.

O quarto das vendas que permanece fora do universo elegível é indicador a acompanhar a cada rodada.

### Estágio 2: perfil de conversão

Constrói os padrões de imóvel que convertem a partir das **vendas assinadas da janela declarada** (adotada: 180 dias, D-033), o que correspondeu a 176 casos em 28/08/2026 e a 184 em 04/09/2026. **Só vendas**: leads não entram na base do perfil, porque em volume dominariam as vendas em cerca de 30 para 1 e o perfil deixaria de descrever o que vende (D-032).

**Restrição de método, imposta pelo volume.** O perfil não cruza as cinco dimensões simultaneamente. Ele mede **uma ou duas dimensões por vez**, começando pelas que mais separam, e cada resultado é acompanhado do número de vendas que o sustenta. Um perfil é **robusto** quando tem ao menos **três vendas** (evidência mínima, D-014); abaixo disso é **frágil**.

As dimensões disponíveis são região, faixa de preço, faixa de metragem, quantidade de dormitórios e quantidade de vagas.

**O perfil é regra, não fator (D-027).** Um perfil **conta para o filtro** quando é robusto **e contém a faixa de preço**. A exigência da faixa de preço não é estética: sem ela, a faixa de metragem sozinha casava 100% do estoque e o filtro não filtrava nada; com ela passam 83,8% dos elegíveis e 64% dos candidatos ao super destaque (medição de 04/09/2026). **Perfil frágil não conta — não pesa menos, não pesa nada**; o desconto de fragilidade que versões anteriores previam deixou de existir. Um candidato **casa** um perfil quando satisfaz todas as dimensões dele, com a mesma bucketização dos dois lados.

O **"perfil que puxou"** — o perfil robusto de mais vendas entre os que o candidato casa — é rótulo da justificativa, não decisão. A ordem de importância entre as dimensões sobrevive apenas como critério de exibição: com o perfil virando veredito binário, ela deixou de ter efeito no cálculo, e o parâmetro que a quantificaria — o decaimento entre dimensões, nº 13 — foi **dissolvido sem valor**, junto com o nº 12, os pesos dos quatro fatores por nível (D-031).

Um imóvel entra por semelhança com um perfil vencedor mesmo sem desempenho próprio. Dado que a maioria dos elegíveis não teve lead nos últimos 180 dias — 84% na leitura de 28/08/2026 —, este é o mecanismo que decide **quem entra**; a ordem, essa é do portal (Estágio 3).

**Hipótese a testar na calibração.** O cruzamento entre frequência de lead e ticket sugere que o valor esperado cresce com o preço, ainda que a probabilidade de lead caia: a frequência cai de 22% na faixa de 400 a 500 mil para 5,5% na faixa de 2 a 2,5 milhões, enquanto o ticket cresce mais rápido. O indicador usado é proxy grosseiro e a hipótese precisa ser validada contra vendas. **Ela não tem mais peso para virar**: desde a D-028 a nota é do portal e não há fator de perfil no ranking. O que "testar a hipótese" entrega segue não especificado ([P-19]).

### Estágio 3: priorização

**Objetivos distintos por nível:**

| Nível | Objetivo do ranking |
|---|---|
| Super Destaque | Valor esperado, isto é, probabilidade de conversão ponderada pelo ticket |
| Destaque | Probabilidade de gerar lead |

**O portal classifica (D-028).** A **nota bruta** de cada imóvel é a soma ponderada de três sinais do seu anúncio no Canal Pro, com pesos em **pontos de 100 que somam exatamente 100**:

| Sinal do anúncio | Peso adotado | Razão medida |
|---|---|---|
| Nota do anúncio no portal | 70 | único sinal com variância medida: 14 valores distintos em 300 anúncios (03/09/2026) e **69 em 55.162 na coleta completa (06/09)**, com preenchimento de 100 %. A conclusão saiu reforçada |
| Cliques, somados entre tipos | 30 | sinal fraco mas real, e é intenção de compra, não curiosidade — **bem mais fraco do que a frase sugeria**: algum clique aparece em 1,69 % dos 55.162 anúncios, e proposta e agendamento são zero em todos. Na rodada 30417 separou 124 dos 6.970 escolhidos, contra 1.550 das visualizações, que pesam zero ([P-25]) |
| Visualizações | 0 | medido zero em 300 de 300 anúncios em 03/09/2026 — **premissa caída em 06/09**: a primeira coleta completa achou 13.175 dos 55.162 com visualizações, 23,9 %. O zero segue adotado (D-034) até decisão do dono ([P-25]); o que caiu foi a razão, não o valor |

Cada sinal é reescalado para uma escala comparável antes de somar. A **forma** dessa normalização é o parâmetro nº 2, que segue **nulo**: a forma em uso (min-max) é **provisória**, sai rotulada como tal na planilha e não foi adotada (D-016). O reescalonamento acontece entre os elegíveis no ranking primário e entre os reprovados no relaxamento — as duas ordenações são internas a cada grupo e nunca se comparam.

**Os dois níveis usam a mesma nota.** O que os separa é o piso de preço aplicado na alocação (Estágio 4), não um conjunto de pesos por nível. A tabela de pesos por nível que este documento trazia até a versão 5.0 — 60/25/15 e 80/10/10 sobre perfil, desempenho e gestor — **deixou de existir** com as D-027 e D-028: o perfil virou regra, e o desempenho de portal virou a nota inteira em vez de um fator entre quatro.

**Leads e produtividade do gestor não pesam na nota**: viraram o desempate — leads em 180 dias primeiro, depois o cadastro mais novo (D-009 por último).

**Imóvel sem anúncio raspado** recebe o tratamento declarado — fim da fila (adotado) ou a nota mediana daquele sinal entre os que o têm —, nunca um zero silencioso. O tratamento é por sinal: um anúncio pode ter nota e não ter cliques.

A capacidade de distrito não participa do ranking, porque o distrito já atua como regra eliminatória.

**Descontos, subtraídos da nota bruta em pontos de 100** (D-030) e sempre visíveis na justificativa:

| Desconto | Quando se aplica | Adotado |
|---|---|---|
| Janela anterior sem resultado | O imóvel ocupou posição e não atingiu o resultado esperado para o nível | 20 pontos |
| Sem avaliação por categoria | O imóvel não tem nenhuma categoria da nota interna avaliada | 5 pontos, baixo de propósito: o pipeline de avaliação parou em 16/10/2025 e 99,76% do estoque novo não tem nota — descontar alto puniria o estoque novo por defeito da base |
| Sem lead em 180 dias | O imóvel não recebeu nenhum lead no período | 10 pontos (D-030). Alcança a maior parte do estoque — 84% na leitura de 28/08/2026, e **78,3 % medidos entre os elegíveis da rodada 30417** (77,0 % entre os escolhidos, 76,3 % entre todos os candidatos) —, de modo que na prática funciona como bônus para a minoria com histórico recente |

Apenas a **última** janela é julgada, não qualquer uma do histórico (D-023). Imóveis sem histórico de destaque não são penalizados por ausência de histórico.

### Estágio 4: alocação nas cotas

Preenche primeiro as 475 posições de super destaque: aplica o piso de R$ 700.000 — que é **condição de nível**, não regra de elegibilidade (D-002) —, ordena pela nota final com o desempate do Estágio 3 e corta na cota. Depois preenche as 6.495 posições de destaque, entre os elegíveis restantes, na mesma ordem.

**Nenhuma posição excedente é proposta.** O corte por fatia torna o excesso impossível por construção, não por conferência posterior.

Os objetivos por nível — valor esperado no super destaque, probabilidade de gerar lead no destaque — permanecem como **intenção do critério**, e é o que justifica o piso de preço num nível e a cedência de regras no outro. Eles não são duas grandezas calculadas: a nota é uma só (Estágio 3).

### Estágio 5: relaxamento por falta de candidato

Se faltar imóvel apto, o sistema cede regras progressivamente até completar, **apenas nas posições de destaque**. As posições de super destaque nunca relaxam — **inclusive para a regra do perfil**, que é o primeiro degrau da cedência e por isso o mais fácil de ler como cedível nos dois níveis.

**Ordem de cedência (D-027):** **perfil de conversão**, fotos, cadastro completo, atualização em 90 dias, gestor produtivo e, por último, capacidade do distrito. A cedência é progressiva e mínima: um degrau só é cedido se o déficit sobrou depois de esgotar o anterior, e para assim que o déficit zera.

**Consequência declarada da ordem.** Como o perfil é o primeiro degrau, ele morde de verdade no super destaque, que nunca relaxa; no destaque é a primeira coisa de que a rodada abre mão quando faltam imóveis — e, pela medição de 02/09/2026, vai faltar quase toda semana.

**Trava do login (D-029).** O degrau `gestor produtivo` — e qualquer degrau posterior, que o inclui — **não recupera** imóvel cujo gestor não entrou no sistema dentro da janela declarada (adotada: 30 dias). Quem não loga não atende o lead que a posição paga gerar. O imóvel fica irrecuperável, e a rodada conta e declara quantos foram travados (medido: 105 dos 2.092 recuperáveis por esse degrau, 04/09/2026).

O relaxamento é executado pelo Decisor e obriga relatório próprio na planilha, indicando qual regra cedeu e quantas posições dependeram de cada cedência — **inclusive zero**, para degrau cedido que não recuperou ninguém. Sem esse relatório a etapa não é considerada pronta.

### Rotação e penalidade

- A lista é recalculada integralmente a cada carga semanal. Não há permanência automática.
- Venda, reserva, despublicação ou alteração relevante de preço provocam saída imediata, fora do ciclo.
- Resultado suficiente é proporcional ao tipo de posição: super destaque exige entrega superior à de destaque.
- O desconto por resultado insuficiente enfraquece a cada **carga aprovada** em que o imóvel permanece: perdão de 50% por carga (adotado). A unidade é a carga, não a semana de calendário — uma sexta que não virou carga não enfraquece desconto nenhum. Mudança de nível fecha a janela e abre outra (D-021).

**O limiar de resultado é nulo, e por isso o desconto não incide.** Quanto é "resultado suficiente" **para cada nível** é o parâmetro nº 14, e ele segue **nulo por decisão expressa do dono** (D-022, D-030): são dois valores, um por nível, e nenhum documento jamais os quantificou. Enquanto forem nulos, o desconto de 20 pontos por janela anterior **existe, é mostrado e não incide**, e a planilha declara isso em toda rodada. A leitura "pelo menos um lead" — que a base histórica deste documento poderia sugerir — foi **examinada e descartada** pelo dono; ela não é o valor do nº 14, e preenchê-lo por conta própria é o erro que este parágrafo existe para impedir.

**O que dos quatro gatilhos de saída é detectável hoje.** Venda, despublicação e alteração de preço têm fato no banco. **A reserva não tem**: o Newcore não modela imóvel reservado em coluna viva nenhuma — o carimbo que teria esse nome é de criação, preenchido em 99,90% dos ativos —, e adotar um substituto é pergunta aberta ([P-21]). A **magnitude** da "alteração relevante de preço" é o parâmetro nº 15, **nulo**, e nem se sabe ainda se é um valor só ou um por nível (D-025): enquanto nulo, esse gatilho não é implementável.

**"Fora do ciclo" está em aberto, e esta revisão não o resolve.** Este documento diz, em outro ponto, que existem dois momentos por semana e nenhuma execução diária — as duas afirmações são do **mesmo** documento, e por isso a hierarquia não as arbitra. As leituras possíveis (criar um terceiro momento, ler "imediatamente" como "na próxima sexta", ou tratar fora do sistema) produzem sistemas diferentes, e a segunda **foi medida e caiu**: o status é binário e 24,69% dos imóveis com venda assinada nos últimos 180 dias seguem ativos. Fica registrado como [P-20]. O que já está fixado: "sair imediatamente" só pode significar **emitir a substituição**, porque o sistema não publica nada (D-024).

Observação de desenho: sem folga no destaque — 0,98 candidato por vaga em 06/09/2026 —, a rotação real ali é baixa por construção, e o que decide quem sai passa a ser a cedência, não o ranking. A rotação efetiva acontece no super destaque, onde há cinco candidatos por vaga.

---

## Parâmetros de decisão

A lista canônica, com a numeração usada em todo o projeto, vive na tabela do `CLAUDE.md`; o que segue é a leitura de produto dela. Os valores marcados **adotado** são da decisão D-034 e podem ser declarados diferentes para uma rodada — o que for declarado sai rotulado na planilha e não muda o adotado.

**Fixos, não parametrizáveis**

| Parâmetro | Valor |
|---|---|
| Preço mínimo geral | R$ 300.000 |
| Piso de nível do super destaque | R$ 700.000 (condição de nível, não regra) |
| Categorias aceitas | Cinco categorias definidas |
| Número mínimo de fotos | 10 |
| Janela de atualização do cadastro | 90 dias |
| Definição de gestor produtivo | Captou ou vendeu em 30 dias (janela agregada na fonte, D-032) |
| Número de dimensões por análise de perfil | Uma ou duas |
| Evidência mínima por combinação de perfil | 3 vendas (parâmetro nº 1, **resolvido** pela D-014; é constante de domínio e não está entre os campos declaráveis da rodada) |
| Cotas por nível | 475 e 6.495 |
| Ordem de cedência do relaxamento | Definida: perfil, fotos, cadastro, atualização, gestor, distrito |

**Declaráveis por rodada, com valor adotado**

| Parâmetro | Adotado | Origem |
|---|---|---|
| Janela de vendas para o perfil | **180 dias** | D-033 |
| Mínimo de corretores ativos no distrito | **2** | D-015, D-033 |
| Janela de login do gestor (trava do relaxamento) | **30 dias** | D-029 |
| Pesos da nota: anúncio · cliques · visualizações | **70 · 30 · 0** pontos de 100 | D-028, D-034 |
| Cobertura mínima da raspagem | **50%** | nº 7, D-034 |
| Idade máxima aceitável da coleta externa | **2 dias** | nº 5, D-034 |
| Tratamento do imóvel sem anúncio raspado | **fim da fila** | D-028 |
| Ordem quando a raspagem não entra | **leads em 180 dias** | D-028 |
| Descontos: janela anterior · sem avaliação · sem lead | **20 · 5 · 10** pontos de 100 | nº 3, D-030, D-034 |
| Perdão do desconto de janela, por carga aprovada | **50%** | nº 3, D-030 |

**Ainda nulos — nenhum pode receber valor inventado, nem "provisório"**

| # | Parâmetro | Situação |
|---|---|---|
| 2 | Forma de normalização de cada sinal do ranking | nulo. A forma em uso (min-max) é **PROVISÓRIA**, rotulada na planilha e **não adotada** (D-016) |
| 4 | Tentativas e intervalo de repetição do Orquestrador | nulo |
| 6 | Limiar de variação de volume que dispara sinalização | nulo |
| 8 | Horários exatos de execução na sexta e na segunda | nulo |
| 9 | Política de retenção do Registro | nulo |
| 10 | Prazo da aprovação tácita | nulo |
| 11 | Prazo de atendimento de lead e limite de inatividade | nulo |
| 14 | Resultado esperado **por nível** para a janela não ser penalizada — **dois** valores | nulo (D-022). Enquanto nulo, o desconto de janela não incide |
| 15 | Magnitude da "alteração relevante de preço" que dispara a saída — e se é um valor ou um por nível | nulo (D-025). Enquanto nulo, o gatilho de preço não é implementável |

**Deixaram de existir**, dissolvidos pela D-031 quando o perfil virou regra e o portal virou a nota: o nº 12, que era o conjunto de pesos dos quatro fatores por nível, e o nº 13, o decaimento entre as dimensões do perfil. Nenhum dos dois recebeu valor — a pergunta desapareceu com a mecânica que a fazia. Os números ficam vagos e não são reaproveitados.

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

A amarração entre anúncio e imóvel é responsabilidade dele, não de um agente separado. **A consequência de uma amarração incompleta deixou de ser limitada** (D-028): como a nota do ranking é agora a do anúncio, o imóvel que não amarra não perde três métricas de refinamento — perde a nota inteira e cai para o tratamento declarado do "sem anúncio". Se a raspagem não entra de todo, a rodada ordena pelo sinal de banco declarado e sai **degradada com a limitação nomeada**.

A planilha de raspagem é **insumo interno**, consumida pelo Decisor e guardada no Registro. Não é entregável.

**Comportamento definido.** Se a raspagem da semana falhar, ele usa a última coleta bem-sucedida dentro de uma janela aceitável e informa a idade do dado. A janela aceitável é de **2 dias** (adotado, D-034) — dado da semana anterior, com sete dias ou mais, **não passa**. Requisito ainda não implementado: o reuso de uma coleta anterior como reserva não existe hoje, e a limitação está declarada na especificação.

### 4. Analista de Perfil de Conversão

Constrói os perfis de imóvel que convertem a partir das vendas da janela declarada, medindo uma ou duas dimensões por vez, com o número de vendas que sustenta cada resultado.

É o único agente que produz conhecimento em vez de dado. **A consequência de ele falhar mudou com a D-027**: como o perfil virou regra de entrada, não há "operar sem esse fator". Quando nenhum perfil conta, a regra do perfil **não é avaliada** — ninguém é reprovado por ela, o que é diferente de todos reprovarem — e a rodada segue **degradada, com a limitação nomeada** na planilha.

### 5. Decisor

Aplica as nove regras de elegibilidade, calcula a nota, aloca nas cotas, executa o relaxamento e escreve a justificativa de cada escolha e o motivo de cada exclusão relevante. **A nota é uma só** para os dois níveis (D-028); o que os separa é o piso de preço na alocação.

Permanece íntegro por decisão explícita: suas etapas formam uma cadeia determinística que falha junto e se conserta junto, então separá-las criaria passagens de bastão sem ganho de isolamento.

O relaxamento fica dentro dele, com relatório obrigatório em seção própria da planilha. É a única etapa que desobedece deliberadamente ao critério, e por isso a auditoria dela é condição de pronto.

### 6. Redator da Entrega

Monta a planilha de decisão de sexta a partir do que o Decisor produziu e o relatório de acompanhamento de segunda a partir do que o Monitor produziu. Mantido como agente por decisão explícita, servindo aos dois ciclos com padrão único de formato.

### 7. Monitor Operacional

Roda na segunda-feira lendo apenas o banco, sem qualquer dependência de raspagem. Apura os leads entrados desde a carga de sexta, identifica os originados de posição paga a partir da **carga vigente registrada** — a lista da rodada de decisão aprovada, lida do Registro; a planilha do Drive é cópia de consulta humana e nunca é lida de volta (D-001) —, e produz duas listas: os leads sem atendimento e sem contato registrado, e todos os imóveis em posição paga com a contagem de leads que cada um gerou.

É o agente mais confiável do conjunto, e por isso o relatório de segunda existe mesmo em semanas em que a raspagem falhou por completo.

**Comportamento definido.** O relatório para no gestor da vitrine, nomeando corretor e gestor de distrito. O sistema não fala diretamente com essas pessoas. Não há alerta diário: a cadência semanal reconhece que o lead que não é atendido nas primeiras horas já está perdido, e o relatório serve para medir e cobrar padrão de comportamento, não para resgatar o lead individual.

### Registro

Serviço compartilhado, não agente. Persiste decisões, justificativas, cortes, relaxamentos, parâmetros vigentes, resultados por janela e o desfecho de cada rodada. Guarda apenas os imóveis escolhidos, cerca de sete mil por rodada, não os excluídos. Vive em **base própria do sistema**, separada do Newcore, sem exigir escrita na base de produção. A planilha de decisão é enviada por e-mail e arquivada no Drive do gestor da vitrine, como cópia de consulta humana.

Sem ele a penalidade não é calculável e a decisão não é auditável depois que a rodada aconteceu sem supervisão.

### Console do Operador

Superfície nova, criada pela D-011, que as versões anteriores deste documento não previam. **Não é agente e não decide nada**: é a tela por onde o gestor da vitrine declara os parâmetros da semana, pede a prévia do funil, dispara a rodada, acompanha o que cada agente concluiu e baixa a planilha. O console **enfileira**; quem executa é um processo separado, porque a rodada leva minutos e uma requisição web não sobrevive a ela.

Fica em **esquema próprio da mesma base própria do sistema**, separado do Registro: o Registro é o trilho de auditoria da **decisão**, e fila de trabalho, rascunho de parâmetro e adiamento são **operação** — dizem respeito a quem clicou e quando, não ao que foi decidido. Toda escrita do console é nessa base; nenhuma toca o Newcore.

A prévia é o elo entre definir e rodar: roda o funil de elegibilidade com os parâmetros da tela, sem raspagem e sem ranking, e responde quantos imóveis sobram para as 6.970 posições antes de a rodada ser disparada.

---

## Conceito de pronto por etapa

Nenhum agente entrega para o seguinte antes de cumprir suas condições de pronto.

### Coleta interna

**Pronto quando** todas as consultas retornaram, os campos obrigatórios estão presentes e o dado mais recente está dentro da janela de frescor.

**Sinaliza, sem impedir,** quando o volume do estoque diverge do esperado.

**Não está pronto se** campo obrigatório vier majoritariamente nulo ou o dado estiver desatualizado. Neste caso a rodada é abortada, porque sem estoque não há decisão.

### Coleta externa e amarração

**Pronto quando** passa nas quatro portas: a coleta terminou sem erro, alguma amarração aconteceu, a cobertura ficou igual ou acima do mínimo (adotado: 50%) e a idade do dado ficou dentro do máximo (adotado: 2 dias).

**Não está pronto se** qualquer uma das quatro fechar. O requisito é aplicar a última coleta válida com a idade declarada e seguir; enquanto esse reuso não existir, a rodada ordena pelo sinal de banco declarado e sai **degradada com a limitação nomeada** — a nota do portal não entra.

### Perfil de conversão

**Pronto quando** ao menos um perfil **conta para o filtro** — robusto e contendo a faixa de preço — e cada resultado carrega o número de vendas que o sustenta.

**Não está pronto se** nenhum perfil contar. Nesse caso a regra do perfil **não é avaliada**: ninguém é reprovado por ela, o que é diferente de todos reprovarem, e a rodada segue degradada com a limitação nomeada. É o caminho de falha que decide se o super destaque sai vazio. **Isto não é relaxamento**: vale igualmente para os dois níveis, é consequência da ausência de evidência e não de cedência de critério — o super destaque continua sem relaxar nada.

### Decisão

**Pronto quando** todos os candidatos passaram pelas nove regras, a nota foi calculada e os descontos aplicados, as cotas foram respeitadas sem excedente, cada item tem justificativa, cada exclusão relevante tem motivo, e todo relaxamento aplicado está no relatório com a regra que cedeu e a quantidade de posições dependentes — inclusive as cedências que recuperaram zero e a contagem dos travados pelo login.

### Entrega

**Pronto quando** a planilha contém as duas listas dentro das cotas, a justificativa por imóvel, o registro dos cortes, o relatório de relaxamento, as posições não preenchidas, os parâmetros vigentes **com a procedência de cada um** (adotado ou declarado para esta rodada), o estado da rodada e os avisos de variação de volume e de idade do dado externo.

Precisa declarar também, porque sem isso a lista engana quem a aplica: que o desconto por janela anterior **não incide** enquanto o parâmetro nº 14 for nulo; que a forma de normalização em uso é **provisória**; quais perfis contam para o filtro e quais são frágeis; e quantos imóveis o **login do gestor** impediu de recuperar no relaxamento.

### Rodada

**Completa quando** todas as etapas ficaram prontas.
**Degradada quando** alguma fonte falhou e a decisão prosseguiu com dado parcial, com a limitação declarada.
**Abortada quando** a coleta interna não fica pronta.

**Dois casos que estes três estados não cobrem, e que seguem em aberto.** Quando o crivo veta a lista, e quando a segunda-feira não encontra carga aprovada, hoje só resta chamar de abortada, por falta de estado próprio. As consequências são **diferentes nos dois**, e a diferença importa: na sexta, a rodada abortada não deixa linha nenhuma no Registro, nem o cabeçalho, de modo que a segunda e a auditoria não enxergam que houve execução; na segunda, a ausência de carga **é** registrada. Se merecem estado próprio, ou se basta gravar o cabeçalho da sexta, é decisão do dono ([P-01] e [P-09]); esta revisão registra a lacuna sem fechá-la.

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
| 5 | Decisor | Saídas dos passos 2, 3 e 4 e parâmetros | As duas listas, ordenadas pela mesma nota e separadas pelo piso de preço, com justificativas, cortes e relatório de relaxamento |
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

**Sinal intermediário semanal.** Leads e visitas gerados por posição paga durante e após a janela. Realimenta o ranking da semana seguinte. A linha de base é conhecida: 12% das janelas históricas geraram ao menos um lead. **Este número é linha de base, não limiar**: ele descreve o passado e não define o "resultado esperado" do parâmetro nº 14, cuja leitura "pelo menos um lead" foi examinada e descartada pelo dono (D-022). O nº 14 segue nulo.

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
- [ ] Imóvel fora de qualquer uma das nove regras não entra no ranking primário. Nas posições de destaque, e apenas nelas, o relaxamento pode recuperá-lo pela ordem de cedência, com a regra cedida registrada — o super destaque nunca cede.
- [ ] Imóvel vendido, despublicado ou com alteração relevante de preço sai imediatamente, fora do ciclo. **Três ressalvas abertas**: a reserva não tem fato no banco ([P-21]), a magnitude do preço é o parâmetro nº 15, nulo (D-025), e o que "imediatamente" significa dentro de dois momentos por semana está em aberto ([P-20]).

### História 3: descobrir o padrão que converte sem inventar padrão

**Como** gestor da vitrine **quero** saber quais características convertem **e** quanta evidência sustenta cada achado **para** não priorizar com base em coincidência.

- [x] A análise parte das vendas assinadas da janela declarada, e só de vendas: leads não entram na base do perfil (D-032).
- [x] O perfil mede uma ou duas dimensões por vez, nunca as cinco simultaneamente.
- [x] Cada resultado informa o número de vendas que o sustenta.
- [ ] Resultados abaixo da evidência mínima são declarados frágeis e **não contam para o filtro** — não pesam menos, não pesam nada (D-027). O critério anterior, "não recebem peso pleno", tornou-se insatisfazível quando o perfil deixou de ser fator de nota.
- [ ] A hipótese de valor esperado é testada contra vendas e o resultado é reportado. **Critério nunca especificado**: o que "testar a hipótese" entrega não existe em código, especificação nem fila de pendências. Segue como [P-19], em aberto.

### História 4: preencher o topo com valor e a base com volume

**Como** gestor da vitrine **quero** que os dois níveis sigam objetivos diferentes **para** que a posição escassa persiga receita e a abundante persiga contato.

- [ ] As 475 posições de super destaque exigem preço a partir de R$ 700.000, aplicado como condição de nível na alocação.
- [ ] Os dois níveis são ordenados pela **mesma** nota, e o desempate persegue o lead: leads em 180 dias primeiro, depois o cadastro mais novo. O critério anterior — "cada nível usa seu próprio conjunto de pesos" — **deixou de valer** com a D-028 e não pode ser marcado.
- [ ] A justificativa informa por qual objetivo o imóvel foi selecionado. Barrado por mecanismo ausente, não por parâmetro nulo: nenhuma coluna nomeia o objetivo.

### História 5: não deixar benefício contratado sem uso

**Como** gestor da vitrine **quero** que o sistema ceda critério de forma controlada quando faltar imóvel **para** aproveitar posições já pagas.

- [x] O relaxamento se aplica apenas às posições de destaque.
- [x] As posições de super destaque nunca relaxam.
- [ ] A ordem de cedência é **perfil de conversão**, fotos, cadastro, atualização, gestor e distrito, e o degrau de gestor — como todo degrau posterior — não recupera imóvel cujo gestor não logou na janela declarada (D-027, D-029). *Estava marcado como cumprido na versão 5.0 com a ordem de cinco degraus; a marcação cai porque o critério mudou, não porque o comportamento regrediu.*
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

**Acesso a dados.** Leitura apenas sobre o Newcore. A escrita ocorre somente na **base própria do sistema** — que hospeda o Registro e, em esquema separado, a operação do console. A aplicação da carga é manual.

**Coleta externa.** O Canal Pro exige sessão autenticada. O portal apresentou aviso de instabilidade durante a varredura e a página de performance renderizou com elementos sem rótulo acessível. Com a raspagem passando a ser semanal, há uma única tentativa por rodada, e o dado de reserva aceitável tem no máximo **2 dias** (adotado, D-034): o da semana anterior não passa.

**Qualidade da coleta existente.** Cerca de 62% das execuções históricas terminaram com erro ou sem processar. A rodada degradada é estado previsto, não exceção.

**Volume de evidência.** As pouco mais de 176 vendas de seis meses — 177 pela contagem canônica da D-013, 184 medidas em 04/09/2026 — limitam estruturalmente o que a análise de perfil pode afirmar. Essa é restrição de negócio, não de tecnologia, e não se resolve com ferramenta.

**Defeitos de dado.** Catalogados na base factual.

**Volume de dados.** As maiores tabelas relevantes são `realtyattributes` (4,2 milhões), `brokerneighborhoods` (6,1 milhões) e `userbrokerrelationshipshistoric` (7,5 milhões).

---

## Fases

### Fase 1: MVP

- Contrato vigente do Grupo OLX, com dois níveis agrupados.
- Elegibilidade com nove regras (oito gerais mais o perfil), perfil de conversão com evidência declarada, a nota do portal com os descontos, alocação, relaxamento e rotação.
- Planilha semanal com as duas listas, justificativas, cortes e relatório de relaxamento.
- Relatório de segunda com as duas listas, parando no gestor da vitrine.
- Execução agendada das duas rodadas.
- Registro persistente em base própria.
- Calibração contra o histórico, incluindo o teste da hipótese de valor esperado.

**Definição de MVP.** O menor conjunto que permite aprovar uma carga semanal com justificativa auditável, aproveitar as posições contratadas e acompanhar **na segunda-feira seguinte** o que aquela carga produziu. *A versão 5.0 dizia "diariamente", contradizendo a cadência de dois momentos por semana afirmada neste mesmo documento; não existe execução diária.*

### Fase 2

- Dissecação dos subníveis do contrato.
- Estabilização ou substituição da coleta no Canal Pro.
- Notificação direta a gestores de distrito.
- ~~Escrita direta após aprovação, com trilha de auditoria.~~ **Item aposentado nesta revisão**: ele previa aplicar a carga automaticamente, e o invariante 1 proíbe escrita no Newcore em qualquer circunstância — não é questão de fase. A aplicação da carga segue manual, e o item ao lado (detecção de que a planilha provavelmente não foi aplicada) continua sendo a única forma prevista de fechar essa malha.
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
| Perfil de conversão produzir padrão a partir de coincidência | Alta | Alto | Poucas vendas na janela (176 lidas em 28/08/2026, 177 pela contagem canônica de 31/08 — D-013 —, 184 em 04/09). Análise limitada a uma ou duas dimensões por vez, com número de casos declarado, evidência mínima de três vendas e **perfil frágil sem efeito nenhum**. O risco cresceu com a D-027: o perfil agora exclui, e um padrão espúrio barra imóvel bom em vez de só ordená-lo mal |
| Planilha aplicada parcialmente, com troca de itens ou com atraso | Alta | Alto | Risco assumido por decisão explícita. Sem verificação, o relatório de segunda atribui resultado a posições possivelmente inexistentes e a penalidade seguinte pode punir imóvel que nunca esteve em vitrine. Degradação silenciosa e cumulativa. Mitigação em aberto |
| Coleta externa falhar sem redundância | Alta | **Alto** | Com raspagem semanal há uma única tentativa por rodada, e desde a D-028 o portal **é** a ordem: sem ele a rodada cai para o sinal de banco declarado e sai degradada. Deixou de ser impacto sobre três métricas de refinamento. O reuso da última coleta válida é requisito ainda não implementado, e a janela aceitável é de 2 dias |
| Território que vende ficar fora do universo elegível | Alta | Alto | 25% das vendas dos últimos seis meses ocorreram em distritos que a regra exclui, mesmo após reduzir o mínimo para dois corretores. Acompanhado como indicador a cada rodada |
| Amarração ligar anúncio ao imóvel errado | Média | **Alto** | Taxa de amarração medida e reportada, com cobertura mínima de 50%. O impacto deixou de ser limitado: a amarração errada troca a nota que ordena a lista |
| Hipótese de valor esperado não se confirmar | Média | Alto | A mitigação escrita na versão 5.0 supunha a mecânica de quatro fatores, que deixou de existir. Hoje a nota é uma só e o objetivo por nível é intenção, não conta: o que resta é o piso de preço. Como testar a hipótese segue não especificado ([P-19]) |
| Defeitos de dado tratados como critério | Alta | Alto | Catalogados; a coleta interna verifica preenchimento antes de declarar pronto |
| Concentração em poucos gestores | Alta | Médio | Universo elegível concentrado em poucas centenas de gestores. Distribuição monitorada desde o MVP |
| Penalidade por ausência de avaliação recair sobre metade dos candidatos | Alta | Médio | Causa **identificada**: o pipeline de avaliação parou em 16/10/2025 e 99,76% do estoque novo não tem nota. Por isso o desconto foi calibrado **baixo de propósito**, em 5 pontos de 100 — descontar alto puniria o estoque novo por defeito da base |
| Execução automática com critério não calibrado | Média | Médio | Calibração precede a primeira rodada agendada; a planilha continua exigindo aprovação |

---

## Dependências e decisões

**Dependências**

- Acesso de leitura estável ao `newcore` e ao `newcore_bi`.
- Provisionamento da base própria do sistema, que hospeda o Registro e a operação do console.
- Sessão autenticada no Canal Pro.
- Confirmação da periodicidade do valor contratual.
- Acesso **somente leitura** autorizado ao MySQL do Newcore a partir da máquina que hospeda o sistema.

**Decisões tomadas com risco assumido**

- O sistema não confirma a aplicação da planilha.
- Ambas as rodadas executam de forma agendada desde o MVP.
- O corte de distrito é mantido, agora com mínimo de dois corretores, deixando 25% das vendas recentes fora do universo elegível.

**Resolvidas desde a versão 5.0**

- Evidência mínima por combinação de perfil: **3 vendas** (D-014).
- Intensidade das três penalidades: **20 / 5 / 10** pontos de 100, e perdão de **50%** por carga aprovada (D-030, D-034).
- Idade máxima aceitável da coleta externa: **2 dias** (D-034).
- Limiar mínimo de taxa de amarração: **50%** (D-034).
- Por que o estoque não possui avaliação por categoria: o pipeline parou em **16/10/2025**.

**Decisões em aberto** — os nove parâmetros nulos da tabela acima (nº 2, 4, 6, 8, 9, 10, 11, 14 e 15), mais:

- Valores-alvo das métricas de sucesso.
- As perguntas de produto enfileiradas em `docs/perguntas-abertas.md`, entre elas: o que "sair fora do ciclo" significa dentro de dois momentos por semana ([P-20]); se a reserva adota um substituto ou sai do escopo com a limitação escrita ([P-21]); o que "testar a hipótese de valor esperado" entrega ([P-19]); o que acontece com a semana quando o dono reprova uma lista ([P-04]); e se o carimbo de aprovação marca o aceite ou a aplicação da carga ([P-05]).

**Divergências em que este documento está certo e a implementação não** — registradas, não corrigidas aqui, porque a correção é do código:

- A planilha deve ser escrita **antes** de a rodada entrar no Registro, como este documento diz; o código faz o inverso. O risco é concreto: uma rodada gravada sem planilha pode ser aprovada por decurso de prazo e virar a carga vigente — uma lista que ninguém recebeu ([P-02]).
- O pronto do relatório de segunda exige responsável nomeado no nível do corretor **e** do gestor de distrito; o predicado implementado olha só o corretor ([P-08]).

---

## Glossário

- **Carga semanal**: publicação periódica de anúncios, com sete dias de duração.
- **Destaque e super destaque**: posições de maior visibilidade no portal. No MVP, destaque agrupa destaque padrão e exclusivo; super destaque agrupa super destaque e Topo VIP.
- **Elegibilidade**: conjunto de nove regras eliminatórias, binárias e sem compensação, aplicadas antes do ranking — **oito gerais mais o perfil de conversão** (D-027). O piso de R$ 700.000 e o status impeditivo não são regras: o primeiro é condição de nível, o segundo é saída imediata.
- **Perfil de conversão**: combinação de uma ou duas características de imóvel observada nas vendas assinadas do período, sempre acompanhada do número de casos que a sustenta. É **regra**, não fator.
- **Perfil robusto e perfil frágil**: robusto tem ao menos três vendas; frágil tem menos. Só o perfil robusto **que contém a faixa de preço** conta para o filtro. Frágil não conta — não pesa menos, não pesa nada.
- **Perfil que puxou**: entre os perfis que o imóvel casa, o de mais vendas. É rótulo da justificativa, não critério.
- **Nota bruta**: soma ponderada dos três sinais do anúncio no portal, em pontos de 100.
- **Nota final**: a nota bruta menos os descontos, na mesma escala. É por ela que a lista é ordenada.
- **Desconto**: subtração da nota bruta em pontos de 100, por janela anterior sem resultado, ausência de avaliação por categoria ou ausência de lead em 180 dias.
- **Carga aprovada**: rodada de decisão aprovada; é a unidade em que o desconto por janela é perdoado. Uma sexta que não virou carga não perdoa nada.
- **Trava do login**: o degrau de gestor produtivo, e todo degrau posterior, não recupera imóvel cujo gestor não entrou no sistema na janela declarada.
- **Valor esperado**: probabilidade de conversão ponderada pelo ticket do imóvel. Objetivo do ranking de super destaque.
- **Janela de destaque**: intervalo em que um imóvel ocupou posição paga.
- **Distrito**: unidade territorial de organização comercial do Newcore.
- **Amarração**: correspondência entre o anúncio no portal e o imóvel no Newcore, responsabilidade do Coletor Externo.
- **Planilha de raspagem**: insumo interno com nota do portal, visualizações e cliques por imóvel. Não é entregável.
- **Relaxamento**: cedência controlada de regras de elegibilidade, apenas nas posições de destaque, com relatório obrigatório. Ordem: perfil de conversão, fotos, cadastro completo, atualização em 90 dias, gestor produtivo, capacidade do distrito — com a trava do login a partir do degrau de gestor.
- **Planilha de decisão**: entrega semanal com as duas listas, justificativas, cortes e relaxamentos. Insumo da substituição manual e registro assumido do que está em vitrine.
- **Rodada completa, degradada e abortada**: estados possíveis de uma execução.
- **Pronto**: conjunto de condições verificáveis que uma etapa cumpre antes de entregar para a seguinte.

---

*Documento produzido por levantamento interativo de requisitos com pontuação de qualidade, apoiado em varredura direta das fontes de dados e no contrato vigente com o Grupo OLX, em 28 de agosto de 2026. Revisto em 5 de setembro de 2026 para incorporar as decisões D-001 a D-034, sem preencher nenhum parâmetro pendente e sem resolver nenhuma pergunta aberta.*
