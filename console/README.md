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

- **Fase 1** (esta): o **painel do operador** —
  - **Caixa de ações**: o que precisa de você agora (refazer o login no Canal Pro quando
    a sessão cai, rodadas aguardando aprovação, parâmetros nulos pendentes).
  - **Saúde das fontes**: estado e idade da coleta externa, lida dos artefatos do
    raspador (`out/status.json`, `NEEDS_WARM.flag`) — nunca do Newcore.
  - **Histórico de rodadas**: estado (completa/degradada/abortada), contagens por nível,
    aprovação.
  A seguir: detalhe por rodada, logs do coletor e embed da planilha.
- **Fase 2**: painéis de agente/rodada ao vivo, painel da decisão + botão de aprovação,
  custos, editor de prompts — cresce com o grafo.

## Rodar localmente

```bash
cd console
npm install
op inject -i .env.tmpl -o .env   # gera o .env (convenção do repo; .env é ignorado)
npm run dev                      # http://localhost:3000
```

`POSTGRES_URL` vem do `.env.tmpl` deste diretório, e é **literal** — `postgresql:///orquestrador_portais`.
Não é DSN com credencial: a forma de socket local não carrega usuário, senha, host nem porta, e
a autenticação é a do usuário do sistema. O console lê o seu PRÓPRIO `.env`, não o da raiz.
Sem a variável, o console mostra o erro em vez de quebrar (e o detalhe fica no log do servidor).

Para a saúde da coleta externa, o console lê os artefatos do raspador. O diretório padrão
é `../coletor-externo/out`; aponte outro com `COLETOR_OUT_DIR` se necessário. Sem esses
arquivos, o painel mostra a coleta como "ausente" — não quebra.

Scripts: `npm run dev`, `npm run build`, `npm run start`, `npm run typecheck`, `npm test`.
