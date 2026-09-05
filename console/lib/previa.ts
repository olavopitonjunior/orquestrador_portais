// A prévia, do lado da tela: o que `executar/previa.py` escreveu (e o trabalhador
// gravou como resumo do trabalho), lido com desconfiança e posto em frases.
//
// Tudo aqui é PURO e testado sem banco. A forma do JSON é o contrato do módulo Python;
// `lerPrevia` recusa o que não tem a forma, para a tela mostrar "sem prévia" em vez
// de quebrar num `undefined.map`.

import type { Trabalho } from "./operacao";

export type LinhaDoFunil = {
  regra: string;
  rotulo: string;
  grupo: string;
  sobram: number;
  cortou: number;
};

export type Previa = {
  hoje: string;
  candidatos: number;
  funil: LinhaDoFunil[];
  reprovados_por_regra: Record<string, number>;
  elegiveis: number;
  candidatos_super_destaque: number;
  posicoes: { super_destaque: number; destaque: number; total: number };
  projecao: {
    super_destaque_preenchido: number;
    destaque_preenchido: number;
    vazias_super_destaque: number;
    vazias_destaque: number;
    vazias_total: number;
  };
  relaxamento: {
    recuperaveis: number;
    travados_pelo_login: number;
    por_degrau: { regra: string; recuperaveis_ate_aqui: number }[];
    vazias_destaque_depois: number;
  };
  perfil: {
    perfis: number;
    robustos: number;
    que_contam: number;
    exigencia: string | null;
    sem_dimensoes: number;
    filtro_incide: boolean;
  };
  degradacoes: string[];
  parametros: {
    origem: string;
    efetivo: Record<string, unknown>;
    procedencia: Record<string, string>;
    declarados_diferentes_do_adotado: string[];
  };
  vendas?: { assinadas: number; descartadas: number; janela_dias: number };
  duracao_s?: number;
};

const EM_VOO = new Set(["pendente", "executando"]);

function ehNumero(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

function objeto(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function numeros(o: Record<string, unknown>, chaves: string[]): boolean {
  return chaves.every((c) => ehNumero(o[c]));
}

/** O resumo gravado pelo trabalhador, se tiver a forma da prévia. Confere TUDO que a
 *  tela dereferencia — um resumo de outra versão do módulo Python vira "sem prévia",
 *  não uma página quebrada. */
export function lerPrevia(
  resumo: Record<string, unknown> | undefined | null,
): Previa | null {
  if (!objeto(resumo)) return null;
  const r = resumo;
  if (!numeros(r, ["elegiveis", "candidatos", "candidatos_super_destaque"])) return null;
  if (!Array.isArray(r.funil) || !Array.isArray(r.degradacoes)) return null;
  for (const ln of r.funil) {
    if (!objeto(ln) || typeof ln.regra !== "string" || typeof ln.rotulo !== "string") return null;
    if (typeof ln.grupo !== "string" || !numeros(ln, ["sobram", "cortou"])) return null;
  }
  const { posicoes, projecao, relaxamento, perfil, parametros } = r;
  if (!objeto(posicoes) || !numeros(posicoes, ["super_destaque", "destaque", "total"])) return null;
  if (
    !objeto(projecao) ||
    !numeros(projecao, [
      "super_destaque_preenchido",
      "destaque_preenchido",
      "vazias_super_destaque",
      "vazias_destaque",
      "vazias_total",
    ])
  ) {
    return null;
  }
  if (
    !objeto(relaxamento) ||
    !numeros(relaxamento, ["recuperaveis", "travados_pelo_login", "vazias_destaque_depois"]) ||
    !Array.isArray(relaxamento.por_degrau) ||
    !relaxamento.por_degrau.every(
      (d) => objeto(d) && typeof d.regra === "string" && ehNumero(d.recuperaveis_ate_aqui),
    )
  ) {
    return null;
  }
  if (!objeto(perfil) || typeof perfil.filtro_incide !== "boolean") return null;
  if (
    !objeto(parametros) ||
    !objeto(parametros.efetivo) ||
    !Array.isArray(parametros.declarados_diferentes_do_adotado)
  ) {
    return null;
  }
  return r as unknown as Previa;
}

/** A prévia em voo, se houver — para a tela apontar para ela em vez de dizer "erro". */
export function previaEmVoo(trabalhos: readonly Trabalho[]): number | null {
  const t = trabalhos.find((x) => x.tipo === "previa" && EM_VOO.has(x.estado));
  return t ? t.id : null;
}

/** Número em português, uma vez só: a lib e a tela usam o mesmo. */
export const formatar = (v: number) => v.toLocaleString("pt-BR");
const n = formatar;

/** A resposta em uma frase: quantos sobram, para quantas posições, e o que falta. */
export function fraseDaPrevia(p: Previa): string {
  const pos = p.posicoes;
  const pr = p.projecao;
  const inicio = `Com estes valores sobram ${n(p.elegiveis)} imóveis para as ${n(pos.total)} posições`;
  if (pr.vazias_total === 0) {
    return `${inicio}: as ${n(pos.super_destaque)} de super destaque e as ${n(pos.destaque)} de destaque ficam todas preenchidas.`;
  }
  const partes: string[] = [];
  if (pr.vazias_super_destaque > 0) {
    partes.push(
      `${n(pr.super_destaque_preenchido)} das ${n(pos.super_destaque)} de super destaque (${n(pr.vazias_super_destaque)} vazias — o super destaque nunca relaxa)`,
    );
  } else {
    partes.push(`as ${n(pos.super_destaque)} de super destaque preenchidas`);
  }
  if (pr.vazias_destaque > 0) {
    const rec = p.relaxamento;
    const cedencia =
      rec.recuperaveis >= pr.vazias_destaque
        ? `; a cedência de regras encheria todas — há ${n(rec.recuperaveis)} recuperáveis`
        : rec.recuperaveis > 0
          ? `; a cedência de regras recuperaria até ${n(rec.recuperaveis)}, sobrando ${n(rec.vazias_destaque_depois)} vazias`
          : "; a cedência de regras não recuperaria ninguém";
    partes.push(
      `${n(pr.destaque_preenchido)} das ${n(pos.destaque)} de destaque (${n(pr.vazias_destaque)} vazias${cedencia})`,
    );
  } else {
    partes.push(`as ${n(pos.destaque)} de destaque preenchidas`);
  }
  return `${inicio}: ${partes.join(" e ")}.`;
}

/** Onde o parâmetro que produziu a linha mora: a âncora do grupo em /parametros. */
export function linkDoGrupo(grupo: string): string {
  return `/parametros#${grupo}`;
}

/** A seção do TOML → o grupo da tela onde o campo mora (a taxonomia do contrato). */
const GRUPO_DA_SECAO: Record<string, string> = {
  conversao: "quem_entra_perfil",
  corretor: "quem_entra_corretor",
  portal: "em_que_ordem_portal",
  desconto: "em_que_ordem_descontos",
  resultado_esperado: "quantos",
};

export function grupoDoCaminho(caminho: string): string {
  return GRUPO_DA_SECAO[caminho.split(".")[0]] ?? "operacao";
}

/** Os valores efetivos na ordem de LEITURA das seções (quem entra → em que ordem),
 *  não na ordem em que o dicionário chegou. */
const ORDEM_DAS_SECOES = ["conversao", "corretor", "portal", "desconto", "resultado_esperado"];

export function valoresEmOrdem(efetivo: Record<string, unknown>): [string, unknown][] {
  const posicao = (caminho: string) => {
    const i = ORDEM_DAS_SECOES.indexOf(caminho.split(".")[0]);
    return i === -1 ? ORDEM_DAS_SECOES.length : i;
  };
  return Object.entries(efetivo).sort(
    ([a], [b]) => posicao(a) - posicao(b) || a.localeCompare(b),
  );
}

export const ROTULO_DO_DEGRAU: Record<string, string> = {
  perfil_de_conversao: "cedendo o perfil de conversão",
  fotos: "cedendo as dez fotos",
  cadastro_completo: "cedendo o cadastro completo",
  atualizacao_90d: "cedendo a atualização em 90 dias",
  gestor_produtivo: "cedendo o gestor produtivo",
  capacidade_distrito: "cedendo a capacidade do distrito",
};

/** O texto de espera: a prévia lê o estoque inteiro, e isso leva minutos. Dito ANTES
 *  do clique e DURANTE a espera, com as mesmas palavras. */
export const ESPERA_DA_PREVIA =
  "A prévia lê o estoque inteiro do Newcore — candidatos, vendas e dimensões. Leva um ou dois minutos; não raspa o portal e não grava nada.";
