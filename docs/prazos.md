# Inventário dos prazos

Toda constante de tempo do sistema, com **quem a renova e com que período**.

## Por que este documento existe

Um defeito de 03/09/2026 mostrou que a classe tem forma própria. O batimento do
trabalhador era dado **uma vez por ciclo**, antes de a rodada começar; o console
declara morto quem não bate há 30 segundos; e uma sexta leva minutos. Em toda rodada
real, meio minuto depois do disparo, a tela diria *"o trabalhador não está no ar"* —
falso, e justamente na tela feita para tranquilizar quem acabou de disparar. Pior: o
alarme falso é o que mais provavelmente faria alguém **matar o processo no meio**,
arriscando a rodada duplicada que a fila existe para impedir. Um defeito de mensagem
virando defeito de dados, pela mão do operador.

Nenhum teste o pegaria, e vale entender por quê — porque a explicação intuitiva está
errada. A fumaça roda em 60 segundos e o prazo é de 30: **o alarme falso estava dentro
da janela observável**. Ele não escapou por a execução ser curta; escapou porque nada
**afirmava** nada sobre o batimento, e a validação era um humano olhando a tela. A
lição não é "rode mais tempo": é *todo prazo precisa de uma asserção sobre a cadência
de quem o renova*.

**A propriedade que define a classe:** todo prazo cria um par *prazo × renovador*. O
defeito nasce quando o renovador tem período maior que o prazo, quando não existe, ou
quando existe só num dos caminhos. A lista abaixo é finita — é isso que torna a caça
sistemática em vez de sorte.

## Prazos NOSSOS

| Prazo | Onde | Quem renova | Período | Folga |
|---|---|---|---|---|
| Trabalhador considerado morto | `console/lib/operacao.ts` — 30 s | `_acompanhar`, na thread que corre junto da rodada | 5 s | 6× |
| Sondagem do progresso | `src/executar/trabalhador.py` — 0,5 s | — (é o próprio laço) | — | — |
| Recarga da tela de acompanhamento | `app/trabalho/[id]` — 5 s | navegador | 5 s | — |
| Espera pelo fim do acompanhamento | `trabalhador.py` — `join(timeout=5)` | — | — | avisa se estourar |
| Consulta do console | `console/lib/db.ts` — `statement_timeout` 15 s | — | — | — |
| `lock_timeout` do checkpointer | `executar/aprovar.py` — 30 s | — | — | — |
| `statement_timeout` do checkpointer | `executar/aprovar.py` — 120 s | — | — | — |
| Leitura do MySQL | `dados/newcore.py` — `LEITURA_MYSQL_S` 600 s por consulta (era 120; a consulta de candidatos mediu 109 s em 03/09/2026 e duas rodadas caíram no teto). A sexta faz ≥4 consultas: pior caso ~40 min em `executando` antes do código 3, com batimento vivo | — | — | — |
| Conexão ao MySQL | `dados/newcore.py` — `connect_timeout` 30 s | — | — | — |

**O único par prazo × renovador do sistema é o primeiro**, e foi exatamente onde o
defeito apareceu. Os demais são tetos de operação isolada: estouram, falham alto, e não
dependem de ninguém os renovar.

## Prazos que NÃO são nossos

Estes não aparecem em execução curta, não são falha de código, e **todos produzem
rodada degradada ou abortada quando o insumo existia**. São o que a classe vira quando a
sexta real, com raspagem, passar a durar horas.

| Prazo | De quem | O que se sabe |
|---|---|---|
| Sessão autenticada do Canal Pro | portal | **Duração desconhecida e nunca medida.** A sessão é capturada uma vez no início e reusada nas ~551 requisições. Se expirar na página 300, o resultado é falha com o CSV meio cheio. Registrado no mapa de dados |
| `wait_timeout` do MySQL do Newcore | Newcore | Não medido. A conexão é aberta pela coleta e a rodada segue por minutos depois |
| `max_execution_time` do MySQL do Newcore e o idle-TCP de proxy/NAT no caminho | Newcore / rede | **Não medidos.** Com `LEITURA_MYSQL_S` em 600 s, são eles que passam a cortar uma consulta longa — falha com a mesma cara (`OperationalError`, código 3) |
| Token do Google Drive | Google | Ainda não existe — chega com a publicação da planilha (`[P-11]`) |
| Cadência do espelho `FT_RealtyRelation` | Newcore | Atrasa **mais de 24 h**; registrado em `bug.md` e parcialmente corrigido |

## Como testar esta classe

1. **Injete o relógio, não durma.** O que trava o teste é esperar. `BATIMENTO` é
   constante de módulo justamente para um teste poder torná-la zero e provar a
   **cadência** em milissegundos — que é o que o defeito era. Provar *uma* batida não
   basta; foi o que o primeiro teste fazia.
2. **Mate a dependência, não o processo.** Fechar a conexão do acompanhamento no meio e
   exigir que o batimento **volte** é o único teste que prova a resiliência que o código
   afirma ter. Sem ele, a frase do CHANGELOG era mais forte que o código — e foi.
3. **Conte conexões.** Uma fumaça longa que compare `pg_stat_activity` antes e depois
   pega a família inteira de vazamento, inclusive a thread que sobrevive a um `join`
   estourado.

## Duas perguntas para a revisão

Custam uma linha e teriam pegado o defeito que originou este documento:

- *Isto acontece uma vez — uma vez por quê, e quanto dura essa unidade?*
- *O teste que cobre isto dura mais que o prazo que ele deveria violar?*
