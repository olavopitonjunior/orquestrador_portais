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
  // O resultado TOTAL: uma linha por candidato, inclusive os excluídos, com as
  // características do imóvel. Vem primeiro porque é o que se leva para aplicar a carga.
  "apuracao",
  "super_destaque",
  "destaque",
  "excluidos_por_regra",
  "relaxamento",
  // Os padrões que o Analista achou na semana (Spec §3.1), com a classificação e o
  // que conta para o filtro do perfil — a nona regra, desde a D-027.
  "perfis",
  "parametros_e_limitacoes",
] as const;
export type Aba = (typeof ABAS)[number];

export const SENTINELA_VAZIA = "(sem linhas nesta rodada)";

export type Tabela = {
  colunas: string[];
  /** As linhas MATERIALIZADAS — no máximo o limite que o chamador declarou. */
  linhas: string[][];
  /** Quantas linhas de dados o arquivo tem, exato mesmo quando `linhas` foi truncada. */
  total: number;
  vazia: boolean; // a SENTINELA estava lá: a etapa rodou e não produziu linha
  semConteudo: boolean; // arquivo de 0 bytes: não é "sem linhas", é escrita que não aconteceu
};

/** Quantas linhas de DADOS materializar por aba. Aba não citada: todas.
 *
 *  REGRA, em uma linha: limite só é seguro em aba de que o chamador **exibe** linhas; se
 *  ele **agrega** sobre elas, o limite corrompe o agregado em silêncio. Quem declara um
 *  limite precisa enumerar quem lê `Tabela.linhas` daquela aba antes.
 *
 *  A declaração da página da rodada — com as exceções, o consumidor que obriga cada uma e
 *  o caso real que já quebrou — vive em `abas-da-rodada.ts`, que é onde o teste a trava.
 *  Aqui fica só a regra, para não haver duas cópias do mesmo texto divergindo.
 *
 *  `lerPlanilha` EXIGE o argumento, e não o deixa opcional de propósito: o defeito que a
 *  assinatura existe para impedir foi um chamador não declarar nada e levar 48.812 linhas
 *  de apuração para uma tela que não as exibe. Quem quer tudo diz isso pelo nome, com
 *  `TODAS_AS_LINHAS`. */
export type LimiteDeLinhas = Partial<Record<Aba, number>>;

/** O limite que não limita — para quem realmente precisa do arquivo inteiro. */
export const TODAS_AS_LINHAS: LimiteDeLinhas = {};

export type Planilha = {
  diretorio: string;
  abas: Partial<Record<Aba, Tabela>>;
  ausentes: Aba[]; // arquivos que deveriam existir e não existem
};

/** Parser de CSV no dialeto do `csv` do Python (QUOTE_MINIMAL, `""`, CRLF), lendo no
 *  máximo `limite` registros e CONTANDO o resto.
 *
 *  Por que contar em vez de parar: a tela precisa dizer "300 de 41.842 linhas", e o total
 *  só sai certo varrendo até o fim — uma célula entre aspas pode conter quebra de linha,
 *  então contar `\n` daria número errado. O que o limite corta é a ALOCAÇÃO: passado ele,
 *  a varredura continua com a mesma máquina de estados mas não concatena célula nem
 *  empilha linha. Numa rodada completa é a diferença entre materializar 2,2 milhões de
 *  células e materializar 14 mil. */
export function lerRegistros(texto: string, limite: number): { registros: string[][]; total: number } {
  const linhas: string[][] = [];
  let linha: string[] = [];
  let celula = "";
  let dentro = false;
  // `inicio` e `celulasNaLinha` espelham `celula.length === 0` e `linha.length` do parser
  // original, e são mantidos MESMO fora do limite: é `inicio` que decide se uma aspa abre
  // célula quotada ou é texto, e sem ele uma aspa no meio de célula não quotada engoliria
  // o resto do arquivo — corrompendo a CONTAGEM, que é o único produto da varredura ali.
  let inicio = true;
  let celulasNaLinha = 0;
  let total = 0;
  let materializa = limite > 0;
  let i = 0;
  while (i < texto.length) {
    const c = texto[i];
    if (dentro) {
      if (c === '"') {
        if (texto[i + 1] === '"') {
          if (materializa) celula += '"';
          inicio = false;
          i += 2;
          continue;
        }
        dentro = false;
        i++;
        continue;
      }
      if (materializa) celula += c;
      inicio = false;
      i++;
      continue;
    }
    if (c === '"' && inicio) {
      // Só abre célula quotada no INÍCIO da célula: uma aspa no meio de célula não
      // quotada é texto (é o que `csv.reader` do Python faz); tratá-la como abertura
      // engolia o resto do arquivo numa célula só. Abrir não escreve em `celula`, então
      // não mexe em `inicio`.
      dentro = true;
    } else if (c === ",") {
      if (materializa) {
        linha.push(celula);
        celula = "";
      }
      celulasNaLinha++;
      inicio = true;
    } else if (c === "\r" || c === "\n") {
      if (c === "\r" && texto[i + 1] === "\n") i++;
      if (materializa) {
        linha.push(celula);
        linhas.push(linha);
        linha = [];
        celula = "";
      }
      celulasNaLinha = 0;
      inicio = true;
      total++;
      materializa = total < limite;
    } else {
      if (materializa) celula += c;
      inicio = false;
    }
    i++;
  }
  // Última linha sem terminador. A condição do original é `celula.length > 0 ||
  // linha.length > 0`; aqui ela é lida dos espelhos, que valem com ou sem materialização.
  if (!inicio || celulasNaLinha > 0) {
    if (materializa) {
      linha.push(celula);
      linhas.push(linha);
    }
    total++;
  }
  return { registros: linhas, total };
}

/** O arquivo inteiro. Preservado com a assinatura antiga porque é o parser que os testes
 *  de dialeto exercitam, e porque quem quer tudo não deve ter de falar em limites. */
export function parsearCsv(texto: string): string[][] {
  return lerRegistros(texto, Number.POSITIVE_INFINITY).registros;
}

/** `limite` é quantas linhas de DADOS materializar; o cabeçalho não conta e vem sempre.
 *  `total` sai exato de qualquer jeito. */
export function tabelaDe(texto: string, limite: number = Number.POSITIVE_INFINITY): Tabela {
  const { registros, total } = lerRegistros(texto, limite + 1);
  if (total === 1 && registros[0]?.length === 1 && registros[0][0] === SENTINELA_VAZIA) {
    return { colunas: [], linhas: [], total: 0, vazia: true, semConteudo: false };
  }
  if (total === 0) return { colunas: [], linhas: [], total: 0, vazia: false, semConteudo: true };
  const [colunas, ...linhas] = registros;
  // O cabeçalho não é linha de dados — por isso `total - 1`, e não `total`.
  return { colunas: colunas ?? [], linhas, total: total - 1, vazia: false, semConteudo: false };
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
 *  validado antes de virar caminho: nada além de `AAAA-MM-DD` chega ao disco.
 *
 *  TODAS as abas são sempre abertas — é assim que `ausentes` sabe o que falta —, mas
 *  `limites` decide quantas linhas de cada uma viram objeto. Leia a armadilha declarada
 *  em `LimiteDeLinhas` antes de limitar uma aba nova. */
export async function lerPlanilha(data: string, limites: LimiteDeLinhas): Promise<Planilha | null> {
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
      const texto = await readFile(resolve(diretorio, `${aba}.csv`), "utf-8");
      abas[aba] = tabelaDe(texto, limites[aba] ?? Number.POSITIVE_INFINITY);
    } catch {
      ausentes.push(aba);
    }
  }
  return { diretorio, abas, ausentes };
}
