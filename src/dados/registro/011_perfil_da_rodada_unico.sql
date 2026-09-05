-- 011 — o mesmo perfil não aparece duas vezes na mesma rodada (issue #79).
--
-- `registro.perfil_da_rodada` existe desde o DDL 001 e nunca foi escrita; agora passa a
-- ser, com todos os perfis que o Analista achou na semana. `perfis_de_conversao` devolve
-- combinações únicas por construção, e este índice transforma essa garantia do domínio
-- em garantia do banco — é o que permite ligar `decisao_imovel.perfil_id` a um perfil
-- sem ambiguidade. Sem ele, um produtor com defeito gravaria o mesmo perfil duas vezes
-- e o vínculo apontaria para uma das cópias, em silêncio.
--
-- Separada da 010 de propósito: a 010 é a nota, esta é o perfil, e cada uma fecha
-- sozinha. Idempotente, como as demais (aplicadas à mão, sem tabela de versões).

CREATE UNIQUE INDEX IF NOT EXISTS perfil_da_rodada_unico
    ON registro.perfil_da_rodada (rodada_id, dimensoes, valores);
