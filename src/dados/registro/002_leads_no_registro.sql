-- Alinhamento do Registro com a D-017: o ranking passou de TRÊS para QUATRO
-- fatores (semelhança, LEADS, desempenho, produtividade). O DDL 001 é anterior
-- à D-017 e só tem `nota_perfil`/`nota_desempenho`/`nota_gestor`; sem a coluna
-- de leads a decisão persistida perderia o fator F2. Esta migração acrescenta
-- `nota_leads` à `decisao_imovel`, ao lado das outras notas de fator.
--
-- Idempotente: `ADD COLUMN IF NOT EXISTS`. DEFAULT 0 cobre o (inexistente)
-- histórico; a camada de escrita sempre informa o valor.

ALTER TABLE registro.decisao_imovel
    ADD COLUMN IF NOT EXISTS nota_leads numeric NOT NULL DEFAULT 0;
