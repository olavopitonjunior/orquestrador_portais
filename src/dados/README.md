# src/dados

Acesso a dados: leitura direta do MySQL do Newcore (`newcore` e `newcore_bi`, SOMENTE LEITURA — invariante 1) e leitura/escrita no Registro em PostgreSQL próprio.

Antes de depender de qualquer campo, consultar `docs/mapa-de-dados.md` — vários campos aparentemente úteis são inválidos.

`registro/001_registro.sql` define o esquema `registro` (as 8 entidades da Spec §2.1). O checkpointer do LangGraph vive em esquema separado no mesmo PostgreSQL, gerenciado pela biblioteca. `registro/006_operacao.sql` acrescenta o esquema `operacao` — a fila que o console escreve e o trabalhador executa, separada do trilho de auditoria da decisão.

## Migração já aplicada não se edita

Não há tabela de versão de schema nem aplicador — pendência declarada em `registro/escrita.py`. As migrações são aplicadas à mão, em ordem lexicográfica, e **o CI só prova o caminho que ninguém percorre**: ele sobe as migrações num Postgres limpo a cada PR, provando que a sequência funciona do zero. O caminho real — aplicar num banco que já tem dado — nenhum check exercita.

Daí a regra: **editar um arquivo de migração que já foi aplicado em algum lugar é como editar histórico.** Quem o aplicou antes fica com um banco que o arquivo não descreve mais, e nada acusa. Duas saídas, nesta ordem de preferência:

1. **Criar a migração seguinte.** É o padrão, e o único que funciona quando a mudança não é idempotente.
2. **Anexar statement idempotente ao fim do arquivo** (`ALTER TABLE ... DROP CONSTRAINT IF EXISTS` seguido de `ADD CONSTRAINT`), deixando o arquivo inteiro reaplicável. Só quando a migração ainda não saiu da máquina de quem a escreveu.

A 006 usou a saída 2 — e por pouco. O CHECK de `cancelado` foi acrescentado depois de o arquivo já ter sido aplicado à mão; o que salvou foi a forma da edição, não o cuidado de quem editou. Toda migração daqui em diante nasce inteiramente reaplicável (`IF NOT EXISTS` / `IF EXISTS`), porque a reaplicação é a única prova barata de que o banco de quem opera bate com o arquivo.
