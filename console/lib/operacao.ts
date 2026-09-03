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
