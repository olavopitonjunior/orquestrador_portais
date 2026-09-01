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
  };
}

const SELECT_RODADA = `
  SELECT r.id, r.tipo, r.estado, r.inicio, r.fim, r.aprovada_em, r.aprovada_por,
         r.motivo_degradacao, r.posicoes_vazias_destaque,
         count(*) FILTER (WHERE d.nivel = 'super_destaque') AS super_destaque,
         count(*) FILTER (WHERE d.nivel = 'destaque') AS destaque
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
 * `aprovada_em` e com estado entregável (completa/degradada; abortada não entrega). */
export async function rodadasAguardandoAprovacao(): Promise<RodadaResumo[]> {
  const { rows } = await db().query<LinhaRodada>(
    `${SELECT_RODADA}
     WHERE r.tipo = 'decisao' AND r.aprovada_em IS NULL
       AND r.estado IN ('completa', 'degradada')
     GROUP BY r.id ORDER BY r.id DESC`,
  );
  return rows.map(mapRodada);
}
