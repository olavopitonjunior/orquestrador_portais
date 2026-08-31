# Mapa de Dados de Referência

Derivado da seção "Base factual" do PRD versão 5.0 (levantamento direto nas fontes em 28/08/2026) e **atualizado em 29/08/2026** com medições diretas no banco (investigador-de-dados). Existe para que ninguém precise redescobrir o banco. Nenhum número aqui foi estimado: tudo vem dos documentos ou de medição datada. Onde falta número, a lacuna está apontada.

O PRD prevalece sobre este mapa, com uma exceção definida: **medição datada posterior ao PRD 5.0 que resolva uma investigação ou pendência listada por ele prevalece sobre a lista de pendências** (caso do defeito 5, vagas). Nesses casos a correção fica registrada aqui com data e tachado, até que uma revisão do PRD a incorpore. Em qualquer outra divergência, é bug deste arquivo.

---

## As duas bases do Newcore

| Base | Tabelas | Papel |
|---|---|---|
| `newcore` | 418 | Base transacional |
| `newcore_bi` | 53 | Camada analítica, com fatos já calculados |

Ambas são **somente leitura** para este sistema (invariante 1). Toda escrita acontece no PostgreSQL próprio.

---

## Tabela central: `newcore_bi.FT_RealtyRelation`

**404.680 registros, um por imóvel.** É a tabela analítica de relação de imóveis e a espinha dorsal da coleta interna.

Campos que o produto usa:

- Corretor gestor (o vínculo usado é o de **gestão**, não o de captação — disponível para todo o estoque)
- Distrito — **a ligação imóvel↔distrito vem daqui, não do endereço**, porque `realtyaddresses.ValueZone_Id` é nulo em 98% dos casos
- Zona de valor, bairro
- Status, tipo, preço, faixa de preço, faixa de área, dormitórios
- `Leads30D` e `Leads180D` por imóvel

Vagas: **não está nesta tabela**, mas existe em `newcore.realties.QtyVacancies` (medido 29/08/2026) — a coleta interna precisa do JOIN `realties.Id = FT_RealtyRelation.Realty_Id`, testado e barato.

---

## Demais tabelas relevantes

| Tabela | Registros | Papel |
|---|---|---|
| `newcore_bi.FT_Leads` | 942.368 | Leads por imóvel, canal, distrito, características e funil |
| `newcore_bi.FT_LeadsVisits` | 84.823 | Visitas com feedback de imóvel e de preço |
| `newcore_bi.FT_LeadsOffers` | 17.332 | Propostas com assinatura, valor, ciclo e características |
| `newcore_bi.FT_LeadsAttendance` | 19.007 | Atendimento de leads |
| `newcore_bi.FT_Districts` | 1.583 | Indicadores consolidados por distrito |
| `newcore_bi.FT_Broker` | 16.691 | Perfil e desempenho de corretor |
| `newcore_bi.productivityrating` | 2.094 corretores | Produtivo (193), Não Produtivo (1.146), Ocioso Passível de Bloqueio (746); captações/semana, vendas, data da última venda, conversão, visitas/semana |
| `newcore.realty_score` | 376.856 imóveis | Nota interna de 0 a 100, média 68. Pesos: descrição (2), fotos (2), atualização (2), ano de construção (1), atributos (1), IPTU (1), condomínio (1) |
| `adsrealtyextra_historic` | 59.653 janelas | Histórico das janelas de destaque: `HighlightedAt`, `RemovedAt`, `QtyFacsGenerated`. 88% das janelas com zero lead; média 0,21 lead/janela; duração média 33 dias |
| `newcore.webscraping_processing_grupo_zap` | 105 exec. em 28/08; **viva**: execuções diárias, última em 27/08/2026 (Id da execução: 351 — identificador, não contagem), 22.597 anúncios | Agregados por execução da raspagem; os ~62% com erro referem-se ao histórico até 28/08 |
| `newcore.webscraping_report_grupo_zap` | 43 registros | **Abandonada**: 100% com erro (erros de publicação devolvidos pelo Grupo ZAP: CEP inválido, campo fora de faixa, anúncio bloqueado), criados entre 01 e 17/12/2025, `ProcessedAt` nulo em todos, nenhuma FK ou view aponta para ela. Era a "tabela de relatórios da raspagem" das investigações abertas — resolvida em 29/08/2026 |
| `newcore.realty_score_category_score` | 1.654.058 linhas, 352.944 imóveis (média 4,7 das 7 categorias) | Avaliação por categoria da nota interna; chave `realtyId`+`categoryId`; categorias em `realty_score_category`. **Tabela zumbi: sem escrita desde 16/10/2025** (ver defeito 4) |
| `adsportalconfigs` | — | Registra 350 destaques e 1 super destaque; **inativa e desatualizada em quase vinte vezes. Não é fonte de cota** |

Maiores tabelas relevantes por volume (cuidado com custo de consulta): `realtyattributes` (4,2 milhões), `brokerneighborhoods` (6,1 milhões), `userbrokerrelationshipshistoric` (7,5 milhões).

Observação sobre URL do portal: **a URL do anúncio não existe em nenhuma tabela do Newcore**. O único endereço armazenado é o do site da própria Newcore, em caminho relativo. A URL do portal só pode ser capturada pelo Coletor Externo durante a raspagem — não é recuperável depois.

---

## Defeitos de dado confirmados

Armadilhas conhecidas. Campos aparentemente úteis que não podem ser usados sem tratamento — ou não podem ser usados de forma alguma.

1. `realties.MarketingType_Id` (tipo de comercialização) é **nulo em 96%** dos ativos.
2. `realtyaddresses.ValueZone_Id` (zona de valor) é **nulo em 98%** dos imóveis ativos relevantes. A ligação com distrito vem de `FT_RealtyRelation`.
3. `FT_LeadsOffers.DaysConversion` (ciclo de conversão) apresenta **valores negativos** e exige tratamento.
4. Cerca de **44% do estoque elegível não possui avaliação por categoria** em `realty_score_category_score`. **Causa identificada em 29/08/2026: o pipeline que popula a tabela parou em 16/10/2025** (último `createdAt` 2025-10-16 22:05), enquanto o da nota geral `realty_score` segue vivo (atualizado no mesmo dia da medição). Dos imóveis do recorte elegível-aproximado ativados após o corte, 99,76% não têm avaliação; dos ativados antes, apenas 4 imóveis. Consequências: o percentual sem avaliação **cresce continuamente** com o estoque novo (33,8% no recorte amplo de 35.592; ~44% nos 10.290 elegíveis plenos, cujas regras enviesam para imóveis recentes), e a penalidade "sem avaliação por categoria" atingirá **sistematicamente o estoque novo** — atenção do dono da decisão ao calibrar sua intensidade. Imóvel sem avaliação não é excluído: passa e recebe penalidade.
5. ~~`realties` não expõe quantidade de vagas~~ **CORRIGIDO em 29/08/2026: o campo existe — `newcore.realties.QtyVacancies`** (escapou às buscas por estar em inglês). No recorte elegível-aproximado: nulo em 0,4%, zero em 3,4% (valor legítimo: imóvel sem vaga), maior que zero em 96,1%. Utilizável como a coluna "vagas" da planilha de decisão (Spec §3.2), via JOIN com `FT_RealtyRelation`.
6. Campos de **placa e de impulsionamento estão integralmente vazios**.
7. `adswhitelist` está **abandonada desde 2022**. `adsblacklist` está viva com 12.155 imóveis, mas **foi decidido ignorá-la**.

---

## Números de referência medidos

Medidos em 28/08/2026. Servem de conferência para implementações (skill `verificar-contra-spec`).

| Referência | Valor |
|---|---|
| Imóveis elegíveis | **10.290** |
| Candidatos ao super destaque (≥ R$ 700.000) | **4.852** |
| Posições contratadas | **6.970** (475 super destaque + 6.495 destaque) |
| Vendas assinadas em 180 dias | **176** |

Funil de elegibilidade medido:

| Etapa acumulada | Imóveis |
|---|---|
| Ativos | 48.964 |
| Nas cinco categorias | 41.478 |
| Preço ≥ R$ 300.000 | 35.560 |
| Após os cinco cortes restantes | 10.290 |

Concorrência por nível: 10,2 candidatos por vaga no super destaque; 1,5 no destaque (folga total de 48%).

Deriva medida em 29/08/2026 (um dia depois da referência):

| Contagem | 28/08 | 29/08 | Deriva |
|---|---|---|---|
| `FT_RealtyRelation` total | 404.680 | 404.756 | +76 |
| Ativos | 48.964 | 48.989 | +25 |
| `realty_score` | 376.856 | 376.914 | +58 |

### Aviso sobre os ganhos de relaxamento

Os ganhos por regra relaxada — fotos +133, cadastro completo +569, atualização em 90 dias +1.680, gestor produtivo +1.747, capacidade do distrito +5.686 — foram medidos com **mínimo de TRÊS corretores por distrito**, enquanto o parâmetro adotado é **DOIS**. O próprio PRD os mantém como "referência de ordem de grandeza; os valores absolutos mudam com o mínimo de dois". **Não usar como conferência exata.** A Spec §6.6 reproduz esses números sem a ressalva — o PRD prevalece.

---

## Lacunas apontadas (não estimar)

- Contagem de registros de `adsportalconfigs`: o PRD não a informa, apenas o conteúdo (350 + 1) e o estado (inativa).
- ~~Contagem de `realty_score_category_score`~~ medida em 29/08/2026: 1.654.058 linhas (ver tabela acima).
- ~~Localização do campo de vagas~~ resolvida em 29/08/2026: `realties.QtyVacancies` (defeito 5).
- ~~Tabela de relatórios da raspagem~~ resolvida em 29/08/2026: `webscraping_report_grupo_zap`, abandonada (ver tabela acima).
- **Segue aberta (pergunta de processo, não de banco)**: se quem aplica a carga localiza o imóvel apenas pelo identificador interno ou depende de outra referência — responder com o gestor da vitrine. No banco está refutado: não existe id nem URL de anúncio do portal em nenhuma tabela (29/08/2026).

## Armadilhas adicionais (medição de 29/08/2026)

- **`realty_score_category_score` é tabela zumbi**: 1,65 mi de linhas aparentando riqueza, mas sem escrita desde 16/10/2025. Cobertura zero para estoque novo.
- **`integrations` e `integrationshistory` são cascas vazias** (0 linhas) apesar de terem as colunas certas (`External_Id`, `IntegrationPortal_Id`); `integrationsportals` tem um único portal ("FFID", 2019). Nada de OLX/Zap.
- **`webscrapper_reports` (0 linhas) coexiste com `webscraping_report_grupo_zap` (43)** — nomes quase idênticos, fácil confundir. Há ainda `webscrapper_cron` (278 linhas).
- **O schema mistura português e inglês** nos nomes de coluna (`QtyVacancies`, `QtyVagas` em `adsrealtyscores`): buscas por regex precisam dos dois idiomas.
- **`information_schema.TABLE_ROWS` superestima** (~3% em `realty_score_category_score`): usar para triagem, nunca para número final — número final é COUNT(*).
- `realties.FriendlyUrl` (91,8% dos ativos) é caminho do site da Newcore; `realties.ExploraURL` tem 0 preenchimentos no banco inteiro.

## Armadilhas adicionais (medição de 31/08/2026)

Medições novas; as de 29/08 permanecem válidas como registro datado.

- **`FT_RealtyRelation.FirstActivationDate` não é proxy de ordem de cadastro**: 38,5% dos pares adjacentes por `Realty_Id` estão invertidos, 11,3% é nula e há 3.985 ativações ANTERIORES à criação. Para ordem de cadastro, o campo é `realties.CreatedAt` (verificação da D-009: Id monotônico com CreatedAt, zero inversões no estoque recente).
- **`realties.Id` ordena, mas não conta**: MAX(Id) 519.239 vs COUNT(*) 483.004 — ~36 mil Ids deletados. Qualquer aritmética "Id como contagem" é inválida; a ordenação não é afetada (pressuposto da D-009 preservado).
- **O JOIN de vendas assinadas com `FT_RealtyRelation` perde 11,3%** (medição na janela de 180 dias: 20 de 177 — 18 `Realty_Id` ausentes da tabela, 2 nulos na oferta). `FT_RealtyRelation` não cobre todo imóvel vendido. Impacto direto no **parâmetro pendente nº 1** (evidência mínima do perfil): a base efetiva com atributos completos é ~157, não ~177 (os 11,3% daqui e os 11,3% de nulos de `FirstActivationDate` acima são medições independentes que coincidem no valor — não deduplicar); `FT_LeadsOffers` tem campos próprios (District, QtyBedrooms, PrivateArea_Range) que podem recuperar parte — decisão do dono.
- **As colunas de visualização de portal em `realties` estão quase mortas**: `QtdViewsZap`/`QtdViewsPortals` > 0 em só 5,5% dos ativos (vitalidade de atualização desconhecida) e `QtdViewsImovelWeb` 100% zero. Impacto direto no fator **"desempenho próprio observado"** do ranking (peso 25/10) e no **parâmetro pendente nº 2**: a métrica de portal por imóvel só existirá via Coletor Externo em tempo de rodada — a normalização desse fator tenderá a ser relativa ao lote da própria rodada (restrição de disponibilidade a considerar na escolha do dono; a forma segue nula). `realties.QtdViews` (site da Newcore) está viva (0,08% de zeros) mas não é métrica de portal.
- **`newcore.adsrealtyscores` é casca vazia** (0 linhas) apesar do schema rico (`ScoreFinal`, `QtyVagas`) — mesma família de `integrations`.
- **Raspagem do Grupo Zap sem execução desde 27/08** (`webscraping_processing_grupo_zap`, último Id 351), contra cadência diária registrada em 29/08 — alerta operacional levado ao dono; o Coletor Externo depende dela.
- Derivas medidas em 31/08 (registro, sem correção das medições de 28–29/08): vendas assinadas 180d 176 → 177 (174 imóveis distintos); ativos 48.989 → 48.985; `productivityrating` 2.094 → 2.105 linhas (Produtivo 193, Não Produtivo 1.143, Ocioso Passível Bloqueio 760, 9 nulas); `FT_RealtyRelation` 404.756 → 404.836; `realties` 483.004.
