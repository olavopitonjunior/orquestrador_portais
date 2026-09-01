-- Persistência das "posições ainda vazias" do destaque (Spec §2.1): quantas das
-- 6.495 posições de destaque ficaram sem candidato depois do ranking E do
-- relaxamento. O domínio carrega isso em `ResultadoRelaxamento.deficit_restante`
-- — um TOTAL da rodada, não um número por regra cedida. A tabela `relaxamento`
-- guarda o per-regra (posições que dependeram de cada cessão); o déficit residual
-- é grandeza da rodada, então mora aqui, na `rodada`.
--
-- Sem esta coluna, `relaxamento.posicoes_vazias` ficava sempre 0 e o déficit se
-- perdia em silêncio — inclusive no pior caso (déficit sem nenhum reprovado a
-- recuperar, em que a tabela `relaxamento` fica vazia). Idempotente.

ALTER TABLE registro.rodada
    ADD COLUMN IF NOT EXISTS posicoes_vazias_destaque integer NOT NULL DEFAULT 0
        CHECK (posicoes_vazias_destaque >= 0);
