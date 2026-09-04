import { responderDownload } from "@/lib/download";
import { arquivoDaAba } from "@/lib/planilha";
import { parametrosDaRodada } from "@/lib/registro";

// GET /rodada/<id>/planilha/<aba>.csv — o CSV de uma aba, como está em disco.
// A decisão inteira mora em `lib/download.ts` (testada sem banco e sem disco); este
// arquivo só liga as leituras reais.

export const dynamic = "force-dynamic";

export async function GET(_req: Request, ctx: { params: Promise<{ id: string; arquivo: string }> }) {
  const { id, arquivo } = await ctx.params;
  return responderDownload(id, arquivo, {
    dataDaRodada: async (n) => {
      const p = await parametrosDaRodada(n);
      return typeof p?.data_referencia === "string" ? p.data_referencia : null;
    },
    bytesDaAba: async (data, aba) => {
      const b = await arquivoDaAba(data, aba);
      return b === null ? null : new Uint8Array(b);
    },
    registrar: (m, e) => console.error(m, e),
  });
}
