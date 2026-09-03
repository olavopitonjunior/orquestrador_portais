import { Pool } from "pg";

// Pool único (lazy), reusado entre requests. `POSTGRES_URL` vem do ambiente
// (op://Personal/orquestrador_portais/POSTGRES_URL); fail-fast se ausente, como a
// camada Python (`conexao.url()`) — nunca um DSN com credencial embutido no repo.
//
// O console é camada de OPERAÇÃO: nesta fase SÓ LÊ o Registro (esquema `registro`).
// Não toca o caminho da decisão (invariante 4) e não lê o Newcore (invariante 1);
// qualquer escrita futura é só no Postgres próprio (invariante 2).
// Singleton cacheado em globalThis para não vazar conexões a cada hot-reload do
// `next dev` (em produção, `next start` é processo único e isto é um Pool só).
const g = globalThis as unknown as { __registroPool?: Pool };

export function db(): Pool {
  if (!g.__registroPool) {
    const url = process.env.POSTGRES_URL;
    if (!url) {
      throw new Error(
        "POSTGRES_URL ausente no ambiente. Gere o .env DENTRO de console/ " +
          "(op inject -i .env.tmpl -o .env) — o console lê o seu próprio .env, não o da " +
          "raiz — ou exporte a URL do Postgres próprio.",
      );
    }
    g.__registroPool = new Pool({
      connectionString: url,
      // Teto por consulta. O console lê tabelas que crescem — `decisao_imovel` tem
      // ~7 mil linhas por rodada — e uma consulta longa segurando transação bloqueia
      // o `CREATE INDEX CONCURRENTLY` que o checkpointer do LangGraph roda ao abrir a
      // aprovação. Já travou de verdade, do lado Python, e a correção lá foi ordem de
      // aquisição; aqui é teto. Uma tela que demora 15s já está quebrada de qualquer
      // forma: falhar é melhor que travar o fluxo de quem aprova.
      options: "-c statement_timeout=15s",
    });
  }
  return g.__registroPool;
}
