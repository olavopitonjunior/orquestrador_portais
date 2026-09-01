# Console do Operador

Interface de **operação e observabilidade** da curadoria da vitrine (D-011). Roda na
máquina do gestor da vitrine, sem exposição externa na v1.

## Enquadramento (o que é e o que NÃO é)

O console é camada de OPERAÇÃO. **Lê** o Registro (esquema `registro` do Postgres
próprio) e, nas próximas fases, os artefatos do coletor (`out/`); **não toca o
caminho da decisão** (invariante 4) e **não lê o Newcore** (invariante 1). A planilha
continua o entregável contratual; o console a exibe, não a substitui. Qualquer escrita
futura é só no Postgres próprio (invariante 2).

## Stack

- **Next.js** (App Router) + **React** + **TypeScript**, full-stack numa peça só.
- **pg** (node-postgres) lendo o Registro por SQL direto — a camada `lib/registro.ts`
  espelha o que `src/dados/registro/leitura.py` expõe, sem reimplementar regra.

## Fases

- **Fase 1** (esta): fundação — leitura do Registro e **histórico de rodadas** (estado
  completa/degradada/abortada, contagens por nível, aprovação). A seguir: caixa de
  ações (login do portal / NEEDS_WARM, pendências), saúde das fontes e logs.
- **Fase 2**: painéis de agente/rodada ao vivo, painel da decisão + botão de aprovação,
  custos, editor de prompts — cresce com o grafo.

## Rodar localmente

```bash
cd console
npm install
op inject -i .env.tmpl -o .env   # gera o .env (convenção do repo; .env é ignorado)
npm run dev                      # http://localhost:3000
```

`POSTGRES_URL` vem do ambiente (`op://Personal/orquestrador_portais/POSTGRES_URL`, via
`.env.tmpl`) — nunca um DSN com credencial no repo. Para um Postgres local sem 1Password,
basta exportar a variável na mão. Sem ela, o console mostra o erro em vez de quebrar (e o
detalhe fica no log do servidor).

Scripts: `npm run dev`, `npm run build`, `npm run start`, `npm run typecheck`.
