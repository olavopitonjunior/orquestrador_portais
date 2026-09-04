-- 008 — a nona regra entra nas listas do Registro (D-027).
--
-- O perfil de conversão virou regra eliminatória e PRIMEIRO degrau do relaxamento
-- (docs/decisoes.md, D-027). `relaxar` grava uma linha por degrau alcançado — inclusive
-- com zero — sempre que há déficit de destaque, então toda rodada com déficit escreve
-- ('perfil_de_conversao', 0, 0) em registro.relaxamento; e um imóvel recuperado por
-- esse degrau leva o mesmo valor em decisao_imovel.regra_relaxada. Os dois CHECKs da
-- 001 param em `capacidade_distrito` e recusariam a linha: SinkFalhou, rodada sem
-- Registro. Achado pela suíte reescrita em 04/09/2026, antes de rodar em produção.
--
-- Os CHECKs da 001 são inline e sem nome: o Postgres os batizou
-- `<tabela>_<coluna>_check`. Idempotente pelo DROP ... IF EXISTS antes do ADD, como as
-- demais: aplicadas à mão, em ordem lexicográfica, sem tabela de versões.

ALTER TABLE registro.decisao_imovel
    DROP CONSTRAINT IF EXISTS decisao_imovel_regra_relaxada_check;
ALTER TABLE registro.decisao_imovel
    ADD CONSTRAINT decisao_imovel_regra_relaxada_check CHECK (regra_relaxada IN
        ('perfil_de_conversao', 'fotos', 'cadastro_completo', 'atualizacao_90d',
         'gestor_produtivo', 'capacidade_distrito'));

ALTER TABLE registro.relaxamento
    DROP CONSTRAINT IF EXISTS relaxamento_regra_cedida_check;
ALTER TABLE registro.relaxamento
    ADD CONSTRAINT relaxamento_regra_cedida_check CHECK (regra_cedida IN
        ('perfil_de_conversao', 'fotos', 'cadastro_completo', 'atualizacao_90d',
         'gestor_produtivo', 'capacidade_distrito'));
