// A decisão de "o que servir" para o download de uma aba, separada do route handler
// para ser testável sem banco e sem disco: as duas leituras entram como funções.
//
// A data da planilha vem do que a RODADA gravou (`parametros_da_rodada.data_referencia`),
// nunca de query string nem de segmento de rota: o cliente escolhe a rodada, e só ela
// diz qual dia está em disco. Os únicos parâmetros de entrada são o id numérico e o
// nome do arquivo, conferido contra a lista fechada de abas antes de virar caminho
// (`arquivoDaAba` reaplica as duas guardas). Arquivo de 0 bytes é 404: a página já
// acusa "escrita que não aconteceu", e servir um CSV vazio desfaria o alarme.

import { ABAS, type Aba } from "./planilha";

export type Leituras = {
  /** `parametrosDaRodada(id)`: a data de referência gravada, ou null. Lança se o banco falhar. */
  dataDaRodada: (id: number) => Promise<string | null>;
  /** `arquivoDaAba(data, aba)`: os bytes crus, ou null se ausente. */
  bytesDaAba: (data: string, aba: Aba) => Promise<Uint8Array | null>;
  /** Para onde vai o erro de banco — a resposta ao cliente fica genérica. */
  registrar?: (mensagem: string, erro: unknown) => void;
};

const SEM_CACHE = { "Cache-Control": "no-store" };

function texto(mensagem: string, status: number): Response {
  return new Response(mensagem, {
    status,
    headers: { "Content-Type": "text/plain; charset=utf-8", ...SEM_CACHE },
  });
}

/** O nome do arquivo vira aba só se for exatamente `<aba>.csv` com a aba na lista. A
 *  classe `[a-z_]` não contém ponto nem barra, então `..`, `/`, `.csv.csv` e maiúsculas
 *  caem antes mesmo da lista. */
export function abaDoArquivo(arquivo: string): Aba | null {
  const m = /^([a-z_]+)\.csv$/.exec(arquivo);
  if (!m) return null;
  return (ABAS as readonly string[]).includes(m[1]) ? (m[1] as Aba) : null;
}

export async function responderDownload(
  idBruto: string,
  arquivo: string,
  l: Leituras,
): Promise<Response> {
  if (!/^\d+$/.test(idBruto)) return texto("rodada inválida", 404);
  const id = Number(idBruto);
  const aba = abaDoArquivo(arquivo);
  if (aba === null)
    return texto(`arquivo desconhecido; as abas são ${ABAS.map((a) => `${a}.csv`).join(", ")}`, 404);

  let data: string | null;
  try {
    data = await l.dataDaRodada(id);
  } catch (erro) {
    // Banco fora não é "rodada sem data": o diagnóstico vai para o log do servidor.
    l.registrar?.(`[console] falha ao ler a data de referência da rodada ${id}`, erro);
    return texto("não foi possível consultar o Registro; o detalhe está no log do servidor", 503);
  }
  if (!data) return texto("a rodada não gravou data de referência; não há como localizar a planilha", 404);

  const bytes = await l.bytesDaAba(data, aba);
  if (bytes === null) return texto(`sem ${aba}.csv em disco para ${data}`, 404);
  if (bytes.length === 0)
    return texto(`${aba}.csv tem 0 bytes para ${data}: a escrita não aconteceu ou foi truncada`, 404);

  return new Response(bytes, {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="rodada-${id}-${aba}.csv"`,
      "X-Content-Type-Options": "nosniff",
      ...SEM_CACHE,
    },
  });
}
