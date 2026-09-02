-- 005 — o que faltava para `janela_destaque` ter produtor (D-021).
--
-- A tabela nasceu no 001 com os campos da Spec §2.1 e nada mais: sem ligação com a
-- carga que a criou, sem nada que impedisse duas janelas abertas para o mesmo imóvel,
-- e sem como saber qual carga já foi acumulada nela. Enquanto ninguém escrevia, isso
-- não doía. O produtor da D-021 acumula ao longo de várias cargas, então as três
-- lacunas viram defeito no mesmo dia.
--
-- Idempotente (`IF NOT EXISTS` / `IF EXISTS`): as migrações são aplicadas à mão, sem
-- aplicador em ordem — pendência declarada em `escrita.py`, herdada aqui.

ALTER TABLE registro.janela_destaque
    -- A carga que ABRIU a janela. Sem isto, "esta janela veio desta decisão" não é
    -- reconstituível, e a D-001 põe o Registro como fonte da verdade.
    ADD COLUMN IF NOT EXISTS rodada_decisao_id bigint REFERENCES registro.rodada (id),
    -- A última CARGA já acumulada nesta janela. É a guarda de idempotência, e a chave
    -- é a carga por uma razão de regra, não de conveniência: a D-021 diz "a cada
    -- CARGA em que ele permanece, a janela acumula os leads do período e incrementa
    -- semanas_consecutivas". Chavear pela rodada de acompanhamento não guardaria
    -- nada — cada reexecução da segunda abre uma rodada nova, com id novo, e o
    -- acúmulo aconteceria de novo. E contaria duas semanas quando duas segundas
    -- medissem a MESMA carga (uma sexta que não rodou, ou não foi aprovada), inflando
    -- uma permanência que não houve.
    ADD COLUMN IF NOT EXISTS ultima_rodada_decisao_id bigint REFERENCES registro.rodada (id),
    -- Rastreabilidade, não guarda: qual segunda tocou a janela por último.
    ADD COLUMN IF NOT EXISTS ultima_rodada_acompanhamento_id bigint
        REFERENCES registro.rodada (id);

-- No máximo UMA janela aberta por imóvel. Sob a D-021 a janela em curso é a unidade de
-- acumulação: duas abertas para o mesmo imóvel significariam leads somados em uma e
-- semanas na outra, sem nada acusando. Índice parcial — janelas ENCERRADAS repetem-se
-- por imóvel de propósito, que é o histórico.
CREATE UNIQUE INDEX IF NOT EXISTS janela_aberta_unica_por_imovel
    ON registro.janela_destaque (imovel_id) WHERE fim IS NULL;

-- Janela que termina antes de começar é erro de fiação, não dado.
ALTER TABLE registro.janela_destaque
    DROP CONSTRAINT IF EXISTS janela_fim_nao_precede_inicio;
ALTER TABLE registro.janela_destaque
    ADD CONSTRAINT janela_fim_nao_precede_inicio CHECK (fim IS NULL OR fim >= inicio);

-- Acumulados não retrocedem.
ALTER TABLE registro.janela_destaque
    DROP CONSTRAINT IF EXISTS janela_acumulados_nao_negativos;
ALTER TABLE registro.janela_destaque
    ADD CONSTRAINT janela_acumulados_nao_negativos
        CHECK (leads_gerados >= 0 AND semanas_consecutivas >= 1);

-- A leitura da sexta busca janelas ENCERRADAS por imóvel (penalidade §6.4). O índice
-- do 001 é (imovel_id, inicio DESC) e serve à abertura; este serve ao consumidor.
CREATE INDEX IF NOT EXISTS janela_encerrada_por_imovel
    ON registro.janela_destaque (imovel_id, fim DESC) WHERE fim IS NOT NULL;
