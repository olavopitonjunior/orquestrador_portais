# Mapa de Dados de Referência

Derivado da seção "Base factual" do PRD versão 5.0 (levantamento direto nas fontes em 28/08/2026). Existe para que ninguém precise redescobrir o banco. Nenhum número aqui foi estimado: tudo vem dos documentos. Onde falta número, a lacuna está apontada.

O PRD prevalece sobre este mapa. Se algo aqui divergir do PRD, é bug deste arquivo.

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

Lacuna conhecida: **quantidade de vagas não está nesta tabela nem em `realties`**. A localização do campo é investigação aberta.

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
| `webscraping_processing_grupo_zap` | 105 execuções | Histórico da raspagem; volume máximo de 36.420 anúncios; ~62% das execuções com erro ou sem processar |
| `adsportalconfigs` | — | Registra 350 destaques e 1 super destaque; **inativa e desatualizada em quase vinte vezes. Não é fonte de cota** |

Maiores tabelas relevantes por volume (cuidado com custo de consulta): `realtyattributes` (4,2 milhões), `brokerneighborhoods` (6,1 milhões), `userbrokerrelationshipshistoric` (7,5 milhões).

Observação sobre URL do portal: **a URL do anúncio não existe em nenhuma tabela do Newcore**. O único endereço armazenado é o do site da própria Newcore, em caminho relativo. A URL do portal só pode ser capturada pelo Coletor Externo durante a raspagem — não é recuperável depois.

---

## Defeitos de dado confirmados

Armadilhas conhecidas. Campos aparentemente úteis que não podem ser usados sem tratamento — ou não podem ser usados de forma alguma.

1. `realties.MarketingType_Id` (tipo de comercialização) é **nulo em 96%** dos ativos.
2. `realtyaddresses.ValueZone_Id` (zona de valor) é **nulo em 98%** dos imóveis ativos relevantes. A ligação com distrito vem de `FT_RealtyRelation`.
3. `FT_LeadsOffers.DaysConversion` (ciclo de conversão) apresenta **valores negativos** e exige tratamento.
4. Cerca de **44% do estoque elegível não possui avaliação por categoria** em `realty_score_category_score`. O motivo é investigação aberta. Imóvel sem avaliação não é excluído: passa e recebe penalidade.
5. `realties` **não expõe quantidade de vagas** diretamente. Localização do campo é investigação aberta.
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

### Aviso sobre os ganhos de relaxamento

Os ganhos por regra relaxada — fotos +133, cadastro completo +569, atualização em 90 dias +1.680, gestor produtivo +1.747, capacidade do distrito +5.686 — foram medidos com **mínimo de TRÊS corretores por distrito**, enquanto o parâmetro adotado é **DOIS**. O próprio PRD os mantém como "referência de ordem de grandeza; os valores absolutos mudam com o mínimo de dois". **Não usar como conferência exata.** A Spec §6.6 reproduz esses números sem a ressalva — o PRD prevalece.

---

## Lacunas apontadas (não estimar)

- Contagem de registros de `adsportalconfigs`: o PRD não a informa, apenas o conteúdo (350 + 1) e o estado (inativa).
- Contagem de registros de `realty_score_category_score`: não informada; apenas o percentual de estoque elegível sem avaliação (~44%).
- Localização do campo de vagas: investigação aberta.
- A tabela de relatórios da raspagem citada nas pendências (43 registros, todos com erro, todos de dezembro de 2025): nome exato da tabela não consta dos documentos; investigação aberta sobre se ainda é usada.
