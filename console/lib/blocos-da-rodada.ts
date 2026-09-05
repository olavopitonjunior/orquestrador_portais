// Os três blocos REALIZADOS de uma rodada — quem entrou, em que ordem, quantos —,
// montados do que os agentes reportaram (`trabalho_evento.resumo`, por nó), do que a
// rodada gravou como parâmetros efetivos e, quando há planilha em disco, da aba de
// relaxamento. PURO: recebe dados, devolve dados; a tela só desenha.
//
// Tudo é opcional: uma rodada em curso ainda não tem o decisor; uma rodada disparada
// pela linha de comando não tem resumo nenhum; uma rodada em modo seco não tem
// planilha. Campo ausente vira `null`, nunca zero — zero é uma contagem, null é a
// ausência dela.

import { ORDEM_RELAXAMENTO, REGRAS_LEGIVEIS, legivel } from "./regras";

type Resumo = Record<string, unknown>;

function num(o: Resumo | undefined, chave: string): number | null {
  const v = o?.[chave];
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function bool(o: Resumo | undefined, chave: string): boolean | null {
  const v = o?.[chave];
  return typeof v === "boolean" ? v : null;
}

function textos(o: Resumo | undefined, chave: string): string[] {
  const v = o?.[chave];
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];
}

function numeroEfetivo(efetivo: Record<string, unknown> | null, caminho: string): number | null {
  const v = efetivo?.[caminho];
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "" && Number.isFinite(Number(v))) return Number(v);
  return null;
}

function textoEfetivo(efetivo: Record<string, unknown> | null, caminho: string): string | null {
  const v = efetivo?.[caminho];
  return typeof v === "string" ? v : typeof v === "number" ? String(v) : null;
}

export type ReprovadosPorRegra = { regra: string; rotulo: string; grupo: string; n: number };

export type QuemEntrou = {
  candidatos: number | null;
  elegiveis: number | null;
  reprovados: number | null;
  porRegra: ReprovadosPorRegra[]; // na ordem de leitura do funil; só as que reprovaram alguém
  perfis: number | null;
  perfisFrageis: number | null;
  comDimensoes: number | null;
  recorteAmostral: number | null;
  degradacoes: string[];
};

export type EmQueOrdem = {
  portalEntrou: boolean | null;
  coberturaAtingida: number | null; // em %, da taxa de amarração
  coberturaMinima: number | null; // em %, o parâmetro
  idadeDias: number | null;
  idadeMaxima: number | null;
  imoveisComAnuncio: number | null;
  pesos: { nota: number | null; cliques: number | null; visualizacoes: number | null };
  semAnuncio: string | null;
  ordemSemPortal: string | null;
  degradacoes: string[];
};

export type Cedencia = { regra: string; rotulo: string; n: number };

export type Quantos = {
  superDestaque: number | null;
  destaque: number | null;
  vaziasDestaque: number | null;
  recuperados: number | null;
  cedencia: Cedencia[]; // na ordem de cedência, só os degraus alcançados
  crivoPassou: boolean | null;
  violacoes: string[];
  degradacoes: string[];
};

export type BlocosDaRodada = { quemEntrou: QuemEntrou; emQueOrdem: EmQueOrdem; quantos: Quantos };

export type LinhaDeRelaxamento = { regra: string; posicoes: number };

/** Lê a aba `relaxamento` da planilha (colunas `regra_cedida` e `posicoes_dependentes`);
 *  devolve vazio quando as colunas não existem. A última linha da aba — "POSIÇÕES AINDA
 *  VAZIAS" — não é degrau, é o resíduo, e já aparece como "destaques vazios". */
export function cedenciaDaAba(colunas: readonly string[], linhas: readonly (readonly string[])[]): LinhaDeRelaxamento[] {
  const iRegra = colunas.indexOf("regra_cedida");
  const iPos = colunas.indexOf("posicoes_dependentes");
  if (iRegra < 0 || iPos < 0) return [];
  return linhas
    .map((l) => ({ regra: l[iRegra] ?? "", posicoes: Number(l[iPos]) }))
    .filter((x) => ORDEM_RELAXAMENTO.includes(x.regra) && Number.isFinite(x.posicoes));
}

export function montarBlocos(entrada: {
  resumos: ReadonlyMap<string, Resumo>;
  efetivo: Record<string, unknown> | null;
  contagens: { superDestaque: number; destaque: number; vaziasDestaque: number } | null;
  relaxamento: readonly LinhaDeRelaxamento[];
}): BlocosDaRodada {
  const { resumos, efetivo, contagens, relaxamento } = entrada;
  const interno = resumos.get("coletor_interno");
  const perfil = resumos.get("analista_perfil");
  const externo = resumos.get("coletor_externo");
  const decisor = resumos.get("decisor");
  const crivo = resumos.get("crivo");

  const porRegraBruto = decisor?.reprovados_por_regra;
  const porRegra: ReprovadosPorRegra[] = [];
  if (porRegraBruto && typeof porRegraBruto === "object" && !Array.isArray(porRegraBruto)) {
    const mapa = porRegraBruto as Record<string, unknown>;
    // Na ordem de leitura do funil (imóvel → perfil → corretor), não na do dicionário —
    // a mesma lista de `regras.ts`, não uma terceira cópia.
    for (const { regra: r } of REGRAS_LEGIVEIS) {
      const n = mapa[r];
      if (typeof n === "number" && n > 0) porRegra.push({ ...legivel(r), n });
    }
    for (const [r, n] of Object.entries(mapa)) {
      if (typeof n === "number" && n > 0 && !porRegra.some((x) => x.regra === r)) porRegra.push({ ...legivel(r), n });
    }
  }

  const taxa = num(externo, "taxa_amarracao");
  // No resumo do decisor, `destaque` é quem entrou pelo RANKING; os recuperados pela
  // cedência vêm à parte. O Registro (contagens) já soma os dois — aqui soma-se igual,
  // para as duas telas dizerem o mesmo número.
  const pelaOrdem = num(decisor, "destaque");
  const recuperados = num(decisor, "recuperados_por_relaxamento");
  const destaqueDoResumo = pelaOrdem === null ? null : pelaOrdem + (recuperados ?? 0);
  const cedencia: Cedencia[] = [...relaxamento]
    .sort((a, b) => ORDEM_RELAXAMENTO.indexOf(a.regra) - ORDEM_RELAXAMENTO.indexOf(b.regra))
    .map((l) => ({ regra: l.regra, rotulo: legivel(l.regra).rotulo, n: l.posicoes }));

  return {
    quemEntrou: {
      candidatos: num(interno, "candidatos"),
      elegiveis: num(decisor, "elegiveis"),
      reprovados: num(decisor, "reprovados"),
      porRegra,
      perfis: num(perfil, "perfis"),
      perfisFrageis: num(perfil, "frageis"),
      comDimensoes: num(interno, "com_dimensoes"),
      recorteAmostral: num(interno, "recorte_amostral"),
      degradacoes: [...textos(interno, "degradacoes"), ...textos(perfil, "degradacoes")],
    },
    emQueOrdem: {
      portalEntrou: bool(externo, "entrou_no_ranking"),
      coberturaAtingida: taxa === null ? null : Math.round(taxa * 1000) / 10,
      coberturaMinima: numeroEfetivo(efetivo, "portal.cobertura_minima"),
      idadeDias: num(externo, "idade_dias"),
      idadeMaxima: numeroEfetivo(efetivo, "portal.idade_maxima_dias"),
      imoveisComAnuncio: num(externo, "imoveis_com_anuncio"),
      pesos: {
        nota: numeroEfetivo(efetivo, "portal.peso_nota"),
        cliques: numeroEfetivo(efetivo, "portal.peso_cliques"),
        visualizacoes: numeroEfetivo(efetivo, "portal.peso_visualizacoes"),
      },
      semAnuncio: textoEfetivo(efetivo, "portal.sem_anuncio"),
      ordemSemPortal: textoEfetivo(efetivo, "portal.ordem_quando_nao_entra"),
      degradacoes: textos(externo, "degradacoes"),
    },
    quantos: {
      superDestaque: contagens?.superDestaque ?? num(decisor, "super_destaque"),
      destaque: contagens?.destaque ?? destaqueDoResumo,
      vaziasDestaque: contagens?.vaziasDestaque ?? num(decisor, "posicoes_vazias"),
      recuperados,
      cedencia,
      crivoPassou: bool(crivo, "passou"),
      violacoes: textos(crivo, "violacoes"),
      degradacoes: [...textos(decisor, "degradacoes"), ...textos(crivo, "degradacoes")],
    },
  };
}

/** Quantos dos três blocos já têm o que mostrar — para a tela em curso dizer "1 de 3". */
export function blocosPreenchidos(b: BlocosDaRodada): number {
  return [b.quemEntrou.elegiveis !== null, b.emQueOrdem.portalEntrou !== null, b.quantos.destaque !== null].filter(
    Boolean,
  ).length;
}
