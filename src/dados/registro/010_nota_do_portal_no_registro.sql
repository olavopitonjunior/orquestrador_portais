-- 010 — o Registro passa a guardar a nota como ela é desde a D-028, e o perfil
-- que filtrou (issue #79).
--
-- O que estava errado, e por que importa. `decisao_imovel` guardava as colunas do
-- desenho de quatro fatores (D-017): `nota_perfil`, `nota_leads`, `nota_desempenho`,
-- `nota_gestor`. Depois da D-028 a nota é a soma ponderada de TRÊS sinais do anúncio
-- e nenhum deles era gravado; `nota_desempenho` recebia a nota bruta dividida por 100
-- enquanto `nota_final` ficava em pontos de 100 — na fonte da verdade do sistema,
-- `nota_final` não fechava com as parcelas guardadas ao lado. Quem auditasse uma
-- rodada pelo Registro não conseguia refazer a conta.
--
-- O que esta migração NÃO faz: reescrever história. Medição de 05/09/2026 antes de
-- decidir: a tabela tem 14.350 linhas em 4 rodadas, TODAS anteriores ao commit que
-- trouxe a D-027/D-028, todas degradadas, nenhuma aprovada, e `nota_desempenho` vale
-- ZERO em 100% delas. Ou seja, não há linha alguma com a semântica nova, e não há
-- informação a preservar naquela coluna — mas também não há razão para apagá-la num
-- banco vivo. Por isso:
--
--   * `nota_leads` e `nota_gestor` são RENOMEADAS. A semântica é a mesma nos dois
--     mundos — leads e produtividade do gestor, normalizados em [0, 1] —, só o papel
--     mudou (eram fator, viraram desempate). Renomear preserva o histórico e o torna
--     legível.
--   * `nota_perfil` e `nota_desempenho` ganham o prefixo `legado_` e perdem o NOT
--     NULL. São as duas que a D-027/D-028 aposentou: a primeira guardava a semelhança
--     ponderada com o perfil, que virou regra binária; a segunda, o desempenho de
--     portal como um fator entre quatro, que virou a nota inteira. O prefixo é o
--     aviso de que ninguém deve lê-las como coluna viva; linha nova as deixa nulas.
--   * As colunas novas nascem NULAS por definição: nenhuma linha antiga as tem, e
--     preenchê-las com zero afirmaria medição que não houve.
--
-- `casa_perfil` é BOOLEAN e tri-estado de propósito: NULL quer dizer "a regra do
-- perfil não foi avaliada" (nenhum perfil que conte, ou candidato sem dimensões —
-- Spec 1.1 §6.1), que é diferente de "não casou".
--
-- O que os `sinal_*` são, e o que o zero NÃO quer dizer. Cada um é o sinal já
-- reescalado para [0, 1] por min-max sobre a população da rodada (forma PROVISÓRIA do
-- parâmetro nº 2, D-016), e a população é declarada na apuração — elegíveis no ranking
-- primário, reprovados no relaxamento. Logo `sinal_x = 0` quer dizer "o menor daquela
-- população", que engloba "todos empatados" e não é o mesmo que "medimos zero". A
-- medição CRUA do portal vive no `apuracao.csv`, não aqui.
--
-- LIMITAÇÃO DECLARADA: a FORMA da normalização não é gravada em lugar nenhum. O
-- parâmetro nº 2 segue nulo e o min-max é fixo no código, então os `sinal_*` são
-- comparáveis entre rodadas apenas enquanto essa forma não mudar. No dia em que o dono
-- decidir o nº 2, linhas escritas antes e depois passam a significar coisas diferentes
-- sem nada no Registro avisando. Gravar a forma junto do efetivo é fatia própria.
--
-- Idempotente, como as demais: aplicadas à mão, em ordem lexicográfica, sem tabela
-- de versões. `RENAME COLUMN` não tem `IF EXISTS`, daí os blocos condicionais.

-- Os dois renomes de semântica preservada.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'registro' AND table_name = 'decisao_imovel'
                 AND column_name = 'nota_leads') THEN
        ALTER TABLE registro.decisao_imovel RENAME COLUMN nota_leads TO sinal_leads;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'registro' AND table_name = 'decisao_imovel'
                 AND column_name = 'nota_gestor') THEN
        ALTER TABLE registro.decisao_imovel RENAME COLUMN nota_gestor TO sinal_produtividade;
    END IF;
    -- As duas ambíguas viram histórico explícito.
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'registro' AND table_name = 'decisao_imovel'
                 AND column_name = 'nota_perfil') THEN
        ALTER TABLE registro.decisao_imovel RENAME COLUMN nota_perfil TO legado_nota_perfil;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'registro' AND table_name = 'decisao_imovel'
                 AND column_name = 'nota_desempenho') THEN
        ALTER TABLE registro.decisao_imovel
            RENAME COLUMN nota_desempenho TO legado_nota_desempenho;
    END IF;
END $$;

ALTER TABLE registro.decisao_imovel ALTER COLUMN legado_nota_perfil DROP NOT NULL;
ALTER TABLE registro.decisao_imovel ALTER COLUMN legado_nota_desempenho DROP NOT NULL;
-- `sinal_leads` e `sinal_produtividade` também passam a aceitar nulo: uma rodada em
-- que a fonte do sinal não veio deve gravar a ausência, não um zero que parece medição.
ALTER TABLE registro.decisao_imovel ALTER COLUMN sinal_leads DROP NOT NULL;
ALTER TABLE registro.decisao_imovel ALTER COLUMN sinal_produtividade DROP NOT NULL;
ALTER TABLE registro.decisao_imovel ALTER COLUMN sinal_leads DROP DEFAULT;

-- A nota como a D-028 a define: bruta em PONTOS DE 100 (a mesma unidade de
-- `nota_final` e dos descontos), e os três sinais do anúncio que a compõem, cada um
-- reescalado em [0, 1] sobre a população declarada na apuração.
ALTER TABLE registro.decisao_imovel
    ADD COLUMN IF NOT EXISTS nota_bruta          numeric,
    ADD COLUMN IF NOT EXISTS sinal_nota_anuncio  numeric,
    ADD COLUMN IF NOT EXISTS sinal_cliques       numeric,
    ADD COLUMN IF NOT EXISTS sinal_visualizacoes numeric,
    ADD COLUMN IF NOT EXISTS casa_perfil         boolean;

COMMENT ON COLUMN registro.decisao_imovel.nota_bruta IS
    'A nota antes dos descontos, em pontos de 100 (D-028). Nula em linhas anteriores. DUAS POPULACOES de normalizacao na mesma coluna: linha com regra_relaxada NULA foi reescalada entre os ELEGIVEIS; com regra_relaxada preenchida, entre os REPROVADOS (D-016). As duas escalas nao sao comparaveis — ordenar a tabela inteira por esta coluna mistura escalas; filtre por regra_relaxada antes.';
COMMENT ON COLUMN registro.decisao_imovel.nota_final IS
    'Nota bruta menos os descontos, em pontos de 100. Vale aqui a mesma ressalva das duas populacoes descrita em nota_bruta.';
COMMENT ON COLUMN registro.decisao_imovel.casa_perfil IS
    'Veredito da nona regra (D-027). NULL = regra não avaliada, diferente de não casou.';
COMMENT ON COLUMN registro.decisao_imovel.legado_nota_perfil IS
    'HISTORICO, nao ler como coluna viva: semelhanca ponderada com o perfil (D-017), em todas as linhas escritas ate 05/09/2026. Linha nova a deixa nula.';
COMMENT ON COLUMN registro.decisao_imovel.legado_nota_desempenho IS
    'HISTORICO, nao ler como coluna viva: desempenho de portal (F3 da D-017), medido ZERO em todas as 14.350 linhas existentes em 05/09/2026. Linha nova a deixa nula.';

COMMENT ON COLUMN registro.decisao_imovel.sinal_nota_anuncio IS
    'Nota do anuncio no portal, reescalada em [0,1] por min-max sobre a populacao da rodada (forma provisoria, parametro no 2). ZERO = o menor da populacao (inclui todos empatados), NAO "medimos zero" — a medicao crua esta no apuracao.csv.';
COMMENT ON COLUMN registro.decisao_imovel.sinal_cliques IS
    'Cliques do anuncio, somados entre tipos e reescalados em [0,1] como acima. ZERO = o menor da populacao, nao a medicao crua.';
COMMENT ON COLUMN registro.decisao_imovel.sinal_visualizacoes IS
    'Visualizacoes do anuncio, reescaladas em [0,1] como acima. Peso adotado zero (D-034), entao nao entra na nota bruta; a coluna guarda o sinal mesmo assim.';
COMMENT ON COLUMN registro.decisao_imovel.sinal_leads IS
    'Leads em 180 dias, reescalados em [0,1]. Nao pesa na nota desde a D-028: e o primeiro criterio de desempate da alocacao.';
COMMENT ON COLUMN registro.decisao_imovel.sinal_produtividade IS
    'Produtividade do gestor em 30 dias, reescalada em [0,1]. Nao pesa na nota desde a D-028; entra como sinal de banco quando a raspagem nao entra.';
