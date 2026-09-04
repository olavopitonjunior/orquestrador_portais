// A planilha da rodada, lida do disco — os cinco CSVs que `entrega/planilha_piloto.py`
// escreve em `saida/sexta/<AAAA-MM-DD>/`.
//
// O console lê o ARTEFATO, não o Registro, de propósito: a planilha é o que foi de fato
// entregue e aprovado (Spec §3.1), e a tela existe para o dono ver o que o sistema
// entregou. O que o Registro guarda a mais (notas por imóvel) vem na fatia seguinte.
//
// Três armadilhas do formato, todas do `csv.DictWriter` padrão do Python:
// 1. aspas só quando necessário (QUOTE_MINIMAL), `""` escapa aspas, e uma célula entre
//    aspas pode conter vírgula E quebra de linha — por isso o parser é por caractere,
//    não `split` por linha;
// 2. terminador `\r\n`;
// 3. aba vazia é UMA linha sem cabeçalho: `(sem linhas nesta rodada)`. Não é erro — é a
//    aba dizendo que a etapa rodou e não produziu linha.

import { readFile, readdir, stat } from "node:fs/promises";
import { resolve } from "node:path";

export const ABAS = [
  "super_destaque",
  "destaque",
  "excluidos_por_regra",
  "relaxamento",
  "parametros_e_limitacoes",
] as const;
export type Aba = (typeof ABAS)[number];

export const SENTINELA_VAZIA = "(sem linhas nesta rodada)";

export type Tabela = {
  colunas: string[];
  linhas: string[][];
  vazia: boolean; // a SENTINELA estava lá: a etapa rodou e não produziu linha
  semConteudo: boolean; // arquivo de 0 bytes: não é "sem linhas", é escrita que não aconteceu
};

export type Planilha = {
  diretorio: string;
  abas: Partial<Record<Aba, Tabela>>;
  ausentes: Aba[]; // arquivos que deveriam existir e não existem
};

/** Parser de CSV no dialeto do `csv` do Python (QUOTE_MINIMAL, `""`, CRLF). */
export function parsearCsv(texto: string): string[][] {
  const linhas: string[][] = [];
  let linha: string[] = [];
  let celula = "";
  let dentro = false;
  let i = 0;
  while (i < texto.length) {
    const c = texto[i];
    if (dentro) {
      if (c === '"') {
        if (texto[i + 1] === '"') {
          celula += '"';
          i += 2;
          continue;
        }
        dentro = false;
        i++;
        continue;
      }
      celula += c;
      i++;
      continue;
    }
    if (c === '"' && celula.length === 0) {
      // Só abre célula quotada no INÍCIO da célula: uma aspa no meio de célula não
      // quotada é texto (é o que `csv.reader` do Python faz); tratá-la como abertura
      // engolia o resto do arquivo numa célula só.
      dentro = true;
    } else if (c === ",") {
      linha.push(celula);
      celula = "";
    } else if (c === "\r" || c === "\n") {
      if (c === "\r" && texto[i + 1] === "\n") i++;
      linha.push(celula);
      linhas.push(linha);
      linha = [];
      celula = "";
    } else {
      celula += c;
    }
    i++;
  }
  if (celula.length > 0 || linha.length > 0) {
    linha.push(celula);
    linhas.push(linha);
  }
  return linhas;
}

export function tabelaDe(texto: string): Tabela {
  const registros = parsearCsv(texto);
  if (registros.length === 1 && registros[0].length === 1 && registros[0][0] === SENTINELA_VAZIA) {
    return { colunas: [], linhas: [], vazia: true, semConteudo: false };
  }
  if (registros.length === 0) return { colunas: [], linhas: [], vazia: false, semConteudo: true };
  const [colunas, ...linhas] = registros;
  return { colunas, linhas, vazia: false, semConteudo: false };
}

function raizDaSaida(): string {
  return process.env.SAIDA_SEXTA_DIR
    ? resolve(process.env.SAIDA_SEXTA_DIR)
    : resolve(process.cwd(), "..", "saida", "sexta");
}

/** As datas com planilha no disco, mais recente primeiro. */
export async function datasComPlanilha(): Promise<string[]> {
  try {
    const nomes = await readdir(raizDaSaida());
    return nomes.filter((n) => /^\d{4}-\d{2}-\d{2}$/.test(n)).sort().reverse();
  } catch {
    return [];
  }
}

const DATA_VALIDA = /^\d{4}-\d{2}-\d{2}$/;

/** Os bytes CRUS de uma aba, para download — o artefato como foi entregue, sem BOM,
 *  sem reescrita. É o ÚNICO outro lugar que transforma data em caminho, e reaplica as
 *  duas guardas de `lerPlanilha`: a data só vira caminho se for `AAAA-MM-DD`, e a aba
 *  só se estiver na lista fechada `ABAS`. `null` para data inválida, aba desconhecida
 *  ou arquivo ausente — o chamador decide o que dizer. Um arquivo de 0 bytes volta
 *  como Buffer vazio de propósito: é `semConteudo`, não "sem linhas", e quem serve
 *  precisa distinguir em vez de entregar um CSV vazio como se fosse planilha. */
export async function arquivoDaAba(data: string, aba: string): Promise<Buffer | null> {
  if (!DATA_VALIDA.test(data)) return null;
  if (!(ABAS as readonly string[]).includes(aba)) return null;
  try {
    return await readFile(resolve(raizDaSaida(), data, `${aba}.csv`));
  } catch {
    return null;
  }
}

/** A planilha de UMA data. `null` se o diretório não existe. O nome da data é
 *  validado antes de virar caminho: nada além de `AAAA-MM-DD` chega ao disco. */
export async function lerPlanilha(data: string): Promise<Planilha | null> {
  if (!DATA_VALIDA.test(data)) return null;
  const diretorio = resolve(raizDaSaida(), data);
  try {
    if (!(await stat(diretorio)).isDirectory()) return null;
  } catch {
    return null;
  }
  const abas: Partial<Record<Aba, Tabela>> = {};
  const ausentes: Aba[] = [];
  for (const aba of ABAS) {
    try {
      abas[aba] = tabelaDe(await readFile(resolve(diretorio, `${aba}.csv`), "utf-8"));
    } catch {
      ausentes.push(aba);
    }
  }
  return { diretorio, abas, ausentes };
}
