# Especificação Funcional: Curadoria Orquestrada da Vitrine de Destaques

**Versão**: 1.0
**Data**: 2026-08-28
**Documento de origem**: PRD versão 5.0
**Escopo desta spec**: comportamento dos agentes, contratos entre eles, estrutura do Registro e dos dois entregáveis, e regras de cálculo. A definição de ferramentas e tecnologia é etapa posterior e não faz parte deste documento.

---

## 1. Cadência

O sistema tem dois momentos fixos por semana. Não há execução diária.

| Momento | Rodada | Produto |
|---|---|---|
| Sexta-feira | Decisão | Planilha de decisão, aprovada e aplicada manualmente na carga |
| Segunda-feira | Acompanhamento | Relatório do que a carga produziu desde sexta |

A rodada de sexta é a única que raspa o portal. A rodada de segunda lê apenas o banco e por isso independe de qualquer fonte externa.

O intervalo entre a aplicação da carga e o relatório é de três dias corridos. Esse recorte é deliberado: mede o efeito da carga nova sem misturar com a anterior.

---

## 2. Registro

Base própria do sistema, separada do Newcore. O Newcore permanece somente leitura.

A planilha de decisão é adicionalmente enviada por e-mail ao gestor da vitrine e arquivada no Drive dele, como cópia de consulta humana. Essa cópia não é fonte para o sistema: tudo que os agentes precisam ler de volta vem da base própria.

### 2.1 Entidades

**rodada** — uma linha por execução.

| Campo | Conteúdo |
|---|---|
| identificador | Chave da rodada |
| tipo | Decisão ou acompanhamento |
| início e fim | Momento de disparo e de conclusão |
| estado | Completa, degradada ou abortada |
| etapas | Situação de pronto de cada etapa |
| motivo da degradação | Qual etapa falhou e por quê |
| tentativas por etapa | Quantas repetições foram necessárias |

**parametros_da_rodada** — cópia integral dos parâmetros vigentes no momento da execução. Sem ela, comparar duas semanas é comparar coisas diferentes sem saber.

**decisao_imovel** — uma linha por imóvel escolhido, cerca de sete mil por rodada. Imóveis excluídos não são guardados, por decisão explícita.

| Campo | Conteúdo |
|---|---|
| rodada | Chave da rodada |
| imóvel | Identificador interno |
| nível | Destaque ou super destaque |
| posição no ranking | Colocação dentro do nível |
| notas dos três fatores | Perfil, desempenho próprio e gestor |
| penalidades aplicadas | Valor de cada uma das três |
| nota final | Resultado da soma ponderada menos penalidades |
| perfil que casou | Identificador do perfil e evidência dele |
| entrou por relaxamento | Qual regra cedeu, quando aplicável |

**perfil_da_rodada** — os padrões que o Analista encontrou naquela semana.

| Campo | Conteúdo |
|---|---|
| rodada | Chave da rodada |
| dimensões analisadas | Uma ou duas por resultado |
| valores | Faixa, região, quantidade |
| vendas que sustentam | Número de casos |
| classificação | Robusto ou frágil |

**relaxamento** — uma linha por regra cedida em cada rodada.

| Campo | Conteúdo |
|---|---|
| rodada | Chave da rodada |
| regra cedida | Qual das cinco |
| posições dependentes | Quantas vagas só foram preenchidas por causa dela |
| posições ainda vazias | Quantas restaram sem candidato |

**janela_destaque** — o histórico que alimenta a penalidade.

| Campo | Conteúdo |
|---|---|
| imóvel | Identificador interno |
| nível | Destaque ou super destaque |
| início e fim | Datas de entrada e saída da vitrine |
| leads gerados | Acumulado durante a janela |
| semanas consecutivas | Contagem de permanência |

**resultado_carga** — o que a rodada de segunda apurou.

| Campo | Conteúdo |
|---|---|
| rodada de acompanhamento | Chave |
| carga de referência | Rodada de decisão correspondente |
| imóvel | Identificador interno |
| leads gerados no período | Contagem |
| leads sem atendimento e sem contato | Contagem |

**alteracao_parametro** — trilha de mudanças.

| Campo | Conteúdo |
|---|---|
| parâmetro | Nome |
| valor anterior e novo | Ambos |
| autor e data | Quem mudou e quando |

### 2.2 Retenção

Não definida. Como o Registro guarda apenas os escolhidos, o crescimento é de aproximadamente 360 mil linhas por ano na entidade principal.

---

## 3. Planilha de decisão

Produzida na sexta pelo Redator, a partir da saída do Decisor.

### 3.1 Estrutura

| Aba | Conteúdo |
|---|---|
| Resumo | Data, estado da rodada, avisos, parâmetros vigentes, posições preenchidas e vazias |
| Super Destaque | 475 linhas escolhidas |
| Destaque | 6.495 linhas escolhidas |
| Relaxamento | Regras cedidas e posições dependentes de cada uma |
| Perfis | Padrões encontrados na semana, com o número de vendas que sustenta cada um |

A aba de resumo carrega obrigatoriamente: variação do estoque elegível em relação à semana anterior, idade do dado do portal, taxa de amarração entre anúncio e imóvel, e estado completa ou degradada.

### 3.2 Colunas das abas de imóvel

Trinta colunas, iguais nos dois níveis. Toda justificativa é estruturada em colunas; não há texto corrido.

| Grupo | Colunas |
|---|---|
| Identificação | Identificador interno do imóvel, título do anúncio, nível atribuído, posição no ranking |
| Conferência | Link do anúncio no portal |
| Localização | Distrito, bairro |
| Características | Categoria, preço, área privativa, dormitórios, vagas |
| Responsável | Corretor gestor |
| Sinais internos | Nota interna, leads em 30 dias, leads em 180 dias |
| Sinais do portal | Nota do portal, visualizações, cliques, idade do dado |
| Perfil | Perfil que casou, número de vendas que o sustentam |
| Composição da nota | Nota do fator perfil, do fator desempenho, do fator gestor, nota final |
| Penalidades | Janela anterior sem resultado, sem avaliação por categoria, sem lead em 180 dias |
| Contexto | Entrou por relaxamento e qual regra cedeu, semanas consecutivas em destaque |

O identificador interno é o mesmo que a raspagem já utiliza para casar imóvel e anúncio. O título e as características existem para que quem aplica a carga confirme, antes de mexer, que o número corresponde ao imóvel certo.

### 3.3 Observação sobre o link do portal

A URL do anúncio não existe em nenhuma tabela do Newcore. O único endereço armazenado é o do site da própria Newcore, no formato de caminho relativo. Portanto a URL do portal precisa ser capturada pelo Coletor Externo durante a raspagem, enquanto ele já está na página. Não é recuperável depois.

---

## 4. Relatório de acompanhamento

Produzido na segunda pelo Redator, a partir da saída do Monitor Operacional. Cobre o período desde a carga de sexta.

### 4.1 Estrutura

| Aba | Conteúdo |
|---|---|
| Resumo | Carga de referência, período coberto, totais das duas listas |
| Leads sem tratamento | Leads de imóveis em posição paga que não tiveram atendimento nem contato registrado |
| Desempenho por imóvel | Todos os imóveis em destaque e super destaque, com a contagem de leads que cada um gerou |

### 4.2 Definição de lead sem tratamento

Um lead entra na lista quando não possui atendimento registrado **e** não possui nenhum contato registrado. As duas ausências são exigidas simultaneamente. É o critério mais conservador dos disponíveis e aponta apenas o abandono indiscutível.

Colunas da lista: identificador do lead, data de entrada, imóvel de origem, nível da posição, corretor gestor, gestor de distrito, distrito, tempo decorrido desde a distribuição.

### 4.3 Definição de desempenho por imóvel

A aba lista as 6.970 posições, inclusive as que geraram zero lead. A opção pela lista completa foi explícita: como o entregável é planilha e não documento de leitura, o filtro fica com quem consulta.

Colunas: identificador do imóvel, nível, leads gerados no período, leads sem tratamento, semanas consecutivas em destaque, leads acumulados na janela atual.

### 4.4 O que este relatório não faz

Não existe alerta diário. A cadência semanal reconhece uma característica medida na base: 85% dos atendimentos acontecem na primeira hora após a distribuição, e 91% dos leads sem atendimento já passaram de três dias. O lead que não é atendido nas primeiras horas não é atendido nunca.

Portanto o relatório de segunda não resgata lead individual. Ele mede o padrão de comportamento e sustenta a cobrança. Essa é uma limitação assumida, não um efeito colateral.

Não há notificação direta a corretores ou gestores de distrito. O relatório para no gestor da vitrine.

---

## 5. Contratos entre agentes

Cada agente consome uma entrada definida e produz uma saída definida. Nenhum agente lê a saída de outro fora do que está nesta tabela.

| Agente | Consome | Produz |
|---|---|---|
| Orquestrador | Horário agendado, parâmetros vigentes, estado de pronto de cada etapa | Rodada iniciada, estado final declarado, registro de tentativas |
| Coletor Interno | Newcore e newcore_bi, em leitura | Estoque elegível com atributos, sinais internos, produtividade do gestor e indicadores de distrito; aviso de variação de volume |
| Coletor Externo | Sessão autenticada no Canal Pro, lista de imóveis do Coletor Interno | Planilha de raspagem com nota, visualizações, cliques e URL, amarrada por imóvel; taxa de amarração; idade do dado |
| Analista de Perfil | Vendas assinadas dos últimos 180 dias | Perfis por uma ou duas dimensões, com número de vendas e classificação de robustez |
| Decisor | Saídas dos três coletores, perfis, parâmetros e histórico de janelas do Registro | Duas listas ordenadas dentro das cotas, notas e penalidades por imóvel, registro de cortes e de relaxamentos |
| Redator | Saída do Decisor, na sexta; saída do Monitor, na segunda | Planilha de decisão e relatório de acompanhamento |
| Monitor Operacional | Banco de leads, planilha aprovada vigente | Lista de leads sem tratamento e contagem de leads por imóvel em posição paga |
| Registro | Saídas do Decisor, do Redator e do Monitor | Persistência consultável de tudo acima |

O Decisor é o único agente que lê o Registro durante a rodada, e o faz para obter o histórico de janelas necessário ao cálculo da penalidade.

---

## 6. Regras de cálculo

### 6.1 Elegibilidade

Nove regras eliminatórias, binárias, aplicadas em conjunto. Reprovar em uma basta para excluir.

| Regra | Critério |
|---|---|
| Status | Publicação ativa |
| Categoria | Casa, Casa de condomínio, Sobrado, Cobertura, Apartamento |
| Preço geral | Igual ou superior a R$ 300.000 |
| Preço de super destaque | Igual ou superior a R$ 700.000 |
| Fotos | Dez ou mais |
| Atualização | Nos últimos 90 dias |
| Cadastro completo | Nenhuma das sete categorias da nota interna com valor zero |
| Gestor produtivo | Captou ou vendeu nos últimos 30 dias |
| Distrito | Dois ou mais corretores que captaram ou venderam nos últimos 30 dias |

Imóvel sem avaliação por categoria registrada não é excluído: passa e recebe penalidade.

A ligação entre imóvel e distrito vem da tabela analítica de relação de imóveis, não do endereço, porque o campo de zona de valor no endereço está nulo em 98% dos casos.

### 6.2 Perfil de conversão

Entrada: vendas assinadas nos últimos 180 dias, cerca de 176 casos.

Dimensões disponíveis: região, faixa de preço, faixa de metragem, dormitórios, vagas.

Método: analisar uma ou duas dimensões por vez, nunca as cinco simultaneamente. Cada resultado carrega o número de vendas que o sustenta. Resultados abaixo da evidência mínima são marcados como frágeis e não recebem peso pleno.

O valor da evidência mínima está em aberto.

### 6.3 Ranking

Nota final de cada imóvel: soma ponderada das notas dos três fatores, descontadas as penalidades.

Pesos por nível:

| Fator | Super Destaque | Destaque |
|---|---|---|
| Semelhança com perfil de conversão | 60 | 80 |
| Desempenho próprio observado | 25 | 10 |
| Produtividade do corretor gestor | 15 | 10 |

Objetivo por nível:

| Nível | Objetivo |
|---|---|
| Super Destaque | Valor esperado, isto é, probabilidade de conversão ponderada pelo ticket |
| Destaque | Probabilidade de gerar lead |

A forma de normalizar cada fator para uma escala comparável está em aberto.

### 6.4 Penalidades

Três, descontadas da nota final e sempre visíveis na planilha:

| Penalidade | Quando se aplica |
|---|---|
| Janela anterior sem resultado | O imóvel ocupou posição e não atingiu o resultado esperado para o nível |
| Sem avaliação por categoria | O imóvel não tem nenhuma categoria da nota interna avaliada |
| Sem lead em 180 dias | O imóvel não recebeu nenhum lead no período |

A penalidade por janela anterior decai ao longo dos ciclos. Imóvel sem histórico de destaque não é penalizado por ausência de histórico.

A intensidade das três e o decaimento estão em aberto.

### 6.5 Alocação

Primeiro o super destaque: aplica o piso de R$ 700.000, ordena por valor esperado e preenche as 475 posições.

Depois o destaque: entre os candidatos restantes, ordena por probabilidade de lead e preenche as 6.495 posições.

Nenhuma posição excedente é proposta.

### 6.6 Relaxamento

Aplica-se apenas às posições de destaque. As de super destaque nunca relaxam.

Ordem de cedência: fotos, cadastro completo, atualização em 90 dias, gestor produtivo, capacidade do distrito.

Cada cedência gera linha no relatório de relaxamento com a quantidade de posições que dependeram dela. Sem esse registro a etapa de decisão não é considerada pronta.

Referência de quanto cada cedência recupera, medida na base: fotos cerca de 133 imóveis, cadastro 569, atualização 1.680, gestor 1.747, distrito 5.686. Os dois primeiros degraus recuperam pouco; déficits maiores exigem chegar ao terceiro.

### 6.7 Rotação

A lista é recalculada integralmente a cada rodada de sexta. Não há permanência automática.

Saída imediata, fora do ciclo: venda, reserva, despublicação ou alteração relevante de preço.

---

## 7. Estados e tratamento de falha

### 7.1 Política do Orquestrador

Quando uma etapa não fica pronta, o Orquestrador repete a etapa antes de concluir que ela não vai completar. Só após esgotar as tentativas ele decide entre seguir degradada ou abortar.

O número de tentativas e o intervalo entre elas estão em aberto.

### 7.2 Estados da rodada

| Estado | Quando ocorre | Consequência |
|---|---|---|
| Completa | Todas as etapas prontas | Entrega normal |
| Degradada | Alguma fonte falhou e a decisão prosseguiu com dado parcial | Entrega com a limitação declarada de forma visível na planilha |
| Abortada | A coleta interna não ficou pronta | Não há entrega; sem estoque não há decisão possível |

### 7.3 Falhas por etapa

| Etapa | Falha possível | Tratamento |
|---|---|---|
| Coleta interna | Campo obrigatório majoritariamente nulo, dado desatualizado | Aborta a rodada |
| Coleta interna | Volume do estoque diverge do esperado | Entrega assim mesmo e sinaliza na planilha; nunca interrompe |
| Coleta externa | Sessão não autentica, cobertura abaixo do esperado | Usa a última coleta válida dentro da janela aceitável e declara a idade do dado |
| Amarração | Taxa abaixo do limiar | A performance externa não entra no cálculo e a rodada é sinalizada |
| Perfil | Nenhum resultado atinge a evidência mínima | A priorização opera sem esse fator, registrado na justificativa |
| Decisão | Item sem justificativa, cota excedida, relaxamento sem registro | Não fica pronta |
| Acompanhamento | Não existe planilha aprovada vigente | O relatório não é emitido e a ausência é declarada |

A coleta externa passou a ter uma única tentativa por rodada, já que a raspagem deixou de ser diária. O dado de reserva é tipicamente o da semana anterior, com sete dias ou mais.

---

## 8. Pendências antes da definição de ferramentas

Parâmetros sem valor definido, que não bloqueiam a arquitetura mas bloqueiam a primeira rodada:

- Evidência mínima por combinação de perfil.
- Forma de normalização de cada fator do ranking.
- Intensidade das três penalidades e decaimento da penalidade por janela.
- Tentativas e intervalo de repetição do Orquestrador.
- Idade máxima aceitável da coleta externa de reserva.
- Limiar de variação de volume que dispara sinalização.
- Limiar mínimo de taxa de amarração.
- Horários exatos de execução na sexta e na segunda.
- Política de retenção do Registro.

Investigações abertas, que podem alterar regras já definidas:

- Por que cerca de 44% do estoque elegível não possui avaliação por categoria registrada.
- Se a tabela de relatórios da raspagem, que tem 43 registros, todos com erro e todos de dezembro de 2025, ainda é usada por alguma coisa.
- Se quem aplica a carga localiza o imóvel apenas pelo identificador interno ou depende de outra referência.
- Confirmação da localização do campo de vagas, hoje ausente da tabela principal de imóveis.

---

## 9. O que esta spec não cobre

- Tecnologia, linguagem, infraestrutura e forma de execução dos agentes.
- Formato de arquivo da planilha e do relatório.
- Mecanismo de envio por e-mail e de arquivamento no Drive.
- Modelo de dados físico do Registro.
- Estratégia de testes.
- Distinção entre os subníveis do contrato, adiada para fase posterior.

---

*Documento derivado do PRD versão 5.0, escrito a partir de decisões tomadas em conversa e de medições diretas nas fontes de dados em 28 de agosto de 2026.*
