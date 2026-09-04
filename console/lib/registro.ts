import { db } from "./db";

// Leitura do Registro (esquema `registro`, Spec §2). Espelha o que a camada Python
// (`src/dados/registro/leitura.py`) expõe, em SQL direto — o console não reimplementa
// regra de decisão, só LÊ o que a rodada gravou.

export type Estado = "completa" | "degradada" | "abortada";

export type RodadaResumo = {
  id: number;
  tipo: "decisao" | "acompanhamento";
  estado: Estado | null;
  inicio: string; // ISO
  fim: string | null;
  aprovadaEm: string | null;
  aprovadaPor: string | null;
  motivoDegradacao: string | null;
  posicoesVaziasDestaque: number;
  superDestaque: number; // posições gravadas por nível
  destaque: number;
  amostral: boolean; // decidiu sobre o recorte da raspagem, não sobre o estoque (A2)
};

type LinhaRodada = {
  id: string;
  tipo: "decisao" | "acompanhamento";
  estado: Estado | null;
  inicio: Date;
  fim: Date | null;
  aprovada_em: Date | null;
  aprovada_por: string | null;
  motivo_degradacao: string | null;
  posicoes_vazias_destaque: number;
  super_destaque: string;
  destaque: string;
  amostral: boolean;
};

function mapRodada(l: LinhaRodada): RodadaResumo {
  return {
    id: Number(l.id),
    tipo: l.tipo,
    estado: l.estado,
    inicio: l.inicio.toISOString(),
    fim: l.fim ? l.fim.toISOString() : null,
    aprovadaEm: l.aprovada_em ? l.aprovada_em.toISOString() : null,
    aprovadaPor: l.aprovada_por,
    motivoDegradacao: l.motivo_degradacao,
    posicoesVaziasDestaque: Number(l.posicoes_vazias_destaque),
    superDestaque: Number(l.super_destaque), // count() volta bigint (string)
    destaque: Number(l.destaque),
    amostral: l.amostral,
  };
}

const SELECT_RODADA = `
  SELECT r.id, r.tipo, r.estado, r.inicio, r.fim, r.aprovada_em, r.aprovada_por,
         r.motivo_degradacao, r.posicoes_vazias_destaque,
         count(*) FILTER (WHERE d.nivel = 'super_destaque') AS super_destaque,
         count(*) FILTER (WHERE d.nivel = 'destaque') AS destaque,
         EXISTS (SELECT 1 FROM registro.parametros_da_rodada p
                 WHERE p.rodada_id = r.id
                   AND p.parametros ->> 'recorte_pela_raspagem' IS NOT NULL) AS amostral
  FROM registro.rodada r
  LEFT JOIN registro.decisao_imovel d ON d.rodada_id = r.id`;

/** Histórico de rodadas, mais recente primeiro. */
export async function listarRodadas(limite = 50): Promise<RodadaResumo[]> {
  const { rows } = await db().query<LinhaRodada>(
    `${SELECT_RODADA} GROUP BY r.id ORDER BY r.id DESC LIMIT $1`,
    [limite],
  );
  return rows.map(mapRodada);
}

/** Uma rodada por id, ou null se não existe. */
export async function lerRodada(id: number): Promise<RodadaResumo | null> {
  const { rows } = await db().query<LinhaRodada>(
    `${SELECT_RODADA} WHERE r.id = $1 GROUP BY r.id`,
    [id],
  );
  return rows.length ? mapRodada(rows[0]) : null;
}

/** Rodadas de decisão que ainda aguardam a aprovação do dono (D-001): sem
 * `aprovada_em` e com estado entregável (completa/degradada; abortada não entrega).
 *
 * Exclui a rodada AMOSTRAL — a que decidiu sobre o recorte que a raspagem trouxe, não
 * sobre o estoque. `rodada-aprovar` a recusa (`executar/aprovar.py::rodada_e_amostral`),
 * e este predicado existe para o console nunca oferecer um cartão que o comando
 * recusa. A marca é DADO em `parametros_da_rodada` (`->>` devolve NULL de SQL tanto
 * para chave ausente quanto para `null` do JSON), o mesmo predicado do comando. */
export async function rodadasAguardandoAprovacao(): Promise<RodadaResumo[]> {
  const { rows } = await db().query<LinhaRodada>(
    `${SELECT_RODADA}
     WHERE r.tipo = 'decisao' AND r.aprovada_em IS NULL
       AND r.estado IN ('completa', 'degradada')
       AND NOT EXISTS (
         SELECT 1 FROM registro.parametros_da_rodada p
         WHERE p.rodada_id = r.id AND p.parametros ->> 'recorte_pela_raspagem' IS NOT NULL)
     GROUP BY r.id ORDER BY r.id DESC`,
  );
  return rows.map(mapRodada);
}

/** O que a rodada gravou como seus parâmetros: o TOML declarado, verbatim, mais as
 *  entradas fora dele (data de referência, definição de ativo, coleta, recorte). É
 *  jsonb; o console mostra, não interpreta. `null` se a rodada não gravou (abortada
 *  não deixa nem cabeçalho; rodadas antigas podem não ter a linha). */
export async function parametrosDaRodada(id: number): Promise<Record<string, unknown> | null> {
  const { rows } = await db().query<{ parametros: Record<string, unknown> }>(
    "SELECT parametros FROM registro.parametros_da_rodada WHERE rodada_id = $1",
    [id],
  );
  return rows.length ? rows[0].parametros : null;
}

/** As limitações gravadas no motivo, uma por LINHA — o separador que `executar/sexta.py`
 *  e `grafo/segunda.py` usam ao juntar. `"; "` NÃO serve: as próprias limitações o
 *  contêm (a da definição de gestor ativo, incondicional), e dividir por ele partia
 *  uma ao meio em toda rodada. Rodadas gravadas antes desta regra (juntadas por `"; "`)
 *  não têm `\n` e ficam como bloco único — contar errado é pior que não contar. Prosa,
 *  não dado: a marca AMOSTRAL é lida de `parametros_da_rodada`, não daqui. */
export function limitacoesDe(motivo: string | null): string[] {
  if (!motivo) return [];
  return motivo.split("\n").map((x) => x.trim()).filter((x) => x.length > 0);
}
