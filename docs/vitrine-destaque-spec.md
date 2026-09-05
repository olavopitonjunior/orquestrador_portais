# Especificação Funcional: Curadoria Orquestrada da Vitrine de Destaques

**Versão**: 1.1
**Data**: 2026-08-28 · **Revisão 1.1**: 2026-09-05, incorporando as decisões D-002/D-003 (piso e status como condições, não regras), D-009, D-014, D-015, D-021/D-023, D-027 a D-034 de `docs/decisoes.md` — o perfil de conversão como regra, o portal como nota, os descontos em pontos, o login como trava e a parametrização adotada. Onde esta revisão e uma decisão registrada divergirem, a decisão prevalece (regra do topo de `docs/decisoes.md`).
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
| nota bruta e os sinais que a compõem | A nota do portal (§6.3) — ou o sinal de banco declarado, quando a raspagem não entra — e os sinais que entraram nela |
| descontos aplicados | Valor de cada um dos três, em pontos de 100 (§6.4) |
| nota final | Nota bruta menos os descontos |
| perfil | Se casa o perfil de conversão (a nona regra, §6.1), o perfil que puxou e a evidência dele |
| entrou por relaxamento | Qual das seis regras cedeu, quando aplicável |

**Limitação declarada (05/09/2026).** O que a tabela guarda hoje ainda é o desenho anterior à D-028: as colunas são `nota_perfil` (1/0 do casamento), `nota_leads`, `nota_desempenho` e `nota_gestor` — **a nota do anúncio, os cliques e as visualizações reescalados não são gravados**, e `nota_desempenho` guarda a nota bruta dividida por 100 enquanto `nota_final` está em pontos de 100. Quem auditar a composição da nota usa o `apuracao.csv` da rodada, que tem os três sinais. Migrar essas colunas é fatia de código; enquanto não vier, a promessa desta seção vale para o `apuracao.csv`, não para o Registro.

**perfil_da_rodada** — os padrões que o Analista encontrou naquela semana.

| Campo | Conteúdo |
|---|---|
| rodada | Chave da rodada |
| dimensões analisadas | Uma ou duas por resultado |
| valores | Faixa, região, quantidade |
| vendas que sustentam | Número de casos |
| classificação | Robusto ou frágil |

**Limitação declarada (05/09/2026).** Esta tabela existe no esquema e **nenhum módulo a escreve**: o identificador do perfil fica nulo em `decisao_imovel` e só a evidência (número de vendas) é gravada. Desde a D-027, em que o perfil é regra eliminatória, isso significa que o Registro não permite reconstituir *qual* perfil filtrou a rodada. Fatia de código.

**relaxamento** — uma linha por regra cedida em cada rodada.

| Campo | Conteúdo |
|---|---|
| rodada | Chave da rodada |
| regra cedida | Qual dos seis degraus da ordem de cedência (§6.6) |
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

**Esquema `operacao`.** Além das entidades acima, que são a auditoria da DECISÃO, o banco tem um segundo esquema com a operação do console (D-011): trabalhos enfileirados e seus eventos e resumos por agente, declarações de parâmetros, publicações, batimento do trabalhador e adiamentos. É quem clicou e quando, não o que foi decidido — os dois nunca se misturam, e nenhuma regra desta spec lê o `operacao`.

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

**O que a geração atual entrega (05/09/2026), declarado.** São seis arquivos: `super_destaque`, `destaque`, `excluidos_por_regra`, `relaxamento`, `parametros_e_limitacoes` e `apuracao` — este último com uma linha por candidato, inclusive os que ficaram fora. O conteúdo obrigatório do Resumo existe, como linhas de nota e de limitação dentro de `parametros_e_limitacoes`, com cada ausência declarada; **a aba Perfis ainda não é produzida**, pela mesma razão que `perfil_da_rodada` não é escrita (§2.1).

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
| Perfil | Se casa o perfil de conversão (a nona regra), o perfil que puxou, número de vendas que o sustentam |
| Composição da nota | Nota bruta do portal, os três sinais reescalados (nota do anúncio, cliques, visualizações), leads e produtividade do gestor (desempate), nota final |
| Descontos | Janela anterior sem resultado, sem avaliação por categoria, sem lead em 180 dias, desconto total |
| Contexto | Entrou por relaxamento e qual regra cedeu, semanas consecutivas em destaque |

O identificador interno é o mesmo que a raspagem já utiliza para casar imóvel e anúncio. O título e as características existem para que quem aplica a carga confirme, antes de mexer, que o número corresponde ao imóvel certo.

**O que a geração atual entrega, declarado.** As abas de nível trazem hoje a identificação, a posição, a composição da nota, os descontos e o contexto do relaxamento; as características do imóvel (preço, distrito, categoria, metragem, dormitórios, vagas, fotos), o código do portal e o desfecho de quem ficou fora vivem no `apuracao.csv`, que é o arquivo que quem aplica a carga abre. Duas colunas desta lista não têm fonte no sistema: **leads em 30 dias** (nenhum produtor) e **link do anúncio** (§3.3). A `última janela paga` é entregue e não está na lista acima.

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
| Coletor Externo | Sessão autenticada no Canal Pro, lista de imóveis do Coletor Interno | Planilha de raspagem com nota do anúncio, visualizações e cliques **por tipo** — a soma entre tipos é da nota (§6.3), não do coletor —, amarrada por imóvel; taxa de amarração (cobertura); idade do dado; o veredito de entrada (as quatro portas da §7.3) |
| Analista de Perfil | Vendas assinadas na janela declarada (adotada: 180 dias) | Perfis por uma ou duas dimensões, com número de vendas e classificação de robustez; os que contam para o filtro são os robustos que contêm a faixa de preço (§6.2) |
| Decisor | Saídas dos três coletores, perfis, parâmetros efetivos (declarados ou adotados) e histórico de janelas do Registro | Duas listas ordenadas dentro das cotas, nota bruta e descontos por imóvel, o veredito do perfil por candidato, registro de cortes por regra e de cedências, contagem de imóveis travados pelo login |
| Redator | Saída do Decisor, na sexta; saída do Monitor, na segunda | Planilha de decisão e relatório de acompanhamento |
| Monitor Operacional | Banco de leads, planilha aprovada vigente | Lista de leads sem tratamento e contagem de leads por imóvel em posição paga |
| Registro | Saídas do Decisor, do Redator e do Monitor | Persistência consultável de tudo acima |

O Decisor é o único agente que lê o Registro durante a rodada, e o faz para obter o histórico de janelas necessário ao cálculo da penalidade.

---

## 6. Regras de cálculo

A cadeia tem três momentos, e as telas do console os chamam pelos mesmos nomes: **quem entra** (§6.1 e §6.2 — regras eliminatórias, vindas do banco), **em que ordem** (§6.3 e §6.4 — a nota vem do portal, os descontos do banco) e **quantos** (§6.5 e §6.6 — cotas, piso e cedência, vindos do contrato). Os valores numéricos citados como *adotados* são os da decisão D-034, vivem em `src/config/adotados.py` e podem ser declarados diferentes para uma rodada; o que for declarado sai rotulado na planilha e não muda o adotado. "O banco manda, o portal classifica" (D-028).

### 6.1 Elegibilidade

Nove regras eliminatórias, binárias e sem compensação, aplicadas em conjunto. Reprovar em uma basta para excluir. Oito são gerais e fixas; a nona é o perfil de conversão (D-027), definido na §6.2.

| Regra | Critério |
|---|---|
| Status | Publicação ativa |
| Categoria | Casa, Casa de condomínio, Sobrado, Cobertura, Apartamento |
| Preço geral | Igual ou superior a R$ 300.000 |
| Fotos | Dez ou mais |
| Atualização | Nos últimos 90 dias |
| Cadastro completo | Nenhuma das sete categorias da nota interna com valor zero |
| Gestor produtivo | Captou ou vendeu nos últimos 30 dias (janela agregada na fonte; não é parâmetro, D-032) |
| Distrito | Corretores que captaram ou venderam nos últimos 30 dias em número igual ou superior ao mínimo declarado (adotado: dois, D-015/D-033) |
| Perfil de conversão | Casa ao menos um perfil que conta (§6.2). Quando nenhum perfil conta, ou o candidato não tem dimensões na coleta, a regra não é avaliada: o imóvel não é reprovado por ela e a rodada declara a limitação (§7.3) |

O piso de R$ 700.000 do super destaque **não é regra de elegibilidade**: é condição de nível, aplicada na alocação (§6.5, D-002). O status impeditivo (venda, reserva, despublicação) é regra de saída imediata (§6.7, D-003).

Imóvel sem avaliação por categoria registrada não é excluído: passa e recebe desconto (§6.4).

O login do gestor **não exclui** ninguém — medido em 04/09/2026, "sem login em 30 dias" é subconjunto estrito de "gestor não produtivo". Ele age no relaxamento, como trava (§6.6, D-029).

A ligação entre imóvel e distrito vem da tabela analítica de relação de imóveis, não do endereço, porque o campo de zona de valor no endereço está nulo em 98% dos casos.

### 6.2 Perfil de conversão

Entrada: vendas assinadas na janela declarada (adotada: 180 dias, D-033; medidas 184 em 04/09/2026). Só vendas: leads não entram na base do perfil, porque em volume dominariam as vendas em cerca de 30 para 1 e o perfil deixaria de descrever o que vende (D-032).

Dimensões disponíveis: região, faixa de preço, faixa de metragem, dormitórios, vagas.

Método: analisar uma ou duas dimensões por vez, nunca as cinco simultaneamente. Cada resultado carrega o número de vendas que o sustenta. Um perfil é **robusto** quando tem ao menos **3 vendas** (evidência mínima, D-014); abaixo disso é frágil.

O perfil é **regra, não fator** (D-027): um perfil **conta para o filtro** quando é robusto **e contém a faixa de preço** — sem essa exigência a faixa de metragem sozinha casava 100 % do estoque e o filtro não filtrava nada; com ela passam 83,8 % dos elegíveis e 64 % dos candidatos ao super destaque (medição de 04/09/2026). Perfil frágil não conta — não pesa menos, não pesa nada. O candidato **casa** um perfil quando satisfaz todas as dimensões dele, com a mesma bucketização dos dois lados.

O "perfil que puxou" — o perfil robusto de mais vendas entre os que o candidato casa — é rótulo da justificativa (§2.1), não decisão. A ordem de importância das dimensões da D-017 sobrevive só como critério de exibição.

### 6.3 Ranking

O portal classifica (D-028). A **nota bruta** de cada imóvel é a soma ponderada de três sinais do anúncio no Canal Pro, cada um reescalado para uma escala comparável (forma provisória: min-max, parâmetro nº 2, D-016) **entre os elegíveis** no ranking primário e **entre os reprovados** no relaxamento, porque as duas ordenações são internas a cada grupo e nunca se comparam (D-016; a apuração diz de qual população cada linha veio), com pesos em **pontos de 100** que somam exatamente 100:

| Sinal | Peso adotado | Razão |
|---|---|---|
| Nota do anúncio | 70 | único sinal com variância medida (14 valores em 300 anúncios, 03/09/2026) |
| Cliques, somados entre tipos (contato, telefone, WhatsApp, proposta, agendamento) | 30 | sinal fraco mas real, e é intenção de compra |
| Visualizações | 0 | medido zero em 300 de 300; zero declarado, não omitido |

A nota final é a nota bruta menos os descontos (§6.4). **Os dois níveis usam a mesma nota**: o que os separa é o piso de preço na alocação (§6.5), não uma nota diferente.

Leads em 180 dias e produtividade do gestor **não pesam na nota**: são o desempate — leads primeiro, depois o cadastro mais novo (D-009). Sob a forma `cadastro_mais_novo` sem raspagem, o desempate por leads é desligado; os descontos da §6.4 continuam incidindo, então a ordem efetiva é "menos descontos primeiro, depois o cadastro mais novo" — a nota bruta é que fica igual para todos, não a nota final.

Imóvel sem anúncio raspado — ou com anúncio que não trouxe o sinal — recebe o tratamento declarado (`portal.sem_anuncio`: **fim da fila**, adotado, ou a nota mediana daquele sinal entre os que o têm), nunca um zero silencioso. O tratamento é por SINAL: um anúncio pode ter nota e não ter cliques.

A raspagem só entra pelas quatro portas da §7.3 (coleta ok, alguma amarração, cobertura mínima — adotada 50 % — e idade máxima — adotada 2 dias). Quando não entra, a nota bruta passa a ser o sinal do banco declarado em `portal.ordem_quando_nao_entra` (**leads em 180 dias**, adotado; ou a produtividade do gestor; ou só o cadastro mais novo) e a rodada sai **degradada com a limitação nomeada**.

Objetivo por nível, preservado como intenção do critério (não como mecânica de pesos):

| Nível | Objetivo |
|---|---|
| Super Destaque | Valor esperado — quem está acima do piso disputa as 475 posições pela nota |
| Destaque | Probabilidade de gerar lead — daí o desempate por leads e a cedência de regras para encher |

### 6.4 Descontos (penalidades)

Três, subtraídos da nota bruta em **pontos de 100** (D-030) e sempre visíveis na planilha:

| Desconto | Quando se aplica | Adotado |
|---|---|---|
| Janela anterior sem resultado | O imóvel ocupou posição e não atingiu o resultado esperado para o nível | 20 pontos |
| Sem avaliação por categoria | O imóvel não tem nenhuma categoria da nota interna avaliada | 5 pontos (baixo de propósito: o pipeline de avaliação parou em 16/10/2025 e 99,76 % do estoque novo não tem nota) |
| Sem lead em 180 dias | O imóvel não recebeu nenhum lead no período | 10 pontos |

O desconto por janela anterior enfraquece a cada carga aprovada em que o imóvel permanece: **perdão por carga** (adotado: 50 %). O parâmetro se chama `desconto.perdao_por_semana` no TOML e na tabela do `CLAUDE.md` — nome herdado da cadência semanal —, mas a unidade é a **carga aprovada**, não a semana de calendário: uma sexta que não virou carga não enfraquece desconto nenhum. Uma carga é uma rodada de decisão aprovada (elaboração 4 da D-021); mudança de nível fecha a janela e abre outra (elaboração 1 da mesma). Imóvel sem histórico de destaque não é penalizado por ausência de histórico.

O **resultado esperado por nível** (parâmetro nº 14, D-022) segue nulo por decisão do dono: enquanto for nulo, o desconto por janela anterior existe, é mostrado e **não incide** — a planilha declara isso em toda rodada.

### 6.5 Alocação

Primeiro o super destaque: aplica o piso de R$ 700.000 (condição de nível, D-002), ordena pela nota final com o desempate da §6.3 e preenche as 475 posições.

Depois o destaque: entre os elegíveis restantes, na mesma ordem, preenche as 6.495 posições.

Nenhuma posição excedente é proposta — o corte por fatia torna o excesso impossível por construção, não por conferência. As cotas aparecem em dois lugares (a constante do domínio e a restrição do Registro que recusa posição fora da faixa) e um teste amarra os dois: mudar um sem o outro quebra a suíte. O console as lê da restrição, para não redigitar um terceiro.

### 6.6 Relaxamento

Aplica-se apenas às posições de destaque. As de super destaque nunca relaxam — inclusive para a regra do perfil.

Ordem de cedência (D-027): **perfil de conversão**, fotos, cadastro completo, atualização em 90 dias, gestor produtivo, capacidade do distrito. A cedência é progressiva e mínima: um degrau só é cedido se o déficit sobrou depois de esgotar o anterior, e para assim que o déficit zera. Dentro de um degrau, a ordem é a da §6.3.

Consequência declarada da ordem: como o perfil é o primeiro degrau, ele morde de verdade no super destaque; no destaque é a primeira coisa de que a rodada abre mão quando faltam imóveis.

**Trava do login (D-029):** o degrau `gestor produtivo` — e qualquer degrau posterior, que o inclui — não recupera imóvel cujo gestor não entrou no sistema dentro da janela declarada (`corretor.login_janela_dias`, adotada: 30 dias). Quem não loga não atende o lead que a posição paga gerar. O imóvel fica irrecuperável, e a rodada conta e declara quantos foram travados (medido: 105 dos 2.092 recuperáveis por esse degrau, 04/09/2026).

Cada cedência gera linha no relatório de relaxamento com a quantidade de posições que dependeram dela — inclusive zero para degrau cedido que não recuperou ninguém. Sem esse registro a etapa de decisão não é considerada pronta.

Referência de quanto cada cedência recupera, medida na base em 28/08/2026 **com mínimo de três corretores por distrito** (o adotado é dois; ordem de grandeza apenas, como o PRD ressalva): fotos cerca de 133 imóveis, cadastro 569, atualização 1.680, gestor 1.747, distrito 5.686. O ganho do degrau do perfil não foi medido nessa data (a regra é de 04/09/2026); a prévia do console o mede a cada pedido.

### 6.7 Rotação

A lista é recalculada integralmente a cada rodada de sexta. Não há permanência automática.

Saída imediata, fora do ciclo: venda, reserva, despublicação ou alteração relevante de preço. O que "imediatamente" pode significar dentro de dois momentos por semana, e a magnitude da alteração relevante (parâmetro nº 15), estão em aberto — ver [P-20], [P-21] e D-024/D-025.

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

**Duas limitações declaradas.** (1) O veto do crivo de auditoria — violação de cota, de piso ou de relaxamento em super destaque — também termina a rodada como ABORTADA, por falta de estado próprio nesta tabela; a distinção fica no motivo e no código de saída. Se isso merece um estado terminal próprio é pendência do dono ([P-01]). (2) A rodada ABORTADA **não deixa linha no Registro, nem o cabeçalho**, o que diverge da §2.1 ("uma linha por execução"): o que existe dela é o trabalho e o log no esquema `operacao`.

### 7.3 Falhas por etapa

| Etapa | Falha possível | Tratamento |
|---|---|---|
| Coleta interna | Campo obrigatório majoritariamente nulo, dado desatualizado | Aborta a rodada |
| Coleta interna | Volume do estoque diverge do esperado | Entrega assim mesmo e sinaliza na planilha; nunca interrompe |
| Coleta externa | Sessão não autentica, raspagem não roda ou termina em erro | Declara a ausência e segue sem a nota do portal (§6.3). O reuso de uma coleta anterior como reserva **não existe hoje** — e, com a idade máxima adotada em 2 dias, a coleta da semana anterior não passaria na porta de idade de qualquer modo |
| Amarração | Nenhuma amarração, ou cobertura abaixo da mínima declarada, ou dado mais velho que a idade máxima | A nota do portal não entra: a ordem cai para o sinal do banco declarado (§6.3) e a rodada sai degradada com a limitação nomeada |
| Perfil | Nenhum perfil robusto contém a faixa de preço | A regra do perfil não é avaliada — ninguém é reprovado por ela — e a rodada sai degradada com a limitação nomeada (D-027) |
| Decisão | Item sem justificativa, cota excedida, relaxamento sem registro | Não fica pronta |
| Acompanhamento | Não existe planilha aprovada vigente | O relatório não é emitido e a ausência é declarada |

A coleta externa tem uma única tentativa por rodada, já que a raspagem deixou de ser diária.

O "dado de reserva" da linha da coleta externa é limitado pela idade máxima declarada (adotada: **2 dias**, D-034): a coleta da semana anterior, com sete dias ou mais, **não passa** nessa porta. Na prática, ou a raspagem da própria rodada entra, ou a nota do portal fica de fora e vale o sinal de banco declarado (§6.3). Reusar coleta antiga exigiria declarar uma idade máxima maior — escolha da semana, visível na planilha.

---

## 8. Parâmetros e pendências

A lista canônica dos parâmetros é a tabela "Parâmetros ainda sem valor" do `CLAUDE.md`, com a numeração da D-004; a fila do dono é `docs/perguntas-abertas.md`. Resumo em 2026-09-05:

**Definidos:** evidência mínima do perfil (nº 1, N ≥ 3, D-014); descontos e perdão (nº 3, D-030/D-034); idade máxima da raspagem (nº 5, 2 dias) e cobertura mínima (nº 7, 50 %) (D-034).

**Declaráveis por rodada, com adotado (D-034):** janela do que vende (180 dias), janela do login do gestor (30 dias), mínimo de corretores no distrito (2), os três pesos da nota do portal (70/30/0), cobertura mínima, idade máxima, tratamento do imóvel sem anúncio, ordem quando a raspagem não entra, os três descontos e o perdão por carga. Nenhum em escala de 0 a 1.

**Ainda nulos, sem valor inventado:** a forma de normalização de cada sinal (nº 2, min-max provisório), tentativas e intervalo do Orquestrador (nº 4), limiar de variação de volume (nº 6), horários (nº 8), retenção do Registro (nº 9), prazo da aprovação tácita (nº 10), prazo de atendimento de lead (nº 11), o resultado esperado por nível (nº 14) e a magnitude da alteração relevante de preço (nº 15).

**Deixaram de existir (D-031):** os pesos dos quatro fatores por nível e o decaimento por dimensão do perfil (nº 12 e nº 13) — com o perfil como filtro e o portal como nota, a pergunta desapareceu.

Investigações abertas, que podem alterar regras já definidas:

- Por que cerca de 44% do estoque elegível não possui avaliação por categoria registrada — e o fato de o pipeline de avaliação ter parado em 16/10/2025.
- Se a tabela de relatórios da raspagem, que tem 43 registros, todos com erro e todos de dezembro de 2025, ainda é usada por alguma coisa.
- Se quem aplica a carga localiza o imóvel pelo código do portal que a apuração entrega (`realties.NewIdMarketingRotation`, igual ao `codigoImovel` em 300 de 300) ou depende de outra referência ([P-13]).
- A deriva dos números de referência (elegíveis de 10.290 para cerca de 8.000 entre 28/08 e 04/09/2026), ainda não incorporada ao mapa de dados.

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
