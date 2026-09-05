import { readFile, access } from "node:fs/promises";
import { resolve } from "node:path";

// Saúde da coleta externa a partir dos ARQUIVOS que o raspador grava (contrato de
// arquivo, Spec §5 / D-010) — o console NÃO lê o Newcore (invariante 1) nem o MySQL:
// só o Postgres próprio e estes artefatos locais. Diretório do coletor via
// COLETOR_OUT_DIR (default: ../coletor-externo/out, ao lado do console no repo).

// "corrompido" ≠ "ausente": o raspador rodou e escreveu lixo (ex.: crash no meio da
// escrita) é sinal de atenção; "ausente" é ele nunca ter rodado.
export type EstadoColeta = "ok" | "blocked" | "error" | "corrompido" | "ausente";

export type SaudeColeta = {
  estado: EstadoColeta;
  needsWarm: boolean; // NEEDS_WARM.flag presente = sessão caiu, precisa re-login
  coletadoEm: string | null; // finishedAt do status.json (ISO); null se inválido
  idadeDias: number | null; // dias desde a coleta (a janela nº 5 vale 2 dias, D-034)
  linhas: number | null; // rows gravadas (status.json)
  // `outDir` NÃO faz parte do tipo público: é caminho absoluto do servidor e não
  // deve escapar daqui (achado do security-audit). Vai só no `title` do card, via
  // `outDirPublico()`, que devolve o caminho para diagnóstico local do operador.
};

function outDir(): string {
  return process.env.COLETOR_OUT_DIR
    ? resolve(process.env.COLETOR_OUT_DIR)
    : resolve(process.cwd(), "..", "coletor-externo", "out");
}

async function existe(caminho: string): Promise<boolean> {
  try {
    await access(caminho);
    return true;
  } catch {
    return false;
  }
}

type LeituraStatus =
  | { tipo: "ok"; dados: Record<string, unknown> }
  | { tipo: "ausente" }
  | { tipo: "corrompido" };

async function lerStatus(caminho: string): Promise<LeituraStatus> {
  if (!(await existe(caminho))) return { tipo: "ausente" };
  try {
    return { tipo: "ok", dados: JSON.parse(await readFile(caminho, "utf-8")) };
  } catch {
    // O arquivo existe mas não parseia: o raspador rodou e escreveu lixo. Não é
    // "nunca rodou" — o operador precisa saber a diferença.
    return { tipo: "corrompido" };
  }
}

/** Data válida do `finishedAt`, ou null se ausente/corrompida (evita NaN na UI). */
function dataValida(v: unknown): string | null {
  if (typeof v !== "string") return null;
  return Number.isNaN(new Date(v).getTime()) ? null : v;
}

function idadeEmDias(iso: string): number {
  const ms = Date.now() - new Date(iso).getTime();
  return Math.floor(ms / 86_400_000);
}

/** Caminho de `out/` consultado — só para diagnóstico local (title do card). */
export function outDirPublico(): string {
  return outDir();
}

/** Lê a saúde da coleta externa. Nunca lança — sem arquivos = "ausente". */
export async function saudeColeta(): Promise<SaudeColeta> {
  const dir = outDir();
  const leitura = await lerStatus(resolve(dir, "status.json"));
  const needsWarm = await existe(resolve(dir, "NEEDS_WARM.flag"));
  const dados = leitura.tipo === "ok" ? leitura.dados : null;

  const finishedAt = dataValida(dados?.finishedAt);
  const result = typeof dados?.result === "string" ? dados.result : null;
  const rows = typeof dados?.rows === "number" ? dados.rows : null;

  let estado: EstadoColeta;
  if (needsWarm || result === "blocked") estado = "blocked";
  else if (leitura.tipo === "corrompido") estado = "corrompido";
  else if (result === "ok") estado = "ok";
  else if (result === "error") estado = "error";
  else estado = "ausente";

  return {
    estado,
    needsWarm,
    coletadoEm: finishedAt,
    idadeDias: finishedAt ? idadeEmDias(finishedAt) : null,
    linhas: rows,
  };
}

export type Amarracao = {
  linhas: number; // linhas de dado (sem o cabeçalho)
  noFormato: number; // codigoImovel no formato `{Id}{letra opcional}` — o que o leitor da rodada amarra
  vazios: number;
  foraDoFormato: number;
  exemplos: string[]; // até 3 valores distintos do campo, para o operador VER o formato
};

/** Parser mínimo do CSV do raspador: toda célula entre aspas, `""` escapa aspas,
 *  CRLF. Não é um parser geral — é o contrato de `csv-writer.ts`, e só ele. Divergência
 *  conhecida com a rodada (que usa `csv.DictReader`): uma quebra de linha DENTRO de uma
 *  célula desloca a coluna aqui, porque o arquivo é partido por linha antes do parse. O
 *  `codigoImovel` é texto do anunciante; improvável, e a medição é diagnóstico, não decisão. */
function celulasDaLinha(linha: string): string[] {
  const celulas: string[] = [];
  let atual = "";
  let dentro = false;
  for (let i = 0; i < linha.length; i++) {
    const c = linha[i];
    if (dentro) {
      if (c === '"') {
        if (linha[i + 1] === '"') {
          atual += '"';
          i++;
        } else dentro = false;
      } else atual += c;
    } else if (c === '"') dentro = true;
    else if (c === ",") {
      celulas.push(atual);
      atual = "";
    } else atual += c;
  }
  celulas.push(atual);
  return celulas;
}

/** Mede a amarração do CSV que o canário escreveu — SEM ler o Newcore (invariante 1):
 *  o formato `{Id}{letra opcional}` é a condição que `dados/coletor_externo._imovel_id_de`
 *  exige (visto na primeira raspagem real, 03/09/2026: `431347A`, 300 de 300 — a letra é a rotação de
 *  marketing, `realties.NewIdMarketingRotation`); casar de fato com um imóvel ativo só a
 *  rodada confere. `null` se não há CSV. */
export async function amarracaoDoCsv(portal = "canalpro"): Promise<Amarracao | null> {
  const caminho = resolve(outDir(), `${portal}.csv`);
  if (!(await existe(caminho))) return null;
  const texto = await readFile(caminho, "utf-8");
  const linhas = texto.split(/\r?\n/).filter((l) => l.length > 0);
  if (linhas.length === 0) return { linhas: 0, noFormato: 0, vazios: 0, foraDoFormato: 0, exemplos: [] };
  const cabecalho = celulasDaLinha(linhas[0]);
  const col = cabecalho.indexOf("codigoImovel");
  if (col < 0) return { linhas: linhas.length - 1, noFormato: 0, vazios: 0, foraDoFormato: linhas.length - 1, exemplos: [] };
  const r: Amarracao = { linhas: 0, noFormato: 0, vazios: 0, foraDoFormato: 0, exemplos: [] };
  const vistos = new Set<string>();
  for (const linha of linhas.slice(1)) {
    r.linhas++;
    const v = (celulasDaLinha(linha)[col] ?? "").trim();
    if (v === "") r.vazios++;
    else if (/^\d+[A-Z]?$/.test(v)) r.noFormato++;  // maiúscula, como `_imovel_id_de`
    else r.foraDoFormato++;
    if (v !== "" && !vistos.has(v) && r.exemplos.length < 3) {
      vistos.add(v);
      r.exemplos.push(v);
    }
  }
  return r;
}
