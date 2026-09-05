// O exame de uma declaração de parâmetros vinda do formulário — PURO, sem servidor:
// as duas ações (`salvarParametros`, `verPrevia`) o chamam, e o teste também. Vive fora
// de `acoes.ts` porque um arquivo "use server" só pode exportar funções assíncronas.

import { CAMPOS, normalizarEscolha } from "./contrato";
import { validar } from "./toml";

export type Recusa =
  | { ok: false; problemas: { caminho: string; mensagem: string }[] }
  | { ok: false; erro: string };

/** O exame comum às duas ações: `por` limpo e os valores válidos. Exportado para o
 *  teste; não é ação de servidor (não é `async`). */
export function conferir(
  entradas: Record<string, string>,
  por: string,
): { valores: Map<string, string> } | Recusa {
  const valores = new Map(Object.entries(entradas));

  // `por` NÃO vem do contrato, então não passa por `validar()` — e era o único dado
  // que chegava aqui ao lado do formulário em vez de dentro dele. Ele vira comentário
  // no TOML, e comentário termina na quebra de linha: sem esta guarda, um nome com
  // `\n[resultado_esperado]` definia o parâmetro nº 14, que a D-022 declara nulo.
  // `paraToml` também limpa, por contrato próprio; aqui a recusa é explícita para o
  // dono VER o problema em vez de ter o nome dele silenciosamente encurtado.
  // Qualquer caractere de controle, não só quebra de linha: a gramática do TOML os
  // proíbe dentro de comentário, e um `\x01` faz o arquivo inteiro deixar de parsear.
  // `paraToml` também os remove, por contrato próprio; aqui a recusa é explícita para
  // o dono VER o problema em vez de ter o nome silenciosamente alterado.
  if (/[\u0000-\u001F\u007F]/.test(por)) {
    return {
      ok: false,
      problemas: [
        { caminho: "por", mensagem: "não pode conter quebra de linha nem caractere de controle" },
      ],
    };
  }
  if (por.length > 200) {
    return { ok: false, problemas: [{ caminho: "por", mensagem: "no máximo 200 caracteres" }] };
  }

  // Revalida no SERVIDOR, mesmo o cliente já tendo validado. O cliente é conveniência
  // para o dono corrigir enquanto digita; ele não é garantia, porque quem chama a
  // ação não é obrigado a ser o formulário.
  const problemas = validar(valores);
  if (problemas.length > 0) return { ok: false, problemas };
  return { valores };
}

// ---------------------------------------------------------------------------
// A declaração guardada, lida de volta e posta em PROSA — para /rodada/nova dizer, em
// frases, o que a próxima rodada vai fazer, com cada número ligado ao parâmetro que o
// produziu. Só lê o formato que `paraToml` gera (seções planas, `chave = valor`); um
// TOML de outra origem pode não ser entendido, e nesse caso a tela mostra o texto cru.

/** Os valores declarados num TOML gerado pelo console: `caminho → texto`. */
export function valoresDoToml(toml: string): Map<string, string> {
  const valores = new Map<string, string>();
  let secao = "";
  for (const bruta of toml.split("\n")) {
    const linha = bruta.trim();
    if (linha === "" || linha.startsWith("#")) continue;
    const cabecalho = /^\[([A-Za-z0-9_.]+)\]$/.exec(linha);
    if (cabecalho) {
      secao = cabecalho[1];
      continue;
    }
    const par = /^([A-Za-z0-9_]+)\s*=\s*(.+)$/.exec(linha);
    if (!par || secao === "") continue;
    valores.set(`${secao}.${par[1]}`, valorDeToml(par[2]));
  }
  return valores;
}

/** O valor de uma atribuição: entre aspas (com escapes simples) ou até o começo de um
 *  comentário em linha — um TOML editado à mão com `= 75  # ajustado` não pode virar
 *  "75  # ajustado" na prosa. */
function valorDeToml(bruto: string): string {
  const texto = bruto.trim();
  const aspas = /^"((?:[^"\\]|\\.)*)"/.exec(texto) ?? /^'([^']*)'/.exec(texto);
  if (aspas) return aspas[1].replace(/\\(["\\])/g, "$1");
  return texto.split("#")[0].trim();
}

export type Efetivo = {
  caminho: string;
  rotulo: string;
  unidade: string;
  valor: string;
  procedencia: "declarado" | "adotado";
  grupo: string;
};

/** O valor EFETIVO de cada campo: o declarado, ou o adotado quando vazio — como
 *  `config.parametros.carregar` resolve. Os campos sem adotado (o nº 14) só entram
 *  se declarados. */
export function efetivosDe(declarados: Map<string, string>): Efetivo[] {
  const saida: Efetivo[] = [];
  for (const c of CAMPOS) {
    const bruto = declarados.get(c.caminho);
    const declarado = bruto !== undefined && bruto.trim() !== "";
    if (!declarado && c.adotado === null) continue;
    const valor = declarado ? (c.escolhas ? normalizarEscolha(bruto) : bruto!.trim()) : String(c.adotado);
    // Declarado IGUAL ao adotado não é escolha nova: rotula como adotado, como
    // `config.parametros._resolver` faz — senão a tela diria "declarado" e a planilha
    // "adotado" para o mesmo número.
    const igualAoAdotado = declarado && c.adotado !== null && Number(valor) === Number(c.adotado)
      ? true
      : declarado && c.adotado !== null && valor === String(c.adotado);
    saida.push({
      caminho: c.caminho,
      rotulo: c.rotulo,
      unidade: c.unidade,
      valor,
      procedencia: declarado && !igualAoAdotado ? "declarado" : "adotado",
      grupo: c.grupo,
    });
  }
  return saida;
}

/** Um trecho de frase: texto corrido, ou um NÚMERO que aponta para o parâmetro. */
export type Trecho = { t: string } | { v: string; caminho: string; grupo: string; procedencia: "declarado" | "adotado" };

export type FraseDoBloco = { bloco: "quem-entra" | "em-que-ordem" | "quantos"; trechos: Trecho[] };

const ESCOLHA_EM_PROSA: Record<string, string> = {
  fim_da_fila: "vai para o fim da fila",
  mediana: "recebe a nota mediana",
  leads_180d: "dos leads em 180 dias",
  produtividade_gestor: "da produtividade do gestor",
  cadastro_mais_novo: "só do cadastro mais novo",
};

/** As três frases de /rodada/nova, montadas dos valores efetivos. Os números vêm
 *  como trechos ligados; o texto ao redor é fixo e diz a regra que o número governa. */
export function proseDaDeclaracao(
  efetivos: Efetivo[],
  cotas: { superDestaque: number; destaque: number } | null,
): FraseDoBloco[] {
  const por = new Map(efetivos.map((e) => [e.caminho, e]));
  const n = (caminho: string): Trecho => {
    const e = por.get(caminho);
    if (!e) return { t: "(não declarado)" };
    const texto = e.unidade ? `${e.valor} ${e.unidade}` : (ESCOLHA_EM_PROSA[e.valor] ?? e.valor);
    return { v: texto, caminho: e.caminho, grupo: e.grupo, procedencia: e.procedencia };
  };
  const quemEntra: Trecho[] = [
    { t: "Vai excluir quem não se parece com o que vendeu nos últimos " },
    n("conversao.janela_dias"),
    { t: " (perfis com ao menos 3 vendas, contendo a faixa de preço), quem tem gestor sem captar nem vender em 30 dias, e quem está em distrito com menos de " },
    n("corretor.minimo_no_distrito"),
    { t: ". Gestor sem login há mais de " },
    n("corretor.login_janela_dias"),
    { t: " não é excluído por isso, mas trava a cedência de regras para os imóveis dele. As seis regras do imóvel seguem fixas: publicação ativa, cinco categorias, preço de R$ 300.000, dez fotos, atualização em 90 dias, cadastro completo." },
  ];
  const emQueOrdem: Trecho[] = [
    { t: "Vai ordenar pela nota do anúncio (" },
    n("portal.peso_nota"),
    { t: "), cliques (" },
    n("portal.peso_cliques"),
    { t: ") e visualizações (" },
    n("portal.peso_visualizacoes"),
    { t: "). A raspagem só entra se cobrir " },
    n("portal.cobertura_minima"),
    { t: " dos candidatos e tiver até " },
    n("portal.idade_maxima_dias"),
    { t: "; imóvel sem anúncio raspado " },
    n("portal.sem_anuncio"),
    { t: "; sem raspagem, a ordem vem " },
    n("portal.ordem_quando_nao_entra"),
    { t: " e a rodada sai degradada. Desconta " },
    n("desconto.janela_sem_resultado"),
    { t: " por janela anterior sem resultado (inerte enquanto a régua de resultado, nº 14, for nula), " },
    n("desconto.sem_avaliacao"),
    { t: " por falta de avaliação por categoria e " },
    n("desconto.sem_lead_180d"),
    { t: " por não ter lead em 180 dias, com perdão de " },
    n("desconto.perdao_por_semana"),
    { t: "." },
  ];
  const quantos: Trecho[] = [
    {
      t: cotas
        ? `Vai preencher ${cotas.superDestaque.toLocaleString("pt-BR")} super destaques acima de R$ 700.000 e ${cotas.destaque.toLocaleString("pt-BR")} destaques`
        : "Vai preencher as posições contratadas de super destaque (acima de R$ 700.000) e de destaque",
    },
    { t: ". No destaque, faltando imóveis, cede regras nesta ordem até encher: perfil de conversão, fotos, cadastro completo, atualização em 90 dias, gestor produtivo, capacidade do distrito. O super destaque nunca cede." },
  ];
  if (por.has("resultado_esperado.super_destaque") && por.has("resultado_esperado.destaque")) {
    quantos.push(
      { t: " A régua de resultado desta rodada: " },
      n("resultado_esperado.super_destaque"),
      { t: " no super destaque e " },
      n("resultado_esperado.destaque"),
      { t: " no destaque." },
    );
  }
  return [
    { bloco: "quem-entra", trechos: quemEntra },
    { bloco: "em-que-ordem", trechos: emQueOrdem },
    { bloco: "quantos", trechos: quantos },
  ];
}
