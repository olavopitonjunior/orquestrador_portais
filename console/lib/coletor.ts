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
  idadeDias: number | null; // dias desde a coleta (para a janela nº 5, nula)
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
