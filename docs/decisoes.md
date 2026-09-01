# Registro de Decisões

Resoluções do dono da decisão (Olavo) para divergências e lacunas encontradas nos documentos-fonte. Cada decisão vale a partir da data registrada e prevalece sobre o trecho divergente dos documentos até que uma revisão deles a incorpore. As contradições foram identificadas na análise da sessão de fundação (2026-08-29), não persistida como artefato; o essencial de cada uma está resumido na própria decisão.

---

## D-001 — Fonte de leitura da segunda-feira: o Registro, não a planilha

**Data**: 2026-08-29 · **Resolve**: contradição C3 (Spec §2 vs. Ferramentas §3 vs. Spec §5/§7.3)

O gestor da vitrine **não edita a planilha de decisão: apenas a aplica** manualmente no portal. Consequências:

- O **Registro é a fonte da verdade** do sistema. A rodada de segunda identifica os imóveis em posição paga lendo o Registro (rodada de decisão correspondente), nunca a planilha do Drive.
- Não existe passo de leitura de volta da planilha. A frase de Ferramentas §3 ("a planilha é entrada e saída... o sistema a lê de volta na segunda") fica **sem efeito**; prevalece a Spec §2.
- Onde a Spec diz "planilha aprovada vigente" (insumo do Monitor, §5; condição do relatório, §7.3), leia-se: **a lista da rodada de decisão registrada, com aprovação tácita confirmada por prazo**. A regra de abortar o relatório na ausência dela permanece.
- A aprovação tácita vira um carimbo de estado na rodada (aprovada em <momento>, por prazo), sem verificação de conteúdo.

**Risco aceito** (já catalogado em Ferramentas §5): se o gestor um dia alterar a planilha antes de aplicar, o Registro medirá contra uma lista que não foi a aplicada. A premissa "não edita, só aplica" é comportamental; se ela mudar, esta decisão deve ser revista antes de qualquer outra coisa.

## D-002 — O piso de R$ 700.000 é condição de nível, não regra eliminatória

**Data**: 2026-08-29 · **Resolve**: contradição C4 (Spec §6.1 vs. §6.5 e o funil medido)

A elegibilidade tem **oito regras binárias gerais**: status ativo, categoria, preço geral ≥ R$ 300.000, fotos ≥ 10, atualização em 90 dias, cadastro completo, gestor produtivo, capacidade do distrito. O piso de R$ 700.000 é **condição de candidatura ao super destaque**, aplicada na alocação (Spec §6.5), e não exclui ninguém do nível destaque. O funil medido confirma: 10.290 elegíveis, 4.852 acima do piso.

Onde os documentos disserem "nove regras", leia-se "oito regras gerais + piso de nível".

## D-003 — Status impeditivo é regra de saída imediata, não de elegibilidade

**Data**: 2026-08-29 · **Resolve**: contradição C5 (tabela do Estágio 1 do PRD vs. glossário do PRD e Spec §6.7)

"Vendido, reservado ou removido" (e alteração relevante de preço) são gatilhos de **saída imediata fora do ciclo** (rotação, Spec §6.7), não uma décima regra de elegibilidade. A décima linha da tabela do Estágio 1 do PRD deve ser lida nesse papel.

## D-004 — Lista única de ONZE parâmetros pendentes

**Data**: 2026-08-29 · **Resolve**: contradição C2 (Spec §8 vs. Ferramentas §6 vs. tabela de parâmetros do PRD)

A lista canônica de parâmetros sem valor consolida os nove bullets comuns mais os dois que aparecem em apenas um documento. São **onze**, mantidos no CLAUDE.md. O nº 1 foi resolvido em 2026-08-31 (D-014, `N ≥ 3`); os outros **dez seguem nulos** até definição:

1. ~~Evidência mínima por combinação de perfil~~ — **resolvido: N ≥ 3 (D-014)**
2. Forma de normalização de cada fator do ranking
3. Intensidade das três penalidades e decaimento da penalidade por janela
4. Tentativas e intervalo de repetição do Orquestrador
5. Idade máxima aceitável da coleta externa de reserva
6. Limiar de variação de volume que dispara sinalização
7. Limiar mínimo de taxa de amarração
8. Horários exatos de execução na sexta e na segunda
9. Política de retenção do Registro
10. Prazo da aprovação tácita (só constava em Ferramentas §6)
11. Prazo de atendimento de lead e limite de inatividade (só constava na tabela do PRD)

## D-005 — Ganhos de relaxamento são ordem de grandeza, não conferência

**Data**: 2026-08-29 · **Resolve**: contradição C1 (PRD "Custo de cada regra" vs. Spec §6.6)

Os valores +133 / +569 / +1.680 / +1.747 / +5.686 foram medidos com mínimo de **três** corretores por distrito; o parâmetro adotado é **dois**. Prevalece a ressalva do PRD: são referência de ordem de grandeza e **nunca** entram em teste como valor exato. Já refletido em `docs/mapa-de-dados.md` e na skill `verificar-contra-spec`.

## D-006 — O modelo do Redator só vê agregados

**Data**: 2026-08-29 · **Resolve**: tensão entre o invariante 3 e o relatório de segunda

O relatório de segunda carrega dado pessoal (identificador de lead, corretor gestor, gestor de distrito) e o Redator é um dos três agentes com modelo. Fronteira dura de implementação: a chamada de modelo do Redator recebe **exclusivamente os números agregados do resumo da rodada** (contagens, percentuais, estado). Todas as abas com linhas nominais são geradas por template, sem passar por modelo. O subagente `auditor-de-invariantes` verifica essa fronteira.

## D-007 — Cadastro completo: apenas zero explícito reprova

**Data**: 2026-08-29 · **Resolve**: leitura da regra "cadastro completo" (Spec §6.1) para avaliação parcial por categoria

A Spec define a regra como "nenhuma das sete categorias da nota interna com valor zero" e decide dois casos: zero explícito reprova; ausência total de avaliação passa e recebe penalidade. Silencia sobre avaliação **parcial** (1 a 6 das 7) — que é a norma: média medida de 4,7 categorias por imóvel, com o pipeline de avaliação morto desde 16/10/2025 (mapa de dados, defeito 4).

**Decisão do dono: leitura A — apenas zero explícito reprova; categoria ausente não é zero.**

Fundamento empírico (medição de 29/08/2026, recorte elegível-aproximado de 35.592 ativos): 15.586 parciais sem zero, 12.025 sem avaliação alguma, 7.981 com algum zero e **zero imóveis com as 7 categorias avaliadas sem zero**. Sob a leitura estrita ("as 7 presentes e não zeradas"), nenhum imóvel avaliado passaria e o funil medido do próprio PRD (10.290 elegíveis) seria matematicamente impossível — a leitura A é a única consistente com a medição que o documento publica.

Assimetria registrada, sem decisão associada: o imóvel parcialmente avaliado sem zeros não é excluído **nem** penalizado, porque a penalidade da Spec §6.4 exige ausência total de avaliação. Se isso merecer correção, é calibração futura de penalidade (parâmetro pendente nº 3), não mudança desta leitura.

## D-008 — A nota final ponderada por nível é a chave de ordenação da alocação

**Data**: 2026-08-29 · **Resolve**: ambiguidade entre Spec §6.3 e §6.5 (e PRD, Estágios 3–4)

A Spec §6.3 define a nota final como soma ponderada das notas dos três fatores, com um conjunto de pesos por nível, descontadas as penalidades. A §6.5 manda ordenar o super destaque por "valor esperado" e o destaque por "probabilidade de lead". Nenhum documento afirma que as duas grandezas são a mesma.

**Decisão do dono: leitura A — a nota ponderada de cada nível É a operacionalização do objetivo daquele nível; a alocação ordena pela nota final.**

A tabela "Objetivo por nível" da §6.3 descreve o que cada conjunto de pesos persegue, não uma segunda grandeza a calcular; a leitura é coerente com o PRD ("esses valores são iniciais e serão revistos depois da primeira lista produzida"). A alternativa — "valor esperado" e "probabilidade de lead" como cálculos próprios — exigiria dois modelos que nenhum documento especifica, criando parâmetros pendentes que a D-004 não lista.

## D-009 — Desempate do ranking: preferência por cadastros mais novos

**Data**: 2026-08-29 · **Resolve**: critério de desempate da alocação, não definido em nenhum documento (leitura estrutural do PR #6, levada ao dono como pergunta)

O PR #6 adotou desempate por `imovel_id` crescente — determinístico, mas com viés declarado a favor de cadastros mais antigos. A pergunta foi levada ao dono, que decidiu.

**Decisão do dono (instrução literal): "O desempate é preferencia por cadastros mais novos."**

Duas camadas, que não podem se confundir:

- **O critério decidido é semântico**: em empate de nota, ganha o imóvel de cadastro mais recente.
- **A implementação é um proxy**: `imovel_id` DECRESCENTE (chave `(-nota, -imovel_id)` nas duas fases de `src/dominio/alocacao.py`). **Pressupõe que `imovel_id` cresce com a data de cadastro no Newcore; não verificado contra a base.** Se o pressuposto for falso, o código faz o oposto da decisão sem que nenhum teste acuse — os testes fixam a ordenação, não a semântica. Verificação pendente: uma consulta do `investigador-de-dados` (correlação entre `realties.Id` e a data de criação/ativação) resolve; precisa de acesso à base e de autorização do dono.

**Alternativa fiel, se o proxy cair**: a data de ativação/cadastro existe no Newcore (o mapa de dados a usa para separar imóveis "ativados após o corte" de 16/10/2025). Substituir o proxy exige apenas um campo novo em `CandidatoAlocacao` (ex.: `cadastrado_em: date`), alimentado pelo Coletor Interno — a decisão não muda.

**Atalho proibido**: `atualizado_em` (já disponível em `elegibilidade.ImovelCandidato`) NÃO é data de cadastro — é data de atualização; um imóvel antigo reeditado ontem contaria como "novo". Usá-lo no desempate seria inventar regra.

**Verificação de 31/08/2026 — pressuposto CONFIRMADO.** `realties.Id` é `auto_increment` e o campo semântico da data de cadastro é `realties.CreatedAt` (datetime, 0 nulos em 483.004 linhas). No estoque recente (Id ≥ 469.353, jul/2025 em diante, 41.969 pares adjacentes): **zero inversões**. Na tabela inteira: 444 inversões (0,092%), sendo apenas 3 com ≥ 24h — todas no resíduo legado de 2017 (Ids ≤ 556); as demais são jitter de segundos a ~3h. Consequência declarada da exceção: nesses casos raros e antigos o desempate pode inverter em relação à intenção — aceitável por ser desempate, não critério primário, e por o estoque que disputa vitrine ser recente por construção das regras. A ressalva original acima permanece como registro histórico do estado em que a decisão foi tomada. Achado colateral: `FT_RealtyRelation.FirstActivationDate` (ativação) NÃO é monotônica com o Id (38,5% de pares invertidos, 11,3% nula) — se o dono um dia reinterpretar o critério como "ativação mais nova", o proxy deixa de servir e a alternativa fiel exigirá esse campo com tratamento de nulos. O atalho `atualizado_em` segue proibido.

## D-010 — Coletor Externo: transporte CDP em Chrome real

**Data**: 2026-08-31 · **Resolve**: como o Coletor Externo raspa o Canal Pro (Ferramentas §2 dizia "automação de navegador com dois caminhos", sem fixar o mecanismo de transporte)

Instrução do dono (literal, nesta sessão): *"vamos reconstruir do zero para já modelar o agente de acordo com ela"* — referindo-se ao raspador `imovelweb-ativos`, validado por ele contra o painel ImovelWeb (canário progressivo 1→10→100→1000 sem bloqueio).

**Decisão: o Coletor Externo adota o transporte CDP em Chrome real** — anexa (via `--remote-debugging-port`) a um Chrome já aberto e autenticado pelo operador, e faz as chamadas à API interna do painel de dentro da própria página, herdando a sessão. Login humano único por aquecimento (a Ferramentas §5 já registrava a preocupação com "login automatizado repetido" como padrão que proteções anti-bot procuram — o login manual a resolve). Componentes arquiteturais: captura de sessão, canário progressivo como portão do full, sharding, checkpoints por lote e detecção de bloqueio com re-aquecimento manual sinalizado.

A técnica pode ser descrita no nível que for útil para manutenção — o código vai a repositório público por decisão do dono (D-012), então manter o documento vago não protege nada e piora a manutenção. **Fica fora de qualquer registro, sempre**: credenciais, senha/e-mail de conta do portal e dados da própria conta — isso nunca foi sobre técnica (ver limites na D-012).

**Caminho de erro e invariante 3.** A Ferramentas §2 previa um caminho de erro em que o modelo interpreta a página quando o determinístico falha. Neste desenho, a detecção de bloqueio é resolvida por **re-aquecimento manual** (o operador loga de novo), não por modelo — a intenção é que o Coletor Externo v0 **não tenha caminho com modelo**, reduzindo a três para dois os pontos do sistema que chamam modelo. Se um caminho com modelo vier a ser reintroduzido, o painel do Canal Pro é autenticado e suas respostas podem conter identidade do operador, dados de corretor ou contadores/contatos de lead: **nenhum payload do painel vai a modelo sem remoção de identidades antes do envio** (invariante 3). Fica registrado como obrigação do PR de implementação do coletor.

**Substitui Selenium por propriedade da técnica, não por causa de incidente.** Selenium/chromedriver é detectado por proteções que injetam desafio interativo e não completa a coleta; o Chrome real dirigido por CDP opera como o navegador do usuário. Esta é justificativa de desenho do coletor NOVO. **Não re-atribui o incidente do `task-titan`** (registrado no mapa de dados como "raspagem do Grupo Zap parada", jobs do `webscrapper_cron`): aquele segue em `docs/mapa-de-dados.md` (31/08) como incidente de infraestrutura (`chrome not reachable`), causa medida no log — decisão do dono nesta sessão de manter essa causa; a hipótese anti-bot não a substitui.

## D-011 — Console do Operador como componente do produto

**Data**: 2026-08-31 · **Resolve**: superfície de operação e observabilidade do sistema (o PRD e a Spec descrevem sete agentes, planilha e relatório, e dizem que o relatório de segunda "para no gestor da vitrine", sem interface)

Instrução do dono (literal): pede uma interface para *"verificar e analisar todos esses agentes, verificar o fluxo de trabalho deles, logs, pendências, ações que eu preciso tomar (como o próprio login no portal), o resultado da raspagem numa planilha do Google dentro dessa interface, custos da operação, monitoramento e observabilidade, edição dos prompts, ver o agente trabalhando"*, mais o painel de decisão com a motivação da lista, o botão de aprovação e o acervo de planilhas semanais.

**Decisão: o produto ganha um Console do Operador** (front-end, camada de OPERAÇÃO). Ele lê o Registro e o checkpointer do grafo e os artefatos do coletor, e escreve apenas no PostgreSQL próprio — **invariante 2 preservado**. Não participa do caminho da decisão nem chama modelo nesse caminho — **invariante 4 preservado**. A planilha do Google continua o entregável contratual; o console a exibe e arquiva, não a substitui.

**Divergência com a hierarquia, declarada e não resolvida aqui** (CLAUDE.md: documento inferior não resolve divergência em silêncio): o console é superfície nova que o PRD > Spec não preveem. Esta decisão registra a escolha do dono; **PRD e Spec precisam ser atualizados** para incorporá-la — enquanto não forem, esta decisão prevalece sobre o trecho divergente (regra do topo de `decisoes.md`).

**Entidade nova do Registro**: custo por execução de agente (rodada, agente, provedor, tokens, custo, duração) é a **nona** entidade, onde a Spec §2.1 define oito. O DDL da migração vem em PR próprio, **fora deste**; registrada aqui para que documento não afirme o que o esquema ainda não tem. Prompts dos três agentes com modelo passam a ser versionados por rodada (cada rodada grava a versão usada; mudança registrada como `alteracao_parametro`).

## D-012 — Publicação aberta do coletor: risco assumido pelo dono

**Data**: 2026-08-31 · **Resolve**: onde mora o código do Coletor Externo, dado que `orquestrador_portais` é um repositório público

O código do coletor (portado do `imovelweb-ativos`) é a receita executável que opera dentro da sessão autenticada do portal. O `orchestrator` sinalizou que publicá-lo no repositório público tem três consequências irreversíveis: expõe a técnica a quem lê o GitHub (Cloudflare, Grupo OLX), atribui nominalmente o contorno de proteção anti-bot ao dono, e não há desfazer (forks, caches e histórico sobrevivem a remoção). As alternativas apresentadas: repositório privado separado, tornar o produto privado, ou publicar aberto.

**Decisão do dono (instrução literal): "Publicar aberto mesmo assim."** Risco assumido de forma explícita e informada — análogo à D-001 (risco de aplicação parcial da carga, aceito por decisão explícita).

**O que foi apresentado ao dono antes da escolha** (o consentimento só é auditável se o registro mostrar a informação): que o repositório `orquestrador_portais` é **público**; e as três consequências, todas irreversíveis: (a) **queima da técnica** — Cloudflare e Grupo OLX leem GitHub, e a vantagem validada por canário vale enquanto não estiver publicada; (b) **atribuição nominal** — o repositório leva o nome do dono, então publicar o contorno de proteção anti-bot é assinar; (c) **irreversibilidade**. As alternativas oferecidas foram repositório privado separado, tornar o produto privado, ou publicar aberto. Ele escolheu publicar aberto.

**Irreversibilidade, sem ambiguidade**: revogar esta decisão depois **não despublica nada**. Forks, caches de terceiros e o histórico do git sobrevivem a `git rm` e a tornar o repositório privado. Não é um interruptor que se desliga; é uma porta que só abre.

**Limites desta decisão** (ela autoriza o núcleo do coletor, e só ele): **NÃO** autoriza publicar credenciais, senha ou e-mail de conta do portal, o perfil do Chrome (`profileDir`), cookies, `cf_clearance` capturado, nem nomes de cluster/serviço AWS ou o runbook do ECS. Isso nunca foi sobre técnica e permanece fora de qualquer repositório público. A varredura de segredos do coletor (além do gitleaks) verifica essa fronteira; a proveniência da cópia é declarada no README do diretório.

Esta é decisão de **processo**, não regra de decisão: registrada no CHANGELOG pela convenção do repositório, sem afetar nenhum invariante.

## D-013 — Venda assinada em 180 dias inclui as posteriormente canceladas (177, não 171)

**Data**: 2026-08-31 · **Resolve**: definição da métrica "venda assinada em 180 dias" que alimenta o perfil de conversão — nenhum documento-fonte fixava se um cancelamento posterior exclui a venda da contagem

Medição (investigador de dados, 31/08): `FT_LeadsOffers.SignedAt` não nulo nos últimos 180 dias = **177 ofertas / 174 imóveis distintos**, batendo com a referência ~176 de 28/08 (+1 de deriva). Dessas 177, o `Status` traz **6 "Cancelado definitivamente" + 1 "aguardando cobrança"**, todas com `CancellationAt` nulo. A referência histórica inclui essas linhas; excluí-las daria **171** ("venda líquida").

**Decisão do dono: venda = 177 (assinada em 180 dias), inclui as posteriormente canceladas.** A alternativa "líquida de cancelamento" (171) fica registrada como não escolhida. Consequência: o perfil de conversão (D-014) e qualquer contagem de vendas contam sobre 177. Se o dono um dia quiser a leitura líquida, esta decisão deve ser revista — muda a base de todo o perfil.

**Nota de robustez (não altera esta decisão):** 177 é a MÉTRICA. Algumas ofertas assinadas em 180d têm `Realty_Id` nulo (medido pela primeira rodada real) — sem imóvel, não ancoram um perfil (sem preço/vagas do JOIN, sem dimensões para casar). O perfil é descoberto sobre as vendas **ancoráveis** (177 menos os nulos), e o número descartado é **contado e declarado** na aba de limitações da rodada (`src/dados/vendas.py`, `_vendas_ancoraveis`). É robustez de leitura, não regra: 177 segue a métrica de "venda assinada".

## D-014 — Evidência mínima por perfil (parâmetro pendente nº 1) = N ≥ 3

**Data**: 2026-08-31 · **Resolve**: parâmetro pendente nº 1 da D-004 ("evidência mínima por combinação de perfil")

Ancorado em medição (distribuição de vendas por perfil, investigador 31/08, sobre as 177 vendas da D-013): **a localização é o gargalo do sinal**. Cobertura das vendas por buckets que atingem o limiar — localização isolada cai de **69% (N≥3) para 32% (N≥5)**; o par localização×dormitórios **zera em N≥8**. Dimensões grosseiras (metragem, vagas) aguentam limiar alto sem perder cobertura, mas dão perfis pouco específicos.

**Decisão do dono: piso único N ≥ 3 para a piloto.** É o menor limiar defensável — abaixo dele, um bucket sobre 177 vendas é coincidência e não padrão — e o único que mantém o sinal geográfico e os pares finos utilizáveis. O dono considerou o esquema diferenciado (N≥3 para dimensões finas, N≥5 para grosseiras) e optou pelo piso único, mais simples de auditar na piloto.

**Isto resolve o nº 1 na lista da D-004.** Os outros dez parâmetros seguem nulos. Os provisórios nº 2 (normalização) e nº 3 (intensidades das penalidades) usados na planilha-piloto são **run-local, rotulados PROVISÓRIO na própria planilha, e NÃO adotados** — continuam nulos na lista canônica e nunca entram em `src/config`.

## D-015 — "Corretor ativo no distrito" = captou ou vendeu em 30 dias (produtivos), fiel à Spec §6.1

**Data**: 2026-08-31 · **Resolve**: `DefinicaoAtivoDistrito`, pendência de mapeamento declarada no Coletor Interno (PR #14) — qual coluna de `FT_Districts` implementa a regra de capacidade do distrito

**Não é lacuna de regra.** A Spec §6.1 já define "corretor ativo no distrito" por extenso: *"Dois ou mais corretores que **captaram ou venderam** nos últimos 30 dias"*. A pendência do PR-A era só de implementação — qual coluna materializa esse texto — não de qual critério adotar.

Medição 31/08: a cobertura de distritos com ≥2 muda conforme a coluna — total 94,8% · logou-30d 76,8% · **produtivos (captou ou vendeu) 45,9%**.

**Decisão do dono: seguir a Spec — "ativo" = captou ou vendeu nos últimos 30 dias** (coluna `BrokersProductivity`, 45,9%). Alinhado ao texto literal da §6.1; **nenhuma divergência a declarar**. A alternativa "logou em 30d" (`Brokers_logged30d`, 76,8%) foi apresentada e **descartada por divergir da Spec** — adotá-la seria override do texto de §6.1, exigindo atualização de Spec/PRD (modelo D-011), e o dono optou por não abrir essa divergência. **Move o funil de elegibilidade para 45,9% de cobertura ≥2: é decisão que muda quem é elegível, não detalhe de operação.**

## D-016 — Leituras estruturais da costura da piloto (rodada degradada declarada)

**Data**: 2026-08-31 · **Resolve**: como a costura da planilha-piloto (`src/piloto/decisao.py`) monta os fatores do ranking quando falta a fonte externa e o sinal de produtividade é pobre — a Spec §6.3 define os fatores e pesos, mas não a forma de normalização (parâmetro pendente nº 2, nulo) nem o comportamento sob fonte ausente

São leituras estruturais da rodada de teste, declaradas (não inventadas), calibráveis, e todas visíveis na aba de limitações da planilha:

1. **`desempenho_proprio` = 0 para todos (rodada DEGRADADA nesse fator).** A piloto não raspa o Canal Pro, então o desempenho de portal por imóvel (peso 25 no super destaque, 10 no destaque — Spec §6.3) não existe. Zerá-lo uniformemente é **order-preserving**: com os outros dois fatores em [0,1] e desempenho 0 para todos, a ordenação é idêntica à de rankear pelos fatores disponíveis com seus pesos. É o estado **degradado** que a Spec já sanciona (fonte falhou, decisão prossegue com dado parcial, limitação declarada). Numa rodada real com o Coletor Externo, o fator deixa de ser zero.
2. **`produtividade_gestor` NÃO zera — é binário na v0.** Vem do sinal `gestor_captou_ou_vendeu_30d` (do Newcore, não do portal): 1 se captou/vendeu em 30 dias, 0 se não. Sob min-max, degenera em dois valores (1,0 / 0,0) — na prática um flag. Alternativa futura registrada: o sinal rico de `productivityrating` (captações/semana, conversão), que o candidato não traz hoje. **Cuidado de não zerar o fator errado por analogia com o desempenho: só o desempenho degrada.**
3. **Normalização (forma do parâmetro nº 2, provisória) SOBRE OS ELEGÍVEIS no ranking primário.** Cada fator é reescalado [0,1] por min-max **entre os elegíveis** — não sobre todos os candidatos. Razão: o `relaxamento.py` ordena os reprovados **dentro de cada grau de cedência** e não compara com o corte dos elegíveis, então reprovados e elegíveis não precisam da mesma escala; e como min-max preserva ordem, a saída do relaxamento é idêntica sob qualquer população. Normalizar sobre **todos** faria o ranking das 475/6.495 posições **depender de imóveis reprovados que nunca serão colocados** (os fatores comprimem de formas diferentes, deslocando o peso relativo) — distorção silenciosa da decisão principal. Por isso: elegíveis normalizados entre si para o ranking primário; reprovados normalizados entre si para o relaxamento (invariante à escala, saída idêntica).

**Provisórios da rodada, dois mecanismos distintos, ambos fora de `src/config` e não adotados** (D-014 mantém nº 2 e nº 3 nulos na lista canônica):

- **Tunáveis injetados run-local** (`ParametrosDecisao` / `ParametrosSemelhanca`): as intensidades e o decaimento das penalidades (nº 3) e o desconto de fragilidade. Trocáveis por rodada sem editar código.
- **Forma da normalização (nº 2) fixa no código, provisória**: a piloto usa **min-max como forma PROVISÓRIA do parâmetro nº 2**. O nº 2 **não é adotado** por isso — permanece **pendente na lista canônica da D-004**. É uma única forma na v0, então vive como função no código (`_normalizar_minmax`), não como callable injetado (injetar uma forma sem segunda opção seria complexidade sem uso), exatamente como as faixas de preço em `bucketizacao.py`. **Trocar a forma, ou adotá-la de vez, exige decisão do dono + CHANGELOG** (afeta o ranking). A aba de limitações da planilha rotula min-max como PROVISÓRIO, ao lado do nº 3 e das faixas — para o dono saber, ao ler a piloto, que a forma de normalização não foi decidida por ele.

**Acúmulo de limitações da piloto** (para o dono ler o resultado como teste de critério, não lista final): distrito = produtivos (D-015, cobertura 45,9%) + desempenho zerado + produtividade binária + normalização sobre elegíveis. As quatro na aba de limitações.
