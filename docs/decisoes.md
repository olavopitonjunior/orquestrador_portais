# Registro de Decisões

Resoluções do dono da decisão (Olavo) para divergências e lacunas encontradas nos documentos-fonte. Cada decisão vale a partir da data registrada e prevalece sobre o trecho divergente dos documentos até que uma revisão deles a incorpore. As contradições foram identificadas na análise da sessão de fundação (2026-08-29), não persistida como artefato; o essencial de cada uma está resumido na própria decisão.

> **O que ainda aguarda o dono está indexado em [`perguntas-abertas.md`](perguntas-abertas.md)** — uma linha por pendência, com o que cada resposta destrava. Este arquivo continua sendo a fonte: quem registrar pendência nova aqui **marca o identificador `[P-NN]`** e acrescenta a linha lá na mesma mudança. `tests/test_perguntas_abertas.py` falha se os dois divergirem.

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

**Adendo 2026-09-05 — esta regra de leitura vale para o PISO, não para a contagem.** A D-027 fez o perfil de conversão voltar a ser a nona regra, por outro caminho: desde ela a elegibilidade é oito regras gerais **mais o perfil**, e o piso de R$ 700.000 segue fora, como condição de nível — que é o que esta decisão fixou e continua valendo. A Spec 1.1 (05/09/2026) §6.1 já lista as nove assim. Em documento anterior a essa data, "nove regras" ainda se lê "oito gerais + piso"; da Spec 1.1 em diante, lê-se "oito gerais + perfil". O PRD é o texto que ainda depende dessa distinção — ver a [P-23], no fim deste arquivo.

## D-003 — Status impeditivo é regra de saída imediata, não de elegibilidade

**Data**: 2026-08-29 · **Resolve**: contradição C5 (tabela do Estágio 1 do PRD vs. glossário do PRD e Spec §6.7)

"Vendido, reservado ou removido" (e alteração relevante de preço) são gatilhos de **saída imediata fora do ciclo** (rotação, Spec §6.7), não uma décima regra de elegibilidade. A décima linha da tabela do Estágio 1 do PRD deve ser lida nesse papel.

## D-004 — Lista única de ONZE parâmetros pendentes

**Data**: 2026-08-29 · **Resolve**: contradição C2 (Spec §8 vs. Ferramentas §6 vs. tabela de parâmetros do PRD)

A lista canônica de parâmetros sem valor consolida os nove bullets comuns mais os dois que aparecem em apenas um documento. São **onze**, mantidos no CLAUDE.md. *(Onde este parágrafo disser "os outros dez", leia-se: dez DOS ONZE DE ENTÃO — a contagem vigente é catorze de quinze, ver as emendas abaixo.)* *(Emenda 2026-09-01, D-022: passaram a **quatorze** — a §6.4 exige um limiar de resultado POR NÍVEL que nenhum documento jamais quantificou, e ele entrou como nº 14. Treze seguem nulos. Mesmo procedimento da emenda da D-017 abaixo.)* O nº 1 foi resolvido em 2026-08-31 (D-014, `N ≥ 3`); os outros **dez seguem nulos** até definição:

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

**Emenda 2026-09-01 (D-017)**: a lista deixou de ser de onze e passou a **treze**. A D-017 (redesenho do ranking) tornou nulos dois parâmetros que a Spec §6.3 dava como **definidos** e que por isso ficavam fora desta lista — acrescentados agora como nº 12 e nº 13:

12. Pesos dos quatro fatores do ranking por nível (semelhança, leads, desempenho, produtividade).
13. Decaimento do peso por dimensão do F1 (a ORDEM preço > localização > metragem > dormitórios > vagas é adotada por decisão do dono; a MAGNITUDE do decaimento é que é nula).

**Emenda 2026-09-02 (D-025)**: a lista passou a **quinze** — a §6.7 exige um limiar para "alteração **relevante** de preço" e nenhum documento o quantifica. Ver a **D-025**, ao fim deste arquivo.

**Catorze** seguem nulos (só o nº 1 resolvido). *(Correção 2026-09-02: esta linha dizia "Doze" e a de cima dizia "onze"/"quatorze"; a tabela do CLAUDE.md sempre disse 13 nulos de 14; o `console/` **não** — `parametros.ts` derivava os pendentes, mas `page.tsx` cravava o total à mão e exibia "13 de 13", escondendo que o nº 1 está resolvido. Corrigido na fatia da rotação, passando a derivar o total. O texto corrido da D-004 não acompanhou as emendas D-017 e D-022.)* A tabela do CLAUDE.md foi atualizada na mesma fatia.

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

**Isto resolve o nº 1 na lista da D-004.** Os outros dez parâmetros seguem nulos. *(Contagem de então: os onze da D-004. Depois das emendas D-017, D-022 e D-025 (nº 15) são catorze nulos de quinze — ver a tabela do CLAUDE.md.)* Os provisórios nº 2 (normalização) e nº 3 (intensidades das penalidades) usados na planilha-piloto são **run-local, rotulados PROVISÓRIO na própria planilha, e NÃO adotados** — continuam nulos na lista canônica e nunca entram em `src/config`.

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

- **Tunáveis injetados run-local** (`ParametrosDecisao` / `ParametrosSemelhanca`): as intensidades e o decaimento das penalidades (nº 3) e o **[P-16]** desconto de fragilidade (peso do perfil frágil, Spec §6.2 "não recebe peso pleno" — provisório, fora dos quinze e sem valor adotado). Trocáveis por rodada sem editar código.
- **Forma da normalização (nº 2) fixa no código, provisória**: a piloto usa **min-max como forma PROVISÓRIA do parâmetro nº 2**. O nº 2 **não é adotado** por isso — permanece **pendente na lista canônica da D-004**. É uma única forma na v0, então vive como função no código (`_normalizar_minmax`), não como callable injetado (injetar uma forma sem segunda opção seria complexidade sem uso), exatamente como as faixas de preço em `bucketizacao.py`. **Trocar a forma, ou adotá-la de vez, exige decisão do dono + CHANGELOG** (afeta o ranking). A aba de limitações da planilha rotula min-max como PROVISÓRIO, ao lado do nº 3 e das faixas — para o dono saber, ao ler a piloto, que a forma de normalização não foi decidida por ele.

**Acúmulo de limitações da piloto** (para o dono ler o resultado como teste de critério, não lista final): distrito = produtivos (D-015, cobertura 45,9%) + desempenho zerado + produtividade binária + normalização sobre elegíveis. As quatro na aba de limitações.

## D-017 — Redesenho dos fatores do ranking: override dos PESOS da Spec §6.3, objetivos preservados

**Data**: 2026-09-01 · **Resolve**: o dono redirecionou a filosofia de priorização e respondeu quatro perguntas objetivas nesta sessão. A Spec §6.3 fixa três fatores com pesos definidos (semelhança 60/80, desempenho 25/10, produtividade 15/10) e trata o lead apenas como penalidade (§6.4). Esta decisão **sobrescreve os PESOS e o conjunto de fatores da §6.3**, mas **preserva os objetivos por nível** que a própria §6.3 declara — valor esperado no super destaque, probabilidade de gerar lead no destaque.

**Leitura de fundo (por que não é ruptura de objetivo):** a §6.3 diz que o objetivo do destaque é "probabilidade de gerar lead", mas na mecânica o lead só aparece como castigo (§6.4 "sem lead 180d"). O redesenho tira o lead da coluna de penalidade e o põe como **sinal positivo primário** — isto realinha a mecânica ao objetivo que a Spec já declara, não o contradiz. O primário da análise é o **banco de dados** (imóveis efetivamente vendidos + imóveis com mais leads), disponível na rodada sem depender da raspagem; a raspagem do portal é **reforço que soma**, não pré-requisito.

### Os quatro fatores do ranking redesenhado

1. **F1 — Semelhança com perfil de venda, PONDERADA POR DIMENSÃO.** Continua sendo a semelhança do candidato com os perfis de conversão (Spec §6.2), mas a contribuição de cada perfil passa a ser ponderada pela importância da(s) dimensão(ões) que o compõem, em **ordem decrescente: preço > localização > metragem > dormitórios > vagas**. A ORDEM EXATA das cinco dimensões é do dono, em palavras dele na mensagem estratégica desta sessão ("características de preço, localização, metragem, quantidade de dormitórios e quantidade de vagas de garagem, **nessa ordem**"); a mecânica de usar essa ordem como **peso DECRESCENTE por dimensão** foi a escolha explícita dele ("Peso decrescente por dimensão"). Nenhuma das duas é inferência do autor. Efeito: o perfil amplo de baixa importância (ex.: "dormitórios=2") deixa de dominar o sinal — corrige a **saturação** observada na primeira rodada real (443/475 super destaques puxados pelo mesmo perfil de dormitórios, todos com nota ≈ 60). A ordem das dimensões é regra de decisão; os **valores** dos pesos por dimensão são parâmetro nulo (ver abaixo).
2. **F2 — Leads (sinal POSITIVO).** Novo fator: `norm(Leads180D)` do banco (`FT_RealtyRelation.Leads180D`, já coletado). Muito lead ganha ponto. Horizonte = **180 dias** (resposta do dono, Q3), casado com a janela da venda assinada. É a mudança central: lead deixa de ser só penalidade e vira sinal primário.
3. **F3 — Desempenho próprio observado (portal) = REFORÇO que soma.** O desempenho de portal (visualizações/cliques da raspagem) deixa de ser fator de peso fixo e passa a ser explicitamente **aditivo/opcional**: roda zerado quando não há raspagem (rodada DEGRADADA nesse fator, order-preserving — mantém a leitura da D-016). Numa rodada com Coletor Externo, soma; sem ele, não bloqueia.
4. **F4 — Produtividade do gestor, por INTENSIDADE CONTÍNUA.** O sinal binário `gestor_captou_ou_vendeu_30d` (D-016) é substituído por uma **medida contínua** — o volume de captações+vendas do gestor em 30 dias (`productivityrating`, hoje não trazido ao candidato) — normalizada (resposta do dono, Q2/produtividade). Esse campo novo entra pelo **caminho de leitura do Coletor Interno** (usuário somente-leitura + guarda SELECT/SHOW já estabelecidos) — **invariante 1 preservado**: é leitura do Newcore, nenhuma escrita; a fatia de código do F4 roteia o campo por essa guarda. Razão: a primeira rodada mostrou o binário **redundante com a regra de elegibilidade "gestor produtivo"** (todo elegível já passou, o fator não diferenciava ninguém). A versão contínua volta a discriminar. A regra de elegibilidade "gestor produtivo" (Spec §6.1) **não muda** — só o fator do ranking.

### Pesos: deixam de ser adotados, viram parâmetro nulo (provisório run-local)

Os pesos da §6.3 eram parâmetro **definido**. Ao trocar o conjunto de fatores e a filosofia, os **valores exatos dos pesos do novo esquema** (importância relativa de F1/F2/F3/F4 por nível) e os **pesos por dimensão do F1** passam a ser **parâmetro nulo** — decisão do dono, ainda não tomada. Regras, coerentes com D-014/D-016:

- Nenhum valor de peso é inventado como adotado. Na planilha-piloto entram como **PROVISÓRIOS run-local**, injetados (nunca hardcode em `src/dominio`, nunca em `src/config`), rotulados PROVISÓRIO na aba de limitações. Invariante 5 exige que `ranking.py` receba os pesos injetados, não constantes escondidas.
- A relação de ordem primário `{F1, F2}` > reforço `{F3}` > `{F4}` é a **direção** decidida pelo dono; os números que a realizam ficam nulos até ele fixar.
- Adotar qualquer valor de peso exige nova decisão do dono + CHANGELOG.
- **Reconciliação com a lista canônica de parâmetros pendentes (D-004/CLAUDE.md) — ressalva do revisor-de-regra.** Os pesos da §6.3 eram parâmetro DEFINIDO, fora da lista de ONZE pendentes da D-004. Torná-los nulos **expande o conjunto de pendentes**, então a lista canônica precisa passar a listá-los: os **pesos do novo esquema de 4 fatores** (por nível) e os **pesos por dimensão do F1** entram como pendentes. Para não abrir em outra chave a mesma divergência silenciosa que a hierarquia proíbe, a **atualização da tabela de parâmetros do CLAUDE.md e da D-004** (renumerando/expandindo a lista) fica atribuída à fatia que tocar `src/config`/domínio (fatia 2), com entrada própria no CHANGELOG. Até lá, esta D-017 é a autoridade que declara os pesos como pendentes.
- **Forma e população de normalização de F2 e F4 (invariante 5) — ressalva do auditor.** Os fatores novos F2 (`norm(Leads180D)`) e F4 (contínuo) herdam a forma **min-max PROVISÓRIA** e a normalização **SOBRE OS ELEGÍVEIS** no ranking primário (reprovados normalizados entre si no relaxamento), exatamente como a D-016 fixou para semelhança/produtividade. A fatia de código deve manter isso explícito — normalizar sobre população variável quebraria a reprodutibilidade entre rodadas (invariante 5).

### Objetivos por nível preservados (Spec §6.3)

Super destaque continua perseguindo **valor esperado** (conversão ponderada pelo ticket — venda é conversão; F1+F2 sob o piso de R$ 700.000 e a ordenação por valor esperado da alocação). Destaque continua perseguindo **probabilidade de gerar lead** (F2 ganha peso relativo maior neste nível, como a semelhança tinha 80). A §6.5 (alocação), o piso (D-002) e as cotas (invariante 6) não mudam.

### Crivo de auditoria/fiscalização (HÍBRIDO)

Novo componente (resposta do dono, Q4: "híbrido"), em duas camadas com naturezas distintas para respeitar os invariantes 4 e 5:

- **Camada 1 — determinística, com veto** (`src/dominio/auditoria.py`, stdlib puro): verificação por cálculo reprodutível de que a seleção honra os critérios objetivos — cotas 475/6.495 exatas, piso de super destaque, relaxamento só em destaque (invariante 7), todo item com justificativa, e **dominância** (nenhum imóvel excluído supera um incluído em TODOS os fatores adotados). O que o dono decidiu é o crivo híbrido em si (Q4); os checks concretos da camada 1 — em especial a dominância — são **elaboração de desenho** do autor para a fatia de implementação, não mandato literal do dono, e podem ser ajustados no code review da fatia 3. Se algum critério falha, a rodada **não fica pronta** (reprova). Não usa modelo — está no caminho da decisão e por isso é cálculo (invariantes 4/5).
- **Camada 2 — consultiva, sem veto** (fora do caminho da decisão): um parecer de sanidade gerado por modelo, **só sobre agregados** (D-006, invariante 3 — nenhuma identidade de lead/comprador/corretor), que o dono lê antes da aprovação. Não altera a lista, não reprova. Por estar fora de elegibilidade/ranking/alocação/relaxamento, não fere o invariante 4. **Onde mora esse modelo (ressalva do auditor):** o CLAUDE.md fixa "apenas três agentes usam modelo" (Coletor Externo, Analista de Perfil, Redator). Para NÃO criar um quarto ponto de modelo, a camada 2 é realizada **dentro do Redator** — que já usa modelo sobre agregados (D-006) —, como um parecer de sanidade a mais no resumo da rodada, não um agente novo. Se o dono preferir um agente/superfície de auditoria separado com modelo próprio, isso é ampliação do "três agentes" e **exige decisão do dono antes da fatia 3** (implementação da auditoria).

### Pontos declarados, não resolvidos aqui

- **Divergência com a hierarquia** (CLAUDE.md: documento inferior não resolve divergência em silêncio): esta decisão sobrescreve os pesos da Spec §6.3, documento superior ao código. **A Spec §6.3 precisa ser atualizada** para incorporar o novo conjunto de fatores e a natureza nula dos pesos; enquanto não for, esta decisão prevalece sobre o trecho divergente (regra do topo de `decisoes.md`). Os objetivos por nível da §6.3 seguem valendo intactos.
- **Redundância da penalidade "sem lead 180d"** (§6.4): com F2 premiando lead, "sem lead" já resulta em F2=0 (piso), então a penalidade vira quase redundante com o próprio fator. **Não é alterada aqui** — fica como item de calibração do dono (mexer nela exige decisão + CHANGELOG).
- **Distrito continua ≥ 2** (Spec §6.1 + D-015): reafirmado nesta sessão, sem mudança.

**Emenda 2026-09-01 (D-017) — ratificação da camada 2 do crivo:** o dono ratificou o default desta decisão — a **camada 2 consultiva (parecer por modelo) mora dentro do Redator** (D-006, só agregados), **sem ampliar o "três agentes usam modelo"**: NÃO há um quarto agente-modelo de auditoria. É confirmação da cláusula já registrada acima (a camada 2 mora no Redator, e um agente/superfície de auditoria separado exigiria decisão do dono) — não decisão nova, por isso emenda, não um D-018. Consequência para a implementação: a fatia do crivo entrega a **camada 1 determinística** (código, pode vetar) e **declara o contrato da camada 2** como pendência da fatia do Redator-com-modelo (o provedor de modelo ainda não foi escolhido; o Redator hoje é template) — nenhuma chamada de modelo é instanciada agora.

## Divergência aberta (aguarda o dono) — estado terminal de um veto do crivo (G1, 2026-09-01)

**Contexto:** o esqueleto do grafo (marco F, G1) liga o crivo de auditoria camada 1 (D-017) como gate de "pronto" da decisão. Quando o crivo VETA (a seleção viola cota, piso ou relaxamento em super), a rodada não pode entregar — "etapa que não cumpre pronto não entrega para a seguinte" (glossário).

**Divergência declarada (não resolvida em silêncio — regra do CLAUDE.md):** a Spec §7.2 só prevê o estado **ABORTADA** para o caso de **coleta interna vazia** (sem estoque). Um veto do crivo é falha de **integridade da decisão**, não de fonte — a §7.2 não oferece estado terminal para isso. A G1 **reusa ABORTADA pela CONSEQUÊNCIA** (sem entrega), com o `motivo_aborto` distinguindo veto-de-integridade de estoque-vazio, e o `_rota_pos_crivo` desviando do Redator.

**Pendência do dono [P-01]:** decidir se um veto do crivo merece **estado terminal próprio** na Spec §7.2 (ex.: "reprovada"/"bloqueada") em vez de reusar ABORTADA. Até a decisão, vale o reuso declarado acima. Na prática o veto não dispara em rodada válida (a piloto/grafo dão PRONTA); é um gate de segurança contra bug upstream.

**Consequência de persistência (G2a-wire, 2026-09-01):** o nó de persistência do grafo só grava rodadas NÃO-abortadas, então uma rodada ABORTADA (por estoque vazio OU por veto do crivo) **não deixa nenhuma linha no Registro — nem o cabeçalho `rodada`**. Isso diverge da Spec §2.1, que prevê "uma linha por execução" e admite `estado='abortada'` + `motivo` + `tentativas_por_etapa`: hoje esses campos nunca são populados para abortos, e o Monitor de segunda / a auditoria não enxergam a execução que abortou. A distinção correta é "seleção inválida não se guarda em `decisao_imovel`" (mantido) versus "a execução não se registra" (diverge). **Pendência do dono, ligada à decisão de estado terminal acima:** registrar o cabeçalho da rodada abortada (sem `decisao_imovel`) é fatia futura candidata — a escrita atomica atual (`gravar_rodada_decisao`, rodada + posições) é tudo-ou-nada e não sabe gravar só o cabeçalho.

## Aprovação humana da rodada (G2b/G3, 2026-09-01)

**O que a fatia entrega:** a interrupção de aprovação da rodada de decisão (D-001, aprovação tácita por prazo) como um grafo LangGraph **separado** do fluxo de decisão (`src/grafo/aprovacao.py`), com estado **deliberadamente leve** — só `rodada_id` + veredito (strings) — e checkpointer **Postgres**. A separação é o ponto: o checkpointer serializa TODO o estado a cada passo, e o estado do fluxo de decisão carrega objetos de domínio não-serializáveis; isolando a aprovação num grafo de estado leve, a pausa que dura "horas ou dias" (Ferramentas §2) persiste no Postgres sem exigir serializadores para o domínio. A decisão de sexta roda e PERSISTE primeiro (G2a-wire), devolvendo o `rodada_id`; a aprovação só carrega essa chave.

**Autoridade de desenho (ressalva do revisor-de-regra):** a aprovação humana traça-se a **D-001 + Ferramentas §6** (parâmetro nº 10, prazo da tácita). A **Spec §7 é "Estados e tratamento de falha" e §8 é "Pendências" — nenhuma descreve mecanismo de aprovação/interrupção**. Não se conclui "a Spec manda X" onde a Spec é silente; contra a autoridade que existe (D-001), o mecanismo pausar→retomar está fiel.

**Prazo tácito (parâmetro nº 10) segue NULO:** o módulo entrega só o **mecanismo** (pausar→retomar). Quem conta o prazo e dispara a retomada tácita é a camada de agendamento (Orquestrador / agendador do SO / botão do console), fora desta fatia. Nenhum valor de prazo é inventado.

**`aprovada_por` passa a ser persistido (migração 004, resolve ressalva do revisor-de-regra):** D-001 descreve o carimbo como "aprovada em ⟨momento⟩, **por prazo**". Antes, `registro.rodada` guardava só `aprovada_em` (o instante) e o "por prazo / por quem" se perdia na borda de persistência. A migração 004 acrescenta a coluna nullable `aprovada_por` (CHECK: só com `aprovada_em`), e o sink de aprovação passa `"tácita"` (decurso de prazo) ou a identificação do dono (explícita) — a fonte da verdade agora distingue as duas, fiel ao "por prazo".

**Limite DECLARADO [P-04] — reprovação não entra na fonte da verdade (tensão com D-001, ressalva do revisor-de-regra):** o esquema `registro.rodada` tem só `aprovada_em`/`aprovada_por` nullable e **nenhuma coluna de status**. Uma **reprovação** explícita do dono é representável no estado do fluxo (`decisao="reprovada"`, no checkpointer), mas **não deixa rastro no Registro** — fica indistinguível de "ainda não decidida" (ambas com `aprovada_em` NULO). Isso é honesto, não é bug, mas cria tensão com D-001 ("o Registro é a fonte da verdade"). **Pendência do dono:** persistir a reprovação exigiria uma coluna de status na `rodada` (ex.: `estado_aprovacao`) — fatia futura candidata, análoga em espírito à divergência da rodada abortada acima.

**Comportamento fail-closed e recuperável (robustez, ressalva do revisor-de-código):** uma retomada fora do contrato (não montada pelos construtores `aprovar_tacita`/`aprovar_explicita`/`reprovar`) **não aplica nada** — reabre a interrupção pedindo uma válida, e a retomada válida seguinte prossegue ("o dono corrigiu e reenviou"). Escolhido re-interromper em vez de `raise` porque um `raise` deixaria o thread preso num resume envenenado (o LangGraph reexecuta o mesmo resume anterior) — verificado empiricamente na fatia.

## Coletor Externo fiado no grafo — F3 vivo (G4, 2026-09-01)

**O que a fatia entrega:** o nó `no_coletor_externo` deixa de ser stub e passa a LER a saída do raspador (`coletor-externo/`, contrato de arquivo `out/*.csv` + `status.json`, D-010) via `src/dados/coletor_externo.py`, aplicar as portas de admissão (Spec §7.3) e, passando, compor o **fator F3 (desempenho de portal)** por imóvel, que entra no ranking (`decidir(..., desempenho_por_imovel=...)`). Com raspagem fresca e amarrada a rodada pode ser **COMPLETA**; sem ela (stub, ausente, velha ou amarração baixa) segue **DEGRADADA** nesse fator, com o motivo declarado. A raspagem fica FORA do caminho da decisão (invariantes 4/5): é fonte datada pelo próprio `finishedAt`; o F3 resultante é cálculo determinístico (min-max entre a população, como os outros fatores), sem modelo.

**Provisórios, NÃO adotados (seguem nulos em `src/config`; injetados run-local, rotulados provisórios):**
- **[P-15] Composição do sinal F3** a partir de nota (LQS)/visualizações/cliques: a FORMA de normalizar cada fator é o parâmetro nº 2, em aberto — a composição também é aberta. Default run-local do runner = `visualizações`; injetada como `ParametrosExterno.compor_desempenho`, nunca hardcode no domínio nem em `src/config`. Adotar uma composição exige decisão do dono + CHANGELOG.
- **Limiar mínimo de amarração** (nº 7) e **idade máxima da coleta** (nº 5): injetados como `ParametrosExterno.limiar_amarracao`/`idade_maxima_dias`, provisórios; seguem nulos na lista canônica (D-004).

**Limites DECLARADOS (honestos, não em silêncio):**
- **Reserva não reusada (Spec §7.3):** a Spec manda "usar a última coleta válida dentro da janela aceitável" quando a sessão falha; hoje uma coleta fora da janela (idade > nº 5) apenas DEGRADA — não há reuso de uma coleta anterior de reserva. Fatia futura candidata (guarda o "dado de reserva ~semana anterior" da Spec §7.3).
- **Formato da amarração:** assume-se `codigoImovel` (externalId) = id NUMÉRICO do Newcore (`realties.Id`, papel do externalId no RECIPE). Linha sem `codigoImovel` ou de formato não-numérico não amarra e conta como `sem_amarracao`; `_imovel_id_de` é a única costura desse formato, se a produção divergir.
- **URL sempre nula:** a listagem do Canal Pro não traz a URL pública do anúncio (lacuna do RECIPE); o F3 usa performance, não a URL. A URL da planilha (Spec §3) fica como lacuna do portal, não desta fatia.

## D-018 a D-020 — rodada de segunda: definições RESOLVIDAS pelo dono (2026-09-01)

A investigação read-only do banco (registrada em `docs/mapa-de-dados.md`, seção "Fonte dos campos da RODADA DE SEGUNDA") confirmou que a maioria dos campos exigidos pela Spec §4.2/§4.3 existe — mas levantou **duas definições que mudam o número entregue e que não podiam ser escolhidas no código**, além de duas colunas sem fonte. As três foram levadas ao dono e **resolvidas em 2026-09-01**; a quarta (D-D) é limitação declarada, sem decisão pendente.

## D-018 — "atendimento registrado" inclui o HISTÓRICO, não só o estado atual

**Data**: 2026-09-01 · **Resolve**: a definição do sinal de atendimento da Spec §4.2

**Decisão do dono: incluir o histórico.** A regra é:

```sql
AttendedAt IS NOT NULL
  OR EXISTS (SELECT 1 FROM newcore.facstatushistory h
             WHERE h.Fac_Id = FacId AND h.StatusAfter = 12)   -- 12 = 'Atendimento'
```

Fundamento (medição 01/09/2026) — o problema que a decisão evita:

`FT_Leads.AttendedAt` é **campo de estado atual, não evento histórico**: só é não-nulo enquanto o lead está em `Status = 'Atendimento'`, e é APAGADO quando o lead sai (nos 6.371 leads `Removido` da janela de 90 dias é nulo em 100%, inclusive nos 4.560 que têm contato registrado).

Medido contra o histórico (`newcore.facstatushistory`, `StatusAfter = 12`):
- passaram por atendimento algum dia: **86,54%**; ainda mantêm o carimbo: **49,94%**;
- dos 4.211 leads "sem tratamento" pela regra ingênua, **1.956 (46,45%) foram atendidos**;
- a regra ingênua **superestima o abandono em ~1,87×** em 90 dias e em **+21,6%** na janela real de 3 dias (197 vs 162, 28→31/08).

**Por que é do dono e não do código:** a aba "leads sem tratamento" é o instrumento de COBRANÇA de pessoas (Spec §4.4: "mede o padrão de comportamento e sustenta a cobrança"). A escolha da definição muda **quem é nomeado como tendo abandonado lead**. Entregar a regra ingênua significaria acusar de abandono ~1 em cada 2 corretores da lista que de fato atenderam.

**Efeito da decisão:** a lista de abandono cai de 197 para **162 leads** na janela real (28→31/08) e de 4.211 para 2.255 em 90 dias. Custa um JOIN a mais. É a leitura que casa com o próprio texto da §4.2 ("critério mais conservador dos disponíveis... aponta apenas o abandono indiscutível") — a regra ingênua acusaria de abandono quem de fato atendeu.

**Consequência de implementação:** a consulta da rodada de segunda lê `newcore.facstatushistory` além de `FT_Leads`. Somente leitura (invariante 1), via `src/dados/newcore.py`.

## D-019 — "gestor de distrito" é o EMBAIXADOR

**Data**: 2026-09-01 · **Resolve**: a coluna "gestor de distrito" da Spec §4.2, que não existe com esse nome no banco

Não existe coluna com esse nome. Há duas camadas medidas:
- **`FT_Leads.embaixador`** — 94,78% preenchido, **23 pessoas distintas**, idêntico a `FT_Districts.Ambassador_Name`. É o responsável de nível distrital.
- **`newcore.districts.AmbassadorManager_Id`** — só **2 pessoas** para 1.616 distritos; é a camada acima (gestor dos embaixadores).
- (`districts.Ambassador_Id` está degenerado: 1 único valor para 1.616 distritos. Inutilizável.)

**Decisão do dono: o embaixador** — `FT_Leads.embaixador` (94,78% preenchido, 23 pessoas). É o responsável de nível distrital e casa com a definição do PRD ("responde pela cobertura e performance dos corretores"). O `AmbassadorManager` foi descartado: com 2 pessoas para 1.616 distritos, a coluna nomearia sempre as mesmas duas.

**Divergência de nomenclatura declarada:** o banco chama de "embaixador" o que a Spec chama de "gestor de distrito". A planilha usa o rótulo da Spec; a origem é a coluna `embaixador`.

## D-020 — as duas colunas da §4.3 sem fonte ficam VAZIAS e acumulam

**Data**: 2026-09-01 · **Resolve**: "semanas consecutivas em destaque" e "leads acumulados na janela atual" (Spec §4.3) sem origem no Newcore

As duas viriam de `newcore.adsrealtyextra_historic`, que está **MORTA desde 27/06/2023** (zero janelas abertas). **Não há fonte no Newcore.**

**Decisão do dono: manter as colunas na planilha, vazias, e acumular.** Só o Registro próprio pode supri-las, somando o histórico das cargas aprovadas rodada a rodada; nas primeiras semanas ficam vazias e vão se preenchendo. O domínio já trata como ausência declarada (`None`), **nunca como zero inventado** — um imóvel sem histórico não é um imóvel com zero semanas.

Mantém a fidelidade à Spec §4.3 (as colunas existem) sem fabricar dado.

## D-D (limitação declarada, sem decisão pendente) — "tempo desde a distribuição" é desde a ÚLTIMA

`FT_Leads.DIstributedAt` (grafia com "I" maiúsculo) vem de `facs.LastDistributedAt`: é a **última** distribuição. `facs.Redistributed = 1` em **25,78%** dos leads de 90 dias. Em um quarto dos casos a coluna da §4.2 mede o tempo desde a REdistribuição, não desde a primeira entrega ao corretor. Reconstruir a original exigiria `facstatushistory`. Fica declarado; se o dono quiser a primeira distribuição, é fatia própria.

**Precondição da fatia seguinte (M3, ligar a segunda ao grafo) — achado do auditor-de-invariantes em 2026-09-01:** `ResultadoAcompanhamento` carrega PII (`leads_sem_tratamento`), e o checkpointer do LangGraph **serializa o estado do grafo no Postgres**. Colocar o objeto inteiro no `EstadoRodada` reintroduziria no banco exatamente a PII que `gravar_acompanhamento` deliberadamente NÃO grava — anulando a redução de exposição desta fatia, e em silêncio. O estado do grafo deve carregar o `PayloadModelo` (agregados) e a lista nominal deve ir direto ao Redator/planilha, sem atravessar o checkpointer. Não é violação hoje (M2 não toca o grafo); é requisito da M3, com teste próprio.

## Ponto de entrada da sexta (2026-09-01) — o que foi resolvido e o que aguarda o dono

A fatia do runner da sexta (`src/executar/sexta.py`) obrigou a decidir **como uma rodada roda se treze dos quatorze parâmetros de então são nulos**, e os três portões levantaram divergências que ficam registradas aqui.

### Resolvido no código: os parâmetros entram por arquivo do dono, e a rodada recusa rodar sem eles

`--parametros ARQUIVO.toml` é obrigatório e **não tem default**. Embutir um valor "razoável" seria o valor inventado que o CLAUDE.md proíbe, com o agravante de ficar invisível numa planilha aprovada. O carregador (`src/config/parametros.py`) recusa chave ausente (nomeando o pendente), chave desconhecida e valor fora de faixa. `src/config` segue **sem valor nenhum**: ganhou o carregador, não os números. Tudo que entra sai rotulado PROVISÓRIO com a origem, e o TOML declarado vai verbatim para o Registro — adotar continua exigindo decisão aqui e entrada no CHANGELOG.

O **modelo** `docs/parametros-da-rodada.exemplo.toml` é recusado como entrada real: ele carrega com sucesso, e sem a recusa sairia dele uma planilha de aparência normal construída sobre números que o próprio arquivo declara ilustrativos.

### [P-02] Divergência aberta (aguarda o dono) — a ordem Registro → Redator

Os documentos põem o Redator **antes** do Registro: PRD (fluxo de sexta, passo 6 = planilha, passo 7 = Registro, "saídas dos passos 5 e 6") e Spec §5 ("Registro | Consome: saídas do Decisor, **do Redator** e do Monitor"). O código faz o inverso: o grafo grava no Registro no último nó e o runner escreve a planilha depois.

O argumento do código é que uma planilha sem rodada no Registro é uma decisão sem trilha. O **contra-argumento do revisor-de-regra é mais forte e fica registrado**: sob a D-001, com o Registro como fonte da verdade, uma rodada gravada sem planilha pode ser aprovada por decurso de prazo e virar a "carga vigente" contra a qual a segunda mede — uma lista que ninguém recebeu nem aplicou. O modo de falha inverso (artefato sem trilha) é detectável na aprovação.

**Pergunta ao dono [P-02]:** inverter para Redator → Registro (e o Registro passar a guardar o caminho do artefato, que hoje ele não guarda), ou manter a ordem atual e declarar a divergência com a §5? Até a resposta, a ordem atual permanece **com a divergência declarada aqui** — não em silêncio.

### ~~Lacuna operacional declarada — a cadeia sexta → carimbo → segunda não fecha~~ (FECHADA em 2026-09-02)

O runner da sexta informa o `rodada_id` e **não abre** o fluxo de aprovação: o que dispara a tácita sozinha é o prazo, parâmetro pendente nº 10, **nulo**, e abrir uma thread sem prazo afirmaria um prazo que ninguém definiu. Isso está correto quanto ao documento — a D-001 pede um carimbo (`aprovada_em`), não um estado formal "pendente", e `aprovada_em IS NULL` já É a pendência.

O buraco era operacional: `ultima_carga_aprovada` exige `aprovada_em` não nulo, e nada carimbava. **Fechada pelo ponto de entrada da aprovação** (`src/executar/aprovar.py`, PR #43, 2026-09-02), que dá o chamador que faltava. *Precisão do fechamento:* fechou o carimbo MANUAL — a cadeia só fecha de fato se alguém rodar `rodada-aprovar` toda semana, porque a aprovação automática por decurso de prazo depende do parâmetro nº 10, que segue nulo. Esse resíduo é o que a fila do dono registra; não é mais esta lacuna. *(O texto original também afirmava que o console não existe — não era verdade nem então: `console/lib/registro.ts` já montava a fila de rodadas aguardando aprovação.)*

### Limitações que passaram a ser DECLARADAS na planilha (antes invisíveis)

Levantadas pelos portões nesta fatia e agora emitidas na aba de parâmetros e limitações:

1. **A penalidade por janela anterior sem resultado não incide sobre ninguém.** O Coletor Interno devolve `janelas_anteriores=()` para todo imóvel e nada no caminho da sexta lê `registro.janela_destaque` — o produtor não existe. Uma das três penalidades da §6.4 fica inerte e a coluna sai 0,0 para todos, indistinguível de "imóvel sem histórico", que o PRD manda identificar como tal. A limitação é **derivada do resultado**: quando o produtor chegar, ela some sozinha.
2. **Razão 1.0 no decaimento não decai**, divergindo da §6.4 — declarada quando escolhida, em vez de o código fingir que não há divergência.
3. **A definição de gestor ativo do distrito** (D-015) cobre 45,9%, como a D-016 já mandava declarar e não estava sendo declarado.
4. **Variação do estoque elegível** (§3.1, obrigatória): sem produtor — exige a rodada anterior no Registro. Declarada como NÃO APURADA.

Corrigido junto: a limitação "desempenho de portal ausente" era emitida **incondicionalmente**, então uma rodada COMPLETA com raspagem viva declarava, duas linhas abaixo do próprio estado, que o portal estava ausente. Limitação falsa na planilha que sustenta a aprovação.

E a **aba de relaxamento** passou a ser gerada: a Spec §6.6 é literal — "sem esse registro a etapa de decisão não é considerada pronta" — e a §3.1 a lista como obrigatória. O Registro já guardava o agregado por regra; ele só não chegava ao artefato que as pessoas leem, e a rodada saía COMPLETA assim mesmo.

### [P-03] Pergunta aberta ao dono — limitação de FIAÇÃO deve mudar o ESTADO da rodada?

As três limitações de fiação (histórico de janelas ausente, razão 1.0 sem decaimento, distrito a 45,9%) são declaradas na planilha **e** gravadas no `motivo_degradacao` do Registro — planilha e fonte da verdade dizem a mesma coisa. Mas elas **não** entram em `estado["degradacoes"]`, então não mudam o estado da rodada.

A escolha é discutível nos dois sentidos. A §7.2 define degradada como "alguma fonte falhou e a decisão prosseguiu com dado parcial", e o histórico de janelas **é** uma fonte ausente produzindo dado parcial — o que argumenta por DEGRADADA. Por outro lado, marcá-las como degradação tornaria **toda** rodada degradada até o produtor de `registro.janela_destaque` existir, e um estado que nunca varia deixa de informar: o dono passaria a aprovar "degradada" toda semana sem que a palavra distinguisse nada.

Mantive o estado intocado e a limitação declarada, porque é a opção que preserva o poder de sinalização do estado. **Mas é decisão de regra, não de código**, e fica aqui para o dono. Achado do `revisor-de-codigo`.

## D-021 — a janela de destaque fecha quando o imóvel SAI da carga

**Data**: 2026-09-01 · **Resolve**: Spec §2.1 define os campos da `janela_destaque` ("início e fim = datas de entrada e saída da vitrine") mas nenhum documento diz quem observa a saída, nem quando a janela fecha.

**Decisão do dono: a janela fica ABERTA enquanto o imóvel continuar aparecendo nas cargas aprovadas.** A cada carga em que ele permanece, a janela acumula os leads do período e incrementa `semanas_consecutivas`. Ela FECHA quando uma carga aprovada nova não o traz mais; `fim` é a data dessa carga.

**Por quê:** é o que casa com o dado histórico — a janela média durou **33 dias** contra 7 dias de ciclo de carga (PRD), ou seja, imóveis costumam permanecer por várias cargas seguidas. **Ressalva sobre a força desse número:** ele vem de `adsrealtyextra_historic`, que o `mapa-de-dados.md` registra como MORTA desde 27/06/2023 — descreve um histórico congelado há três anos, não o estoque vivo. A procedência é o PRD, não é número inventado; mas o argumento é mais fraco do que parece, e a regra deve ser revista quando houver histórico próprio no Registro (que esta fatia começa a produzir). E é a única leitura que dá sentido a `semanas_consecutivas`, campo que a Spec §2.1 exige e que só existe se a janela atravessa semanas: sob a alternativa (uma janela por ciclo) ele seria sempre 1.

**Consequência para a penalidade §6.4:** a janela julgada é o período INTEIRO de exposição, não a última semana. Um imóvel que ficou 21 dias na vitrine é julgado pelos leads dos 21 dias — sob a alternativa, seria julgado pelos 7 últimos, ignorando a exposição real que o contrato pagou.

## D-022 — "resultado esperado para o nível" é parâmetro pendente nº 14

**Data**: 2026-09-01 · **Resolve**: Spec §6.4 penaliza a janela que "não atingiu o resultado esperado **para o nível**", e nenhum documento quantifica isso.

O `src/dominio/penalidades.py` já se recusava a inventar o limiar — `atingiu_resultado` chega pré-calculado, "pela camada que o dono da decisão vier a definir". Esta decisão nomeia a camada e o parâmetro.

**Decisão do dono: o limiar entra na tabela de parâmetros pendentes como nº 14**, com **dois valores** (super destaque e destaque, porque a §6.4 diz "para o nível"), declarados no arquivo TOML da rodada como os demais. Fica **nulo** até o dono o definir.

**Enquanto nulo:** o histórico de janelas é gravado normalmente — `semanas_consecutivas` e leads acumulados passam a funcionar, fechando a D-020 —, mas a penalidade não incide e a rodada **declara** "limiar de resultado não definido" na planilha. Nunca 0,0 silencioso: um imóvel sem penalidade por falta de limiar não é um imóvel que passou no critério.

**Descartado: "pelo menos 1 lead", igual nos dois níveis.** Tem apoio descritivo no PRD ("12% das janelas históricas geraram ao menos um lead"), mas diverge da §6.4 ao julgar super destaque e destaque pela mesma régua, e penalizaria **88%** da base — uma penalidade quase universal perde o poder de discriminar que a §6.4 lhe atribui.

### Elaborações e divergências da D-021, declaradas (2026-09-01)

Os portões levantaram quatro casos que a D-021 não cobre e que o código teve de resolver. Ficam aqui em vez de dentro do código, porque cada um é regra.

**1. Mudança de nível fecha a janela e abre outra.** **RATIFICADO pelo dono em 2026-09-02.** Muda o insumo da §6.4, e o precedente para leitura estrutural que altera quem é penalizado é levar ao dono (D-009, D-015). Custo aceito e declarado: o imóvel promovido perde o acumulado da janela anterior, porque cada janela passa a ser julgada pela régua do seu próprio nível — uma janela que atravessasse os dois não teria régua nenhuma. O documento decide quando a janela abre e fecha, não o que fazer quando o imóvel permanece na carga mas muda de destaque para super destaque. A primeira implementação congelava o nível da abertura — e como a §6.4 julga "o resultado esperado **para o nível**" e o nº 14 tem um valor por nível, uma janela que atravessasse os dois seria julgada pela régua errada, em silêncio. Adotado: a mudança de nível encerra a janela e abre uma nova, pela mesma razão que sair e voltar gera janela nova — são exposições distintas, com expectativas distintas.

**2. A unidade de acumulação é a CARGA.** A guarda de idempotência é `ultima_rodada_decisao_id`, não a rodada de acompanhamento. Não é detalhe de implementação: chaveada pela execução, a guarda não guardaria nada (cada reexecução abre uma rodada nova, com id novo) e duas segundas medindo a mesma carga contariam duas semanas para uma carga só. É a letra da D-021 — "a cada **carga** em que ele permanece".

**3. Carga retroativa é recusada.** Rodar uma segunda antiga depois de uma nova sobrescreveria histórico mais novo com dado mais velho. Recusado com mensagem própria, em vez de deixar o CHECK do banco derrubar a transação inteira com uma violação que não diz a causa.

**4. `ciclo`, para o decaimento da penalidade, é uma carga APROVADA.** **RATIFICADO pelo dono em 2026-09-02.** A alternativa — contar toda sexta que rodou — faria a penalidade enfraquecer por semanas em que nada foi ao ar e o imóvel não teve chance nenhuma de gerar lead. Nenhum documento define "ciclo"; o contrato de `JanelaAnterior` diz "rodada de decisão completa". Adotado: conta só rodada de decisão **aprovada** (D-001: carga vigente é a aprovada), porque uma sexta abortada ou não aprovada não expôs imóvel nenhum, e fazer o decaimento avançar por ela contaria um ciclo que não aconteceu.

### Duas limitações do acúmulo, declaradas na planilha da segunda

- **Os leads da janela são AMOSTRA, não total.** A segunda mede três dias corridos (Spec §1) sobre um ciclo de carga de sete, então parte da exposição nunca é contada — e a Spec §2.1 pede "acumulado durante a janela". Quando o limiar nº 14 existir, a janela será julgada por um número subestimado, o que **penaliza a mais**. Fechar isso exige contar os leads do intervalo inteiro: fatia própria.
- **A contagem de semanas começa agora.** Um imóvel que já está na vitrine há semanas aparece com poucas — é o que o Registro sabe, não o que aconteceu. A D-020 previa colunas vazias que se preenchem; um "1" tem aparência de medição e por isso a limitação vai declarada.

### [P-02] Divergência de ordem também na SEGUNDA (Registro antes do Redator)

Já estava declarada para a sexta. Vale igual para a segunda: o PRD põe o Redator no passo 4 e o Registro no passo 5, e o código grava primeiro (o histórico da janela só existe depois de acumular, e é ele que preenche as duas colunas da §4.3). Há uma tensão interna no próprio PRD aqui — sob leitura estrita, o Redator do passo 4 jamais teria colunas que o passo 5 produz. O código escolheu a leitura que salva a §4.3. **Vai ao dono junto com a pergunta da sexta.**

### Reaberta: limitação de fiação deve mudar o ESTADO da rodada?

O argumento que sustentou "não" era explicitamente temporal: marcá-las como degradação tornaria toda rodada degradada **até o produtor de `janela_destaque` existir**, e um estado que nunca varia deixa de informar. **O produtor existe agora.** Quando o consumidor da sexta for ligado, a limitação passa a ser variável — some sozinha quando houver janelas encerradas — e o argumento cai. A pergunta volta ao dono na fatia do consumidor, com esse fato novo.

## Consumidor das janelas na sexta (2026-09-02) — a §6.4 passa a incidir

A fatia anterior deu produtor a `registro.janela_destaque`; esta liga o **consumidor**. A penalidade "janela anterior sem resultado" (Spec §6.4), inerte desde sempre, passa a incidir.

**Onde a leitura acontece, e por quê.** No nó do **Decisor**, não no Coletor Interno. A Spec §5 é explícita: "o Decisor é o único agente que lê o Registro durante a rodada, e o faz para obter o histórico de janelas necessário ao cálculo da penalidade". O Coletor Interno continua lendo só o Newcore e devolvendo `janelas_anteriores=()`; a costura é do Decisor.

**Ler e julgar são separados.** O nó **sempre lê** (se a fonte estiver fiada) e só **julga** quando o limiar por nível existir. A razão é de diagnóstico: sem a separação, "o Registro não devolveu janela nenhuma" e "há histórico, mas o nº 14 é nulo" sairiam idênticos na planilha — e as duas zeram a penalidade por motivos **opostos**, com correções opostas. Só a segunda está sob controle do dono. O estado da rodada passa a carregar `janelas_lidas`, e a planilha declara as duas limitações separadamente.

**O limiar é injetado, nunca constante.** `julgar_janelas` é função pura do domínio e recebe o mapa por nível como argumento obrigatório; nível ausente no mapa é **erro**, não default — usar a régua de outro nível é exatamente o que a §6.4 proíbe ao dizer "para o nível". Nenhum valor de parâmetro pendente entrou em `src/config` ou no domínio.

**Ainda inerte na prática, por um motivo declarado:** o nº 14 continua nulo, então nenhuma janela é julgada hoje. O que mudou é que a fiação existe e a planilha diz **qual** das duas coisas falta. No dia em que o dono declarar os dois limiares no arquivo da rodada, a penalidade acende sem mais nenhuma mudança de código.

### Perguntas que o consumidor levantou (2026-09-02) — as duas primeiras RESOLVIDAS pela D-023

Ligar a penalidade tornou vivas quatro questões que estavam dormentes. Nenhuma bloqueia a fatia — o nº 14 segue nulo —, mas todas mudam quem é penalizado quando ele for declarado.

**1. ~~A §6.4 julga a ÚLTIMA janela ou QUALQUER janela do histórico?~~ RESOLVIDA pela D-023 (só a última).** *(o texto abaixo descreve o estado ANTERIOR à decisão; fica como registro histórico)* O código aplica a penalidade se *alguma* janela encerrada não atingiu o resultado (`any(...)` em `penalidades.py`), sem recorte temporal. O PRD, no critério de aceite, fala em "o resultado da **sua última janela**, quando houver", e a Spec §6.4 usa o singular "janela **anterior**". Sob o código, uma janela ruim de um ano atrás penaliza para sempre — e com decaimento de razão 1.0, sem nunca esmaecer. **Agrava-se com a elaboração 1 da D-021, que o dono acabou de ratificar**: a mudança de nível fecha a janela, então a promoção a super destaque cria uma janela curta que quase certamente não bate o limiar e passaria a penalizar indefinidamente justo o imóvel que subiu por mérito. A leitura `any` estava declarada só no código; agora está aqui. ~~Vai ao dono.~~ **Respondida — ver D-023 abaixo.**

**2. ~~Falha ao ler o Registro derruba a rodada.~~ RESOLVIDA pela D-023 (degrada e entrega).** *(o texto abaixo descreve o estado ANTERIOR à decisão; fica como registro histórico)* A leitura acontece no nó do Decisor; qualquer exceção propaga e a sexta não entrega. A Spec §7.2 só prevê ABORTADA para "a coleta interna não ficou pronta", e a linha de DEGRADADA — "alguma fonte falhou e a decisão prosseguiu com dado parcial" — descreve exatamente este caso. O vocabulário para degradar já existe ("HISTÓRICO DE JANELAS vazio"). Hoje aborta por omissão, não por decisão. ~~Vai ao dono.~~ **Respondida — ver D-023 abaixo.**

**3. [P-07] O imóvel que nunca sai da carga nunca é julgado.** Só janelas ENCERRADAS são julgáveis (contrato de `ImovelPenalizavel`, e a §6.4 diz "janela anterior"). Mas sob a D-021 a janela só fecha quando o imóvel sai ou muda de nível — então o permanente-sem-lead, que é o caso que abre o PRD (88% das janelas sem lead, "a vitrine não gira"), é justamente o que a §6.4 nunca alcança. Não afirmo que o documento esteja errado; registro a suspeita. **Vai ao dono.**

**4. [P-03] Reaberta de fato: limitação de fiação deve mudar o ESTADO da rodada?** A fatia anterior prometeu reabrir esta pergunta "na fatia do consumidor, com o fato novo" e a seção anterior não o fez — ficou fechada por omissão. Reabro aqui: o argumento original era temporal ("tornaria toda rodada degradada até o produtor existir"), e agora produtor e consumidor existem. A limitação de histórico vazio passou a ser **variável** — some quando houver janela encerrada. **Vai ao dono.**

**5. Declarado, não perguntado:** `ciclos_desde` deriva a data no fuso da máquina que roda. A hospedagem é uma máquina só, então o risco é baixo, mas a mesma entrada em outra máquina pode dar ciclos diferentes. Fica registrado como limitação, não como pergunta.

## D-023 — a §6.4 julga a ÚLTIMA janela, e Registro fora DEGRADA em vez de abortar

**Data**: 2026-09-02 · **Resolve**: as duas perguntas 1 e 2 da seção anterior, respondidas pelo dono.

### Qual janela é julgada

**Decisão do dono: só a ÚLTIMA.** O código aplicava a penalidade se *qualquer* janela encerrada tivesse falhado, sem recorte temporal. O PRD descreve outra coisa — "o resultado da **sua última janela**, quando houver" — e a Spec §6.4 usa o singular "janela **anterior**".

**O que motivou:** sob a regra antiga, uma janela ruim de um ano atrás penalizava para sempre, e com decaimento de razão 1.0 nunca esmaecia. Pior em combinação com a D-021, que o dono ratificou na fatia anterior: a promoção de nível fecha a janela, então subir para super destaque criava uma janela curta de destaque que quase nunca bate o limiar — e passaria a penalizar indefinidamente **justo o imóvel que subiu por mérito**.

**Custo aceito e declarado:** um imóvel com histórico ruim longo "limpa a ficha" com uma única janela boa. O dono viu o trade-off e escolheu o desempenho recente.

**Duas precisões da implementação, declaradas:** "mais recente" é o MENOR `ciclos_desde_encerramento`, não a posição na lista — a ordem vem do chamador e não pode governar a regra (invariante 5). E empate de ciclos é desempatado pelo veredito: a que FALHOU vence.

**Correção de uma justificativa que eu tinha escrito errado:** disse que o empate "é o que a mudança de nível produz". Não é — o produtor da D-021 fecha no máximo uma janela por imóvel por carga, então duas encerradas têm sempre `fim` distintos, e como todo `fim` é data de carga aprovada a contagem de ciclos as separa por pelo menos 1. **O empate é hoje inalcançável.** O desempate existe porque a função precisa ser total e a regra não pode passar a depender da ordem da lista se alguma premissa mudar. Registro a correção porque uma justificativa falsa num registro de decisão é pior que nenhuma: o dono decide de novo em cima dela.

Efeito colateral bom: `penalidades_aplicaveis` e `ciclos_desde_janela_sem_resultado` passam a olhar a MESMA janela. Antes divergiam — o predicado olhava qualquer uma, o desconto a mais recente sem resultado — e coincidiam só porque o desconto se aplica uma vez.

### Registro indisponível na rodada de sexta

**Decisão do dono: DEGRADA e entrega.** Antes, uma falha ao ler o Registro derrubava a rodada inteira: nenhuma planilha, semana sem vitrine, por causa de **uma** das três penalidades. A Spec §7.2 descreve exatamente este caso — "alguma fonte falhou e a decisão prosseguiu com dado parcial" — e nenhum documento sancionava o aborto, que acontecia por omissão.

A etapa `janelas` entrou em `ETAPAS_PARA_COMPLETA`: sem o histórico a rodada é honestamente DEGRADADA, com o motivo declarado (só o TIPO da exceção, nunca a mensagem, que pode ecoar dado do banco). Sem a etapa na lista, uma rodada cujo Registro caiu sairia COMPLETA com a penalidade silenciosamente inerte.

### Ainda abertas, não resolvidas aqui

As perguntas 3 (o imóvel que nunca sai da carga nunca é julgado) e 4 (limitação de fiação deve mudar o estado da rodada) seguem com o dono, e a 3 mudou de peso com esta decisão: **com "só a última janela", o alcance da §6.4 encolheu**. Antes, o histórico antigo ainda alcançava alguém; agora o imóvel que nunca sai não tem janela encerrada, e o que ele fez em exposições passadas também deixou de contar. A pergunta ficou MAIS relevante depois da D-023, não menos.

Atualização da limitação de fuso registrada antes: desde a D-023, `ciclos_desde` não governa só o decaimento — governa **qual janela é julgada**. Um fuso trocado deixou de significar "decaimento deslocado em um" e passou a poder trocar a janela eleita, mudando quem é penalizado. A decisão de não fixar o fuso no código continua (a hospedagem é uma máquina só, e fixá-lo seria escolher um valor que ninguém definiu), mas o risco é maior do que o texto anterior dizia.

## Carimbo de aprovação: o elo entre a sexta e a segunda (2026-09-02)

O mecanismo de aprovação existia inteiro e testado desde a G2b/G3 — grafo com interrupção que sobrevive a reinício de processo, e `marcar_aprovada` no Registro. **Faltava chamador**: nenhum arquivo do repositório invocava `construir_grafo_aprovacao` fora dos testes. O efeito era silencioso e total: `ultima_carga_aprovada` filtra por `aprovada_em IS NOT NULL`, então enquanto ninguém carimbasse, **toda** rodada de segunda declararia ausência de carga e sairia pelo código de "insumo ausente", que o agendador trata como no-op benigno. A cadência semanal que a D-021 fechou no papel não fechava na prática.

`executar/aprovar.py` é esse chamador. Nenhuma regra de decisão vive nele. As escolhas abaixo são **elaborações declaradas**, não decisões novas do dono — cada uma protege um significado que os documentos já fixaram.

**1. O carimbo é único: re-carimbar é recusado.** Nenhum documento diz "não sobrescreva", porque nenhum documento imaginou que se pudesse. Mas `aprovada_em` carrega dois papéis: é o início da janela de três dias que a segunda mede (Spec §1, via `janela_da_carga`) e é a chave que elege a carga vigente (`ORDER BY aprovada_em DESC`). Sobrescrevê-lo desloca a medição e pode promover uma decisão velha a carga vigente — sem rastro, porque o esquema não guarda o carimbo anterior.

O caminho que produz o carimbo duplo é concreto, não hipotético: reinvocar o grafo com o mesmo `rodada_id` numa thread **já concluída** não é no-op — o LangGraph reinicia do começo, reabre a interrupção, e a retomada seguinte chama o sink outra vez. Verificado, não deduzido. A guarda é dupla: no ponto de entrada (lendo o Registro antes de tocar o grafo) e em `marcar_aprovada` (`aprovada_em IS NULL` no WHERE), que é a que vale quando o chamador for outro — o console, um agendador.

**2. Aprovar fora de ordem é recusado por default, com escape declarado — e são DUAS recusas, não uma.** A eleição da carga vigente é por `(aprovada_em, id)` (`ultima_carga_aprovada`: `ORDER BY aprovada_em DESC, id DESC`), não por id. Logo há dois jeitos opostos de errar a ordem, e ambos fazem a segunda medir a lista errada:

- aprovar uma rodada **antiga** havendo outra mais nova já aprovada — o carimbo novo promove a velha a vigente;
- carimbar uma rodada **nova** num instante ANTERIOR a um carimbo já existente — a lista nova é aprovada e a vigente continua sendo a outra, em silêncio.

A segunda só é alcançável por causa do `--em` desta mesma fatia, e a primeira versão da guarda não a pegava: ela comparava **ids**, e por id o caso passa (12 > 11). Achado pelo portão de regra. `--fora-de-ordem` libera as duas, e a mensagem diz qual é o caso e o que vai acontecer. Sem as recusas, o caminho destrutivo seria o default silencioso.

**3. O instante do carimbo é o da CARGA, não o do clique.** `aprovada_em` é o proxy que o sistema tem para "a carga entrou no ar" — a carga é manual e o sistema não publica nada (cabeçalho de `registro/janelas.py`). Aprovar na segunda uma carga aplicada na sexta, carimbando "agora", deslocaria em três dias a janela que a segunda mede, sem nada acusar. `--em` deixa declarar o instante real; o default continua sendo agora. Instante no futuro é recusado, e anterior ao fim da própria rodada também — a carga não pode ter entrado no ar antes de a lista existir.

**4. Só rodada `completa` ou `degradada` é aprovável.** É exatamente o filtro que o console usa hoje para montar a fila de pendentes — `console/lib/registro.ts::rodadasAguardandoAprovacao`, `WHERE tipo = 'decisao' AND aprovada_em IS NULL AND estado IN ('completa','degradada')` — então ele nunca oferece um cartão que o comando recusa.

**Declarado: a recusa de ABORTADA é hoje inalcançável pelo caminho de produção.** O nó de persistência do grafo só grava rodadas não-abortadas (consequência de persistência registrada na G2a-wire), então uma rodada abortada não deixa nem o cabeçalho `rodada` — não há id para aprovar. O teste só alcança o caso com `INSERT` direto. A guarda existe porque a pendência do dono sobre gravar cabeçalho de abortada segue aberta e porque `estado` é `NULL`-ável no DDL; o motivo — aprovar uma abortada criaria carga vigente sem imóvel nenhum, e a segunda mediria contra ela — vale para o dia em que o cabeçalho passar a ser gravado. Registro o alcance junto com a guarda, seguindo o precedente da D-023, para não parecer que o cenário é corrente.

**5. Aprovação tácita: o mecanismo existe, o prazo não.** O comando `tacita` grava `aprovada_por = "tácita"`, o "por prazo" da D-001. **Nada aqui calcula prazo**: o parâmetro nº 10 segue nulo, e quem invoca o comando está AFIRMANDO que o prazo decorreu. O carimbo distingue essa afirmação de uma aprovação que o dono deu olhando a lista — que é a razão de a coluna `aprovada_por` existir (migração 004).

### [P-04] Pergunta ao dono — a reprovação não é representável

`grafo/aprovacao.py` sabe representar um veredito de reprovação, mas `registro.rodada` **não a distingue de "ainda não decidida"**: as duas deixam `aprovada_em` nulo. Por isso o comando `reprovar` NÃO foi exposto — expô-lo daria ao dono a sensação de ter agido, enquanto o console continuaria mostrando "Aprove a rodada N" para sempre e a thread ficaria queimada.

Isso deixa um buraco real, e a formulação precisa importa. **No sistema como está, o silêncio NÃO aprova**: sem carimbo, `ultima_carga_aprovada` devolve `None` e a rodada de segunda declara ausência de carga. Ou seja, hoje o silêncio já é a recusa efetiva — o que falta não é poder recusar, é poder **registrar** a recusa, distinguindo "o dono disse não" de "ninguém olhou".

**E isso é uma divergência com Ferramentas §4, que passo a declarar em vez de deixar implícita.** O documento fixa o default oposto: "se a planilha não for alterada até um horário definido, ela é considerada aprovada como saiu". No sistema, o default é o contrário — nada acontece sem alguém carimbar. A inversão é forçada pelo parâmetro nº 10 (prazo da aprovação tácita) ser **nulo**: aprovar sozinho por decurso de prazo exigiria um prazo que ninguém definiu, e inventá-lo é o que este projeto não faz. É a escolha segura (a carga não é aplicada sem decisão humana), mas é divergência com documento e agora está escrita como tal. Declarado o nº 10, o comando `tacita` é o mecanismo pronto para restaurar o default do documento.

Resolver o registro do "não" exige coluna de estado no esquema (uma migração) e uma decisão sobre o que a reprovação significa para a semana seguinte: a sexta seguinte reprocessa a mesma semana? A lista reprovada some da fila do console? **Vai ao dono.**

### [P-05] Pergunta ao dono — `aprovada_em` registra o ACEITE ou a entrada da carga no ar?

O `--em` desta fatia expôs uma ambiguidade que já existia e ninguém tinha precisado resolver. Os documentos puxam para os dois lados:

- **aceite**: a D-001 descreve o carimbo como "aprovada em ⟨momento⟩, por prazo", e Ferramentas §4 diz que o prazo "registra o aceite";
- **entrada no ar**: Spec §1 ancora a janela de três dias na **aplicação da carga**, e o PRD fala em "leads entrados desde a carga de sexta". Estes são hierarquicamente superiores.

Hoje o campo é único e serve aos dois usos: `janelas.py` já o tratava como "o melhor proxy" para a entrada no ar, com o resíduo declarado. O `--em` deixa o dono **absorver** esse resíduo — e ao fazê-lo, o instante do aceite deixa de existir no Registro, que a D-001 chama de fonte da verdade. As duas leituras fiéis são: coluna nova para a aplicação da carga, com `aprovada_em` preservando o aceite; ou emenda à D-001 redefinindo o campo. **Vai ao dono.** Enquanto não decidido, o `--em` é opcional e o default (`agora`) preserva o comportamento anterior.

### [P-06] Pergunta ao dono — a aprovação tácita deve registrar quem a invocou?

`aprovar` exige `--por`; `tacita` grava só `aprovada_por = "tácita"`. Como nada calcula o prazo (nº 10 nulo), a tácita é hoje uma **afirmação humana sem autor** no Registro. Ferramentas §5 já cataloga o risco de o Registro afirmar aprovação não dada, então não é violação — mas enquanto o prazo for nulo, quem invocou a tácita é informação que existe e não está sendo guardada. **Vai ao dono.**

### Declarado, não perguntado — o veredito digitado tem de ser o que vale

O grafo de aprovação tem QUATRO estados, não três, e a diferença é de correção. Além de "inexistente", "aguardando o dono" e "concluída", existe **"travada no `aplicar`"**: o veredito já foi consumido e o sink levantou. Classificar por "tem próximo nó" — que era o que o ponto de entrada fazia — colapsa a travada com a aguardando, e nela o `Command(resume=...)` **não é consumido**, porque não há interrupção pendente: o nó roda de novo com o veredito ANTERIOR.

O efeito medido: a aprovação tácita falha no sink, o dono roda `aprovar --por olavo`, e o Registro grava `aprovada_por = "tácita"`, com saída 0. Na direção oposta é pior — atribui a uma **pessoa** uma aprovação que ela não deu naquele momento. É exatamente o campo que a D-001 criou para distinguir a tácita da explícita, e exatamente a classe de falha silenciosa que motivou esta fatia. A classificação passa a ser por interrupção pendente, e uma thread já decidida sem carimbo é recusada com código próprio (`9`) em vez de reaplicar o veredito antigo. `--refazer` é a saída: descarta a thread e decide de novo, e só age quando o Registro não tem carimbo.

### Declarado, não perguntado — o impasse dos dois usos do mesmo Postgres

O projeto usa **um único** PostgreSQL para o Registro e para o checkpointer do grafo, por desenho. O `setup()` do `PostgresSaver` roda `CREATE INDEX CONCURRENTLY`, que espera **toda** transação concorrente do banco terminar. Com a conexão do Registro já aberta, o índice espera por ela, ela espera o grafo terminar, e o comando trava para sempre — sem erro, sem timeout. Aconteceu de verdade, e só apareceu ao simular o passo de CI: nenhum teste com checkpointer em memória o alcança, porque o impasse é entre duas conexões do mesmo Postgres.

A correção é de ordem — o checkpointer nasce antes de a conexão do Registro abrir — e tem teste próprio, porque a ordem aqui é correção e não estilo. Fica registrado porque **qualquer fatia futura que abra o checkpointer dentro de uma transação do Registro reintroduz o impasse**, e o sintoma não se parece com um bug de código.

## Pendências que existiam sem registro próprio (2026-09-02)

Ao consolidar a fila do dono (`docs/perguntas-abertas.md`) apareceram itens que **já aguardavam o dono** mas viviam só num comentário de código ou numa tabela de outro documento — sem entrada aqui, e portanto invisíveis para quem lesse este arquivo. *(Precisão apontada pelo portão de regra: em [P-10] e [P-11] o que pré-existe é a ESCOLHA já fechada em Ferramentas §2 e o ônus assumido em §5 — não um registro de que algo estivesse pendente. O fato e o ato que restam são derivados dela, e formulados aqui pela primeira vez; nenhuma regra nova nasce disso.)* Nenhum item abaixo é pendência nova: cada um recebe identificador estável e aponta para onde já vivia. **Nenhum enunciado normativo é criado ou alterado aqui.**

**[P-08] O "pronto" do Monitor olha só o corretor, e o PRD fala em corretor E gestor de distrito.** `src/grafo/segunda.py:59-62` e `:164-168`: o predicado que declara o Monitor pronto considera apenas o corretor gestor. Um lead sem tratamento que tenha corretor mas nenhum embaixador de distrito conta hoje como "com responsável". Mesma família da D-019, que já resolveu o que é "gestor de distrito". **Vai ao dono.**

**[P-09] "Não há carga aprovada" na segunda é chamado de rodada ABORTADA.** `src/grafo/segunda.py:55-58`: reuso declarado do estado — a consequência casa com a Spec §7.2 ("não há entrega"), mas o gatilho não está previsto lá. É a mesma questão de vocabulário do [P-01], e pode ser respondida junto. **Vai ao dono.**

**[P-10] A conta Google do gestor é Workspace ou pessoal?** Não é decisão: `docs/vitrine-destaque-ferramentas.md` já **fechou** "Acesso ao Google: autorização na conta do gestor da vitrine", e o mesmo documento já assumiu o ônus dessa escolha ("quebra se a conta mudar de senha ou sair da organização"). O que falta é o **fato**, que só o dono tem, e que determina o fluxo de autorização. **Fato, não decisão.**

**[P-11] A autorização na conta e o depósito da credencial no 1Password.** Decorre da escolha já fechada acima. Enquanto não acontecer, a entrega é CSV em disco — não a planilha do Google com link por e-mail que o contrato prevê. **Ato que só o dono pratica.**

**[P-12] A sessão logada no Canal Pro para o reconhecimento do painel.** `coletor-externo/README.md` e D-010: o adapter do Canal Pro é stub. Sem a sessão, o fator de desempenho de portal (F3) nunca sai de zero e **toda rodada de sexta é degradada nesse fator**. Pela D-010, o reaquecimento após bloqueio é sempre manual — é ato recorrente, não único. **Ato que só o dono pratica.**

**[P-13] Quem aplica a carga encontra o imóvel só pelo código interno?** `docs/mapa-de-dados.md` e Spec §8: a investigação foi **refutada no banco** — não existe id nem URL de anúncio do portal em nenhuma tabela, e a listagem do Canal Pro não traz a URL pública. Se quem carrega precisar de outra referência, a planilha entregue não é aplicável na prática. É a única das quatro investigações da Spec §8 que segue aberta. **Fato, não decisão.**

**[P-14] Qual provedor comercial de modelo o sistema usa.** `docs/vitrine-destaque-ferramentas.md` deixa a escolha em aberto, com critério já definido (qualidade em navegação por visão contra o portal real). Não bloqueia nada hoje — o Redator é template, o Analista de Perfil é determinístico e a D-010 tirou o modelo do Coletor Externo. Bloqueia a camada consultiva do crivo prevista na D-017. **Escolha de ferramenta, com custo recorrente.**

### Lacuna de especificação declarada — o mecanismo de Drive e e-mail

`docs/vitrine-destaque-spec.md` §9 ("O que esta spec não cobre") lista literalmente: *"Mecanismo de envio por e-mail e de arquivamento no Drive."* A Ferramentas diz o **quê** (planilha do Google no Drive, link por e-mail) e nenhum documento diz o **como**.

Isso **não é pendência do dono** e não entra na fila dele: é lacuna de especificação. Registro aqui porque ela tem consequência de engenharia imediata — o adaptador de publicação não tem critério de pronto contra o qual ser construído nem verificado, e este projeto não escreve peça que não possa provar. Some quando a spec for estendida, o que é trabalho meu, não decisão dele. Os itens [P-10] e [P-11] são o que resta do lado do dono.

## Bloqueio de credencial encontrado ao medir as referências (2026-09-02)

**[P-17] As credenciais do Newcore no 1Password são recusadas pelo servidor, e `POSTGRES_URL` não existe no item.** Ao construir a medição reprodutível dos números de referência, a conexão ao MySQL do Newcore falhou com `Access denied` usando exatamente os valores do item `op://Personal/orquestrador_portais`. Caracterizado: o TCP alcança a instância (porta 3306 aceita), então **é recusa de autenticação, não bloqueio de rede** — senha girada no servidor, ou concessão restrita por host de origem. No mesmo dia, mais cedo nesta sessão, a mesma leitura funcionou; o erro nomeia o host do cliente, o que aponta para o IP de origem ter mudado.

Separadamente, o item do cofre **não tem `POSTGRES_URL`**, embora o `.env.tmpl` a declare — logo `op inject -i .env.tmpl -o .env` não produz um `.env` completo, e nada que dependa do Registro (aprovação, janelas, console) roda na máquina do gestor.

**O que está bloqueado — atualizado em 2026-09-02, depois de o dono destravar o acesso.** A metade do MySQL caiu: a credencial existe e funciona (veio da configuração do MCP de MySQL, não do cofre), e **a medição contra a base foi executada** — a ferramenta rodou ponta a ponta e reproduziu a deriva por caminho independente do portão de números (7.803 elegíveis contra 7.801, duas horas antes). Isso fechou o risco residual de a ferramenta nunca ter tocado o banco.

**O que permanece:** o item do cofre continua errado. O campo `NEWCORE_MYSQL_PASSWORD` guarda uma **linha de comando** (uma referência a outro item), não a senha — então `op inject -i .env.tmpl -o .env` não produz um `.env` utilizável. E `POSTGRES_URL` segue **ausente** do item, embora o template a declare, então nada ligado ao Registro roda sem rodeio. Enquanto isso durar, a credencial de produção vive em texto claro em dois arquivos de configuração de MCP, contra a convenção do próprio projeto (`${VAR}` do ambiente, nunca no arquivo) — três cópias e nenhuma fonte da verdade.

A recontagem noutro dia, que a incorporação da deriva exige, deixou de estar bloqueada por credencial e passou a ser só questão de calendário.

**Adendo 2026-09-02 — o diagnóstico acima estava errado, e a causa real era outra.** Ao construir o console, o `op inject` foi medido em vez de suposto, e as duas afirmações do parágrafo anterior caem:

- **O campo `NEWCORE_MYSQL_PASSWORD` não guarda linha de comando.** Guarda senha, e ela **funciona**: com o `.env` gerado, a conexão de leitura ao Newcore respondeu (405.053 linhas no espelho, 48.881 ativos, medido em 02/09). O defeito registrado não corresponde ao que está no cofre — ou foi consertado pelo dono sem o registro acompanhar.
- **`POSTGRES_URL` não precisava estar no cofre.** O Postgres próprio roda na máquina do gestor por decisão de hospedagem, e a forma `postgresql:///banco` usa o socket local com a autenticação do usuário do sistema: **não carrega usuário, senha nem host**. Não havia credencial a proteger, e uma referência de cofre para endereço local seria indireção sem proteção. Passou a ser literal no template.

**A causa real do `op inject` falhar era o próprio template.** Ele declarava **três** referências para campos inexistentes no item: `POSTGRES_URL`, `CANALPRO_USER` e `CANALPRO_PASSWORD`. O `op inject` falha **inteiro** quando uma só falta, então o sintoma ("não produz um `.env` utilizável") nunca foi do cofre — era do arquivo versionado. As duas do Canal Pro eram resíduo anterior à **D-010**, que adotou login manual: contradiziam a decisão e nenhuma linha de código as lia.

**Armadilha achada no caminho, e vale registrar porque custou uma execução:** o `op inject` varre o arquivo inteiro, **comentário inclusive**. Explicar em prosa o formato de uma referência de cofre, mesmo dentro de crase, faz o comando abortar com `invalid secret reference`. O `.env.tmpl` agora declara essa regra no próprio cabeçalho.

**O que sobra do [P-17]:** só a metade que este trabalho não alcança — a credencial de produção em texto claro em arquivos de configuração de MCP, fora deste repositório. Some a menção ao cofre e ao `op inject`, que deixaram de ser verdade.

**Ato que só o dono pratica.** Não é decisão nem defeito de código: é conserto de cofre e de acesso.

**Adendo 2026-09-02 — o [P-17] mudou de natureza: deixou de ser higiene de cofre e passou a exigir ROTAÇÃO.** A varredura que precedeu esta fatia achou, no repositório **público**, cinco pontos que descrevem a senha viva: `docs/mapa-de-dados.md` nomeava o caractere não-ASCII em duas frases e, mais adiante, descrevia uma **segunda** propriedade do mesmo segredo, de outra classe de caracteres; `CHANGELOG.md` e o docstring de `src/dados/newcore.py` repetiam o primeiro. O mesmo trecho publicava a identidade da conta de leitura. A **prosa** foi limpa nesta fatia, **e isso não resolve** — por duas razões que precisam ficar escritas, porque a primeira eu afirmei errado antes de medir.

**Primeira: a árvore não ficou limpa.** Os quatro literais continuam versionados, em `LITERAIS` de `tests/test_sem_vazamento_de_credencial.py`, por necessidade da guarda — sem eles não há detecção de revert exato. A varredura que eu dei por limpa usara `git ls-files`, que não enxerga arquivo ainda não adicionado; era artefato de medição, não limpeza. A exposição desses quatro fica **igual** à de hoje, não pior, e depois da rotação eles ficam inertes.

**Segunda: um sexto vetor, que edição nenhuma alcança.** A **mensagem do commit** que fundou o Coletor Interno (31/08) carrega o mesmo fato no corpo. Mensagem de commit não é tocada por edição de árvore de trabalho: fica no log, na página do commit e em todo clone. Some apenas com reescrita de histórico — que reduz visibilidade casual e **não** desfaz clones já feitos, e por isso não substitui a rotação.

Só a troca da senha invalida o que já saiu.

O agravante é de composição, não de um item isolado. Somando o que o repositório dava de graça — identidade da conta, mais de um caractere da senha e uma nota de infraestrutura sobre transporte — o espaço de busca de uma credencial de produção viva encolheu por escrito. Nenhum desses fatos era necessário: em todos os cinco casos a **mecânica** (senha não-ASCII quebra o pymysql; o shell expande metacaractere ao carregar o `.env`) documenta a manutenção igual ou melhor, porque vale para qualquer senha e sobrevive à própria rotação.

**Por que nenhuma ferramenta pegou.** O gitleaks casa **padrão de segredo** — chave, token, DSN. Prosa que **descreve** o segredo não casa com padrão nenhum e passa intacta, sem que nada avise. O portão de regra olha para a Spec, não para isto. O filtro, nas duas vezes em que o material veio de relatório de investigação, era humano — e na segunda vez falhou: em 02/09 um caractere foi copiado de relatório para o documento e só a revisão o barrou. Substituído por guarda que executa: `tests/test_sem_vazamento_de_credencial.py` varre todo arquivo versionado e reprova tanto os literais já vazados quanto a **forma** do vazamento — qualquer afirmação sobre o conteúdo do segredo, e notação de ponto de código na vizinhança da palavra —, com contraprova contra passar por vacuidade. Verificado por mutação em quatro direções, inclusive um vazamento de forma nova sem nenhum literal conhecido.

**Regra que fica, para importação de relatório de investigação:** relatório de subagente é insumo, não texto pronto. O que descreve credencial — conteúdo, identidade da conta, host, política de transporte — não atravessa para documento versionado; atravessa a mecânica. A guarda impõe a parte automatizável; o resto é a regra escrita aqui.

## A checklist de critérios de aceite do PRD passa a ser mantida viva (2026-09-02)

**Decisão do dono**, tomada nesta data: as caixas do PRD deixam de ser lista morta e passam a refletir o estado real. Até aqui **nenhuma das 31 tinha sido marcada**, inclusive as de critérios entregues há semanas — o que fazia a checklist não significar nada, nem "pronto" nem "não pronto".

**Quem marca, quando, com que prova.** Marca quem entrega a fatia, no mesmo PR, **só depois de conferência item a item com evidência de arquivo e linha**, feita pelo portão `revisor-de-regra`. Marcar é afirmar "pronto" no documento do topo da hierarquia; sem evidência verificável, não se marca.

**Regra que a primeira conferência estabeleceu, e que vale daqui em diante: critério que depende de parâmetro pendente NULO não está cumprido**, mesmo com a fiação inteira pronta. Mecanismo ligado e inerte não é critério atendido — é a diferença entre a lista sair e a lista perseguir o objetivo que o PRD lhe atribui. Foi o que reprovou os itens de ordenação por valor esperado e por probabilidade de lead: os quatro fatores estão fiados e injetados, mas os pesos são o parâmetro nº 12, nulo, e ninguém pode dizer que a ordem persegue o objetivo enquanto o dono não os declarar.

### Por que `:478` é marcado e `:500` não — a regra do parâmetro nulo aplicada

Os dois parecem simétricos e não são, e a distinção precisa estar escrita: sem ela, quem aplicar a regra vai ler as duas marcações lado a lado e concluir que uma está errada. (O portão apanhou exatamente isso.)

**`:500` exige um COMPORTAMENTO do ranking** — "não recebem peso pleno". Quem garante esse comportamento é o desconto de fragilidade, tunável provisório sem valor adotado ([P-16]); a faixa aceita `1.0`, que é peso pleno. Enquanto ninguém adotar o valor, o comportamento não está garantido. **Não cumprido**, pela regra.

**`:478` exige uma APRESENTAÇÃO** — "cada imóvel apresenta ... o resultado da sua última janela, quando houver". A coluna apresenta o resultado: o nível da exposição, os leads que ela acumulou e há quantos ciclos encerrou. Isso É o resultado da janela. O que o parâmetro nº 14 governa é o **veredito sobre** esse resultado — se atingiu ou não o esperado para o nível —, que é julgamento, não resultado, e que a §6.4 pede noutro lugar. A coluna **rotula a ausência do veredito** em vez de fingi-lo, o que é o oposto de mecanismo inerte. **Cumprido.**

A régua geral continua valendo sem emenda: critério que depende de parâmetro nulo não é cumprido. O que esta seção fixa é *do que* `:478` depende — e não é do nº 14.


## Primeira conferência da checklist do PRD (2026-09-02) — 19 marcadas, 12 em aberto

Conferência item a item pelo portão `revisor-de-regra`, com evidência de arquivo e linha por critério, sob a política e a régua fixadas acima. Duas caixas (`:478`, `:479`) foram marcadas na fatia da coluna; as outras dezessete, aqui.

**Marcadas aqui (17), das 19 no total** — `:478` e `:479` saíram na fatia da coluna: as cotas; o corte binário sem compensação e o registro de cada exclusão; as vendas assinadas em 180 dias, o perfil de uma ou duas dimensões e a contagem de casos que o sustenta; o relaxamento restrito ao destaque, a proibição no super, a ordem de cedência, o registro por regra cedida e as posições vazias declaradas; e **seis** dos sete critérios da rodada de segunda.

**Duas distinções que o portão exigiu por escrito**, porque sem elas as marcações se leem como incoerentes — é a mesma classe de falha que o par `:478`/`:500` teve, e que só aparece olhando as marcações lado a lado, nunca item a item:

- **`:528` marcado × [P-08] em aberto, sobre a mesma matéria.** O critério pede que o relatório **liste** os leads sem tratamento "com corretor e gestor de distrito nomeados", e ele lista: as duas colunas existem e o campo do embaixador é preenchido. A [P-08] é sobre outra coisa — o predicado de **pronto** do Monitor, que olha só o corretor e pode dar a rodada por pronta com leads que ninguém do nível distrital responde. Listar e julgar-se pronto são atos diferentes; o critério cobra o primeiro.
- **`:527` marcado sob a convenção "leia-se" do CLAUDE.md.** O texto do PRD diz "a partir da planilha aprovada vigente", e o código lê do Registro. A D-001 **não revogou** essa frase — revogou outra, a de Ferramentas §3 — e para esta deu leitura: "leia-se: a lista da rodada de decisão registrada". O CLAUDE.md adota essa convenção explicitamente ("onde os documentos dizem 'nove regras', leia-se assim"), e o projeto inteiro lê os documentos através das decisões. Deixar `:527` aberto por causa da redação, lendo todo o resto pela decisão, seria a incoerência — não o contrário. *(Uma versão anterior deste registro afirmava que a D-001 declarara a frase "sem efeito". Era falso, e o portão o apanhou: ela dá leitura, não revoga.)*

**Em aberto (12), e a razão de cada grupo importa mais que o número:**

- **Sete não cumpridas.** Duas — `:480` e `:491` — dependem da rotação (§6.7), que não existe: um imóvel vendido ou removido só sai na sexta seguinte, por recoleta, e não "imediatamente, fora do ciclo". Duas — `:481` e `:532` — dependem do agendador, que não existe porque o horário é o parâmetro nº 8, nulo. Uma (`:482`) depende do produtor da variação de volume (nº 6). Uma (`:500`) — o desconto do perfil frágil — depende de valor adotado ([P-16]). E `:501` **não existe em lugar nenhum**: ver [P-19].

- **Uma barrada por MECANISMO AUSENTE, não por parâmetro nulo: `:510`** ("a justificativa informa por qual objetivo o imóvel foi selecionado"). A planilha separa as abas por nível e traz fatores, perfil e penalidades, mas **nenhuma coluna nomeia o objetivo** — nem "valor esperado" nem "probabilidade de lead" aparecem na saída. Ela é critério de APRESENTAÇÃO, como `:478`, e a distinção entre as duas é simples: em `:478` a coluna existe e rotula o que não sabe; aqui não existe coluna nenhuma. *(A versão anterior deste registro dizia "oito não cumpridas" e enumerava sete — `:510` ficava sem razão escrita, inflado dentro de um número que não fechava. Achado do portão.)*
- **Três parciais — `:507`, `:508` e `:509`**, todas pelo mesmo motivo e é o padrão que a régua expôs: a fiação está pronta e o valor é nulo. As listas saem ordenadas, mas por pesos que ninguém adotou (nº 12) — então não se pode afirmar que o super destaque persegue valor esperado nem que o destaque persegue probabilidade de lead.
- **Uma que a reescrita do documento não destrava: `:490`.** A redação ("nove regras") é anterior às D-002/D-003, mas trocá-la por "oito" não a marca: sob o relaxamento que a História 5 sanciona, imóveis fora de até cinco regras **entram** no destaque, e "não entra" segue literalmente falso para aquele nível. Ver [P-18]. *(A versão anterior deste registro dizia "Duas cumpridas no código e não marcáveis" — rótulo falso para `:490` e contagem que fechava em 13 contra o 12 do cabeçalho. Segunda recorrência do mesmo achado; apanhada pelo portão.)*

### Limite DECLARADO — o crivo de cotas não confere a UNIÃO entregue

A lista de destaque que a planilha entrega **não é** `alocacao.destaque`: é o ranking **mais** os recuperados pelo relaxamento, numerados em continuação. O crivo de auditoria (`_checar_cotas`) confere só a primeira. O invariante 6 vale — o corte por déficit garante a soma por construção, e `relaxar` recusa déficit maior que a cota —, mas **por aritmética, não por veto**.

Marcar o critério das cotas com a evidência sendo leitura de código seria afirmar mais do que se verifica. Esta fatia acrescenta a prova: dois testes amarram que `relaxar` nunca devolve mais recuperados que o déficit e que ranking + recuperados cabe na cota, verificados por mutação (remover o corte por déficit faz os dois morderem).

Estender o crivo para a união é **mudança em regra de decisão** — puxa CHANGELOG e revisão própria —, então fica como **candidata a fatia futura**, não como pendência do dono: é cobertura de auditoria, engenharia, não decisão.

### [P-18] Uma linha do PRD carrega redação anterior às decisões

Não é pendência de código — o código está fiel às decisões. É linha do documento superior com a redação anterior a elas. E não pode ser corrigida aqui: o CLAUDE.md manda que divergência entre documentos seja **apontada, não resolvida em silêncio** — e tocar a linha das "nove regras" seria mudança de regra.

- **`:490` — "Imóvel fora de qualquer uma das NOVE regras não entra".** As D-002 e D-003 fixaram **oito** regras eliminatórias, mais o piso de R$ 700.000 como condição de nível e o status impeditivo como saída imediata. Segunda tensão no mesmo item, e ela é do próprio PRD: sob o relaxamento que a História 5 sanciona, imóveis fora de até cinco dessas regras **entram** no destaque — então "não entra" é literalmente falso para aquele nível.
**Vai ao dono:** autorizar a reescrita da linha `:490`. **Não destrava a marcação** — e a promessa anterior de "destrava duas marcações imediatas" era falsa, contradita três linhas acima pela segunda tensão: trocar "nove" por "oito" não resolve o fato de o relaxamento fazer entrar quem está fora de até cinco regras. `:527` saiu do P-18 e foi marcado sob a convenção "leia-se"; o que resta aqui é só o texto de `:490`, e ele é higiene documental, não destravamento.

### Fronteira declarada — o recorte da coleta não gera linha em "excluídos por regra"

A coleta interna recorta `WHERE RealtyStatus = 'Ativo'`, então a regra de status nunca reprova no caminho real: as oito regras operam como sete, e imóvel inativo fica de fora **sem linha na aba de excluídos**. Toca `:489` ("cada exclusão registra o motivo"), que está marcado. A marcação se sustenta — o recorte define o universo, não é exclusão de um candidato —, mas a fronteira fica escrita porque um leitor a lerá como exclusão silenciosa. Pergunta que os documentos não respondem e que vale investigar: se `RealtyStatus` não distingue "Reservado" de "Ativo", nem a recoleta de sexta remove o reservado, e o `:491` está pior do que este registro descreve.

**Adendo 2026-09-02 — esta fronteira foi FECHADA, e a pergunta acima foi respondida (pela pior alternativa).** A pergunta se confirmou: `RealtyStatus` é binário (`Ativo`/`Removido`) e não distingue reserva nem venda. A fatia da correção do espelho fechou a fronteira: `publicacao_ativa` passou a exigir também `COALESCE(r.PublishStatus_Id, 0) = 1` do transacional, então **`Regra.STATUS_ATIVO` passou a reprovar de verdade** — 86 imóveis na medição de 02/09 —, com motivo registrado na aba de excluídos. **As oito regras voltaram a operar como oito**, e o trecho acima ("as oito regras operam como sete", "sem linha na aba de excluídos") descreve o comportamento ANTERIOR. O `:489` deixa de ter esta fronteira. Ver `bug.md` (causa 1, resolvida) e o CHANGELOG. O que **não** mudou: o recorte segue definindo o universo pelo espelho, e a reserva continua não modelada ([P-21]).

### [P-19] Um critério de aceite sem dono, sem prazo e sem contrato

**`:501` — "A hipótese de valor esperado é testada contra vendas e o resultado é reportado".** Não existe em lugar nenhum: nem código, nem Spec, nem esta fila. As únicas menções em `src/` são comentários. Não é parâmetro faltando nem fiação inerte — é trabalho inteiro por fazer que nunca foi especificado. Registro porque critério de aceite invisível é pior que um não cumprido: ninguém o vê para decidir se ainda vale. **Vai ao dono:** confirmar se o critério permanece e, se sim, o que "testar a hipótese" entrega.

## Rotação (§6.7) — o que impede a fatia de código (2026-09-02)

A §6.7 tem duas metades. A primeira — *"a lista é recalculada integralmente a cada rodada de sexta. Não há permanência automática"* — **já vale hoje**: a sexta recalcula tudo, e nenhum imóvel permanece por inércia. A segunda — *"saída imediata, fora do ciclo: venda, reserva, despublicação ou alteração relevante de preço"* — não existe em código, e esta fatia registra **por que ela não pode ser simplesmente construída** antes de tentar construí-la.

Dois critérios de aceite dependem dela e seguem abertos: `:491` ("imóvel vendido, reservado ou removido sai imediatamente, fora do ciclo") e `:480` ("a remoção de um imóvel libera a posição para o próximo elegível do mesmo nível"). A D-003 já fixou o enquadramento desses gatilhos: são **saída imediata fora do ciclo**, não regra de elegibilidade — "não uma **décima** regra", na numeração de então, que contava as nove do PRD mais o status.

### [P-20] "Fora do ciclo" contradiz "dois momentos por semana" — dentro do MESMO documento

Não é divergência entre PRD e Spec, que a hierarquia resolveria. É divergência **interna ao PRD**, entre duas linhas suas:

- `:313` — *"A cadência é de dois momentos: sexta-feira para decisão e carga, segunda-feira para acompanhamento."* O `CLAUDE.md` reforça: **"Não existe execução diária."**
- `:491` — *"Imóvel vendido, reservado ou removido sai imediatamente, **fora do ciclo**."* E não é linha isolada: a mesma regra aparece **três vezes** no PRD — `:155` (tabela do Estágio 1: "Vendido, reservado ou removido, com saída imediata fora do ciclo") e `:270` (prosa normativa: "Venda, reserva, despublicação ou alteração relevante de preço provocam saída imediata, fora do ciclo"). A `:270` é afirmação de **comportamento do produto**, não critério verificável — o que enfraquece a leitura 3 abaixo: "tratar fora do sistema" contradiz mais texto do que só um critério de aceite.

Nenhuma leitura torna as duas verdadeiras ao mesmo tempo. "Fora do ciclo" exige um momento de execução que a cadência nega. Como os dois trechos têm a mesma hierarquia e estão no mesmo documento, a regra do projeto ("se dois documentos divergirem, prevalece o superior") não decide nada aqui — não há superior.

**Vai ao dono [P-20]:** escolher entre três leituras, que produzem sistemas diferentes.

1. **Terceiro momento.** Uma verificação entre sexta e sexta, que detecta os gatilhos e emite substituição. Contradiz "não existe execução diária" e exige dizer com que frequência.
2. **"Imediatamente" leia-se "na próxima rodada de sexta".** **Esta leitura foi MEDIDA e não se sustenta.** A coleta interna filtra `WHERE f.RealtyStatus = 'Ativo'` (`coletor_interno.py:80`), e essa coluna é **binária** — `Ativo` 48.881, `Removido` 356.172, sem terceiro valor. Não existe "Reservado" nem "Vendido" nela. E a venda **não move o status de forma confiável**: **24,69% (40 de 162) dos IMÓVEIS distintos com venda assinada em 180 dias seguem `Ativo`** — medição de 02/09, janela móvel; a D-013 mediu 177 ofertas / 174 imóveis em 28/08, e a unidade aqui é imóvel, não oferta. Ou seja, a recoleta de sexta **continua propondo para destaque pago um quarto dos imóveis já vendidos**. Nesta leitura `:491` não estaria cumprido — estaria silenciosamente violado.
3. **Fora do sistema.** Quem aplica a carga trata a saída manualmente ao encontrá-la, e o sistema não promete nada. Honesto, e torna `:491` um critério de aceite de processo, não de software.

Não escolho por ele: a 2 é a mais barata e a 1 é a que o texto literalmente pede, e a diferença entre elas é dinheiro de posição paga, não estilo.

## D-024 — "sai imediatamente" só pode significar EMITIR a substituição

**Enquadramento, não pergunta.** É dedutível dos documentos e por isso não vai à fila do dono.

O PRD `:15` diz que **"a carga é substituída manualmente a partir dela"**, e o `CLAUDE.md` fecha: "a carga é aplicada manualmente por uma pessoa a partir da planilha; **o sistema não publica nada**". Logo, qualquer que seja a leitura escolhida em [P-20], "sai imediatamente" **não pode** significar que o sistema remove o imóvel do portal — ele não tem esse poder, por desenho.

O máximo que a §6.7 pode exigir de software é **emitir a substituição**: dizer quem sai, por qual gatilho, e quem entra no lugar. A remoção efetiva é ato humano em todas as três leituras. Isso não enfraquece `:491`; delimita o que ele pode cobrar de código.

## D-025 — "alteração relevante de preço" é parâmetro pendente nº 15

**Data**: 2026-09-02 · **Resolve**: nada — **REGISTRA** um parâmetro que faltava. Como a D-024, é enquadramento, não ato do dono: ninguém decidiu o valor aqui, e ele segue **nulo** até o dono defini-lo.

Dos quatro gatilhos da §6.7, três são de estado (venda, reserva, despublicação) e um é de **magnitude**: "alteração **relevante** de preço". Nenhum documento quantifica "relevante" — nem o PRD, nem a Spec §6.7, nem Ferramentas. É a mesma situação que a D-022 encontrou na §6.4 e resolveu criando o nº 14.

**Não sei se é um valor ou dois.** A D-022 fez o nº 14 ser **dois** valores, um por nível, porque a §6.4 diz "o resultado esperado **para o nível**". A §6.7 **não** distingue nível: fala da lista inteira. Afirmar que é um número só seria decisão minha, e afirmar que são dois seria copiar o precedente sem base no texto. A linha fica registrada com essa indefinição explícita, e a resposta do dono a resolve junto com o valor.

Enquanto o nº 15 for nulo, o gatilho de preço **não é implementável** — e os outros três não dependem dele.

## Rotação (§6.7) — levantamento no banco e limites estruturais (2026-09-02)

### Limite estrutural: o Registro não guarda reserva, então `:480` não é servível hoje

`:480` pede "o próximo elegível do mesmo nível". Ele **não existe no Registro**: a `registro.decisao_imovel` só guarda quem foi alocado. O comentário do esquema diz "uma linha por imóvel ESCOLHIDO", e a constraint `posicao_dentro_da_cota` limita `posicao_ranking` a 1–475 e 1–6.495 — nada é silenciosamente descartado: a constraint **rejeita** linha fora da cota, e a camada de escrita só oferece os alocados. De um jeito ou de outro, a reserva não existe no Registro.

E recomputar na hora **não** substitui a reserva: o invariante 5 garante a mesma lista para a *mesma entrada*, e o estoque do Newcore numa terça não é o de sexta. Uma recomputação posterior produziria outra lista — legítima como rodada nova, mas não como "o próximo daquela lista".

Consequência: servir `:480` exige **persistir a reserva ordenada** (mudança de esquema), e isso é fatia de código própria, posterior a esta. Registro aqui porque a alternativa aparentemente óbvia — "é só recalcular" — é falsa, e alguém a tentaria.

### O que o banco realmente oferece para os quatro gatilhos (medido em 2026-09-02)

Levantamento somente-leitura antes de qualquer implementação depender dos campos. **Três dos quatro gatilhos são detectáveis hoje; um não existe.**

| Gatilho | Detectável? | Fonte | Data |
|---|---|---|---|
| Alteração de preço | **sim, plenamente** | `newcore.realtypricehistory` — `PriceBefore`/`PriceAfter` na MESMA linha | `CreatedAt` datetime, indexado |
| Despublicação | **sim, plenamente** | `newcore.realtystatushistory_new` (`StatusBefore=1 → StatusAfter=3`) | `CreatedAt` datetime, indexado |
| Venda | **sim, plenamente** — por `SignedAt` | `FT_LeadsOffers.SignedAt` (D-013) | `date`, granularidade de dia |
| **Reserva** | **NÃO** | não modelada em coluna viva nenhuma | — |

Duas consequências de desenho, para quem construir a fatia de código:

- **O gatilho de venda não pode ser status.** Tem de ser `SignedAt`, e por esse caminho a detecção é plena. Os **24,69%** medidos são a taxa de falha do caminho **por status** — a razão de ele ficar proibido, não uma limitação do caminho adotado. A limitação real do `SignedAt` é a granularidade de dia, suficiente para uma cadência semanal.
- **A rotação não pode ler só o `FT_RealtyRelation`.** Ver a limitação abaixo.

### [P-21] A §6.7 exige "reserva", e o Newcore não modela imóvel reservado

A §6.7 lista quatro gatilhos e um deles **não tem fato correspondente no banco**. Não é que a coluna seja imprecisa: o conceito não existe em coluna viva alguma. `newcore.publishstatus` tem 51 status, incluindo `7 = 'Ficha Reservada'` e `19 = 'Vendido'`, mas o `FT_RealtyRelation` usa apenas dois, e as transições medidas mostram que `Ficha Reservada` flui **para dentro** de `Ativo` (7→1, 2.099 vezes em 30 dias) — é estado de captação **pré-publicação**, não reserva de anúncio vivo. `Ativo → Vendido` ocorreu **uma única vez em toda a história** da tabela.

**Armadilha que quase custou caro:** `realties.ReservedAt` tem o nome certo e o conteúdo errado. Está preenchida em **99,90% dos imóveis ativos** (48.831 de 48.881), seu `MAX` é o instante da consulta e coincide com `CreatedAt` em 40,3% das linhas — é carimbo de criação/toque de linha. Quem a usar sem medir marca praticamente todo o estoque ativo como reservado.

**Vai ao dono [P-21]:** ou adotar um proxy declarado — `FT_LeadsOffers.AcceptedAt`, proposta aceita e ainda não assinada nem cancelada, hoje **157 imóveis ativos** —, ou tirar a reserva do escopo da §6.7 com a limitação escrita. É decisão, não engenharia: o proxy responde outra pergunta (há proposta aceita) e adotá-lo como se fosse reserva é escolha do dono, não minha.

### Limitação encontrada FORA do escopo desta fatia: o espelho está defasado

A coleta interna lê `newcore_bi.FT_RealtyRelation`, que é mantido **incrementalmente e atrasa mais de 24 horas** contra o transacional. Quem mede o **prazo** é o par remoção/espelho: das 82 remoções (`Ativo → Removido`) das últimas 24 horas, **70 ainda constavam `Ativo` no espelho — 85,4%**. Separadamente, como sinal de defasagem **corrente** no momento da medição, `MAX(FT_RealtyRelation.RealtyUpdate)` marcava 07:30 contra `MAX(realties.UpdatedAt)` às 18:38 do mesmo dia — 11 horas, que sozinhas não sustentariam o "mais de 24 h"; quem o sustenta é o 70 de 82.

Isto **não é da rotação**: atinge a coleta interna e, por consequência, a elegibilidade — a sexta pode propor para posição paga imóvel já removido no transacional. Registro aqui porque foi esta fatia que mediu, e porque uma rotação construída sobre o espelho herdaria a defasagem e falharia **exatamente no caso que ela existe para cobrir**. Corrigir exige cruzar com `newcore.realties`/`realtystatushistory_new`, o que muda o universo de candidatos — mudança em regra de decisão, com CHANGELOG e revisão próprios. **Fatia separada, anterior ou paralela à rotação.**

## D-026 — rotação da senha do Newcore recusada pelo dono: risco aceito, e permanente (2026-09-02)

**Data**: 2026-09-02 · **Resolve**: o que acontece com o vazamento registrado no adendo do [P-17], depois de o dono recusar a única mitigação que o fecharia

**Decisão do dono (instrução literal): "Não vou girar a snha, descarte."** Risco assumido de forma explícita, no molde da D-012 e da D-001. O risco não desapareceu: **mudou de dono**, e é isso que precisa ficar escrito.

**Uma decisão anterior do mesmo dono já cercava exatamente isto, e a divergência precisa ficar visível em vez de resolvida em silêncio.** A D-012 §"Limites desta decisão" diz, palavra por palavra, que publicar aberto **NÃO** autoriza publicar credenciais ou senha — a única fronteira que ela cravou. O vazamento a atravessou por acidente, e a D-026 aceita como permanente um risco que a D-012 excluíra preventivamente. Não é erudição: o argumento central desta decisão é que consentimento só é auditável se o registro mostrar a informação, e quem ler as duas precisa saber que a segunda revoga na prática o limite que a primeira escreveu.

**O que foi apresentado antes da escolha** — o consentimento só é auditável se o registro mostrar a informação. Foi dito, nesta ordem: que o repositório é **público**; que sete pontos descreviam por escrito características de uma credencial de produção **viva**; que a limpeza da árvore **não fecha nada**, porque histórico publicado não se desfaz por edição; que o agravante é de **composição** — identidade da conta, mais de um caractere da senha e uma nota de infraestrutura sobre transporte encolhem juntos o espaço de busca; e que a rotação era o **único** fechamento. Ele leu e recusou.

**O que muda de estado, de temporário para permanente.** Todo o registro anterior — o adendo do [P-17], a entrada `Security` do CHANGELOG, o docstring da guarda — foi escrito na hipótese de que a rotação viria. Ela não vem, e por isso:

1. **Os sete vetores passam a ser permanentes**, não transitórios. São eles: os cinco pontos de prosa no histórico (limpos da árvore em `8fb8826`, intactos no histórico), a **mensagem do commit** que fundou o Coletor Interno, e o **corpo do PR #14** — este último achado depois, na varredura do orquestrador sobre os 59 commits, os 53 PRs e todos os comentários, e o **único ainda editável**, porque corpo de PR se redige sem reescrever histórico.

Uma versão anterior desta decisão **omitia esse número**, para não publicar um índice à única cópia legível que resta. A omissão foi desfeita porque comprava zero e custava precisão: a **D-015**, três seções acima **neste mesmo arquivo**, já imprime o número ao declarar a pendência do Coletor Interno, e esta decisão diz que o vetor é da mesma mudança — o ponteiro já circula. E a redação do #14 é **ação pendente de autorização**: pendência com alvo descrito por perífrase obriga quem for executar a re-derivar qual é, que é o mesmo modo de falha que o [P-22] acabou de corrigir. Registro que omitir **não protegia**; o que protege é redigir.

Redigir reduz republicação casual e **não** é fechamento — o menu de edição do GitHub guarda a versão anterior. **Depende de autorização do dono**, que recusou a rotação mas não se manifestou sobre editar conteúdo já publicado. Perguntar custa nada, porque o dono está presente e responde; agir onde perguntar não custa seria unilateralidade sem ganho.
2. **Os quatro `LITERAIS` da guarda nunca ficam inertes.** O texto anterior dizia "depois da rotação eles ficam inertes e podem continuar aqui". Como não há depois, `tests/test_sem_vazamento_de_credencial.py` passa a carregar fragmento de segredo **vivo** por tempo indeterminado. Continua sendo a escolha certa — sem eles não há detecção de revert —, mas deixa de ser uma exposição com prazo.
3. **A guarda deixa de ser complemento e vira o único controle.** Enquanto a rotação era esperada, a fronteira declarada no docstring dela era uma ressalva. Agora é o **teto do risco residual**: o que ela não pega, nada pega. Em particular ela varre `git ls-files` e **não vê mensagem de commit nem corpo de PR** — exatamente os vetores 6 e 7. Essa lacuna passa a ser o caminho de menor resistência para a próxima reincidência, e fechá-la (hook `commit-msg` mais um passo de CI sobre `git log` e sobre o corpo do PR, reaproveitando as regexes já revisadas) deixa de ser refinamento e vira parte do controle.

**Mitigação que NÃO foi recusada, porque não chegou a ser oferecida.** A escolha apresentada ao dono foi binária: girar ou não girar. Existe uma terceira, de custo menor que a rotação: **restringir a conta de leitura por host/IP de origem**. A identidade da conta foi publicada junto com as características da senha, e o próprio [P-17] observou que o `Access denied` de 02/09 nomeava o host do cliente — ou seja, a restrição por origem já opera nesse servidor. Ela não invalida o que saiu, mas torna o que saiu muito menos útil a quem não estiver na rede certa. Fica registrada como **[P-22]**, e é a única coisa que este registro pede que o dono reconsidere.

**O que NÃO é resolvido por esta decisão.** A recusa foi sobre **girar a senha**, e só. A outra metade do [P-17] segue pendente e não foi tocada: o item do cofre guarda uma linha de comando no campo da senha e não tem `POSTGRES_URL`, e a credencial de produção vive em texto claro em arquivos de configuração de MCP. O [P-17] permanece na fila do dono por essa metade.

Decisão de **processo**, não regra de decisão: nenhum invariante é afetado.

## D-027 a D-034 — "o banco manda, o portal classifica" (2026-09-04)

Em 04/09/2026 o dono, ao usar o resultado das primeiras rodadas, pediu três coisas: a apuração inteira num CSV só (entregue, PR #72), parâmetros que uma pessoa consiga julgar ("não dá pra entender o que é excludente, o que é classificatório e o que é decisório"), e uma cadeia de decisão em seis passos que ele descreveu por extenso — o que vende no banco, com que cara, quem está ativo para vender, e o portal ordenando o que sobrou. As oito decisões abaixo registram o que ele escolheu, o que foi medido antes de cada escolha virar código, e o que cada uma supera nos documentos. Todas foram tomadas com os números na frente: **duas premissas do pedido original caíram por medição e o dono re-decidiu** (D-027 e D-029).

Nenhum invariante muda. O caminho da decisão continua cálculo puro (4 e 5); as cotas continuam lidas do Registro (6); o super destaque continua sem relaxamento (7), inclusive para a regra nova.

## D-027 — O perfil de conversão passa a ser regra ELIMINATÓRIA, exige a faixa de preço e é o primeiro degrau cedido

**Data**: 2026-09-04 · **Resolve**: o papel do perfil de conversão (Spec §6.2) no critério — fator de nota (§6.3, D-017 F1) ou filtro.

**Decisão do dono: o perfil filtra, nos dois níveis.** Só entra na vitrine quem se parece com o que vendeu. `Regra.PERFIL_DE_CONVERSAO` entra em `dominio.elegibilidade`: reprova o candidato que não casa nenhum perfil que conta. O casamento é o mesmo de antes (bucketização única para venda e candidato, match exato em todas as dimensões do perfil); o que muda é o consumo — vira veredito, não nota.

**Medição que mudou a decisão antes de ela virar código (04/09/2026, `investigador-de-dados`, reusando os módulos do sistema):** 184 vendas assinadas em 180 dias produzem 187 perfis robustos (N ≥ 3, D-014). Com o filtro como pedido — "casa pelo menos um perfil robusto" — **100,0 % dos 8.230 elegíveis passam**, porque a faixa de metragem sozinha cobre o estoque inteiro; subir N não filtra (N ≥ 10 ainda dá 100 %). O que filtra é a especificidade. Apresentadas as alternativas, **o dono escolheu exigir que o perfil contenha a faixa de preço** — a dimensão que ele mesmo pôs em primeiro lugar na D-017. Com isso passam **83,8 % dos elegíveis e 64 % dos candidatos ao super destaque**. A exigência é `config.parametros.DIMENSAO_EXIGIDA_NO_PERFIL = Dimensao.FAIXA_PRECO`, constante de decisão (não parâmetro da semana): mudá-la é nova decisão.

**Perfil frágil não conta.** Um perfil com N < 3 não entra no filtro — nem pesa menos, nem pesa nada: simplesmente não existe para a regra. Por isso **o desconto de fragilidade ([P-16]) deixa de existir**: era o mecanismo que dava "peso não pleno" a um perfil que agora não pesa. Junto com ele somem `semelhanca.desconto_fragil` e `semelhanca.decaimento` do contrato.

**Primeiro degrau do relaxamento — decisão do dono, "antes das regras de cadastro".** `ORDEM_RELAXAMENTO` passa a ser: **perfil de conversão → fotos → cadastro completo → atualização em 90 dias → gestor produtivo → capacidade do distrito**. A consequência foi dita ao dono com todas as letras e aceita: como o perfil é o primeiro degrau cedido, ele morde de verdade no **super destaque**, que nunca relaxa (invariante 7); no destaque é a primeira coisa de que o sistema abre mão quando faltam imóveis — e, pela folga medida em 02/09 (12 %), vai faltar quase toda semana. O "perfil que puxou" sobrevive como rótulo da justificativa (Spec §2.1): o perfil robusto de mais vendas entre os que o candidato casa.

**Quando a regra NÃO incide (elaboração da revisão de código, 04/09/2026).** Se nenhum perfil conta — nenhum robusto contendo a faixa de preço — o filtro reprovaria 100 % do estoque e o super destaque sairia vazio. A Spec §7.3 manda o contrário: "sem robustez a priorização opera sem o fator". O código segue a Spec: o veredito fica `None` (não avaliado), a elegibilidade não reprova `None`, e a rodada sai **degradada com a limitação nomeada**. O mesmo vale para candidato sem dimensões na coleta de perfil (contado e declarado, não reprovado por dado ausente). O critério de pronto do nó de perfil passa a ser o mesmo do filtro: ao menos um perfil que conte. Se o dono preferir abortar a rodada nesse caso, é decisão a registrar.

**O que esta decisão supera, declarado:** a Spec §6.2 ("não recebe peso pleno") e §6.3 (semelhança como fator com peso) e o **F1 da D-017** (semelhança ponderada por dimensão, com decaimento). A ordem das dimensões da D-017 deixa de ter efeito no cálculo — sobrevive só como critério de exibição. **A Spec §6.2/§6.3 precisa ser reescrita** (fatia própria); até lá esta decisão prevalece sobre o trecho divergente.

## D-028 — O portal CLASSIFICA: a nota é a soma ponderada de três sinais do anúncio, em pontos de 100

**Data**: 2026-09-04 · **Resolve**: o que ordena os elegíveis. A D-017 dizia "o primário é o banco; a raspagem é reforço que soma, não pré-requisito"; o dono, em 04/09, inverteu: **"o banco manda, o portal classifica"** — o banco decide QUEM entra (elegibilidade, agora com o perfil), o portal decide EM QUE ORDEM.

**A nota.** `dominio.ranking.nota_portal` = `peso_nota × nota_anuncio + peso_cliques × cliques + peso_visualizacoes × visualizacoes`, cada sinal normalizado para [0, 1] a montante (min-max sobre os elegíveis, forma provisória do nº 2, D-016) e os três pesos em **pontos de 100, somando exatamente 100** (`PesosPortal` recusa qualquer outra soma). A nota bruta vive em [0, 100]; os descontos (D-030) são subtraídos dela. **Os dois níveis usam a mesma nota** — o que separa o super destaque é o piso de R$ 700.000 na alocação (D-002), não uma nota diferente.

**Os valores, por medição (03/09/2026, primeira raspagem real, 300 anúncios):** visualizações = **0 em 300 de 300**; cliques quase todos zero; a nota do anúncio (LQS) é o único sinal com variância, 14 valores distintos. Daí os pesos adotados (D-034): **nota 70, cliques 30, visualizações 0**. O zero é **declarado, não omitido** — fica visível na tela com a razão ao lado, para voltar a pesar quando o raspador achar o campo. Isso **fecha a [P-15]** (composição do sinal de portal) com dado, não com preferência.

**Cliques somados entre os tipos — divergência declarada.** O contrato anterior do coletor exigia escolher UM tipo de clique (`cliques_do_tipo` + `tipo`) e nunca os somava. A nota nova soma contato, telefone, WhatsApp, proposta e agendamento. É leitura nova, registrada aqui; nenhum documento definia a composição.

**Imóvel sem anúncio raspado deixa de virar zero em silêncio.** Antes recebia 0,0 fixo e, como a nota do portal vivia numa faixa alta, ia para o fim da fila por um zero que ninguém escolheu. Vira escolha declarada — `portal.sem_anuncio` ∈ {`fim_da_fila`, `mediana`}, adotado `fim_da_fila` (é o que já acontecia, agora dito).

**Quando o portal não entra, a ordem cai para um sinal do banco — e a rodada declara.** As quatro portas de `avaliar_coleta` (Spec §7.3) continuam. Fechadas, a nota bruta passa a ser o sinal escolhido em `portal.ordem_quando_nao_entra` ∈ {`leads_180d`, `produtividade_gestor`, `cadastro_mais_novo`}, adotado `leads_180d` (o sinal de banco mais próximo do objetivo do destaque, que é gerar lead), e a rodada sai **degradada com a limitação nomeada**. É remendo de segurança declarado, não o modelo.

**Leads e produtividade do gestor viram DESEMPATE, não fator.** A alocação e o relaxamento ordenam por `(-nota, -leads normalizados, -imovel_id)`: leads primeiro, depois cadastro mais novo (D-009 preservada como último critério). Exceção coerente com o rótulo: sob `ordem_quando_nao_entra = cadastro_mais_novo`, que promete SÓ o cadastro mais novo, o desempate por leads é desligado e a ordem é o próprio `imovel_id`. Os dois sinais continuam gravados no Registro e mostrados na planilha.

**O que esta decisão supera, declarado:** a **Spec §6.3 inteira** (quatro fatores com pesos por nível) e a **D-017** no ponto "raspagem é reforço, não pré-requisito" e nos fatores F2/F3/F4 com peso. Os objetivos por nível da §6.3 (valor esperado no super destaque, probabilidade de lead no destaque) não são contraditos: o piso separa os níveis e o desempate por leads serve ao segundo. **A Spec §6.3 precisa ser reescrita**; até lá esta decisão prevalece. Consequência para a lista de parâmetros: ver D-031.

## D-029 — "Corretor inativo" é trava do relaxamento, não regra de exclusão

**Data**: 2026-09-04 · **Resolve**: o pedido do dono de excluir "corretores inativos", definido por ele como **quem não loga há 30 dias**.

**Medição que mudou a decisão (04/09/2026):** o campo é `newcore_bi.productivityrating.LastLogin` (join 1:1 por `User_Id = FT_RealtyRelation.BrokerID`, cobertura 99,4 %; `NULL` ≡ nunca logou dentro da retenção de `userlogs`, que começa em 2025-05-25). Resultado: **"sem login em 30, 60 ou 90 dias" é subconjunto estrito de "gestor não produtivo"** — como regra de exclusão adicional, exclui **0 imóveis** (três fontes concordam). A regra pedida, implementada como pedida, seria código correto que não faz nada.

**Onde o login morde:** no relaxamento. Dos 2.092 imóveis recuperáveis pelo degrau `gestor_produtivo`, **105** têm gestor sem login na janela — imóveis que a cedência devolveria à vitrine para um corretor que não entra no sistema e não vai atender o lead que a posição paga gerar.

**Decisão do dono (recomendada e escolhida): o login vira TRAVA do relaxamento.** O degrau `gestor_produtivo` — e qualquer degrau posterior, que o inclui — **não recupera** imóvel cujo gestor não logou dentro de `corretor.login_janela_dias` (adotado 30, D-034). O imóvel fica irrecuperável, e `ResultadoRelaxamento.bloqueados_por_login` conta quantos foram travados, declarado na planilha mesmo quando ninguém foi cedido. A D-015 fica **reafirmada**: a capacidade do distrito continua contando corretores **produtivos** (captou ou vendeu), fiel à Spec §6.1.

**Armadilhas de dado registradas para quem vier depois** (a incorporar ao `docs/mapa-de-dados.md`): `userbrokerrelationships.LastLogin` está **morta desde 2021**; `FT_Broker.Logged30D` é **falso-negativo** em 282 gestores / 7.075 imóveis; `productivityrating.DaysLastLogin` é derivada fiel de `LastLogin`.

## D-030 — Descontos das penalidades em PONTOS DE 100; decaimento como "perdão por semana" em por cento

**Data**: 2026-09-04 · **Resolve**: a escala das três penalidades da Spec §6.4 (parâmetro nº 3), que o dono não conseguia julgar ("o formato de 0 a 1").

**O defeito que a escala escondia:** a nota bruta vai de 0 a 100 e as intensidades provisórias, em [0, 1], somavam **0,4 de 100** — as três penalidades estavam **duas ordens de grandeza abaixo** da nota, praticamente inertes, e nada avisava.

**Decisão:** cada penalidade é um **desconto em pontos de 100**, subtraído da nota bruta (`dominio.ranking.nota_final`); o decaimento da penalidade por janela (D-021/D-023) vira **perdão por semana, em por cento** — quanto o desconto encolhe a cada carga aprovada em que o imóvel permanece. Valores adotados (D-034): janela anterior sem resultado **20**, sem avaliação por categoria **5**, sem lead em 180 dias **10**, perdão **50 %** por semana. O de avaliação é baixo de propósito: o pipeline de avaliação parou em 16/10/2025 e 99,76 % do estoque novo não tem nota — descontar alto puniria o estoque novo por defeito da base. **Com isso o nº 3 passa a DEFINIDO.**

**A penalidade por janela continua INERTE, e declarada.** O dono decidiu em 04/09 que a régua de resultado (nº 14, D-022) **segue nula**. O desconto de 20 pontos existe, é mostrado, e não incide até a régua ser definida — a planilha diz isso em toda rodada.

## D-031 — Os parâmetros nº 12 e nº 13 DEIXAM DE EXISTIR

**Data**: 2026-09-04 · **Resolve**: a lista canônica de parâmetros pendentes (D-004, CLAUDE.md) depois das D-027 e D-028.

O nº 12 (pesos dos quatro fatores por nível) e o nº 13 (decaimento por dimensão do F1) eram os pendentes criados pela D-017. Com o perfil virando filtro (D-027) e o portal virando a nota (D-028), **as perguntas desapareceram**: não há quatro fatores a pesar nem dimensões a decair. Os dois saem da tabela **sem receber valor** — não foram resolvidos, foram dissolvidos. A numeração não é reaproveitada: os números 12 e 13 ficam vagos, para que citações antigas continuem apontando para o que apontavam. Os pesos do portal (D-028) não entram como pendente novo: são adotados pela D-034 e declaráveis na semana.

## D-032 — Limitações de dado declaradas: o que NÃO virou parâmetro nesta fatia

**Data**: 2026-09-04 · **Resolve**: dois campos do desenho aprovado pelo dono que não entraram no contrato, e por quê.

- **"Gestor produtivo: janela".** A Spec §6.1 diz 30 dias, e a fonte (`FT_Districts.BrokersProductivity` e a produtividade do gestor em `productivityrating`) já vem **agregada em 30 dias pelo Newcore** — não há como pedir outra janela sem reconstruir a produtividade a partir dos eventos. Não é parâmetro: é o número da Spec, fixo, e a tela o mostra como texto.
- **"Base do perfil: vendas ou vendas e leads".** O passo 1 do dono dizia "mais leads OU vendas". São 184 vendas em 180 dias contra ~5.200 leads em 30: misturar faz os leads dominarem cerca de **30 para 1** e o perfil deixa de descrever o que vende. O perfil fica **só de vendas assinadas**, como a Spec §6.2 define; a alternativa não entra como escolha nesta fatia. Reabrir é decisão nova.

## D-033 — Janelas e mínimo do distrito viram PARÂMETROS declaráveis, com adotado igual ao texto da Spec

**Data**: 2026-09-04 · **Resolve**: o pedido do dono de "período configurável" para o que vende e para a atividade do corretor.

Entram no contrato, todos em unidade que uma pessoa julga: `conversao.janela_dias` (dias; adotado **180**, Spec §6.2), `corretor.login_janela_dias` (dias; adotado **30**, D-029), `corretor.minimo_no_distrito` (corretores; adotado **2**, Spec §6.1 e D-015). Enquanto a semana não declarar outro valor, vale o adotado e **nenhuma divergência existe com a Spec**. Declarar valor diferente é permitido, sai rotulado "declarado" na planilha e **diverge da Spec no texto** — divergência visível, não silenciosa.

## D-034 — Parametrização padrão ADOTADA: catorze valores com procedência, declaráveis na semana

**Data**: 2026-09-04 · **Resolve**: o pedido do dono — "propor opções e entregar uma parametrização padrão com explicações". Adotada pelo dono ao aprovar o plano que a listava, valor a valor, com a razão de cada um.

**Onde vive:** `src/config/adotados.py` — a única lista de valores adotados, cada um com decisão de procedência. O contrato (`src/config/contrato.py`) expõe cada campo com **unidade** (dias, pontos de 100, por cento, corretores), **valor adotado** e uma linha **"se aumentar"** no imperativo; o console herda o JSON e o CI compara byte a byte. **Três funções, não sete:** excludente (decide quem entra; vem do banco), classificatório (decide a ordem; vem do portal), decisório (decide onde e quantos; vem do contrato). **Nenhum campo em escala de 0 a 1.**

| Campo | Adotado | Por quê |
|---|---|---|
| `conversao.janela_dias` | 180 dias | a janela medida, com 184 vendas; em 30 dias seriam ~25, evidência de menos |
| `corretor.login_janela_dias` | 30 dias | mesma janela da irmã produtiva, para a trava ficar coerente (D-029) |
| `corretor.minimo_no_distrito` | 2 corretores | D-015: de 3 para 2 elevou a cobertura de vendas de 62 % para 75 % |
| `portal.peso_nota` | 70 pontos | único sinal com variância medida: 14 valores em 300 anúncios |
| `portal.peso_cliques` | 30 pontos | sinal fraco mas real, e é intenção de compra, não curiosidade |
| `portal.peso_visualizacoes` | 0 pontos | medido zero em 300 de 300; zero declarado, não omitido |
| `portal.cobertura_minima` | 50 % | abaixo da metade, a ordem seria decidida por menos da metade do estoque (nº 7) |
| `portal.idade_maxima_dias` | 2 dias | a rodada raspa no mesmo dia; 2 tolera um retry sem aceitar dado da semana passada (nº 5) |
| `portal.sem_anuncio` | fim da fila | é o que já acontecia, agora dito (D-028) |
| `portal.ordem_quando_nao_entra` | leads em 180 dias | o sinal de banco mais próximo do objetivo do destaque (D-028) |
| `desconto.janela_sem_resultado` | 20 pontos | inerte enquanto o nº 14 for nulo, e declarado (D-030) |
| `desconto.sem_avaliacao` | 5 pontos | baixo de propósito: 99,76 % do estoque novo não tem nota (D-030) |
| `desconto.sem_lead_180d` | 10 pontos | D-030 |
| `desconto.perdao_por_semana` | 50 % | o desconto cai pela metade a cada carga; some em cerca de três semanas |

**Consequências na lista canônica:** **nº 3, nº 5 e nº 7 passam a DEFINIDOS** por esta decisão; nº 12 e nº 13 deixam de existir (D-031); **nº 14 segue NULO** por decisão expressa do dono; **nº 2 continua provisório** (min-max fixo no código, D-016) — não é adotado aqui. O que o TOML da semana declarar diferente do adotado sai na planilha com procedência "declarado"; o que não declarar usa o adotado com procedência "adotado D-034". A planilha deixa de rotular PROVISÓRIO o que é adotado; rotula só o que segue nulo.

**Trocar qualquer adotado exige decisão nova + CHANGELOG** — a regra da convenção continua.

### [P-13] Adendo (2026-09-04) — o código do portal existe no banco

A pendência estava registrada como refutada ("não existe id nem URL de anúncio do portal em tabela nenhuma"). A primeira raspagem real (03/09/2026) mostrou `realties.NewIdMarketingRotation` **igual ao `codigoImovel` do Canal Pro em 300 de 300** anúncios amarrados. A apuração já o entrega como `codigo_portal` (PR #72). O que resta é fato do dono, não medição: **é esse o código que quem aplica a carga usa para achar o anúncio?** Se sim, a [P-13] fecha; a planilha entregue passa a ser aplicável sem consulta ao banco.

## Spec revisada para 1.1 (2026-09-05) — as divergências declaradas nas D-027, D-028 e D-030 foram incorporadas

`docs/vitrine-destaque-spec.md` passou à versão 1.1. O que mudou no texto, e por quê:

- **§6.1**: nove regras = oito gerais + o perfil de conversão (D-027); o piso de R$ 700.000 sai da tabela e vai para a §6.5 como condição de nível (D-002); status impeditivo é saída imediata (D-003); mínimo do distrito é declarável (D-033); login não exclui, trava (D-029).
- **§6.2**: evidência mínima N ≥ 3 (D-014); o perfil é regra, conta só se robusto e contendo a faixa de preço (D-027); só vendas na base (D-032); "não recebe peso pleno" deixa de existir.
- **§6.3**: a nota é a soma ponderada dos três sinais do portal em pontos de 100 (adotados 70/30/0), leads e produtividade viram desempate com a D-009 por último, imóvel sem anúncio tem tratamento declarado, e sem raspagem a ordem cai para o sinal do banco declarado com rodada degradada (D-028). A tabela 60/25/15 e 80/10/10 sai; os objetivos por nível ficam como intenção.
- **§6.4**: passa a chamar-se "Descontos": pontos de 100 e perdão por carga (D-030), com os adotados; o nº 14 nulo deixa o desconto por janela inerte e declarado (D-022).
- **§6.5**: piso como condição de nível; cotas lidas do Registro.
- **§6.6**: perfil como primeiro degrau (D-027), trava do login (D-029), linha com zero para degrau cedido sem recuperação, ressalva do PRD sobre os ganhos medidos com três corretores.
- **§3.2, §5, §7.3, §8**: colunas da planilha, contratos dos agentes, tratamento de falha do perfil e da amarração, e a lista de parâmetros (definidos, declaráveis, nulos, dissolvidos) alinhados ao `CLAUDE.md`.

### O que esta revisão NÃO fez, e a pendência que ela cria — [P-23]

Com isso, as frases "a Spec §6.x precisa ser reescrita" das D-027, D-028 e D-030 estão cumpridas. Mas a revisão abre uma divergência nova, no topo da hierarquia, e ela precisa ficar visível em vez de resolvida em silêncio.

**Antes:** PRD e Spec estavam velhos JUNTOS, e este arquivo superava os dois — desconfortável, porém uniforme. **Agora:** a Spec diz o que o código faz, e o PRD, que é o documento SUPERIOR, contradiz os dois. Enquanto durar, vale a regra do topo daqui: a decisão registrada prevalece sobre o trecho divergente de qualquer documento, PRD incluído.

**[P-23] Vai ao dono: autorizar a revisão do PRD para incorporar as D-027 a D-034.** Os pontos medidos, em `docs/vitrine-destaque-prd.md`:

- **A tabela de pesos do ranking** (linha 236, e a tabela de parâmetros em :278-299): ainda traz semelhança 60/80, desempenho 25/10, produtividade 15/10, e "A definir" para as intensidades das penalidades. Superada pelas D-028 e D-030 — a nota passou a ser do portal, em pontos de 100, e os descontos têm valor adotado.
- **A disputa do super destaque**: "4.852 candidatos, dez por vaga" (:17 e :187). A medição de 02/09/2026 achou 3.562 candidatos e 7,5 por vaga, e o filtro de perfil da D-027 reduz mais. Ver o aviso de deriva em `docs/perguntas-abertas.md`.
- **As "nove regras"** (:490, :574, :654) — e aqui a **[P-18] mudou de sentido**. Ela foi aberta para perguntar se o PRD podia trocar "nove" por "oito", leitura correta sob as D-002/D-003. Depois da **D-027** o número voltou a ser nove (oito gerais mais o perfil), por outro caminho: **executar a [P-18] como está escrita tornaria o PRD errado de um jeito novo.** A pergunta certa hoje é a desta pendência — rever o PRD inteiro contra as decisões —, e a [P-18] deve ser respondida dentro dela, não antes.

Enquanto o dono não autorizar, o PRD segue como está e nada no código muda: o PRD é fonte de INTENÇÃO, e a intenção dele — valor esperado no super destaque, não deixar benefício pago sem uso no destaque — continua sendo perseguida. O que mudou foi a mecânica, não o objetivo.

Nesta revisão o PRD **não** foi tocado, e a hierarquia continua PRD > Spec: onde os dois divergirem, o PRD prevalece **exceto** no que uma decisão registrada já resolveu, que é o caso dos três pontos acima. Reescrever o PRD é fatia própria, e depende da [P-23].

