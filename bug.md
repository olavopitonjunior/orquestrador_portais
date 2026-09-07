# Registro de defeitos

## Formato

Cada entrada usa o modelo abaixo. O identificador é sequencial: `BUG-001`, `BUG-002`, …

O campo **Afetou carga publicada?** é o mais importante da entrada: um defeito que alterou uma vitrine que foi ao ar tem consequência diferente de um que quebrou antes da entrega. Nenhuma entrada é fechada sem esse campo respondido — se ainda não se sabe, a resposta é "em apuração", não em branco.

```markdown
## BUG-NNN — AAAA-MM-DD

- **Onde ocorreu**: <agente do produto ou etapa: Orquestrador, Coletor Interno, Coletor Externo,
  Analista de Perfil, Decisor, Redator, Monitor Operacional, Registro, entrega, infraestrutura>
- **Esperado**: <o que deveria ter acontecido>
- **Ocorrido**: <o que aconteceu>
- **Afetou carga publicada?**: <sim/não/em apuração; se sim, qual rodada e qual planilha>
- **Estado da rodada no momento**: <completa | degradada | abortada | fora de rodada>
- **Situação**: <aberto | em correção | resolvido>
```

---

<!-- Entradas abaixo desta linha, mais recente primeiro. -->

## A suíte de testes contra o banco vigente derruba o trabalhador vivo

- **Onde ocorreu**: infraestrutura (fila de operação + trabalhador), 2026-09-05
- **Esperado**: a suíte cria trabalhos dentro de transações desfeitas no fim de cada teste, invisíveis a quem está fora delas; o trabalhador vivo nunca os vê.
- **Ocorrido**: com o trabalhador no ar durante `uv run pytest`, ele reivindicou um trabalho criado pela suíte (`operacao.trabalho` id 4245) que o rollback do teste desfez em seguida; ao concluir, `concluir()` recusou ("não estava 'executando'") e a exceção — fora do `try` do ciclo — matou o laço inteiro. O console passou a mostrar "trabalhador fora". Já se sabia que a suíte podia vazar linhas `pendente` (comentário em `criar()`); o efeito de derrubar o processo é novo. Só acontece na máquina de quem desenvolve com o trabalhador ligado; em produção não há suíte.
- **Afetou carga publicada?**: não
- **Estado da rodada no momento**: fora de rodada
- **Situação**: em correção — o fechamento do ciclo passou a ser resiliente (`_fechar` sob `except ValueError`, o laço continua e loga). A causa (suíte e trabalhador no mesmo banco) segue aberta: a saída é um banco de teste separado, ou a suíte recusar rodar com trabalhador vivo.

## O espelho lido pela coleta interna está defasado — a sexta pode propor imóvel já removido

**Data**: 2026-09-02 · **Severidade**: alta (gasta posição contratada) · **Onde**: Coletor Interno — `src/dados/coletor_interno.py`, a coluna `publicacao_ativa` e o `WHERE` de `_SQL_CANDIDATOS` (âncora textual de propósito: número de linha dessincroniza)

- **Esperado**: o universo de candidatos da sexta contém apenas imóveis efetivamente anunciáveis no momento da rodada.
- **Ocorrido**: contém imóveis já removidos ou já vendidos, por **duas causas medidas** em 2026-09-02.
- **Afetou carga publicada?**: **em apuração.** O mecanismo está presente hoje e nada indica que tenha começado agora; não foi verificado contra as cargas já aplicadas. Responder isto exige cruzar as decisões gravadas em `registro.decisao_imovel` com o histórico de status — não feito nesta fatia.
- **Estado da rodada no momento**: fora de rodada (medição direta no banco, somente leitura).
- **Situação**: **causa 1 resolvida** (a regra de status passa a ver o transacional); **causa 2 aberta**, contingente à [P-20].

**Causa 1 — o espelho atrasa (defeito sob qualquer leitura). RESOLVIDA em 02/09/2026.** A coleta lê `newcore_bi.FT_RealtyRelation`, mantido incrementalmente. Das 82 remoções (`Ativo → Removido`) das últimas 24 h, **70 ainda constavam `Ativo` no espelho — 85,4%**. Como sinal separado de defasagem corrente, `MAX(RealtyUpdate)` marcava 07:30 contra `MAX(realties.UpdatedAt)` às 18:38 do mesmo dia; são 11 h, e quem sustenta o "mais de 24 h" é o 70 de 82, não esse par.

**Causa 2 — a venda não move o status (contingente à [P-20]).** `FT_RealtyRelation.RealtyStatus` é binário (`Ativo` 48.881 / `Removido` 356.172): não existe "Vendido" nem "Reservado". **24,69% (40 de 162) dos imóveis distintos com venda assinada em 180 dias seguem `Ativo`.** Esta causa **deixa de ser defeito** sob a leitura 3 da [P-20] ("a saída é tratada fora do sistema"); a causa 1 é defeito em qualquer leitura.

**Por que não corrigi nesta fatia:** corrigir muda o universo de candidatos — cruzar com `newcore.realties`/`realtystatushistory_new` é **mudança em regra de decisão**, com CHANGELOG e revisão próprios. Registrado em `docs/decisoes.md` (seção da rotação) e aqui, porque é comportamento em execução e não divergência entre documentos.

**Como a causa 1 foi resolvida:** a coluna `publicacao_ativa` da coleta passou a exigir as duas fontes — `(f.RealtyStatus = 'Ativo' AND COALESCE(r.PublishStatus_Id, 0) = 1)` —, mantendo o `WHERE` no espelho. O imóvel defasado **entra** como candidato e **reprova** em `Regra.STATUS_ATIVO`, com motivo registrado na aba de excluídos, em vez de sumir do universo sem deixar linha. Não volta por relaxamento: status não é regra relaxável. Medido em 02/09: reprova **86** imóveis (0,176% do recorte), todos `Removido` e todos saídos do ar nas últimas 24 h; efeito no funil de **−12 elegíveis e −2 candidatos ao super** na definição de distrito adotada (`PRODUTIVOS`).

**O que a correção NÃO faz, declarado:** o caminho inverso segue descoberto — **54** imóveis publicados que o espelho ainda não viu (51 criados nas últimas 24 h, 44 com preço ≥ R$ 300.000) continuam invisíveis, porque sem linha no espelho não há distrito nem gestor para avaliar, e é o espelho que define quem é candidato. Não gasta posição paga — é oportunidade perdida, não desperdício —, mas é a mesma defasagem do espelho (~13,5 h na medição das 21:00; o parágrafo da causa 1 cita outro instante do mesmo dia). **Fatia própria.**

**Causa 2** segue aberta e depende da [P-20]. Achado do levantamento da fatia da rotação.

## Memoização das fontes não é thread-safe — amarrado ao parâmetro nº 4

**Data**: 2026-09-01 · **Severidade**: latente (sem corrida alcançável hoje) · **Onde**: `src/executar/sexta.py` (`_fontes`) e `src/executar/segunda.py` (`_fontes`)

Os dois runners memoizam com `if not cache: cache.append(...)`, sem trava. O `invoke` síncrono do LangGraph executa o fan-out em thread pool, então duas threads podem passar pelo teste antes de qualquer uma preencher o cache — e o Newcore seria consultado duas vezes, com as duas leituras podendo divergir.

**Por que não corrigi agora, e não é preguiça:** hoje só `no_analista_perfil` chama `coletar_vendas`, então não há corrida alcançável; o mesmo padrão já está mergeado na segunda, e consertar só a sexta cria assimetria entre os dois runners; e o gatilho real é o **retry do Orquestrador — parâmetro pendente nº 4, nulo**, que é a mesma fatia que torna vivo o problema de reexecução do nó de registro (hoje resolvido por `capturado[-1]`).

**Quando tratar**: junto da definição do parâmetro nº 4, com um `threading.Lock` nos dois runners de uma vez. Achado do `revisor-de-codigo`.

## A fila de operação pode encravar em definitivo, e nada a destrava

**Agente:** — (infraestrutura de operação) · **Aberto em:** 2026-09-03 · **Afetou carga publicada?** não

A guarda que impede rodada duplicada é um índice parcial único: um trabalho por tipo
enquanto `pendente` ou `executando`. Se o trabalhador morrer sem poder concluir — SIGKILL,
queda de energia, contêiner derrubado —, a linha fica `'executando'` para sempre e **todo
trabalho daquele tipo passa a ser recusado**, em definitivo. A única saída hoje é SQL na mão.

Já aconteceu de forma acidental, e é assim que se sabe que dói: seis linhas de teste
vazaram para o banco vigente em 03/09 (um `conn.transaction()` que, sendo o mais externo,
commitava) e travaram a fila de cinco tipos até serem removidas manualmente.

O material para consertar já existe e está parcialmente ocioso: `'cancelado'` está no CHECK
e nenhum código o escreve. O `visto_em` **deixou de ser ocioso em 03/09** — o console o lê
para avisar que o trabalhador não está no ar —, mas ninguém o usa para RECUPERAR trabalho
órfão, que é a metade que falta. Falta a peça que
os liga — algo que, ao arrancar, marque como `cancelado` o que está `executando` sob um
`pid` que não existe mais, ou cujo batimento envelheceu além de um limite.

**Não corrigido nesta fatia** porque nem console nem agendador existem ainda, e a decisão
de "quanto tempo sem batimento significa morto" é parâmetro que ninguém definiu — inventá-lo
seria valor inventado. Precisa estar resolvido **antes** de o sistema ir para a máquina do
gestor sem supervisão.

## O console nunca vai ligar um trabalho à rodada que ele produziu

**Agente:** — (infraestrutura de operação) · **Aberto em:** 2026-09-03 · **Afetou carga publicada?** não

`operacao.trabalho.rodada_id` existe, tem chave estrangeira e docstring explicando quando
fica nula. Mas **nenhum chamador a preenche**: o trabalhador chama `concluir()` sem o
argumento, e não há outro caminho. Uma rodada real gravará `NULL` do mesmo jeito que um
modo seco — e aí o acervo do console não consegue dizer qual execução produziu qual rodada.

Escapou porque o teste de fumaça foi em modo seco, onde `NULL` é a resposta certa.

**RESOLVIDO em 2026-09-03, na fatia F4.** O runner passou a escrever um arquivo de
resultado em TODOS os caminhos de saída (`--resultado`), com o `rodada_id` declarado; o
trabalhador o lê e o passa a `concluir()`. Parsear a prosa do log era a alternativa, e
faria uma mudança de redação virar defeito de integração. Uma guarda estrutural exige que
todo `return` de `main` escreva o arquivo antes de sair — verificada por mutação.

## `npm` vem do PATH herdado, e sob agendador ele não está lá

**Agente:** Coletor Externo (disparo) · **Aberto em:** 2026-09-03 · **Afetou carga publicada?** não

O trabalhador executa `npm run canary|full` contando com o PATH do processo. Sob `launchd`
no macOS o PATH é mínimo (`/usr/bin:/bin:/usr/sbin:/sbin`) e um `npm` de homebrew, nvm ou
mise não está nele. Some-se que o `mise.toml` da raiz fixa Python e **não fixa node**,
enquanto o `package.json` do coletor exige `>= 22`: um `npm` herdado pode rodar o raspador
na versão errada sem erro nenhum.

**Mitigado, não resolvido:** a mensagem de erro passou a NOMEAR o executável ausente e a
apontar o PATH mínimo do agendador — antes dizia só `FileNotFoundError`, verdadeiro e
inútil. Falta resolver o binário no arranque e fixar node no `mise.toml`.

## A lista de etapas do console é cópia manual do grafo, sem vínculo

**Agente:** — (console) · **Aberto em:** 2026-09-03 · **Afetou carga publicada?** não

`console/lib/operacao.ts` declara as sete etapas do grafo à mão, e `src/grafo/fluxo.py` as
define. Os nomes batem hoje — conferidos um a um —, mas **nada os prende**: um nó renomeado
no Python passa limpo pelo teste do console, que trava tamanho, primeiro e último, não os
nomes do meio. O sintoma seria uma etapa que nunca acende, sem erro nenhum.

É a mesma classe do "8 de 7 anunciadas" que esta fatia consertou, e da divergência que a
F5 resolveu no formulário — lá a correção foi **gerar** o contrato a partir do validador,
com um passo de CI comparando byte a byte. O mesmo caminho serve aqui: o grafo pode emitir
sua topologia, e o console consumir a cópia travada.

**Não corrigido nesta fatia** por escopo: a F6 entrega o disparo e o acompanhamento, e
acrescentar um segundo contrato gerado misturaria duas mudanças com riscos diferentes.

## A ação que dispara a rodada é um endpoint sem autenticação

**Agente:** — (console) · **Aberto em:** 2026-09-03 · **Afetou carga publicada?** não

`"use server"` faz de `dispararSexta` um endpoint HTTP alcançável por qualquer página aberta
no navegador do dono — sem origem confiável, sem autenticação —, e `por` é autodeclarado (a
própria tela diz isso). Até a F5 o pior desfecho era gravar uma linha de parâmetros
provisórios. **A partir da F6 é disparar rodada real**, que grava no Registro e escreve a
planilha.

O que limita o estrago hoje: o console escuta só em `127.0.0.1`, roda na máquina do gestor,
a fila recusa dois trabalhos do mesmo tipo em voo, e a rodada revalida os parâmetros ao
carregar. É aceitável enquanto essas quatro condições valerem — e nenhuma delas é
verificada por código.

**Fica registrado em vez de implícito.** Qualquer exposição de rede exige autenticação
antes; e o dia em que o console deixar de ser local, este item vira bloqueio.

**Alcance ampliado em 03/09:** a guarda que impede disparar com uma declaração de
parâmetros diferente da que o dono viu depende de o cliente informar qual viu. Contra a
corrida real — outra aba, outra pessoa — funciona; contra um POST direto, não, porque
quem chama pode omitir o dado. É a mesma ausência de autenticação, por outra porta.

## O canário e a coleta completa escrevem no mesmo CSV, sem limpeza — a sonda da amarração mede o acúmulo

**Data**: 2026-09-03 · **Severidade**: média (diagnóstico enganoso; não gasta posição) · **Onde**: Coletor Externo — `coletor-externo/src/run.ts` (o `CsvWriter` de `canalpro.csv` é append-only e o mesmo nos dois modos); a medição em `console/lib/coletor.ts::amarracaoDoCsv`

- **Esperado**: a sonda "quantas linhas têm `codigoImovel` numérico" descreve o que o ÚLTIMO canário trouxe, para decidir em segundos se vale raspar em volume.
- **Ocorrido**: descreve `out/canalpro.csv` inteiro — uma coleta completa antiga de 55 mil linhas mais N canários repetidos. Um formato antigo numérico pode mascarar um novo não-numérico (o portão da coleta completa abriria indevidamente), e três canários de 100 viram "300 linhas". Achado do `revisor-de-codigo` na fatia A3.
- **Afetou carga publicada?**: não — a medição é diagnóstico do console; a rodada lê o CSV com dedupe por `idPortal` e aplica as portas de amarração e idade por conta própria.
- **Estado da rodada no momento**: fora de rodada.
- **Situação**: **RESOLVIDO em 2026-09-06.** O canário passou a escrever `canalpro.canario.csv`, truncado a cada corrida; a coleta completa tem arquivo próprio; o `status.json` declara o `mode` em todos os caminhos, inclusive nos de falha; `ler_coleta` e `amarracaoDoCsv` escolhem o arquivo pelo modo declarado. **A intenção — corrida nova ou retomada — deixou de ser inferida do disco e passou a ser declarada** (`coletor-externo/src/core/corrida.ts`), e `CsvWriter.init({truncar})` recebe a decisão do chamador em vez de adivinhá-la.
- **O que o defeito custou antes de ser corrigido**, medido em 06/09/2026 ao preparar a rodada amostral: o CSV tinha **1.910 registros para 1.300 `idPortal` distintos** — a coleta do dia empilhada sobre a de 04/09, com 300 duplicados — enquanto o `status.json` declarava 1.000. Agrava que `_linhas_do_csv` dedupa ficando com a **primeira** ocorrência: num arquivo contaminado, **o dado velho vence o novo**. A limpeza foi manual; a rodada 27976 só saiu íntegra porque alguém olhou.
- **Prova**: dois canários seguidos, com o Chrome real, deixam 1.000 registros e zero duplicados, batendo com `status.rows`. Testes em `coletor-externo/test/corrida.test.ts` e `tests/test_coletor_externo.py`, provados por mutação.

## "Numérico" tem duas definições — `str.isdigit()` na rodada é mais frouxo que `/^\d+$/` no console

**Data**: 2026-09-03 · **Severidade**: baixa · **Onde**: `src/dados/coletor_externo.py::_imovel_id_de` (`codigo.isdigit()` seguido de `int(codigo)`) vs `console/lib/coletor.ts::amarracaoDoCsv` (`/^\d+$/`, ASCII)

- **Esperado**: as duas leituras concordam sobre quais `codigoImovel` amarram.
- **Ocorrido**: `str.isdigit()` aceita dígitos Unicode como `"²"` e `"١"`; para `"²"`, `int()` levanta `ValueError` e derruba a leitura do CSV inteira (falha ruidosa, não silenciosa); para `"١"`, `int()` converte e amarra um id que o console conta como não-numérico. Achado do `auditor-de-invariantes` (A2) e do `revisor-de-codigo` (A3).
- **Afetou carga publicada?**: não — nenhum CSV real foi lido ainda.
- **Situação**: **resolvido em 2026-09-03 (noite)**, junto com a chave real da amarração (`{Id}{letra}`): `_imovel_id_de` passou a `re.fullmatch(r"([0-9]+)[A-Z]?")`, com testes para `"²"`, `"١"` e `"１０"`; o console mede pelo mesmo formato. Issue #61.

## O diretório da raspagem é dito em três lugares, e só dois obedecem às variáveis de ambiente

**Data**: 2026-09-03 · **Severidade**: baixa (só sob configuração não-padrão) · **Onde**: `coletor-externo/src/core/config.ts` (`OUT_DIR`, default `./out` relativo a `coletor-externo/`), `console/lib/coletor.ts` (`COLETOR_OUT_DIR`, default `../coletor-externo/out` relativo ao console) e `console/app/rodada/nova/acoes.ts` (`SAIDA_DO_RASPADOR = "coletor-externo/out"`, literal, relativo à raiz que o trabalhador fixa)

- **Esperado**: a tela que diz "há uma coleta ok", a rodada que lê o CSV e o raspador que o escreve olham o MESMO diretório, sempre.
- **Ocorrido**: nas configurações padrão os três resolvem para `<raiz>/coletor-externo/out`. Quem definir `OUT_DIR` ou `COLETOR_OUT_DIR` passa a ter a tela olhando um diretório e a rodada lendo outro, sem aviso — a literal do disparo ignora as duas variáveis. Achado do `revisor-de-codigo` e do `orchestrator` na fatia A4.
- **Afetou carga publicada?**: não.
- **Situação**: **aberto, declarado** em comentário no `acoes.ts`. Correção: uma única fonte (variável lida pelo trabalhador ao montar `--externo`, e a mesma pelo console), com teste que os três resolvem igual. Fatia própria.

## Duas rodadas morreram no Coletor Interno por prazo de cliente — a fonte estava viva

**Data**: 2026-09-03 · **Severidade**: média (rodada abortada com a fonte disponível) · **Onde**: `src/dados/newcore.py`, `read_timeout` do pymysql (120 s); a consulta `_SQL_CANDIDATOS` do Coletor Interno

- **Esperado**: uma base mais lenta que o normal alonga a rodada; não a mata.
- **Ocorrido**: os trabalhos 2349 e 2416 (sextas em modo seco, disparadas pelo trabalhador à noite) saíram com código 3 e `OperationalError` no Coletor Interno. `SELECT 1` respondia em 0,2 s; a consulta de candidatos, medida em seguida, levou **109 s** — contra 62 s de rodada inteira pela manhã. O teto de 120 s por consulta estava a um soluço da variância normal da base.
- **Afetou carga publicada?**: não — modo seco, e a rodada abortou antes de qualquer entrega.
- **Estado da rodada no momento**: ABORTADA por falha de fonte (código 3), nas duas.
- **Situação**: **mitigado** neste fix: `read_timeout` de 120 s para 600 s por consulta (`LEITURA_MYSQL_S`, `docs/prazos.md` atualizado) — a causa (base carregada, consulta de 109 s) não muda; o teto foi alargado. O que o fix NÃO faz: o teto efetivo passa a ser do lado de lá — `max_execution_time` do MySQL ou o idle-TCP de proxy/NAT no caminho, além de `wait_timeout`/`net_write_timeout` —, **nenhum medido**; se algum for menor que 600 s, a falha muda de forma (conexão perdida em vez de estouro de leitura), com o mesmo código 3. E a forma da falha **não é observável hoje**: a sexta loga só `type(e).__name__`, então "caíram no teto de 120 s" é inferência (109 s medidos, errno nunca logado). O que fecha a pendência: logar `e.args[0]` quando for `pymysql.err.MySQLError` — é um inteiro (2013/2006), não ecoa dado do banco. Fatia própria.

## `visualizacoes` vem zero em todos os anúncios da API do Canal Pro — o F3 por visualizações não tem sinal

**Data**: 2026-09-03 (noite) · **Severidade**: média (o fator de portal entra no ranking sem discriminar ninguém) · **Onde**: Coletor Externo — a API `listings` do painel (`coletor-externo/src/portals/canalpro.ts`); a forma do F3 declarada em `[externo.desempenho] forma` (`docs/parametros-da-rodada.exemplo.toml`)

- **Esperado**: com a raspagem entrando, o F3 diferencia os imóveis pelo desempenho do anúncio no portal.
- **Ocorrido**: na primeira rodada real (trabalho 2790 → rodada 15474, 300 anúncios), `visualizacoes` veio `0` em **300 de 300**; os cliques também (contato ≠ 0 em 2, telefone em 1, WhatsApp em 0). A `nota` (LQS) tem **14 valores distintos** (9580 em 188, 8442.5 em 61, 9080 em 22…). Com a forma declarada `visualizacoes`, o min-max dá 0,0 para todos e `nota_desempenho` ficou 0 em todas as linhas gravadas — o F3 "entrou" e não pesou nada.
- **Afetou carga publicada?**: não — rodada amostral, inaprovável por construção.
- **Situação**: **A PREMISSA CAIU em 2026-09-06, e a decisão volta ao dono.** A medição de 03/09 foi sobre 300 anúncios; a primeira coleta COMPLETA, de **55.162 anúncios**, mostra **13.175 com visualizações diferentes de zero — 23,9 %**, e 69 valores distintos de nota. O zero não era do campo: era do tamanho da amostra. A D-028/D-034 adotou `portal.peso_visualizacoes = 0` justamente porque "medido zero em 300 de 300", e essa frase deixou de ser verdadeira. **Consequência hoje:** um sinal presente em quase um quarto do estoque não pesa nada na nota que ordena a vitrine. Rever o peso é decisão do dono (é parâmetro adotado, D-034); o que este registro faz é derrubar a premissa que o sustentava. A pergunta ao raspador está respondida por medição: a API `listings` **expõe** visualizações — o campo não estava vazio, a amostra é que era pequena.

## A idade da coleta saía −1 — `finishedAt` é UTC e a data era tirada no fuso da máquina

**Data**: 2026-09-03 (noite) · **Severidade**: baixa (número declarado errado na planilha; a porta de idade não fechava indevidamente) · **Onde**: `src/dados/coletor_externo.py::avaliar_coleta`

- **Esperado**: uma coleta feita hoje às 21h tem idade 0.
- **Ocorrido**: rodada 15474 declarou "idade do dado do portal: −1 dia(s)". O raspador grava `finishedAt` em UTC (`toISOString()`: `2026-09-04T00:04Z`) e a idade era `data_referencia − coletado_em.date()` — data em UTC. A primeira correção usou `astimezone()` sem argumento, que lê o fuso do SO: mesma entrada, idade diferente noutra máquina — o revisor provou com `TZ=Pacific/Pago_Pago` (invariante 5).
- **Afetou carga publicada?**: não.
- **Situação**: **resolvido em 2026-09-03 (noite)**: `FUSO_DA_OPERACAO = America/Sao_Paulo`, fixo e nomeado (fato operacional — a máquina do gestor —, não parâmetro de decisão), entra em `ParametrosExterno.fuso`; `finishedAt` sem offset é UTC por declaração. Teste com data fixa; suíte verde em três fusos.

## A prévia nunca carregou o `.env` — e o sintoma acusava o servidor

**Data**: 2026-09-05 · **Severidade**: alta (o único caminho de execução da prévia estava quebrado desde que ela nasceu) · **Onde**: `src/executar/previa.py::main`, ausência de `carregar_env()`; a lista escrita à mão em `tests/test_ambiente.py::test_todo_ponto_de_entrada_carrega_o_ambiente`

- **Esperado**: `python -m executar.previa --resultado <arquivo>` lê o Newcore como a sexta lê, com as credenciais do `.env`.
- **Ocorrido**: a prévia era o único ponto de entrada sem `carregar_env()`. Entrou assim no PR #75 e **nunca rodou contra um Newcore real** — só em teste, que não precisa de credencial. Sem ambiente, `_config()` levanta `RuntimeError` por variável ausente; a única tentativa real (trabalho 4172, 05/09 11:17) falhou em 1 segundo.
- **O que custou caro foi o sintoma, não o defeito.** `previa.py` loga só `type(e).__name__`, então o registro diz **`falha ao ler o Newcore: RuntimeError`** — indistinguível de fonte fora do ar. O diagnóstico foi para o servidor e ficou lá por horas: acusou-se rotação de senha, grant preso a host e necessidade de DBA no `newcore-prod`. Nada disso era verdade: o acesso sempre esteve bom, e o servidor autenticava normalmente os outros clientes da mesma máquina. **Se alguém procurar essa string num log, é esta entrada que responde.**
- **Duas armadilhas que prolongaram o erro**, ambas por testar *por fora* do código do projeto: carregar o `.env` com `set -a; . ./.env` (o shell expande o `$` da senha — proibido por `docs/mapa-de-dados.md:301`) e chamar `pymysql.connect` passando a credencial como `str` (o PyMySQL a codifica em **latin-1** e o servidor guarda o hash dos bytes **UTF-8** — as duas codificações divergem para qualquer valor que não seja ASCII puro, e a divergência aparece como `Access denied`, indistinguível de credencial errada). `dados.newcore._config()` já trata as duas desde 31/08. O que derrubou a hipótese errada foi o dono observar que o MCP de MySQL conectava normalmente com as mesmas credenciais.
- **Por que nenhum teste pegou**: o teste certo já existia, mas listava os módulos à mão — `sexta, segunda, aprovar, referencias` — e a prévia nasceu fora da lista.
- **Afetou carga publicada?**: não. A prévia não publica, não ordena, não escreve no Registro e nunca chegou a produzir saída.
- **Estado da rodada no momento**: fora de rodada (a prévia é trabalho próprio na fila).
- **Situação**: **resolvido em 2026-09-05.** `carregar_env()` entra em `previa.main`; a lista de pontos de entrada deixa de ser escrita à mão (`_pontos_de_entrada()` varre `src/executar/*.py` atrás de `def main(`), e a dispensa de `contrato` é afirmada por teste em vez de pulada, porque o CI recusa skip. Provado nos dois sentidos: sem a correção a guarda falha em `[previa]`; com ela, a prévia sai 0 contra o Newcore ao vivo (48.827 candidatos, 186 vendas, 7.009 elegíveis para 6.970 posições). **Fica aberta a metade não corrigida**: `previa.py` descarta `str(e)` e guarda só o nome do tipo — a próxima falha será igualmente opaca. Enriquecer a mensagem é fatia própria, porque `falha` é contrato asserido em `tests/test_previa.py` (o console lê o campo) e exige decidir antes se exceção de driver pode arrastar string de conexão para o log. É o mesmo pendente já registrado para a sexta, na entrada dos 120 s.

## `--full` sobre um checkpoint esgotado declarava sucesso sem coletar nada

**Data**: 2026-09-06 · **Severidade**: **alta** (dado velho entra como fresco numa carga aplicável, sem sintoma) · **Onde**: Coletor Externo — o laço de paginação de `coletor-externo/src/run.ts` e a ausência de remoção de `out/progress.json`

- **Esperado**: uma coleta completa que roda de novo, depois de uma anterior ter terminado, recomeça e traz dado do dia.
- **Ocorrido**: o checkpoint sobrevivia com `lastPage = totalPages`, então `start = totalPages + 1`, o laço **não iterava nenhuma página**, e o código escrevia `status.json` com `result: "ok"`, `rows` da corrida anterior e um **`finishedAt` novo**. A porta de idade do lado Python (máximo 2 dias, D-034) aceitava como fresco. Não havia nenhum `unlink` em todo o `src/` do raspador: o checkpoint era imortal por omissão.
- **Por que é o pior dos três**: não tem sintoma. O CSV existe, o status diz `ok`, a idade passa — e a rodada de sexta ordena a vitrine com o desempenho de portal de dias atrás.
- **Afetou carga publicada?**: não — nenhuma coleta completa real chegou a rodar duas vezes; o defeito foi achado por leitura, não por incidente.
- **Estado da rodada no momento**: fora de rodada.
- **Situação**: **resolvido em 2026-09-06.** `clearCheckpoint()` roda **antes** de declarar `ok` (morrer entre os dois perde a retomada, que é seguro; o inverso reproduz o defeito). O checkpoint ganhou `contrato`, `portal` e `modo`: só retoma sobre a mesma coisa, e um checkpoint sem `contrato` é da versão antiga e vira corrida nova, com log alto. Há ainda uma rede de segurança: se mesmo assim o checkpoint vier esgotado, a corrida se rebaixa para nova em vez de não iterar. Fecha de graça um defeito latente — `progress.json` não tem o portal no nome, então um segundo adapter retomaria o progresso do primeiro.

## `NEEDS_WARM.flag` nunca era removida, e o console prometia que sumia sozinha

**Data**: 2026-09-06 · **Severidade**: média (uma vez disparada, trava todas as rodadas seguintes) · **Onde**: Coletor Externo — `raiseNeedsWarm` criava a flag e nada a apagava; `console/lib/acoes.ts:23` afirmava o contrário

- **Esperado**: a flag sinaliza "a sessão caiu, re-logue"; some quando a próxima coleta autentica, como o console diz ao operador.
- **Ocorrido**: nenhum `unlink` no `src/` do raspador. Uma vez criada, `ler_coleta` devolvia `blocked` para sempre — ela faz OR entre a flag e o status —, independentemente de quantas coletas bem-sucedidas viessem depois, até alguém apagar o arquivo à mão. O console instruía o operador a re-logar por um problema que não era de login.
- **Afetou carga publicada?**: não — a flag não chegou a disparar em rodada real.
- **Estado da rodada no momento**: fora de rodada.
- **Situação**: **resolvido em 2026-09-06.** A flag é removida quando a **primeira requisição autenticada responde** — não ao capturar a sessão. A primeira versão da correção fazia isso e a revisão a reprovou: capturar cabeçalhos prova que a SPA disparou uma XHR, **não** que o portal aceita o token, e um 401 logo depois apagaria o alarme certo. Depois disso, e não no fim da corrida: um full que autentica e morre na página 900 provou o login, e mandar re-logar seria diagnóstico errado. Se a corrida autenticar e for bloqueada adiante, o tratamento recria a flag.

## 401 do portal não vira `blocked` — sai como erro genérico, sem flag

**Data**: 2026-09-06 · **Severidade**: baixa (diagnóstico enganoso; não corrompe dado) · **Onde**: `coletor-externo/src/core/corrida.ts`, o tratamento que só testa `BlockedError`

- **Esperado**: sessão expirada leva o operador a re-logar, que é o conserto.
- **Ocorrido**: `AuthExpiredError` existe e é levantada em `classificarResposta`, mas o tratamento só converte `BlockedError` em `blocked` + flag. Um 401 sai como `error`, sem flag, e o console mostra "a coleta falhou" em vez de "refaça o login".
- **Afetou carga publicada?**: não.
- **Situação**: **resolvido em 2026-09-06**, na mesma fatia. Eu havia decidido deixá-lo para outra, por mexer no significado de `exit 1` contra `exit 2`; a revisão de código mostrou que ele deixou de ser independente: com a flag passando a ser removida a cada corrida, um 401 que não a reergue apaga o alarme e devolve um diagnóstico errado ao operador. `AuthExpiredError` passou a ser tratado como `BlockedError` — o conserto dos dois é o mesmo, re-logar —, levantando a flag e saindo com código 2.

## O `status.json` era um arquivo só para os dois modos — o canário tornava a coleta completa inalcançável

**Data**: 2026-09-06 · **Severidade**: alta (a rodada de sexta perde o fator de portal da semana, com o console dizendo `ok`) · **Onde**: `coletor-externo/src/core/corrida.ts` (a escrita do status) e `src/dados/coletor_externo.py::ler_coleta` (a escolha do CSV pelo `mode`)

- **Esperado**: a rodada lê a coleta que lhe interessa — a completa numa sexta real, o canário numa amostral.
- **Ocorrido**: `status.json` era "a última corrida", e a última apagava o registro da outra. Como o leitor escolhe o CSV pelo `mode` declarado, **um canário de segundos rodado depois de uma coleta completa de horas tornava o full inalcançável**, com o `finishedAt` da sonda passando na porta de idade. Não é sequência hipotética: é a que o console prescreve, porque o canário é o portão que libera o full. Efeito colateral: `guardarGeracaoAnterior` lia o mesmo status, via `mode: canary` e recusava preservar a última geração boa — derrotando a função exatamente no caso para o qual ela existe.
- **Como apareceu**: o defeito era inofensivo antes da correção do contrato de arquivo. Só virou defeito **porque** aquela correção fez o leitor depender do campo `mode`. É a assinatura da fatia inteira: cada correção moveu a fronteira de um contrato de estado compartilhado, e o defeito seguinte nasceu na fronteira nova.
- **Afetou carga publicada?**: não — nenhuma coleta completa real chegou a rodar.
- **Situação**: **resolvido em 2026-09-06.** `escreverStatus` grava também `status.<modo>.json`; `status.json` segue sendo a última corrida, que é o que o card do console mostra. `ler_coleta` aceita o modo pedido, a amostral pede o canário que definiu a amostra e a rodada real pede a completa. Uma `out/` anterior à correção é migrada na primeira corrida, **antes de qualquer escrita** — sem isso o fallback de leitura morreria justamente na sequência canário-antes-do-full que o console prescreve.

## A retomada não declarava que estava em curso, e não conferia se o arquivo existia

**Data**: 2026-09-06 · **Severidade**: alta (coleta parcial declarada `ok`, com `rows` prometendo o que não está no arquivo) · **Onde**: `coletor-externo/src/core/corrida.ts` — o bloco de retomada

- **Esperado**: enquanto uma coleta apende linhas, quem ler `out/` sabe que ela está em curso; e retomar continua um arquivo que existe.
- **Ocorrido**: dois defeitos. **(1)** `escreverStatus('running')` estava dentro do `if (!retomando)`: numa retomada, o status vigente seguia dizendo `ok` com o `rows` da corrida anterior durante as horas em que linhas eram apendadas embaixo. **(2)** `podeRetomar` conferia coerência do checkpoint consigo mesmo e **zero sobre o disco**: com o checkpoint vivo e o CSV apagado à mão — que era o que o próprio console ensinava até esta fatia ("apague o arquivo antes de disparar o canário") —, a coleta saía parcial e declarada `ok`, com o `rows` do checkpoint prometendo o que não estava lá.
- **Afetou carga publicada?**: não.
- **Situação**: **resolvido em 2026-09-06.** `running` é declarado nos dois casos, porque uma retomada também está em curso; e retomar passa a exigir que o CSV do modo exista no disco, rebaixando para corrida nova com log alto quando não existe. Mesmo guard nos dois caminhos, linear e shards, cada um com teste.

## Um soluço de dez segundos do portal derruba treze minutos de coleta

**Data**: 2026-09-06 · **Severidade**: média (a sexta tem tentativa única por rodada; perder a coleta é perder o fator de portal da semana) · **Onde**: `coletor-externo/src/core/block-detector.ts::isTransient` e a ausência de repetição em `corrida.ts`

- **Esperado**: uma instabilidade momentânea do portal atrasa a coleta; não a mata.
- **Ocorrido**: a primeira tentativa da coleta completa morreu em 10 s com `Canal Pro GraphQL errors: Can not reach the API` — o gateway do portal respondendo **200** e dizendo, no corpo, que não alcançava o backend dele. O canário rodou um minuto depois e passou, e as duas consultas são **idênticas** (`probeList` faz a mesma chamada que o canário faz primeiro), o que descarta diferença de código. A segunda tentativa da coleta completa levou 13 minutos e trouxe 55.162 anúncios.
- **Por que não foi retentado**: `isTransient` classifica 429, 503 e falha de rede (`status -1`). Um **200 com erro de GraphQL** não passa por ele: `classificarResposta` levanta, e `executarComTratamento` traduz em `error` sem nova tentativa. O raspador não tem política de repetição.
- **Afetou carga publicada?**: não — a segunda tentativa foi manual e concluiu; a rodada 30417 saiu com dado íntegro.
- **Situação**: **parcialmente resolvido em 2026-09-06 — a classificação existe, a política de repetição não.** Das duas partes, a primeira era minha e está feita: `TransientError` nasceu ao lado de `BlockedError`/`AuthExpiredError`, `classificarResposta` levanta-o quando a mensagem de GraphQL descreve inalcançabilidade, o status ganha `retryable: true` e o console passa a dizer "rode de novo" em vez de "veja os logs do raspador". A segunda parte **segue com o dono**: quantas vezes tentar e com que intervalo é o **parâmetro nº 4, ainda nulo**, e nenhum laço automático foi criado — hoje quem repete é o operador, agora avisado. Fica registrado que o custo de não ter a política é uma coleta de treze minutos perdida por um soluço de dez segundos, numa rodada que só tem uma tentativa.
- **Três coisas que a correção obrigou a decidir, e que valem mais que ela**:
  1. **`isTransient` era código MORTO.** Existia desde a portabilidade, tinha teste, e **nenhum caminho de produção o chamava** — 429, 503 e falha de rede saíam como `resposta inesperada`, indistinguíveis de um defeito de consulta. Um classificador que ninguém chama é pior que classificador nenhum: dá a impressão de que o caso está coberto. O mesmo padrão sobrevive ao lado, e fica registrado sem conserto nesta fatia: **`isAuthExpired`** (a função) também não tem chamador em produção — `canalpro.ts` testa `resp.status === 401` inline. Não confundir com **`AuthExpiredError`** (a classe), que é lançada em `canalpro.ts:195` e capturada em `corrida.ts:432`: essa está viva e sustenta o caminho do re-login.
  2. **Bloqueio vence transitório, e a ordem é regra.** Um 503 servindo desafio do Cloudflare casa os dois classificadores. Consultar `isTransient` antes de `isBlockResponse` faria esse caso deixar de criar a `NEEDS_WARM.flag`: o operador nunca seria mandado re-logar, numa rodada de tentativa única. Achado do `orchestrator` no portão, antes do commit. Há teste dos dois lados do mesmo 503.
  3. **O vocabulário `ok|blocked|error|running` NÃO mudou, de propósito.** Dois consumidores fazem passthrough cru: `src/dados/coletor_externo.py` (`estado = status.get("result", "error")`) e `console/lib/coletor.ts`, cuja cadeia termina em `else estado = "ausente"`. Um valor novo de `result` viraria, no console, **"o raspador nunca rodou"** — a pior tradução possível para uma falha cuja resposta é rodar de novo. Por isso o sinal entrou como campo **aditivo** (`retryable` no status, `repetivel` na `SaudeColeta`): quem o ignora continua correto. É a lição da D-037 aplicada antes de doer, e não depois.

## A prontidão dizia "status ilegível" para uma coleta em andamento

**Data**: 2026-09-06 · **Severidade**: baixa (diagnóstico errado; nada corrompe) · **Onde**: `console/lib/prontidao.ts`

- **Esperado**: uma coleta completa em curso aparece como aviso, com a ação "espere ela fechar".
- **Ocorrido**: o estado `em_curso` foi acrescentado ao tipo `EstadoColeta` e tratado em `lib/acoes.ts`, mas `prontidao.ts` não acompanhou: caía no `else` final e reportava **"A última coleta ficou pela metade: o status está ilegível"**, em vermelho — o diagnóstico errado para a única situação em que a resposta é simplesmente esperar.
- **Como apareceu**: é a terceira ocorrência do mesmo padrão nesta série de fatias — **uma correção move a fronteira de um contrato e um consumidor não acompanha**. Aqui o contrato era o conjunto de estados da coleta.
- **Afetou carga publicada?**: não.
- **Situação**: **resolvido em 2026-09-06**, com teste provado por mutação. Reforça a regra de rito registrada na D-037: quando a fatia mexe em contrato compartilhado, enumerar os consumidores é o primeiro artefato, não o último.

## A página da rodada parseia a planilha inteira para exibir 300 linhas por aba

**Data**: 2026-09-06 · **Severidade**: média (custo por requisição numa máquina que também roda o banco e o trabalhador) · **Onde**: `console/lib/planilha.ts::lerPlanilha` e `console/app/rodada/[id]/page.tsx`

- **Esperado**: a página da rodada abre rápido e mostra as primeiras linhas de cada aba, com o CSV inteiro em disco.
- **Ocorrido**: `lerPlanilha` lê e parseia **todas** as abas de `ABAS`, inclusive `apuracao.csv` — 14 MB e 48.812 linhas na rodada 30417. A página tem o cuidado explícito de não EXIBIR a apuração (`ORDEM_DAS_ABAS` a omite, com comentário dizendo por quê) e de mostrar só 300 linhas das demais, mas paga o parse inteiro: **2.221.660 células materializadas e +251 MB de heap por requisição**, para usar 13.896 delas. *(A primeira versão deste registro dizia 41.958 excluídos — a contagem **antes** de a cedência do perfil recolocar 116. O arquivo gravado tem 41.842.)*
- **Por que só apareceu agora**: nas rodadas amostrais a apuração tinha 1.000 linhas. O defeito é de escala, e a primeira rodada completa é a primeira oportunidade de vê-lo.
- **DUAS AFIRMAÇÕES ERRADAS na primeira versão deste registro, corrigidas ao medir:**
  1. *"a resposta da página saiu com 23 MB"*. Os 23 MB eram do servidor de **desenvolvimento**, e não do que o gestor recebe. Construído em produção e medido no mesmo artefato, o payload é **1,05 MB antes e depois da correção** — a apuração parseada nunca esteve nele, porque nunca foi renderizada, e o RSC serializa o que a árvore produz, não o que o componente de servidor leu. O que inflava era a instrumentação de I/O do modo dev, que serializa o resultado de cada `readFile` para as ferramentas de depuração: o payload trazia um `fs.Stats` e um bloco de texto de **14.710.747 bytes, exatamente o tamanho do `apuracao.csv`**. Lição de método: número de servidor de desenvolvimento não é número de produção, e eu registrei um sem qualificar qual era.
  2. *"mexe no contrato de `lerPlanilha`, que tem outros consumidores (o download por aba e o zip)"*. `lerPlanilha` tem **um** consumidor, a página da rodada. O download e o zip usam `arquivoDaAba`, que devolve os bytes crus de uma aba por vez. A afirmação inflou o custo aparente da correção.
- **Afetou carga publicada?**: não — a página responde 200 e o conteúdo está correto.
- **Situação**: **resolvido em 2026-09-06**, com prova de mutação e prova de equivalência do parser.
  `lerPlanilha` passa a **exigir** `LimiteDeLinhas`, que diz quantas linhas de cada aba materializar. `Tabela` ganha `total`, exato mesmo com as linhas fora da memória: passado o limite a varredura continua com a mesma máquina de estados — inclusive o rastreio de "início de célula", sem o qual uma aspa no meio de célula não quotada abriria uma célula e corromperia a contagem — mas para de alocar. Medido no mesmo artefato: parse **238 ms → 66 ms**, células **2.221.660 → 131.601**, heap **+252 MB → +46 MB**, latência em produção **~0,25 s → ~0,15 s**, totais idênticos (48.812 e 41.842).

  **UMA REGRESSÃO no caminho, pega no portão do orquestrador antes do commit, e ela é a parte que vale guardar.** A primeira versão limitou TODAS as abas exibidas a 300, `destaque` inclusive — e a página **agrega** sobre `destaque.linhas`: conta `origem = "relaxamento"` para o painel "N pelo ranking + M por relaxamento". Os relaxados ocupam as **últimas** posições (da 6.380 à 6.495 em 2026-09-06), então ficam fora de qualquer prefixo e a conta daria **0 em vez de 116** — número falso na tela do dono sobre exatamente o mecanismo que a D-036 tornou o modo ordinário de encher a cota. Nada acusaria: tipo, build, os 156 testes e a contagem da aba continuam certos, porque `total` continua exato. Só quebra o AGREGADO. Corrigido limitando apenas `apuracao` e `excluidos_por_regra` — 94 % do custo, zero agregados —, com `destaque` e `relaxamento` inteiras, e `tests/abas-da-rodada.test.ts` travando as duas por nome; a mutação que reintroduz o limite devolve `esperado 116, obtido 0`.

  **A lição, e ela desce um nível abaixo do rito da D-037.** Aquele rito manda enumerar os consumidores quando a fatia mexe em contrato compartilhado. Eu enumerei — e acertei: `lerPlanilha` tem um consumidor. O que não enumerei foram os consumidores dos **dados que ela devolve**: `Tabela.linhas` tem cinco leitores na página, e **dois deles agregam**. Enumerar a função não basta; é preciso enumerar o dado. Foi exatamente essa a diferença entre o parser (provado por equivalência e mutação, impecável) e a página (quebrada em silêncio).
  **Custo que PERMANECE**: o arquivo de 14 MB ainda é lido inteiro para a string a cada requisição, porque contar registros exige varrer até o fim (uma célula entre aspas pode conter quebra de linha, então contar `\n` daria número errado). Ler por fluxo, sem materializar a string, é fatia própria — e só vale se a leitura virar gargalo, o que hoje não é o caso.
