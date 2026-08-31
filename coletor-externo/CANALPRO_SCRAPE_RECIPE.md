# Canal Pro — receita de raspagem (reconhecimento de 31/08/2026)

Mapeamento da API interna do painel do Canal Pro (Grupo OLX/ZAP), feito com o
operador logado no Chrome real. Documenta **estrutura**, nunca segredos: nomes
de header sim, valores nunca (o `authorization` e os `x-publisherid/x-contractid/
x-odinid` identificam a conta do dono — fora dos limites da D-012).

## Endpoint e forma

- **`POST https://gandalf-api.grupozap.com/`** — API GraphQL.
- **operationName: `listings`** — a listagem dos anúncios do anunciante.
- **Paginação linear** por `pageNumber` / `pageSize` (100 — o máximo que o canário validou). A resposta traz
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
`pageSize: 100`, `pageNumber: <n>`. Filtros de lista (`listingStatus`,
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

~55 mil anúncios ativos (`totalResults`), ~551 páginas a 100/página (31/08/2026).

## Paginação estável

Ordenação por `CREATED_AT` decrescente (chave imutável), não `UPDATED_AT`: a
retomada por página não pula nem duplica anúncios editados durante a coleta. O
resíduo remanescente é pequeno — um anúncio *criado* durante as ~2h de coleta
desloca a fronteira em uma posição; dedupe por `id` na leitura fecha isso, como
no ImovelWeb. O checkpoint guarda `lastPage`; a retomada continua de `lastPage+1`.

## Transporte VALIDADO (canário de 31/08/2026)

O canário foi rodado com o operador logado, contra a API real. Resultado:

- **A autenticação é por header (Bearer), não por cookie.** Uma requisição POST
  cross-origin (`canal-pro` → `gandalf-api`) **com** credenciais é rejeitada no
  preflight CORS (`fetch`/XHR com `credentials: 'include'` → status **0**);
  **sem** credenciais autentica pelos headers e retorna **200** (`credentials:
  'omit'` → 200). `fetch` sem credenciais basta — não foi preciso trocar por
  `XMLHttpRequest`. É por isso que o adapter passa `credentials: 'omit'`
  explicitamente (o `Failed to fetch` das primeiras tentativas era o
  `credentials: 'include'`, não o mecanismo de fetch).
- **Escada 1 → 10 → 100 anúncios**: todos status 200, sem bloqueio, ~1,5–2 s por
  página, todos com `id`. `pageSize: 100` funciona (o adapter o adota: menos
  batidas no portal).
- **Query mínima confirmada contra a API real**: em 100 anúncios reais, nenhum
  trouxe campo de endereço/geo (`address` ausente) — o invariante 3 tem prova
  viva, não só o fixture.
- **Volume**: ~55 mil anúncios ativos na conta (`totalResults`), ~551 páginas a
  100/página.

Nenhum header, token ou trecho de resposta real foi transcrito aqui — só os
números agregados do canário.
