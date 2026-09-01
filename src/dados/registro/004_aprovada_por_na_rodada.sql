-- Registra QUEM/COMO aprovou a rodada de decisão (D-001). O carimbo de aprovação
-- de D-001 é "aprovada em <momento>, POR PRAZO" — ou seja, a fonte da verdade
-- deve distinguir a aprovação tácita (decurso de prazo) da explícita (o dono
-- clicou). Sem esta coluna, `aprovada_em` guardava só o instante e o "por prazo /
-- por quem" se perdia na borda de persistência (achado do revisor-de-regra na
-- fatia G2b/G3).
--
-- Nullable: rodadas ainda não aprovadas — e as anteriores a esta migração —
-- ficam com NULL. O CHECK amarra "por" a "em": não se registra quem aprovou sem
-- o instante da aprovação. Idempotente.

ALTER TABLE registro.rodada
    ADD COLUMN IF NOT EXISTS aprovada_por text;

ALTER TABLE registro.rodada
    DROP CONSTRAINT IF EXISTS aprovada_por_exige_instante;
ALTER TABLE registro.rodada
    ADD CONSTRAINT aprovada_por_exige_instante
        CHECK (aprovada_por IS NULL OR aprovada_em IS NOT NULL);
