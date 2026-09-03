-- 007 — o relatório de cada agente, por evento de etapa.
--
-- `operacao.trabalho_evento` guardava, por nó concluído, só "etapa concluída: <nó>".
-- O dono pediu "os relatórios gerados pelos agentes, as explicações, os logs do que eles
-- fizeram" — e sem modelo de linguagem a resposta honesta é o que cada nó deixou no
-- estado, CONTADO: candidatos lidos, perfis achados (e quantos frágeis), se a raspagem
-- entrou e com que taxa, elegíveis e reprovados por regra, alocados por nível, veto do
-- crivo, e as degradações que cada nó acrescentou. Derivado no runner a partir do estado
-- (`executar/resumos.py`), nunca escrito pelo nó — zero mudança no caminho da decisão.
--
-- jsonb, e não colunas: a forma varia por nó, e o console mostra chave/valor sem saber
-- o esquema de cada agente. Só contagens, rótulos e frases de limitação — nenhum id de
-- imóvel, nenhum objeto de domínio, nada do Newcore além de totais (invariante 3 em
-- profundidade; há teste que serializa cada resumo e outro que procura ids).
--
-- Idempotente (`IF NOT EXISTS`), como as demais: as migrações são aplicadas à mão, em
-- ordem lexicográfica, sem tabela de versões.

ALTER TABLE operacao.trabalho_evento ADD COLUMN IF NOT EXISTS resumo jsonb;
