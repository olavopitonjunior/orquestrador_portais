---
name: consultar-newcore
description: Como consultar o banco do Newcore com segurança — somente leitura, qual tabela responde qual pergunta, e os defeitos conhecidos que invalidam campos aparentemente úteis. Use antes de qualquer consulta ao MySQL do Newcore.
---

# Consultar o Newcore

## Regras de segurança

1. **Somente leitura, sem exceção** (invariante 1 do CLAUDE.md). Apenas SELECT, SHOW, DESCRIBE, EXPLAIN. Nunca INSERT, UPDATE, DELETE ou DDL, nem "só para testar".
2. Toda escrita do sistema vai para o PostgreSQL próprio, nunca para o Newcore.
3. Credenciais vêm do `.env` gerado por `op inject` (1Password, `op://Personal/orquestrador_portais/<VAR>`). Nunca hardcode.
4. Custo consciente: `realtyattributes` tem 4,2 milhões de linhas, `brokerneighborhoods` 6,1 milhões, `userbrokerrelationshipshistoric` 7,5 milhões. Use COUNT, LIMIT e filtro por status antes de varrer.
5. Dentro da rodada de produção, os nós consultam por conexão direta; o MCP de MySQL é só para exploração fora da rodada.

## Qual tabela responde qual pergunta

| Pergunta | Tabela |
|---|---|
| Atributos de um imóvel: gestor, distrito, preço, faixas, dormitórios, Leads30D/180D | `newcore_bi.FT_RealtyRelation` (404.680, uma linha por imóvel — a tabela central) |
| A que distrito pertence um imóvel | `FT_RealtyRelation` — **nunca** pelo endereço (ver defeitos) |
| Leads (funil, canal, características) | `newcore_bi.FT_Leads` (942.368) |
| Visitas e feedback | `newcore_bi.FT_LeadsVisits` (84.823) |
| Propostas, valor, assinatura, ciclo | `newcore_bi.FT_LeadsOffers` (17.332) |
| Atendimento de leads | `newcore_bi.FT_LeadsAttendance` (19.007) |
| Indicadores por distrito | `newcore_bi.FT_Districts` (1.583) |
| Perfil e desempenho de corretor | `newcore_bi.FT_Broker` (16.691) |
| Produtividade do corretor (Produtivo / Não Produtivo / Ocioso) | `newcore_bi.productivityrating` (2.094) |
| Nota interna do anúncio (0–100, sete categorias) | `newcore.realty_score` (376.856) |
| Histórico de janelas de destaque | `adsrealtyextra_historic` (59.653; `HighlightedAt`, `RemovedAt`, `QtyFacsGenerated`) |
| Execuções de raspagem | `webscraping_processing_grupo_zap` (105) |
| Cotas do contrato | **Nenhuma.** `adsportalconfigs` está inativa e errada em ~20×. As cotas (475/6.495) são contratuais, não vêm do banco |
| URL do anúncio no portal | **Nenhuma.** Só existe durante a raspagem; o Coletor Externo captura na hora |

## Defeitos que invalidam campos aparentemente úteis

Os quatro que mais enganam:

1. **`realties.MarketingType_Id`** (tipo de comercialização): nulo em 96% dos ativos. Não filtre por ele.
2. **`realtyaddresses.ValueZone_Id`** (zona de valor): nulo em 98% dos ativos relevantes. Distrito vem de `FT_RealtyRelation`.
3. **`FT_LeadsOffers.DaysConversion`**: contém valores negativos. Trate antes de agregar.
4. **Vagas**: ausente da tabela central `FT_RealtyRelation`, mas existe em `newcore.realties.QtyVacancies` (96% preenchida no recorte elegível; resolvido em 29/08/2026) — exige JOIN. Cuidado: o nome está em inglês, como parte do schema.

Os demais: campos de placa e impulsionamento integralmente vazios; `adswhitelist` abandonada desde 2022; `adsblacklist` viva (12.155 imóveis) mas decidida como ignorada; ~44% do estoque elegível sem avaliação em `realty_score_category_score` — **pipeline morto desde 16/10/2025**: todo imóvel ativado depois disso nasce sem avaliação (imóvel sem avaliação passa e recebe penalidade, não é excluído). Armadilhas de nome: `integrations`/`integrationshistory` vazias, `webscrapper_reports` (0 linhas) ≠ `webscraping_report_grupo_zap` (43, abandonada).

Lista completa e números de referência: `docs/mapa-de-dados.md`.
