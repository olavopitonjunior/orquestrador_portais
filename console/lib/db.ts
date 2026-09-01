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
        "POSTGRES_URL ausente no ambiente. Gere o .env (op inject -i .env.tmpl -o .env) " +
          "ou exporte a URL do Postgres próprio.",
      );
    }
    g.__registroPool = new Pool({ connectionString: url });
  }
  return g.__registroPool;
}
