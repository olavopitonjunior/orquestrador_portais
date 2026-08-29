# src/dados

Acesso a dados: leitura direta do MySQL do Newcore (`newcore` e `newcore_bi`, SOMENTE LEITURA — invariante 1) e leitura/escrita no Registro em PostgreSQL próprio.

Antes de depender de qualquer campo, consultar `docs/mapa-de-dados.md` — vários campos aparentemente úteis são inválidos.

`registro/001_registro.sql` define o esquema `registro` (as 8 entidades da Spec §2.1). O checkpointer do LangGraph vive em esquema separado no mesmo PostgreSQL, gerenciado pela biblioteca. Aplicação de migração e código de acesso vêm em etapa posterior.
