// As nove regras de elegibilidade como o dono as lê, e o grupo de /parametros que
// governa cada uma. Espelha `dominio.elegibilidade.Regra` (valores) e a ordem de
// leitura do funil da prévia (`executar.previa.ORDEM_DO_FUNIL`): imóvel, perfil,
// corretor. A ordem de CEDÊNCIA (Spec §6.6, D-027) é outra, e está em ORDEM_RELAXAMENTO.

export type RegraLegivel = { regra: string; rotulo: string; grupo: string };

export const REGRAS_LEGIVEIS: readonly RegraLegivel[] = [
  { regra: "status_ativo", rotulo: "publicação ativa", grupo: "quem_entra_imovel" },
  { regra: "categoria", rotulo: "nas cinco categorias", grupo: "quem_entra_imovel" },
  { regra: "preco_geral", rotulo: "preço de R$ 300.000 ou mais", grupo: "quem_entra_imovel" },
  { regra: "fotos", rotulo: "dez fotos ou mais", grupo: "quem_entra_imovel" },
  { regra: "cadastro_completo", rotulo: "cadastro completo", grupo: "quem_entra_imovel" },
  { regra: "atualizacao_90d", rotulo: "atualizado nos últimos 90 dias", grupo: "quem_entra_imovel" },
  { regra: "perfil_de_conversao", rotulo: "parece com o que vendeu", grupo: "quem_entra_perfil" },
  { regra: "gestor_produtivo", rotulo: "gestor captou ou vendeu em 30 dias", grupo: "quem_entra_corretor" },
  { regra: "capacidade_distrito", rotulo: "distrito com corretores produtivos", grupo: "quem_entra_corretor" },
];

export const POR_REGRA: ReadonlyMap<string, RegraLegivel> = new Map(REGRAS_LEGIVEIS.map((r) => [r.regra, r]));

/** A ordem de cedência no destaque (D-027): perfil primeiro; o super destaque nunca cede. */
export const ORDEM_RELAXAMENTO: readonly string[] = [
  "perfil_de_conversao",
  "fotos",
  "cadastro_completo",
  "atualizacao_90d",
  "gestor_produtivo",
  "capacidade_distrito",
];

export function legivel(regra: string): RegraLegivel {
  return POR_REGRA.get(regra) ?? { regra, rotulo: regra.replace(/_/g, " "), grupo: "quem_entra_imovel" };
}
