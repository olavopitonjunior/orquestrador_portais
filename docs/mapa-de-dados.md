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
| `newcore_bi.FT_Leads` | ~~942.368~~ → **1.128.909** (COUNT(*), 01/09/2026) | Leads por imóvel, canal, distrito, características e funil. **Grão = `FacId` (par lead↔imóvel), NÃO `LeadID`**: 17.741 linhas em 90d são 17.741 `FacId` para só 14.331 `LeadID` — a mesma pessoa aparece em várias linhas. Fonte de TODOS os campos da rodada de segunda (ver seção própria abaixo) |
| `newcore_bi.FT_LeadsVisits` | 84.823 | Visitas com feedback de imóvel e de preço |
| `newcore_bi.FT_LeadsOffers` | 17.332 | Propostas com assinatura, valor, ciclo e características |
| `newcore_bi.FT_LeadsAttendance` | 19.007 | ~~Atendimento de leads~~ **NÃO é por lead** (medição 01/09/2026): o grão é `BrokerID` × `Periodo` (2.361 corretores × 8 períodos = 18.888). Não tem `LeadID` nem `FacId`. **Não serve** para o sinal de atendimento por lead — esse vem de `FT_Leads.AttendedAt` (com a ressalva da seção da rodada de segunda) |
| `newcore_bi.FT_Districts` | 1.583 | Indicadores consolidados por distrito |
| `newcore_bi.FT_Broker` | 16.691 | Perfil e desempenho de corretor |
| `newcore_bi.productivityrating` | 2.094 corretores | Produtivo (193), Não Produtivo (1.146), Ocioso Passível de Bloqueio (746); captações/semana, vendas, data da última venda, conversão, visitas/semana |
| `newcore.realty_score` | 376.856 imóveis | Nota interna de 0 a 100, média 68. Pesos: descrição (2), fotos (2), atualização (2), ano de construção (1), atributos (1), IPTU (1), condomínio (1) |
| `adsrealtyextra_historic` | 59.653 janelas | Histórico das janelas de destaque: `HighlightedAt`, `RemovedAt`, `QtyFacsGenerated`. 88% das janelas com zero lead; média 0,21 lead/janela; duração média 33 dias. **⚠️ TABELA MORTA desde 27/06/2023** (medição 01/09/2026): `MAX(HighlightedAt)` = `MAX(RemovedAt)` = 2023-06-27 13:29 e **zero janelas abertas** (`RemovedAt IS NULL` = 0). Os números acima descrevem um histórico congelado há 3 anos, não o estoque vivo — ver consequência na seção da rodada de segunda |
| `newcore.webscraping_processing_grupo_zap` | ~~105 exec. em 28/08; viva: execuções diárias, última em 27/08/2026 (Id 351), 22.597 anúncios, ~62% com erro no histórico até 28/08~~ (medições de 28–29/08) → **parada desde 28/08/2026** (diagnóstico de 31/08: última ingestão `ScrapedAt` 27/08 06:00; cadência histórica era diária de verdade, fins de semana incluídos, cobertura perfeita por 42 dias) | Agregados por execução da raspagem. **Armadilhas (31/08)**: `Id` NÃO é monotônico com `ReportDateTime` (Id 351 tem data anterior ao 350) — ordenar/datar sempre por `ScrapedAt`; ingestão em lote é normal (backfill de 13 LINHAS cobrindo 19–25/08 ingeridas de uma vez em 25/08 — ~2 relatórios/dia): a fonte-espelho do Canal Pro pode ficar **até ~6 dias defasada** e sempre recuperou por backfill — conversa direto com o parâmetro pendente nº 5 (idade máxima da coleta de reserva) |
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
- **`webscrapper_reports` (0 linhas) coexiste com `webscraping_report_grupo_zap` (43)** — nomes quase idênticos, fácil confundir. `webscrapper_cron` (285 linhas em 31/08; era 278) é o **log operacional do raspador**: três jobs diários (`sync-views-zap-group` 06:00, `imovel-web` 16:00, `zap-group` 17:00 — horários em **UTC**, enquanto o resto do banco usa horário local: `CreatedAt` 16:00 UTC = 13:00 local), `Status` com quarto valor vazio "" (42 execuções aparentemente iniciadas e nunca finalizadas) e falha crônica silenciosa: 221 de 285 disparos como `Falhou` (~78%), a maioria sem mensagem de erro — e `Falhou` NÃO implica ausência de dado: são só 22 sucessos no log contra 105 ingestões reais e 42 dias de cobertura perfeita, ou seja, o status do cron não é confiável como indicador de resultado.
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
- **Raspagem do Grupo Zap parada — incidente de infraestrutura confirmado em 31/08**: última ingestão em 27/08 06:00 (`ScrapedAt`). Desde 28/08 16:00 UTC, TODOS os disparos do cron falharam: **11 consecutivos com `Status='Falhou'`** (Ids 320–330, os três jobs; medição até 31/08 ~17:05 UTC — a sequência cresce a cada disparo, datar qualquer citação), nenhum ausente e nenhum preso em "Executando" nesse trecho; o último não-falho é o Id 319 (28/08 06:00 UTC, `sync-views-zap-group`), preso com Status vazio — o problema começou entre 28/08 06:00 e 16:00 UTC. Erros predominantes: `session not created / chrome not reachable` e `unable to connect to renderer`; timeout de 29/08 06:00 revela `chrome=152.0.7977.64`. Parou saudável (erros de conteúdo em queda, 264→28; volume estável ~22–24 mil anúncios). Faltam os relatórios de 28–31/08; defasagens de até ~6 dias sempre foram recuperadas por backfill do portal. Alerta levado ao dono com perguntas para o time do Newcore; o Coletor Externo depende desta fonte.
- Derivas medidas em 31/08 (registro, sem correção das medições de 28–29/08): vendas assinadas 180d 176 → 177 (174 imóveis distintos); ativos 48.989 → 48.985; `productivityrating` 2.094 → 2.105 linhas (Produtivo 193, Não Produtivo 1.143, Ocioso Passível Bloqueio 760, 9 nulas); `FT_RealtyRelation` 404.756 → 404.836; `realties` 483.004.

## Conexão Python ↔ MySQL: o "1045 só mysql2" resolvido (31/08/2026)

Mistério encerrado. A investigação da fundação registrou que **só o mysql2 (Node) autenticava; pymysql e mysql.connector davam `1045 Access denied`** para as mesmas credenciais, causa nunca explicada — e "descartou o U+00A8 cedo demais". Era exatamente o U+00A8.

**Causa raiz**: a senha do usuário `olavo` contém **U+00A8 (¨)**, que em UTF-8 são 2 bytes (`0xC2 0xA8`) e em latin-1 é 1 byte (`0xA8`). O hash `caching_sha2_password` no servidor foi criado sobre a forma **UTF-8**. O **pymysql (`connections.py`) força `.encode('latin1')` em senha `str`**, ignorando o `charset` — envia o byte errado, o hash não bate, `1045`. O mysql2 sempre funcionou por enviar UTF-8 nativo. **Não era falta de `cryptography` nem SSL.**

**Correção**: passar a senha ao pymysql como **`bytes` UTF-8** (`pw.encode('utf-8')`), não `str`. Com `bytes`, o `isinstance(str)` do pymysql é falso e ele envia os bytes intactos. `charset` não corrige (é ignorado na senha). Encapsular a conversão num único ponto de conexão, comentando o porquê, para ninguém "limpar" o `bytes` e reintroduzir o `1045`. Manter `cryptography` instalado (cobre o caminho não-SSL do caching_sha2).

**Infra medida (31/08)**: MySQL **8.4.9**, `authentication_policy = *:caching_sha2_password` (`@@default_authentication_plugin` foi removido no 8.4). `require_secure_transport = 0` — o RDS **não exige SSL**; o pymysql auto-negocia TLS por padrão. `CURRENT_USER() = olavo@%`, sem `SELECT` em `mysql.user`. Sanidade: `SELECT COUNT(*) FROM newcore_bi.FT_RealtyRelation` → 404.836 via pymysql.

Consequência para o produto: o **Coletor Interno é Python puro** (pymysql), sem ponte Node. Cardinalidade confirmada (31/08): `FT_RealtyRelation` é 1:1 por `Realty_Id` também no recorte ativo (48.985 linhas = 48.985 imóveis) e a query completa do Coletor não infla — nenhum dos LEFT JOINs (`productivityrating` por User_Id, `FT_Districts` por ID_District, subquery de fotos com DISTINCT) multiplica linhas.

## Fonte das vendas do perfil de conversão (Coletor de Vendas, B2 — 31/08/2026)

O perfil de conversão (Spec §6.2, `src/dados/vendas.py` → `src/dominio/perfil.py`) lê as vendas assinadas de **`newcore_bi.FT_LeadsOffers`** — não de `FT_RealtyRelation`, cujo JOIN perde 11,3% (ver armadilha acima). Decisão concretizada: as dimensões vêm da **própria oferta**, que tem cobertura melhor.

- **Definição da venda (D-013)**: `SignedAt IS NOT NULL AND SignedAt >= CURDATE() - INTERVAL 180 DAY`. Medido: **177 ofertas / 174 imóveis distintos**. `SignedAt` é a data de assinatura (não `OffersCreatedAt`). A contagem **inclui** 6 "Cancelado definitivamente" + 1 "aguardando cobrança" (`CancellationAt` nulo nas 177); a leitura líquida (171) foi descartada pelo dono. A evidência do perfil é **por venda**, não por imóvel (um imóvel com duas assinaturas conta duas vezes).
- **Cobertura das dimensões nas 177** (colunas da própria oferta, salvo vagas): `District` (região) 177/177 · `PrivateArea_Range` (faixa de metragem, já nativa) 177/177 · `RealtyType` 175 · `QtyBedrooms` (dormitórios) 157 (20 nulos = os mesmos 11,3%) · vagas por JOIN `realties.QtyVacancies` (por `Realty_Id`) 158. Preço para a faixa também vem de `realties.Price` por `Realty_Id`.
- **Bucketização (na coleta, não no domínio)**: `faixa_metragem` = `PrivateArea_Range` nativo; `faixa_preco` derivada do preço em faixas ancoradas nos pisos da Spec §6.1 (300k / 700k); `dormitorios`/`vagas` colapsam o topo (≥5 e ≥3, "N ou mais"), espelhando a medição de 31/08. `RealtyType` (categoria) **não** é dimensão de perfil — a Spec §6.2 lista cinco (região, faixa de preço, faixa de metragem, dormitórios, vagas) e categoria não é uma delas.
- **Invariante 3**: o SELECT projeta só características de imóvel (região, faixas, dormitórios, vagas, preço). Nenhum nome/contato de comprador ou corretor; `SignedAt` é data.

## Fonte das dimensões de perfil do CANDIDATO (match do perfil, B3b — 31/08/2026)

Para casar o imóvel candidato com os perfis de conversão, as cinco dimensões da Spec §6.2 saem das MESMAS colunas nativas que o lado da venda, casando string-a-string (verificado no banco, 31/08). Recorte `FT_RealtyRelation.RealtyStatus='Ativo'` (48.985 imóveis):

- **Região** = `FT_RealtyRelation.District` (não `FT_Districts` nem endereço): os 66 distritos das vendas 180d estão TODOS nos ativos (66/66), formato idêntico, zero vazios. Cobertura 100%.
- **Faixa de metragem** = `FT_RealtyRelation.PrivateArea_Range` — faixa-texto NATIVA, mesmos 8 rótulos exatos dos dois lados (`até 30m2`, `30 - 60m2`, `60 - 80m2`, `80 - 100m2`, `100 - 120m2`, `120 - 150m2`, `150 - 200m2`, `acima de 200m2`). **Não bucketizar** — comparar direto. Cobertura 100%.
- **Dormitórios** = `FT_RealtyRelation.QtyBedrooms` (= `realties.QtyBedrooms`, 0 divergências): 98,30% preenchido (831 nulos), 3.630 estúdios (0, legítimo).
- **Vagas** = `realties.QtyVacancies` por JOIN `realties.Id = FT_RealtyRelation.Realty_Id`: 97,76% (1.097 nulos).
- **Preço** = `realties.Price` por JOIN → `faixa_de_preco()`: ~100% (2 ausentes).

**Armadilha (crítica): NÃO usar `FT_RealtyRelation.Price_Range` como faixa de preço.** Ele tem vocabulário PRÓPRIO e incompatível com `faixa_de_preco()` das vendas (rótulos `300 - 400mil`, `1 - 1.5M`, `acima 3.5M`); casar por ele com a venda daria zero. A faixa de preço vem SEMPRE de `realties.Price` + `faixa_de_preco()`, nos dois lados. A assimetria entre as duas colunas "_Range" é a pegadinha: `PrivateArea_Range` é compatível e nativo, `Price_Range` não.

`FT_RealtyRelation` também carrega `Price`, `PrivateArea`, `Bairro`, `ValueZone` (redundância com `realties`); a referência de preço/vagas continua sendo `realties` por JOIN, como no lado venda. O `coletor_interno.py` (elegibilidade/penalidade) NÃO lê essas 3 colunas de perfil — a leitura do candidato para o match vive em `dados/candidatos_perfil.py`.

## Fonte do fator F4 produtividade contínua (D-017 — medição 01/09/2026)

O fator de ranking F4 (produtividade do gestor, D-017) passou de binário para intensidade contínua em 30 dias, lido de `newcore_bi.productivityrating` (JOIN por `User_Id = f.BrokerID`, 1:1, não infla). Achados que limitam o "contínuo":

- **`Captations_per_week_last_30d`** é a ÚNICA métrica genuinamente de 30 dias: uma **taxa semanal** (int 0–15), 99,5% preenchida, 12,8% > 0. É a dimensão contínua do F4.
- **`Sells` é contagem de 365 DIAS, não de 30d nem vitalícia.** Prova (01/09): `SUM(Sells>0)` = 189 = `SUM(LastSell >= NOW()-365d)` = 189, idênticos; 238 corretores têm `LastSell` com `Sells=0` (venda anterior à janela). max 11, média 0,19.
- **Não existe contagem de captações nem de vendas em 30d.** `Captations` (sem sufixo, max 880) é acumulado de longo prazo, escala incompatível com a taxa semanal.
- O único sinal de venda em 30d é derivar de **`LastSell`** (só 20% preenchida; 22 gestores com venda em 30d).

**Consequência declarada (D-017):** o F4 usa `Captations_per_week_last_30d` (captação, contínua) + flag `LastSell >= NOW()-30d` (venda recente, binário, pois não há contagem de vendas de 30d). A dimensão de venda entra só como flag — limitação assumida, rotulada nas degradações da rodada. A regra de elegibilidade "gestor produtivo" (captou OU vendeu em 30d) segue usando o binário, intocada.

## Fonte dos campos da RODADA DE SEGUNDA (Monitor Operacional, M2 — medição 01/09/2026)

Investigação read-only sobre `newcore_bi.FT_Leads` (janela de 90 dias: 17.741 linhas /
14.331 `LeadID` distintos, 2026-06-03 → 2026-09-01). Sustenta `src/dominio/acompanhamento.py`.

### Mapa campo do domínio → coluna (com preenchimento medido em 90d)

| Campo do domínio | Coluna real | Preenchimento |
|---|---|---|
| `lead_id` | **`FT_Leads.FacId`** (NÃO `LeadID` — ver grão abaixo) | 100%, 0 órfãos contra `newcore.facs.Id` |
| `imovel_id` | **`FT_Leads.IdImovel`** (NÃO `Realty_Id`, que é o nome no transacional e em `FT_RealtyRelation`) | 96,60%; 0 órfãos contra `realties.Id` |
| `entrada` | `FT_Leads.CreatedAt` | 100% (é o único caminho INDEXADO — `IDX_FT_Leads_CreatedAt`; filtre por ele) |
| `distribuicao` | **`FT_Leads.DIstributedAt`** — atenção à grafia, **"I" maiúsculo** | 93,63% |
| `atendimento_registrado` | `FT_Leads.AttendedAt IS NOT NULL` — **mas ver a armadilha crítica abaixo** | 49,94% |
| `contato_registrado` | `FT_Leads.QtdeContatos > 0` (idêntico a `UltimoContato IS NOT NULL`) | 51,99% |
| `corretor_gestor` | **`FT_Leads.Gestor`** (NÃO `BrokerName`, que é quem RECEBEU o lead: coincide com o gestor em só 11,92%) | 96,42% |
| `distrito` | `FT_Leads.District` | 94,79% |
| `gestor_distrito` | **não existe com esse nome** — candidato é `FT_Leads.embaixador` (23 pessoas) | 94,78% |

### Armadilha crítica: `AttendedAt` é ESTADO ATUAL, não evento histórico

`AttendedAt` só é não-nulo enquanto `Status = 'Atendimento'`; nos 6.371 leads `Removido` é
nulo em **100%**, inclusive nos 4.560 que têm contato registrado. O carimbo é APAGADO quando
o lead sai do atendimento. Contra o histórico (`newcore.facstatushistory`, `StatusAfter = 12`):

- passaram por atendimento algum dia: **86,54%**; mantêm `AttendedAt`: **49,94%**;
- dos 4.211 "sem tratamento" pela regra ingênua, **1.956 (46,45%) foram atendidos**;
- a regra ingênua **superestima o abandono em ~1,87×** em 90 dias e em **+21,6%** na janela
  real de 3 dias (197 ingênuo vs 162 corrigido, 28→31/08).

Como a aba "leads sem tratamento" é instrumento de COBRANÇA de pessoas, a escolha da
definição muda quem é acusado de abandono. **Decisão do dono, registrada em `docs/decisoes.md`
— não resolver no código.**

### Consequência para a Spec §4.3: duas colunas sem fonte

"Semanas consecutivas em destaque" e "leads acumulados na janela atual" viriam de
`adsrealtyextra_historic`, **morta desde 27/06/2023**. Não há fonte no Newcore.

**Passaram a ter fonte no Registro próprio** (D-021, 2026-09-01): `registro.janela_destaque`
tem produtor — a rodada de segunda acumula por carga aprovada. As colunas se preenchem desde
a primeira rodada; o que é parcial não é a presença, é a **profundidade** do histórico, e a
planilha declara isso enquanto houver janela em curso aberta na primeira carga que o produtor
viu. Duas limitações vão declaradas junto: os leads são amostra de três dias num ciclo de sete
(a §2.1 pede o acumulado da janela inteira) e as datas são as da APROVAÇÃO da carga, não as da
aplicação manual na vitrine — que o sistema não observa.

Imóvel fora da carga continua com `None` nas duas: ausência declarada, nunca zero.

### Outras armadilhas medidas

- **`DIstributedAt` é a ÚLTIMA distribuição** (origem: `facs.LastDistributedAt`), não a
  primeira. `facs.Redistributed = 1` em **25,78%** dos leads de 90d (`QtyRedists` até 4): em
  um quarto dos casos "tempo desde a distribuição" é *desde a redistribuição*. Reconstruir a
  original exigiria `facstatushistory`.
- **`entrada` e `distribuicao` são genuinamente distintas** (diferem em 96,41% dos casos), mas
  o atraso mediano é de **49 s** — o sinal está na cauda: p75 = 16,2 h, p90 = 6,4 dias.
- **`districts.Ambassador_Id` está degenerado**: 1 único valor distinto para 1.616 distritos.
  Não usar; a referência viva é `FT_Districts.Ambassador_Name` / `FT_Leads.embaixador`.
  `districts.AmbassadorManager_Id` tem só 2 pessoas para 1.616 distritos (camada acima).
- **`facs.QtyRedists` mudou de comportamento por volta de 25/08/2026** (de ~0,3% para 70–80%
  ao dia): não usar série histórica sem checar a quebra.
- **`fac_followups` e `brokertriedcontacts` não servem**: o primeiro cobre 4,43% dos leads; o
  segundo não tem `Fac_Id`.
- `TABLE_ROWS` **subestimou** `FT_Leads` em 13% (978.890 vs 1.128.909 real) — a armadilha já
  registrada só citava superestimação; o certo é sempre `COUNT(*)`.

### Volume da janela (dimensionamento)

Sexta 00:00 → segunda 00:00, últimas 12 semanas: **381 a 582 leads, mediana ≈ 511**; a janela
de 28–31/08 teve 701 leads / 625 imóveis. A consulta de segunda lê centenas de linhas — custo
desprezível. `FT_Leads` é atualizada praticamente em tempo real (não é snapshot diário).

### Corroboração da Spec §4.4

Latência distribuição → 1º atendimento (30d, n = 4.398): **82,2% em até 1 hora** (a Spec diz
85%), 98,5% em 24 h, mediana 74 s. Mesma ordem de grandeza — a afirmação da Spec se sustenta.
