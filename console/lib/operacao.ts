// Escrita e leitura do esquema `operacao` — a fila que o console alimenta.
//
// É a PRIMEIRA escrita do console. Até aqui ele era estritamente leitura, e a
// fronteira continua valendo onde importa: nada aqui toca `registro`, que é o trilho
// de auditoria da decisão (D-001). O console enfileira e guarda rascunho; quem decide
// e quem grava decisão é a rodada.
//
// O executor é INJETÁVEL pelo mesmo motivo que `Fontes` e `conectar_registro` o são no
// lado Python: a lógica de estado precisa ser testável sem banco, e o teste que exige
// um Postgres no ar é o teste que ninguém roda.
//
// **Nesta fatia só `guardarParametros` tem chamador.** O resto — enfileirar, listar,
// checar batimento — é o espelho de `src/dados/operacao.py`, que já está na `main`, e
// chega junto de propósito: partir o espelho entre fatias deixaria o mesmo esquema
// descrito em dois arquivos e dois momentos, e a metade adiada nasceria sem os testes
// que a primeira ganhou. A tela que os consome é a fatia seguinte.

import { db } from "./db";

export type Consulta = <T>(sql: string, params?: unknown[]) => Promise<{ rows: T[] }>;

const padrao: Consulta = async (sql, params) => {
  const r = await db().query(sql, params as never[]);
  return { rows: r.rows as never[] };
};

/** Já existe um trabalho deste tipo pendente ou executando.
 *
 *  Não é condição rara: é o duplo-clique no botão. A guarda vive no índice parcial
 *  único do banco, não aqui — duas requisições simultâneas passariam por qualquer
 *  verificação feita antes do INSERT. */
export class TrabalhoEmVoo extends Error {}

const VIOLACAO_DE_UNICIDADE = "23505";

export type Trabalho = {
  id: number;
  tipo: string;
  estado: string;
  pedido_em: string;
  pedido_por: string | null;
  codigo_saida: number | null;
  rodada_id: number | null;
};

/** Guarda o TOML declarado, verbatim. Append-only: cada submissão é linha nova, e isso
 *  é o versionamento. Nunca vai para `registro.alteracao_parametro`, que é a trilha de
 *  parâmetro ADOTADO — e o que sai do formulário é PROVISÓRIO. */
export async function guardarParametros(
  toml: string,
  por: string | null,
  exec: Consulta = padrao,
): Promise<number> {
  const { rows } = await exec<{ id: string }>(
    "INSERT INTO operacao.parametros_declarados (toml, por) VALUES ($1, $2) RETURNING id",
    [toml, por],
  );
  return Number(rows[0].id);
}

/** Enfileira um trabalho. Levanta `TrabalhoEmVoo` quando já há um do mesmo tipo. */
export async function criarTrabalho(
  tipo: string,
  argumentos: Record<string, unknown>,
  por: string | null,
  exec: Consulta = padrao,
): Promise<number> {
  try {
    const { rows } = await exec<{ id: string }>(
      "INSERT INTO operacao.trabalho (tipo, pedido_por, argumentos) VALUES ($1, $2, $3) RETURNING id",
      [tipo, por, JSON.stringify(argumentos)],
    );
    return Number(rows[0].id);
  } catch (e) {
    if ((e as { code?: string })?.code === VIOLACAO_DE_UNICIDADE) {
      throw new TrabalhoEmVoo(
        `já existe um trabalho '${tipo}' pendente ou executando. Um segundo criaria ` +
          "uma rodada duplicada: a gravação no Registro não tem chave natural de " +
          "deduplicação, então duas execuções produzem duas rodadas indistinguíveis.",
      );
    }
    throw e;
  }
}

export async function ultimosParametros(
  exec: Consulta = padrao,
): Promise<{ id: number; toml: string; criado_em: string; por: string | null } | null> {
  const { rows } = await exec<{ id: string; toml: string; criado_em: Date; por: string | null }>(
    "SELECT id, toml, criado_em, por FROM operacao.parametros_declarados " +
      "ORDER BY criado_em DESC, id DESC LIMIT 1",
  );
  if (rows.length === 0) return null;
  const l = rows[0];
  return { id: Number(l.id), toml: l.toml, criado_em: l.criado_em.toISOString(), por: l.por };
}

export async function listarTrabalhos(
  limite = 20,
  exec: Consulta = padrao,
): Promise<Trabalho[]> {
  const { rows } = await exec<Trabalho & { id: string; pedido_em: Date }>(
    "SELECT id, tipo, estado, pedido_em, pedido_por, codigo_saida, rodada_id " +
      "FROM operacao.trabalho ORDER BY pedido_em DESC, id DESC LIMIT $1",
    [limite],
  );
  return rows.map((l) => ({ ...l, id: Number(l.id), pedido_em: l.pedido_em.toISOString() }));
}

export type Evento = {
  id: number;
  momento: string;
  nivel: string;
  no_grafo: string | null;
  texto: string;
  // O relatório do agente daquele nó — contagens e limitações, derivadas do estado da
  // rodada (`src/executar/resumos.py`). Nulo em linha de log comum.
  resumo: Record<string, unknown> | null;
};

/** As sete etapas do grafo da decisão, na ordem em que o fluxo as percorre.
 *
 *  Serve à tela de acompanhamento, que precisa mostrar "etapa 4 de 7" mesmo antes de a
 *  quarta acontecer. NÃO é a topologia do grafo — é a ordem de APRESENTAÇÃO, e as duas
 *  podem divergir sem defeito: `analista_perfil` e `coletor_externo` correm em
 *  paralelo, e listá-los em sequência é uma escolha de leitura, não uma afirmação sobre
 *  execução. O `registrar` fica de fora porque não é etapa da decisão: é o sink. */
export const ETAPAS = [
  "coletor_interno",
  "analista_perfil",
  "coletor_externo",
  "decisor",
  "crivo",
  "redator",
  "finalizar",
] as const;

export async function lerTrabalho(
  id: number,
  exec: Consulta = padrao,
): Promise<Trabalho | null> {
  const { rows } = await exec<Trabalho & { id: string; pedido_em: Date }>(
    "SELECT id, tipo, estado, pedido_em, pedido_por, codigo_saida, rodada_id " +
      "FROM operacao.trabalho WHERE id = $1",
    [id],
  );
  if (rows.length === 0) return null;
  const l = rows[0];
  return { ...l, id: Number(l.id), pedido_em: l.pedido_em.toISOString() };
}

/** O log de uma execução, do mais antigo para o mais novo — é a ordem em que se lê
 *  um progresso. `limite` existe porque uma rodada pode imprimir muito, e a tela não
 *  pode ficar pesada por isso; o corte é no COMEÇO, preservando o fim, que é onde
 *  está o desfecho. */
/** Quantas linhas de log a tela lê — as ÚLTIMAS; o começo de um log maior fica fora. */
export const LIMITE_DO_LOG = 300;

export async function eventosDoTrabalho(
  trabalhoId: number,
  limite = LIMITE_DO_LOG,
  exec: Consulta = padrao,
): Promise<Evento[]> {
  const { rows } = await exec<Evento & { id: string; momento: Date }>(
    "SELECT id, momento, nivel, no_grafo, texto, resumo FROM (" +
      "  SELECT id, momento, nivel, no_grafo, texto, resumo FROM operacao.trabalho_evento" +
      "  WHERE trabalho_id = $1 ORDER BY id DESC LIMIT $2" +
      ") ultimos ORDER BY id",
    [trabalhoId, limite],
  );
  return rows.map((l) => ({ ...l, id: Number(l.id), momento: l.momento.toISOString() }));
}

/** Quais etapas do grafo já se anunciaram. Consulta PRÓPRIA, e é o ponto.
 *
 *  Derivar do log seria de graça e estaria errado: `eventosDoTrabalho` corta em 300
 *  linhas pelo COMEÇO — certo para o log, onde o desfecho está no fim; errado para a
 *  contagem. Numa rodada que imprime muito, os primeiros eventos de etapa saem da
 *  janela e a lista **apaga para trás**: `coletor_interno` escurece enquanto `redator`
 *  acende. Em modo seco a rodada fala pouco e isso nunca aparece; na primeira sexta
 *  real, apareceria. */
export async function etapasConcluidas(
  trabalhoId: number,
  exec: Consulta = padrao,
): Promise<string[]> {
  const { rows } = await exec<{ no_grafo: string }>(
    "SELECT DISTINCT no_grafo FROM operacao.trabalho_evento " +
      "WHERE trabalho_id = $1 AND no_grafo IS NOT NULL AND no_grafo <> ''",
    [trabalhoId],
  );
  return rows.map((l) => l.no_grafo);
}

/** Há trabalhador batendo ponto há menos de `segundos`? Sem isto, o dono clica em
 *  "rodar", nada acontece, e não há nada na tela explicando que o processo que executa
 *  não está no ar. */
export async function trabalhadorVivo(
  segundos = 30,
  exec: Consulta = padrao,
): Promise<boolean> {
  const { rows } = await exec<{ vivo: boolean }>(
    "SELECT EXISTS (SELECT 1 FROM operacao.trabalhador " +
      "WHERE visto_em > now() - make_interval(secs => $1)) AS vivo",
    [segundos],
  );
  return rows[0]?.vivo ?? false;
}

/** O último canário que terminou bem — o portão da coleta completa. */
export async function ultimoCanarioOk(
  exec: Consulta = padrao,
): Promise<{ id: number; terminado_em: string } | null> {
  const { rows } = await exec<{ id: string; terminado_em: Date }>(
    "SELECT id, terminado_em FROM operacao.trabalho " +
      "WHERE tipo = 'canario' AND estado = 'ok' AND codigo_saida = 0 " +
      "ORDER BY terminado_em DESC, id DESC LIMIT 1",
  );
  if (rows.length === 0) return null;
  return { id: Number(rows[0].id), terminado_em: rows[0].terminado_em.toISOString() };
}

/** O relatório de cada agente: o ÚLTIMO resumo gravado por nó. Consulta PRÓPRIA, pela
 *  mesma razão de `etapasConcluidas`: `eventosDoTrabalho` corta nos últimos 300 eventos,
 *  e numa sexta real — cada linha de stdout vira evento — os resumos das primeiras
 *  etapas saem da janela e o relatório apagaria para trás. Último por nó, e não
 *  primeiro: se um nó for reexecutado (retry do Orquestrador, parâmetro nº 4), o que
 *  vale é o que ficou. */
export async function resumosDoTrabalho(
  trabalhoId: number,
  exec: Consulta = padrao,
): Promise<Map<string, Record<string, unknown>>> {
  const { rows } = await exec<{ no_grafo: string; resumo: Record<string, unknown> }>(
    "SELECT DISTINCT ON (no_grafo) no_grafo, resumo FROM operacao.trabalho_evento " +
      "WHERE trabalho_id = $1 AND resumo IS NOT NULL AND no_grafo <> '' " +
      "ORDER BY no_grafo, id DESC",
    [trabalhoId],
  );
  return new Map(rows.map((l) => [l.no_grafo, l.resumo]));
}

/** O trabalho que gravou esta rodada — o elo entre a tela da rodada e a do log. */
export async function trabalhoDaRodada(
  rodadaId: number,
  exec: Consulta = padrao,
): Promise<number | null> {
  const { rows } = await exec<{ id: string }>(
    "SELECT id FROM operacao.trabalho WHERE rodada_id = $1 ORDER BY id DESC LIMIT 1",
    [rodadaId],
  );
  return rows.length ? Number(rows[0].id) : null;
}
