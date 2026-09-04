# Coletor Externo

Raspagem do Canal Pro (Grupo OLX/ZAP) para o produto de curadoria da vitrine.
É o **agente Coletor Externo** da Spec §5: entrega, por imóvel, a nota do
portal, visualizações, cliques e URL, mais a taxa de amarração e a idade do
dado. Vive fora do caminho da decisão — o produto consome o CSV de saída por
contrato de arquivo, então o determinismo da decisão não depende desta coleta.

## Estado: em uso

a primeira raspagem real aconteceu em 03/09/2026 (canário de 10 e de 300 anúncios, `status ok`, pelo trabalhador do console). O adapter do Canal Pro está implementado (API listings, D-010); o que resta são as pendências do `bug.md` (canário e full no mesmo CSV; pausa/repetição entre páginas).

## Arquitetura

- `src/core/` — agnóstico de portal: `types`, `config`, `block-detector`
  (classificadores puros de Cloudflare), `sharding` (drill recursivo por
  facets), `csv-writer` (append-only + checkpoint por shard).
- `src/cdp/` — transporte: `browser` (anexa a um Chrome real via CDP, nunca o
  fecha), `transport` (captura de sessão por hook + fetch dentro da página
  autenticada).
- `src/portal.ts` — a interface `Portal`: a fronteira entre o núcleo e o que é
  específico de cada portal (endpoints, header de sessão, shapes, colunas).
- `src/portals/canalpro.ts` — adapter Canal Pro (stub).
- `src/run.ts` — entrypoint: `canary` (portão) e `full` (com checkpoints).

## Por que CDP no Chrome real, e não Selenium

Selenium/chromedriver é detectado por proteções anti-bot (Cloudflare Turnstile)
e não completa a coleta. O Chrome real dirigido por CDP opera como o navegador
do operador, herdando a sessão autenticada. Ver `docs/decisoes.md` D-010.

## Fluxo do operador

1. (Só se for usar o perfil padrão, o que o Chrome ≥ 136 não permite mais — ver passo 2.)
   Feche **todo** o Chrome: a porta de depuração só abre na 1ª instância do perfil.
2. Reabra com a porta e as flags anti-throttling:
   ```
   chrome --remote-debugging-port=9222 \
     --disable-background-timer-throttling \
     --disable-backgrounding-occluded-windows \
     --disable-renderer-backgrounding
   ```
   **Chrome ≥ 136 recusa `--remote-debugging-port` no perfil padrão.** Use um perfil
   separado — fora do repositório (D-012) — e nem precisa fechar o Chrome normal. No macOS:
   ```
   open -na "Google Chrome" --args --remote-debugging-port=9222 \
     --user-data-dir="$HOME/.chrome-canalpro" \
     --disable-background-timer-throttling \
     --disable-backgrounding-occluded-windows \
     --disable-renderer-backgrounding "https://canal-pro.grupozap.com/"
   ```
3. Faça login no Canal Pro nessa janela (perfil novo = login e Cloudflare de novo) e
   deixe a aba do painel aberta.
4. `npm run canary` (valida sem bloqueio) e depois `npm run full`.
5. Se aparecer o arquivo `out/NEEDS_WARM.flag`, a sessão caiu — logue de novo na janela
   de depuração (passo 3) e rode de novo.

## Segredos — o que NUNCA entra neste repositório

Este diretório é público (decisão D-012). **Fora daqui, sempre**: senha/e-mail
de conta do portal, o perfil do Chrome (`OUT_DIR`/`tmp`), cookies, `cf_clearance`
capturado. As credenciais são lidas de `process.env` no adapter, nunca embutidas
no código; `out/` e `tmp/` estão no `.gitignore`.

## Proveniência

O núcleo foi portado, arquivo a arquivo, do projeto **`imovelweb-ativos`**
(raspador validado do dono contra o painel ImovelWeb):

- Repositório: `task-titan` (grupo `newcore-team`), branch `feat/imovelweb-ativos`
- Commit de origem: `03747d9` ("fix(imovelweb-ativos): checkpoint por shard,
  defaults seguros e URL/num robustos")
- **A fonte é uma working copy local (OneDrive `mac-migration`), não publicada no
  GitHub** — a proveniência aponta para algo que só o dono enxerga.

O legado Selenium do projeto de origem (bloqueado pelo Turnstile) **não** foi
portado; a nomenclatura específica do ImovelWeb foi generalizada ou movida para
trás da interface `Portal`.

## Testes e CI

`npm run typecheck` (tsc --noEmit) e `npm test` (node:test sobre os módulos
puros: classificação de bloqueio, sharding, CSV). O job de CI deste diretório
**não é obrigatório** na proteção de `main` — só o job `verificar` (Python) é —
até que seja adicionado à proteção pelo dono.
