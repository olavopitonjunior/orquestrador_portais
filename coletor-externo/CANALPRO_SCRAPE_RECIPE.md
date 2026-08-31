# Canal Pro — receita de raspagem (reconhecimento de 31/08/2026)

Mapeamento da API interna do painel do Canal Pro (Grupo OLX/ZAP), feito com o
operador logado no Chrome real. Documenta **estrutura**, nunca segredos: nomes
de header sim, valores nunca (o `authorization` e os `x-publisherid/x-contractid/
x-odinid` identificam a conta do dono — fora dos limites da D-012).

## Endpoint e forma

- **`POST https://gandalf-api.grupozap.com/`** — API GraphQL.
- **operationName: `listings`** — a listagem dos anúncios do anunciante.
- **Paginação linear** por `pageNumber` / `pageSize` (30). A resposta traz
  `totalResults` e `totalPages` — não há sharding por facets (mais simples que o
  ImovelWeb). No coletor, isso vira o caminho `collectPage` + checkpoint por
  página (retomada sem re-bater o portal do início).

## Autenticação

Headers (só **nomes** — valores vêm da sessão do operador logado, capturados de
uma XHR `listings` real via hook in-page, e nunca persistidos):

- `authorization` (Bearer)
- `x-publisherid`, `x-contractid`, `x-odinid`, `x-clientid`, `x-company`,
  `x-appversion`, `x-publishercontracttype`
- `accept: application/json`, `content-type: application/json`

Não é cookie — o coletor herda a sessão via CDP no Chrome real do operador
(D-010) e reusa os headers capturados.

## Variáveis usadas (mínimas)

`contractType: "REAL_ESTATE"`, `orderBy: "CREATED_AT"`, `orderDesc: true`,
`pageSize: 30`, `pageNumber: <n>`. Filtros de lista (`listingStatus`,
`publicationType`, `businessType`) enviados vazios = todos.

## Resposta — `data.listings.listListing[]`

Campos que o adapter consome (query MÍNIMA — invariante 3, sem endereço/geo/
imagens/contato de lead):

| Campo do portal | Uso no produto |
|---|---|
| `externalId` | amarração com o imóvel interno do Newcore |
| `id` | identificador do anúncio no portal |
| `score` + `scoreName` (`"lqsBeta"`, escala ~5.580–9.580) | **nota do portal** (crua, sem reescala) |
| `publicationType` (`STANDARD` / `PREMIUM`) | nível de publicação |
| `status` (`ACTIVE` …) | situação |
| `pricingInfos[].price` (prefere `businessType: SALE`) | preço |
| `portals` (`OLX`, `VIVAREAL`, `ZAP`) | portais do anúncio (confirma o plano Exclusivo) |
| `createdAt` | data de criação (formato `dd/MM/yyyy HH:mm:ss`) |
| `leads.views` | visualizações |
| `leads.{contactForm, phoneView, clickProposal, clickWhatsapp, clickSchedule}` | cliques por tipo — **contagens agregadas, não identidades**; guardados em colunas separadas (não somados) |

**Deliberadamente NÃO pedidos** (invariante 3 — o CSV alimenta o Analista de
Perfil, que usa modelo): `address`, `street`, `point{lat,lon}`, `zipCode`,
`neighborhood`, `originalAddress`, `images`. O cruzamento de características do
imóvel vem do Coletor Interno; o Externo só traz performance de portal.

## Lacuna conhecida

A **URL pública do anúncio não vem na listagem** (`url` fica `null`). Ela pode
existir no detalhe do anúncio ou ser construída a partir do `id`/portal — a
resolver numa iteração futura, se o produto precisar do link direto. Nota e
performance, que são o essencial da Spec §5, estão todos presentes.

## Volume observado

~1.835 páginas × 30 = ~55 mil anúncios ativos do anunciante (31/08/2026).

## Paginação estável

Ordenação por `CREATED_AT` decrescente (chave imutável), não `UPDATED_AT`: a
retomada por página não pula nem duplica anúncios editados durante a coleta. O
resíduo remanescente é pequeno — um anúncio *criado* durante as ~2h de coleta
desloca a fronteira em uma posição; dedupe por `id` na leitura fecha isso, como
no ImovelWeb. O checkpoint guarda `lastPage`; a retomada continua de `lastPage+1`.

## Risco em aberto — validação de transporte

O **shape da resposta e o parsing estão confirmados** com dados reais (via
observação da rede da app). O que **não** foi validado é o **transporte POST
cross-origin por injeção**: `canal-pro.grupozap.com` chama `gandalf-api.
grupozap.com` (subdomínios distintos → CORS), e tentativas de replicar o POST
por injeção deram `Failed to fetch` — a página instrumenta `fetch` (Datadog
RUM), e a cadeia interfere. A app faz a mesma chamada com sucesso o tempo todo,
então o CORS é permitido para o fluxo natural dela.

O **canário do coletor via CDP** (rodando como a própria página, sem injeção
externa) é quem valida o transporte de fato. Se o `fetch` in-page também
esbarrar no wrapper do Datadog, o ajuste provável é usar `XMLHttpRequest` (não
instrumentado da mesma forma) ou capturar o `fetch` nativo antes da
instrumentação. Fica registrado como o primeiro item do canário, não como
suposição de que "já funciona".
