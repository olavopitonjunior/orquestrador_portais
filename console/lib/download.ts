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
import { ZipGrandeDemais, zipStore } from "./zip";

/** O pacote com todas as abas presentes e com conteúdo. */
export const TODAS = "todas.zip";

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
  if (aba === null && arquivo !== TODAS)
    return texto(
      `arquivo desconhecido; as abas são ${ABAS.map((a) => `${a}.csv`).join(", ")} — ou ${TODAS}, com todas juntas`,
      404,
    );

  let data: string | null;
  try {
    data = await l.dataDaRodada(id);
  } catch (erro) {
    // Banco fora não é "rodada sem data": o diagnóstico vai para o log do servidor.
    l.registrar?.(`[console] falha ao ler a data de referência da rodada ${id}`, erro);
    return texto("não foi possível consultar o Registro; o detalhe está no log do servidor", 503);
  }
  if (!data) return texto("a rodada não gravou data de referência; não há como localizar a planilha", 404);

  if (aba === null) return zipDeTodas(id, data, l);

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

/** `todas.zip`: as abas presentes e com conteúdo, na ordem de `ABAS`. Aba ausente ou de
 *  0 bytes fica de fora (o zip não deve esconder o que a tela acusa) — e se não sobrar
 *  nenhuma, é 404, não um zip vazio. O carimbo de data das entradas é a data de
 *  referência da rodada: mesmo conteúdo, mesmos bytes. */
async function zipDeTodas(id: number, data: string, l: Leituras): Promise<Response> {
  const entradas = [];
  for (const a of ABAS) {
    const bytes = await l.bytesDaAba(data, a);
    if (bytes !== null && bytes.length > 0) entradas.push({ nome: `${a}.csv`, dados: bytes });
  }
  if (entradas.length === 0) return texto(`sem planilha em disco para ${data}`, 404);
  const [ano, mes, dia] = data.split("-").map(Number);
  let zip: Uint8Array;
  try {
    zip = zipStore(entradas, new Date(ano, mes - 1, dia));
  } catch (erro) {
    // Só o teto vira 413; qualquer outra falha do escritor é defeito nosso, e dizer
    // "grande demais" ao cliente esconderia o bug.
    if (erro instanceof ZipGrandeDemais) {
      l.registrar?.(`[console] zip da planilha da rodada ${id} acima do teto`, erro);
      return texto("a planilha é grande demais para ir num zip só; baixe aba por aba", 413);
    }
    l.registrar?.(`[console] falha ao montar o zip da planilha da rodada ${id}`, erro);
    return texto("não foi possível montar o zip; o detalhe está no log do servidor", 500);
  }
  return new Response(zip, {
    headers: {
      "Content-Type": "application/zip",
      "Content-Disposition": `attachment; filename="rodada-${id}-planilha-${data}.zip"`,
      "X-Content-Type-Options": "nosniff",
      ...SEM_CACHE,
    },
  });
}
