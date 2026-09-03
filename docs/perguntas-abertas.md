# Fila de decisão do dono

Tudo que hoje aguarda o dono da decisão, num lugar só.

## Como este documento funciona

**É índice, não cópia.** O texto integral de cada pendência — fundamentação, alternativas, histórico — continua em `docs/decisoes.md`, que o CLAUDE.md torna normativo. Aqui ficam só quatro coisas: a pergunta em uma frase, onde ela vive, **o que está bloqueado hoje** e **o que muda quando você responder**. As duas últimas não existem em lugar nenhum além desta tabela — é o que esta fila acrescenta.

**A ordem é julgamento meu, não fato.** Agrupei por quanto cada resposta destrava, com este critério explícito: primeiro o que já tem a fiação pronta e liga só com o valor; depois o que precisa de código além da resposta; depois fatos e atos; por último o que não bloqueia nada. Você pode discordar da ordem sem discordar de nenhum item.

**Contrato de manutenção:** quem registrar pendência nova em `docs/decisoes.md` **marca o identificador `[P-NN]`** lá e acrescenta a linha aqui, na mesma mudança. `tests/test_perguntas_abertas.py` faz os dois casarem: pendência marcada e ausente daqui quebra o CI, e vice-versa. A trava alcança também quem esquecer de marcar — o teste exige `[P-NN]` em todo trecho que diga "vai ao dono", "pergunta ao dono" ou "pendência do dono".

**Identificadores.** Os parâmetros usam o número da tabela do CLAUDE.md (§ *Parâmetros ainda sem valor*), citados também pelo nome, porque uma renumeração futura não pode invalidar este índice. As demais pendências usam `P-NN`, marcado no próprio `docs/decisoes.md`.

---

## 1. Destrava só com o valor — a fiação já existe, nenhum código novo

Estes são os mais baratos em CÓDIGO — nenhum precisa de linha nova. Mas atenção ao que "responder" significa: escrever o número no arquivo da semana faz a rodada **usar** o valor, rotulado PROVISÓRIO, e o parâmetro **continua nulo**. **Adotar** exige três coisas: decisão registrada em `docs/decisoes.md`, entrada no `CHANGELOG.md` e a linha da tabela do `CLAUDE.md` deixando de dizer "nulo". Sem as três, a pendência segue aberta e este documento continua cobrando.

| Id | Pergunta | Bloqueado hoje | Quando você responder |
|---|---|---|---|
| **nº 14** — resultado esperado por nível | Quantos leads uma janela precisa ter gerado para não ser punida? Dois números: um para super destaque, outro para destaque. | **Uma das três penalidades da §6.4 não incide sobre ninguém.** A coluna sai 0,0 e a planilha declara "limiar não definido". Produtor e consumidor de janelas já existem. | A penalidade acende sem mudança de código. Guardas já prontas: zero é recusado, e super destaque tem de ser maior que destaque. |
| **nº 12** — pesos dos quatro fatores, por nível | Quanto vale cada fator do ranking (semelhança, leads, desempenho de portal, produtividade do gestor) em cada nível? | Toda planilha sai com os pesos rotulados **PROVISÓRIO** — e eles não ordenam só a lista: decidem **quais** elegíveis ocupam as 6.970 posições contratadas, e em que ordem. **Leia o aviso abaixo antes de decidir este:** a folga entre candidatos e posições encolheu de 48% para ~12% desde a medição do PRD. | O valor deixa de ser provisório. Zero código. |
| **nº 3** — intensidade das penalidades e decaimento | Qual o tamanho do castigo de cada uma das três penalidades, e quanto o castigo por janela ruim enfraquece a cada ciclo? | A rodada recusa rodar sem. E **quando a razão declarada é 1.0** — como na planilha-piloto — o decaimento **não decai**, divergindo da §6.4; a planilha declara isso na própria rodada. | Zero código. |
| **nº 13** — decaimento por dimensão do F1 | Quanto cada dimensão pesa menos que a anterior, na ordem preço > localização > metragem > dormitórios > vagas? A ordem já é sua; falta a magnitude. | O fator que corrigiu a saturação do super destaque opera com número provisório. | Zero código. |
| **nº 7** — limiar mínimo de amarração | Qual a taxa mínima de imóveis amarrados para a raspagem valer? | O portão de admissão do desempenho de portal opera com número provisório. | Zero código. |
| **nº 5** — idade máxima da coleta externa | Uma raspagem de quantos dias atrás ainda serve como dado de reserva? | O limiar é exigido, mas hoje coleta velha apenas degrada. | Zero código para o limiar. *(O reuso da coleta de reserva que a Spec §7.3 pede não existe — dívida minha, não sua.)* |
| **[P-15]** — composição do sinal de desempenho de portal | Como combinar nota do anúncio, visualizações e cliques num sinal só? | O runner usa `visualizações` como default run-local, **não adotado**. Muda o desempenho de portal de todo imóvel. | Escolha registrada + CHANGELOG. Já é injetada, não está fixa no domínio. |
| **[P-16]** — desconto do perfil frágil | Quanto vale a menos um perfil sustentado por poucos casos? A Spec §6.2 diz "não recebe peso pleno" e não quantifica. | Tunável provisório, injetado por rodada. Fica **fora** dos quinze parâmetros e sem prazo. | Valor adotado; a fiação já existe. |
| **nº 2** — forma de normalização dos fatores | A forma de reescalar cada fator para uma escala comum é min-max, ou outra? | Min-max está **fixo no código** como forma provisória, e a planilha declara "não adotada". A decisão roda sob uma forma que você não escolheu. | Se confirmar min-max: só documento. Se escolher outra: **muda código**. |

## 2. Precisa de código além da sua resposta

| Id | Pergunta | Bloqueado hoje | Quando você responder |
|---|---|---|---|
| **nº 10** — prazo da aprovação tácita | Depois de quantas horas sem resposta a planilha é considerada aprovada? | **A aprovação automática não existe.** Alguém tem de rodar o comando toda semana; sem isso, toda segunda-feira declara ausência de carga. Diverge de Ferramentas §4, que fixa o default oposto. | Mecanismo pronto (comando `tacita`). Falta o agendador que conta o prazo — código novo. |
| **nº 8** — horários de execução | A que horas exatas roda a sexta, e a que horas roda a segunda? | **Nada dispara as rodadas.** Só acontecem se alguém digitar o comando. | Valor + criar a entrada no agendador da máquina. |
| **nº 11** — prazo de atendimento de lead | Em quanto tempo um lead precisa ser atendido, e a partir de quando o corretor conta como inativo? | A aba de cobrança não tem régua de "atrasado". | Valor + fiação no runner da segunda. |
| **nº 6** — limiar de variação de volume | Quanto o estoque elegível precisa variar de uma semana para outra para o sistema levantar a mão? | A planilha declara "variação do estoque elegível: não apurada" toda semana, embora a Spec §3.1 a exija. | **O valor sozinho não destrava**: falta o produtor que compara com a rodada anterior. |
| **nº 4** — tentativas e intervalo de repetição | Quantas vezes o sistema tenta de novo antes de desistir, e com que intervalo? | A "repetição antes de desistir" que justifica o LangGraph **não existe**. Prende também um defeito de concorrência registrado no `bug.md`. | **O valor sozinho não destrava**: falta a política de repetição nos nós. |
| **nº 15** — o que é "alteração relevante de preço" | Quanto o preço precisa mudar para o imóvel sair da carga? E **é um valor só ou um por nível?** A §6.4 dizia "para o nível" e virou dois (nº 14); a §6.7 não distingue nível, então copiar o precedente seria inventar. | **O quarto gatilho da rotação não existe.** Venda, reserva e despublicação são de estado; este é de magnitude, e sem limiar não é implementável. | O gatilho de preço passa a ser construível — depois de [P-20] dizer QUANDO ele roda. |

## 3. Divergências e buracos de esquema

| Id | Pergunta | Bloqueado hoje | Quando você responder |
|---|---|---|---|
| **[P-19]** | O critério de aceite "a hipótese de valor esperado é testada contra vendas e o resultado é reportado" permanece? Se sim, o que "testar a hipótese" entrega? | Não existe em lugar nenhum — nem código, nem spec, nem esta fila. Não é parâmetro faltando: é trabalho nunca especificado. | Define escopo; hoje é critério invisível, que ninguém vê para decidir se ainda vale. |
| **[P-04]** | Quando você reprova uma lista, o que acontece com a semana — a sexta seguinte reprocessa, e a lista some da fila? | O comando de reprovar **não existe**: o banco não distingue "o dono disse não" de "ninguém olhou". Hoje o silêncio já recusa na prática; falta poder registrar a recusa. | Migração de esquema + expor o comando. Sua resposta define a semântica. |
| **[P-05]** | O carimbo de aprovação marca quando você aceitou a lista, ou quando a carga foi aplicada no portal? | O campo é único e serve aos dois usos. Declarar a aplicação real apaga do Registro o instante do aceite — e o Registro é a fonte da verdade. | Uma saída pede coluna nova; a outra, emenda à D-001. |
| **[P-03]** | Uma limitação de fiação deve fazer a rodada sair como DEGRADADA, ou só ir declarada na planilha? | Hoje vai à planilha e ao motivo gravado, mas não muda o estado. O argumento que sustentava o "não" era temporal e caiu: produtor e consumidor de janelas já existem. | Mudança pequena de fiação. |
| **[P-02]** | A planilha deve ser escrita **antes** de a rodada entrar no Registro, como dizem PRD e Spec §5, ou o Registro vem primeiro como o código faz? | Risco concreto: uma rodada gravada **sem planilha** pode ser aprovada e virar a carga vigente — uma lista que ninguém recebeu. Vale para as duas rodadas. | Se inverter: muda código e esquema. Se mantiver: declarar a divergência com a §5. |
| **[P-01]** e **[P-09]** | Quando o crivo veta a lista, isso é rodada "abortada" ou merece estado próprio? E "não há carga aprovada" na segunda também é "abortada"? | Consequência acoplada e bloqueante: rodada abortada **não deixa linha nenhuma no Registro, nem o cabeçalho** — o Monitor não enxerga que houve execução, contra a Spec §2.1. | Estado próprio e/ou gravar o cabeçalho: muda código e provavelmente o DDL. |
| **[P-07]** | O imóvel que nunca sai da carga nunca tem janela encerrada, logo nunca é penalizado — o caso que abre o PRD é justamente o que escapa. Está certo? | Nada trava, mas o alcance da penalidade encolheu depois da D-023. | "Está certo" = só registro. Alcançar o permanente = muda regra. |
| **[P-06]** | A aprovação tácita deve guardar quem a invocou, ou basta gravar "tácita"? | Enquanto o prazo for nulo, a tácita é uma afirmação humana **sem autor** no Registro. | A coluna já existe; guardar o autor é mudança pequena. |
| **[P-08]** | Um lead sem tratamento que tem corretor mas não tem embaixador conta como "com responsável"? | O "pronto" do Monitor olha só o corretor; o PRD fala em corretor **e** gestor de distrito. A segunda pode dar pronta com leads que ninguém do nível distrital responde. | Mudança pequena no predicado — mas é regra, não código. |
| **[P-18]** | A linha :490 do PRD diz "nove regras" onde as D-002/D-003 fixaram oito. Autoriza reescrevê-la? | Nada. É higiene documental: o código está fiel às decisões, e o projeto já lê os documentos através delas. **Não destrava marcação** — :490 segue em aberto por outra razão, que a reescrita não resolve: sob o relaxamento, imóveis fora de até cinco regras entram no destaque. | O texto do PRD passa a dizer o que as decisões dizem. |
| **[P-20]** | "Fora do ciclo" (`:491`) contradiz "dois momentos por semana" (`:313`), e as duas linhas são do **mesmo** documento — hierarquia não resolve. Vale (1) criar um terceiro momento, (2) ler "imediatamente" como "na próxima sexta", ou (3) tratar fora do sistema? | **A rotação inteira.** `:491` e `:480` seguem abertos: um imóvel vendido mantém posição paga até a sexta seguinte — e **um quarto deles, indefinidamente**, porque o status nunca se move (24,69% medidos). | Define se a §6.7 pede código novo, momento novo, ou sai do escopo. A leitura "a recoleta já resolve" foi **medida e caiu** — ver D-024 e o levantamento de 02/09. |
| **[P-21]** | A §6.7 exige saída por **reserva**, e o Newcore não modela imóvel reservado em coluna viva nenhuma (`realties.ReservedAt` é carimbo de criação: 99,90% dos ativos). Adotamos o proxy `FT_LeadsOffers.AcceptedAt` — proposta aceita, não assinada, não cancelada, hoje 157 ativos — ou a reserva sai do escopo com a limitação escrita? | **Um dos quatro gatilhos da rotação.** Os outros três (preço, despublicação, venda) são detectáveis. | Fecha o desenho da rotação: três gatilhos mais a reserva, ou três com ausência declarada. |

## 4. Fatos que só você tem, e atos que só você pratica

Não são decisões: nada a escolher, só a informar ou fazer.

| Id | O quê | Bloqueado hoje |
|---|---|---|
| **[P-12]** *(ato, recorrente)* | Abrir a sessão logada no Canal Pro para o reconhecimento do painel. | O adapter é stub: o desempenho de portal nunca sai de zero e **toda rodada de sexta é degradada nesse fator**. Pela D-010, o reaquecimento após bloqueio é sempre manual. |
| **[P-17]** *(ato)* | Consertar o **item do cofre**: `NEWCORE_MYSQL_PASSWORD` guarda uma linha de comando (referência a outro item), não a senha, e `POSTGRES_URL` **não existe** no item. E tirar a credencial de produção dos arquivos de MCP, onde ela está em texto claro. | `op inject -i .env.tmpl -o .env` não produz um `.env` utilizável, então nada ligado ao Registro roda sem rodeio. A metade do MySQL **caiu em 02/09**: a credencial do MCP funciona e a medição contra a base foi executada. O que permanece é o cofre — e, enquanto permanecer, a senha de produção vive em **três** cópias (dois arquivos de MCP mais o que estiver em uso) e nenhuma é a fonte da verdade, contra a convenção do projeto (`${VAR}` do ambiente). A metade de SEGURANÇA saiu daqui: a rotação da senha foi **recusada pelo dono** em 02/09 e virou risco aceito na **D-026** — não aguarda mais nada, e por isso não é pendência. O que resta nesta linha é o cofre. | `op inject` volta a funcionar, a credencial passa a ter uma casa só, e a recontagem da deriva deixa de depender de rodeio. |
| **[P-22]** *(ato)* | Restringir a conta de leitura do Newcore **por host/IP de origem**. | Alternativa à rotação, que você recusou em 02/09 (**D-026**) — e que nunca lhe foi oferecida, porque a escolha que apresentei foi binária. A identidade da conta saiu publicada junto com características da senha, e o `Access denied` de 02/09 nomeava o host do cliente: a restrição por origem já opera nesse servidor. **Não** invalida o que já saiu; torna o que saiu pouco útil a quem não estiver na rede certa. | A credencial publicada deixa de ser aproveitável fora da rede de origem, sem tocar na senha. |
| **[P-11]** *(ato)* | Autorizar o app na conta Google e depositar a credencial no 1Password. | A entrega é CSV em disco, não a planilha do Google com link por e-mail que o contrato prevê. |
| **[P-13]** *(fato)* | Quem aplica a carga encontra o imóvel só pelo código interno, ou precisa de outra referência? | Investigado e **refutado no banco**: não existe id nem URL de anúncio do portal em tabela nenhuma. Se precisar de outra referência, a planilha entregue não é aplicável na prática. |
| **[P-10]** *(fato, talvez só confirmar)* | A conta Google do gestor é Workspace ou pessoal? | Nada — a escolha de acesso já está fechada. O tipo de conta determina o fluxo de autorização. A Ferramentas intitula o ônus como "Autorização na conta **pessoal**", mas o texto fala em "sair da organização", que sugere Workspace — pode ser só confirmar, não decidir. |
| **TOML da rodada** *(ato, recorrente)* | Escrever e manter o arquivo de parâmetros da semana. | **Nenhuma sexta roda sem ele**, e o arquivo-modelo é recusado de propósito, para não sair planilha de aparência normal sobre números ilustrativos. Enquanto os parâmetros forem provisórios, é ato semanal. |

## 5. Não bloqueia nada hoje

| Id | Pergunta | Situação |
|---|---|---|
| **nº 9** — política de retenção | Por quanto tempo o Registro guarda o histórico antes de expurgar? | Sem TTL nem expurgo: o banco cresce indefinidamente. Nada quebra. |
| **[P-14]** | Qual provedor comercial de modelo o sistema usa? | Nada depende dele hoje: o Redator é template, o Analista de Perfil é determinístico, e a D-010 tirou o modelo do Coletor Externo. Bloqueia a camada consultiva do crivo prevista na D-017. |

---

## ⚠ Aviso de deriva — leia antes de decidir os pesos

Ao conferir os números desta fila contra a base, em **2026-09-02**, o portão de números encontrou uma diferença grande em relação ao que o PRD publica (medição de 28/08). Não é erro de implementação: o código embarcado e uma consulta independente chegam ao mesmo funil, e duas outras medições documentadas continuam batendo.

| Referência | PRD (28/08) | Medido (02/09) | Diferença |
|---|---|---|---|
| Imóveis elegíveis | 10.290 | **7.801** | −24% |
| Candidatos ao super destaque (≥ R$ 700 mil) | 4.852 | **3.562** | −27% |
| Distritos com ≥2 corretores produtivos | 61 | **45** | −26% |
| **Folga GERAL** — elegíveis contra as 6.970 posições | **48%** | **~12%** | — |
| **Disputa no super destaque** — candidatos por vaga | **10,2** | **7,5** | −27% |
| **Folga no destaque** — candidatos por vaga | **1,5** | **1,13** | −25% |

*As três últimas linhas medem coisas diferentes e o PRD às vezes as confunde: a "folga geral" compara todo o universo elegível com o total de posições; as outras duas são por nível, e são elas que governam cada objetivo de ranking.*

**Causa aparente:** queda de produtividade de corretor, que derruba a regra de capacidade do distrito. As três primeiras etapas do funil (ativos, categorias, preço) variaram menos de 0,25% — a diferença nasce toda na etapa das cinco regras restantes.

**Por que isso importa para as suas decisões — e os dois níveis se moveram, não só um:**

- **No destaque**, o PRD desenha um nível com folga, onde o problema é *não deixar benefício contratado sem uso*. Com 1,13 candidato por vaga, as posições ainda enchem, mas por pouco. Se a trajetória continuar, o relaxamento deixa de ser plano B e passa a ser o mecanismo que enche a cota.
- **No super destaque**, o PRD fixa o objetivo de ranking sobre "disputa real — mais de dez candidatos por posição". Essa frase **deixou de ser verdadeira**: são 7,5. É justamente o nível onde os pesos do nº 12 mais decidem quem entra, e onde o invariante 7 proíbe relaxar para compensar.

**O que isto NÃO é:** uma decisão sua nova, nem uma correção já aplicada. É uma **medição única, de um dia**, que ainda não foi incorporada ao `docs/mapa-de-dados.md` — e uma medição só não distingue deriva estrutural de oscilação. Está aqui porque você vai decidir os pesos lendo este documento, e decidir peso de ranking acreditando em folga de 48% quando ela é de 12% é decidir sobre um sistema que não existe mais.

**Este aviso tem prazo.** Incorporar a medição aos números de referência é a **fatia seguinte** — ela repete a contagem noutro dia antes de mexer em qualquer referência, e toca PRD, `CLAUDE.md` e `docs/mapa-de-dados.md`, que hoje ainda dizem 48%. Quando ela entrar, este bloco encolhe para um ponteiro. Enquanto isso, este é o único lugar do repositório onde a medição está escrita.

---

## O que NÃO está nesta fila

Duas categorias ficam de fora de propósito, para a fila não misturar o que é seu com o que é meu:

- **Dívida técnica minha**: publicação no Drive e envio por e-mail, adapter do Canal Pro, reuso da coleta de reserva, produtor da variação de volume, política de repetição, e a atualização do PRD e da Spec para incorporar decisões já tomadas. Registrada em `docs/decisoes.md` e no `bug.md`.
- **Lacuna de especificação**: a Spec §9 declara que o mecanismo de e-mail e de arquivamento no Drive **não é coberto**. Não é decisão sua — é spec a estender, trabalho meu. O que resta do seu lado são [P-10] e [P-11].
