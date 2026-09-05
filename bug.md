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
- **Situação**: **mitigado, não resolvido.** A tela declara que o número é do arquivo acumulado e instrui a apagar o CSV antes de uma sonda limpa (com o aviso de que isso apaga também uma coleta completa anterior). A tela não afirma mais "o canário mostrou".

**O que resolve:** o raspador escrever o canário em arquivo próprio (`canalpro.canario.csv`, truncado a cada corrida) e o `status.json` dizer de qual modo é. Mudança no `coletor-externo`, com o leitor Python (`dados/coletor_externo.py::ler_coleta`) e a medição do console apontando para o arquivo certo. Fatia própria.

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
- **Situação**: **aberto, e é do dono.** A forma do F3 é parâmetro declarado (`externo.desempenho.forma`: `visualizacoes` | `nota` | `cliques_do_tipo`), PROVISÓRIO. Recomendação medida: declarar `forma = "nota"` (com `quando_ausente`) — é o único sinal com variância na amostra. Fica também a pergunta ao raspador: a API `listings` expõe visualizações em outro campo, ou só no detalhe do anúncio? (`QtdViewsZap` existe em `realties` no Newcore, mas é do banco, não do portal.)

## A idade da coleta saía −1 — `finishedAt` é UTC e a data era tirada no fuso da máquina

**Data**: 2026-09-03 (noite) · **Severidade**: baixa (número declarado errado na planilha; a porta de idade não fechava indevidamente) · **Onde**: `src/dados/coletor_externo.py::avaliar_coleta`

- **Esperado**: uma coleta feita hoje às 21h tem idade 0.
- **Ocorrido**: rodada 15474 declarou "idade do dado do portal: −1 dia(s)". O raspador grava `finishedAt` em UTC (`toISOString()`: `2026-09-04T00:04Z`) e a idade era `data_referencia − coletado_em.date()` — data em UTC. A primeira correção usou `astimezone()` sem argumento, que lê o fuso do SO: mesma entrada, idade diferente noutra máquina — o revisor provou com `TZ=Pacific/Pago_Pago` (invariante 5).
- **Afetou carga publicada?**: não.
- **Situação**: **resolvido em 2026-09-03 (noite)**: `FUSO_DA_OPERACAO = America/Sao_Paulo`, fixo e nomeado (fato operacional — a máquina do gestor —, não parâmetro de decisão), entra em `ParametrosExterno.fuso`; `finishedAt` sem offset é UTC por declaração. Teste com data fixa; suíte verde em três fusos.
