-- 006 — o esquema `operacao`: a fila que o console escreve e o trabalhador executa.
--
-- Por que um esquema NOVO, e não mais tabelas em `registro`. O `registro` é o trilho
-- de auditoria da DECISÃO: sob a D-001 ele é a fonte da verdade sobre o que a rodada
-- decidiu, e a segunda mede contra ele. Fila de trabalho, rascunho de parâmetro,
-- link de publicação e adiamento são OPERAÇÃO — dizem respeito a quem clicou e
-- quando, não ao que foi decidido. Misturados, uma consulta de auditoria passaria a
-- ter de saber distinguir as duas coisas, e a fronteira apodreceria na primeira
-- pressa.
--
-- Por que existe. O console é uma aplicação web e a rodada leva minutos; disparar por
-- `spawn` dentro de uma requisição significa processo que morre no hot-reload, sem
-- dedup, sem cancelamento e sem ninguém para observar a transição — a linha ficaria
-- "executando" para sempre. Aqui o console só INSERE; um trabalhador de processo
-- separado reivindica e executa. O estado vive no banco, então nada precisa
-- sobreviver ao reinício do servidor de desenvolvimento.
--
-- Idempotente (`IF NOT EXISTS`): as migrações são aplicadas à mão, em ordem
-- lexicográfica, sem tabela de versões — pendência declarada em `escrita.py`.

CREATE SCHEMA IF NOT EXISTS operacao;

-- Uma linha por DISPARO. Note que ela existe mesmo quando `registro.rodada` não
-- existir: uma rodada ABORTADA não deixa nenhuma linha no Registro (nem cabeçalho),
-- então sem esta tabela o motivo de um aborto viveria só no log do processo e sumiria.
CREATE TABLE IF NOT EXISTS operacao.trabalho (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tipo            text        NOT NULL CHECK (tipo IN (
                        'sexta', 'segunda', 'canario', 'full', 'aprovar', 'publicar')),
    estado          text        NOT NULL DEFAULT 'pendente' CHECK (estado IN (
                        'pendente', 'executando', 'ok', 'falhou', 'cancelado')),
    pedido_em       timestamptz NOT NULL DEFAULT now(),
    -- Quem clicou. O sistema NÃO sabe quem escreveu os parâmetros de uma rodada — o
    -- runner grava a procedência do ARQUIVO, não uma identidade —, e esta coluna é a
    -- primeira vez que o pedido tem autor. Não é autenticação: é o que o operador
    -- declarou de si, e a UI diz isso.
    pedido_por      text,
    iniciado_em     timestamptz,
    terminado_em    timestamptz,
    codigo_saida    integer,
    -- Os argumentos do comando, como o trabalhador os montou. Guardados para que uma
    -- execução seja reconstituível sem depender de quem lembrou do que clicou.
    argumentos      jsonb       NOT NULL DEFAULT '{}'::jsonb,
    -- Preenchido DEPOIS, quando a rodada nasce. Fica nulo em aborto e em dry-run.
    rodada_id       bigint      REFERENCES registro.rodada (id),
    pid             integer,

    CONSTRAINT trabalho_tempos_coerentes CHECK (
        (iniciado_em IS NULL OR iniciado_em >= pedido_em)
        AND (terminado_em IS NULL OR iniciado_em IS NOT NULL)
        AND (terminado_em IS NULL OR terminado_em >= iniciado_em)),
    -- Estado terminal exige desfecho, e não-terminal proíbe: sem isto, "ok" sem
    -- código de saída e "pendente" com código conviveriam, e a UI teria de adivinhar
    -- qual dos dois campos acreditar.
    CONSTRAINT trabalho_desfecho_coerente CHECK (
        (estado IN ('ok', 'falhou') AND codigo_saida IS NOT NULL AND terminado_em IS NOT NULL)
        OR (estado NOT IN ('ok', 'falhou') AND codigo_saida IS NULL))
);

-- A GUARDA CENTRAL: um trabalho em voo por tipo.
--
-- `gravar_rodada_decisao` não tem chave natural de deduplicação — duas chamadas
-- produzem duas rodadas, e nada no esquema do Registro impede. Um duplo-clique no
-- botão "rodar" criaria duas rodadas de sexta sobre o mesmo estoque, ambas válidas e
-- indistinguíveis. A dedup sobe de nível: aqui o segundo INSERT falha por unicidade
-- antes de qualquer processo nascer.
--
-- Parcial de propósito: trabalhos CONCLUÍDOS repetem-se por tipo indefinidamente, que
-- é o histórico. E por tipo, não global: raspar enquanto se aprova uma rodada antiga
-- é legítimo.
CREATE UNIQUE INDEX IF NOT EXISTS trabalho_um_por_tipo_em_voo
    ON operacao.trabalho (tipo) WHERE estado IN ('pendente', 'executando');

CREATE INDEX IF NOT EXISTS trabalho_recentes ON operacao.trabalho (pedido_em DESC);

-- O log de uma execução, linha a linha. É o que a tela de acompanhamento mostra.
CREATE TABLE IF NOT EXISTS operacao.trabalho_evento (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    trabalho_id bigint      NOT NULL REFERENCES operacao.trabalho (id) ON DELETE CASCADE,
    momento     timestamptz NOT NULL DEFAULT now(),
    nivel       text        NOT NULL DEFAULT 'info'
                            CHECK (nivel IN ('info', 'aviso', 'erro')),
    -- Qual nó do grafo terminou, quando a linha vem do fluxo da decisão. Nulo para
    -- linha de log comum.
    no_grafo    text,
    texto       text        NOT NULL
);

CREATE INDEX IF NOT EXISTS evento_por_trabalho
    ON operacao.trabalho_evento (trabalho_id, id);

-- O TOML que o dono declarou, VERBATIM, por submissão. Append-only: cada submissão é
-- uma linha nova, e isso é o versionamento — barato, e o histórico é o registro de
-- como os provisórios do dono evoluíram.
--
-- NÃO usa `registro.alteracao_parametro`: aquela tabela é a trilha de mudança de
-- parâmetro ADOTADO. O que sai do formulário é PROVISÓRIO, e o CLAUDE.md é explícito
-- que provisório não é adotado e não entra em `src/config`. Misturar os dois
-- destruiria a distinção que o projeto inteiro sustenta.
CREATE TABLE IF NOT EXISTS operacao.parametros_declarados (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    criado_em   timestamptz NOT NULL DEFAULT now(),
    por         text,
    toml        text        NOT NULL,
    -- Preenchido quando esta submissão vira uma rodada. Nulo enquanto é só rascunho.
    trabalho_id bigint      REFERENCES operacao.trabalho (id)
);

-- Onde a planilha foi publicada. Append-only, e NÃO uma coluna em `registro.rodada`:
-- sob a D-001 o link não é dado de decisão (a segunda mede pelo Registro, jamais pela
-- planilha do Drive), e uma coluna não teria onde guardar tentativa falha nem
-- republicação.
CREATE TABLE IF NOT EXISTS operacao.publicacao (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rodada_id    bigint      NOT NULL REFERENCES registro.rodada (id),
    destino      text        NOT NULL DEFAULT 'google_sheets',
    estado       text        NOT NULL CHECK (estado IN ('ok', 'falhou')),
    url          text,
    publicado_em timestamptz NOT NULL DEFAULT now(),
    por          text,
    CONSTRAINT publicacao_ok_tem_url CHECK (estado <> 'ok' OR url IS NOT NULL)
);

-- Batimento do trabalhador. Sem isto, o dono clica em "rodar", nada acontece, e não
-- há nada na tela explicando que o processo que executa não está no ar.
CREATE TABLE IF NOT EXISTS operacao.trabalhador (
    nome     text        PRIMARY KEY,
    visto_em timestamptz NOT NULL DEFAULT now(),
    pid      integer
);

-- "Não vou aprovar esta agora."
--
-- NÃO é reprovação: `registro.rodada` não distingue reprovada de não-decidida (as
-- duas deixam `aprovada_em` nulo) e, sob a D-001, silêncio já significa aprovação
-- tácita. Um botão "Reprovar" daria a sensação de ter agido enquanto o cartão
-- reapareceria para sempre e a thread do LangGraph ficaria queimada. Aqui se registra
-- CIÊNCIA, não veredito — e a distinção fica escrita na tela.
CREATE TABLE IF NOT EXISTS operacao.rodada_adiada (
    rodada_id bigint      PRIMARY KEY REFERENCES registro.rodada (id),
    adiada_em timestamptz NOT NULL DEFAULT now(),
    por       text,
    nota      text
);
