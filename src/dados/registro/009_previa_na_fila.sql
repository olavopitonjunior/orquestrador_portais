-- 009 — a PRÉVIA entra na fila de operação.
--
-- Tipo novo de trabalho: `previa` roda o funil de elegibilidade com os parâmetros
-- declarados na tela — sem raspagem, sem ranking, sem escrever no Registro — e
-- responde "com estes valores sobram N imóveis para 6.970 posições". É o elo entre
-- definir e rodar (plano da Fatia 5). Só lê o Newcore (invariante 1); o resultado
-- volta por arquivo e vira `trabalho_evento.resumo`, como o resumo dos agentes.
--
-- O CHECK de `tipo` da 006 é inline e sem nome: o Postgres o batizou
-- `trabalho_tipo_check`. Idempotente pelo DROP ... IF EXISTS antes do ADD, como as
-- demais: aplicadas à mão, em ordem lexicográfica, sem tabela de versões. A lista
-- precisa ser a MESMA de `dados.operacao.TIPOS` — há teste que compara as duas.

ALTER TABLE operacao.trabalho DROP CONSTRAINT IF EXISTS trabalho_tipo_check;
ALTER TABLE operacao.trabalho ADD CONSTRAINT trabalho_tipo_check CHECK (tipo IN (
    'sexta', 'segunda', 'canario', 'full', 'aprovar', 'publicar', 'previa'));
