// Valida o que o dono digitou e serializa o TOML da rodada. PURO: nada de I/O.
//
// A autoridade continua sendo `config/parametros.carregar()`, no lado Python, que roda
// no trabalhador e recusa a rodada com código 5 e mensagem em português. O que este
// módulo faz é adiantar essa recusa para ANTES da submissão — o dono corrige enquanto
// digita, em vez de descobrir depois que a rodada foi enfileirada e morreu.
//
// Adiantar não é duplicar: as faixas, os tipos e as escolhas vêm todos do contrato
// gerado do próprio validador, e o CI compara byte a byte. Nada aqui é redigitado.

import { CAMPOS, POR_CAMINHO, REGRAS, campoAtivo, normalizarEscolha, type Campo } from "./contrato";

export type Valores = ReadonlyMap<string, string>;
export type Problema = { caminho: string; mensagem: string };

/** O que o formulário considera "não preenchido". Espaço em branco conta como vazio:
 *  um campo com um espaço é tão não-decidido quanto um campo vazio, e tratá-lo como
 *  preenchido faria o `Number("")` virar 0 — um valor que ninguém escolheu. */
function vazio(bruto: string | undefined): boolean {
  return bruto === undefined || bruto.trim() === "";
}

function problemaDeNumero(campo: Campo, bruto: string): string | null {
  // `Number` aceita "", "0x10" e " 1 "; nenhum deles é o que o dono quis digitar.
  if (!/^-?\d+(\.\d+)?$/.test(bruto.trim())) {
    return "precisa ser um número (use ponto para decimal)";
  }
  const n = Number(bruto);
  if (!Number.isFinite(n)) return "precisa ser um número finito";

  if (Math.abs(n) > Number.MAX_SAFE_INTEGER) {
    // Acima disso o JavaScript perde precisão em silêncio (9007199254740993 vira
    // ...992) e `String` passa a emitir notação científica: `1e+21`, que o TOML lê
    // como FLOAT e o `_inteiro` do validador recusa. Formulário verde produzindo
    // arquivo que a rodada rejeita é precisamente a falha que esta camada elimina.
    return "é grande demais para ser representado sem perder precisão";
  }
  if (campo.tipo === "inteiro" && !Number.isInteger(n)) {
    // A distinção que o JavaScript não faz e o validador faz: `_inteiro` recusa 40.0.
    // Sem esta checagem, um formulário perfeitamente preenchido produz um TOML que a
    // rodada rejeita — e o dono descobre pelo código de saída, não pelo campo.
    return "precisa ser inteiro, sem casa decimal";
  }
  if (campo.minimo !== null) {
    if (campo.minimo_aberto && n <= campo.minimo) {
      return `precisa ser MAIOR que ${campo.minimo} (o limite não vale)`;
    }
    if (!campo.minimo_aberto && n < campo.minimo) {
      return `não pode ser menor que ${campo.minimo}`;
    }
  }
  if (campo.maximo !== null && n > campo.maximo) {
    return `não pode ser maior que ${campo.maximo}`;
  }
  return null;
}

/** Todos os problemas do formulário, na ordem dos campos. Lista vazia = pode enviar. */
export function validar(valores: Valores): Problema[] {
  const problemas: Problema[] = [];
  const ativos = CAMPOS.filter((c) => campoAtivo(c, valores));

  for (const campo of ativos) {
    const bruto = valores.get(campo.caminho);
    if (vazio(bruto)) {
      // Campo opcional vazio é legítimo — a seção inteira fica de fora. A regra
      // `todos_ou_nenhum` abaixo é quem cobra a indivisibilidade.
      if (campo.obrigatorio) {
        problemas.push({ caminho: campo.caminho, mensagem: "falta preencher" });
      }
      continue;
    }
    if (campo.tipo === "escolha") {
      if (!(campo.escolhas ?? []).includes(normalizarEscolha(bruto))) {
        problemas.push({
          caminho: campo.caminho,
          mensagem: `escolha inválida; aceitas: ${(campo.escolhas ?? []).join(", ")}`,
        });
      }
      continue;
    }
    const erro = problemaDeNumero(campo, bruto!);
    if (erro !== null) problemas.push({ caminho: campo.caminho, mensagem: erro });
  }

  problemas.push(...validarRegras(valores));
  return problemas;
}

/** As regras que nenhum campo isolado expressa. O contrato as traz com TIPO legível
 *  por máquina justamente para não serem reimplementadas a partir da descrição. */
function validarRegras(valores: Valores): Problema[] {
  const problemas: Problema[] = [];
  for (const regra of REGRAS) {
    const brutos = regra.campos.map((c) => valores.get(c));
    const preenchidos = brutos.filter((b) => !vazio(b));

    if (regra.tipo === "todos_ou_nenhum") {
      if (preenchidos.length > 0 && preenchidos.length !== regra.campos.length) {
        problemas.push({ caminho: regra.campos[0], mensagem: regra.descricao });
      }
      continue;
    }
    // As demais só se aplicam quando tudo está preenchido e numérico: enquanto houver
    // campo vazio ou inválido, o problema dele já está listado e cobrar a regra em
    // cima disso produziria dois erros para uma causa só.
    if (preenchidos.length !== regra.campos.length) continue;
    const numeros = brutos.map((b) => Number(b));
    if (numeros.some((n) => !Number.isFinite(n))) continue;

    if (regra.tipo === "soma_igual") {
      const soma = numeros.reduce((a, b) => a + b, 0);
      if (soma !== regra.valor) {
        problemas.push({
          caminho: regra.campos[0],
          mensagem: `${regra.descricao} Somam ${soma}.`,
        });
      }
    } else if (regra.tipo === "maior_que" && !(numeros[0] > numeros[1])) {
      problemas.push({ caminho: regra.campos[0], mensagem: regra.descricao });
    }
  }
  return problemas;
}

function escalar(campo: Campo, bruto: string): string {
  if (campo.tipo === "escolha") return JSON.stringify(normalizarEscolha(bruto));
  const n = Number(bruto);
  // Inteiro sai SEM casa decimal: `_inteiro` do validador recusa `40.0`, e é assim
  // que a distinção que o JavaScript não tem atravessa para o TOML.
  return campo.tipo === "inteiro" ? String(Math.trunc(n)) : String(n);
}

/** A procedência vira COMENTÁRIO, e comentário termina na quebra de linha.
 *
 *  Sem esta limpeza, o texto livre de "quem está declarando" escapava do comentário e
 *  virava TOML: `"olavo\n[resultado_esperado]\nsuper_destaque = 3\ndestaque = 1"`
 *  produzia um arquivo VÁLIDO que definia o parâmetro nº 14 — o que a D-022 declara
 *  nulo, e exatamente o que esta tela existe para impedir. Reproduzido em 03/09/2026.
 *
 *  A limpeza mora aqui, na função pura, e não só em quem chama: o contrato de
 *  `paraToml` não pode depender do cuidado do chamador, porque o próximo chamador não
 *  leu esta história. */
function saoUmaLinha(texto: string): string {
  // Não basta tirar quebra de linha. A gramática do TOML proíbe QUALQUER caractere de
  // controle dentro de comentário, e um `\x01` no nome faz o arquivo inteiro deixar de
  // parsear — a rodada morre antes de ler um parâmetro, com o console tendo dito
  // "Guardado". Mesma classe do defeito da injeção: texto livre entrando num formato
  // onde certos bytes têm significado. Aqui só passa tabulação e o que é imprimível.
  return texto
    .replace(/[\r\n\t]+/g, " ")
    .replace(/[\u0000-\u001F\u007F]/g, "")
    .slice(0, 200);
}

/** O TOML que a rodada vai receber. Só chame com `validar()` vazio. */
export function paraToml(valores: Valores, procedencia: string): string {
  const secoes = new Map<string, string[]>();
  for (const campo of CAMPOS) {
    if (!campoAtivo(campo, valores)) continue;
    const bruto = valores.get(campo.caminho);
    if (vazio(bruto)) continue; // seção opcional não declarada some inteira
    const partes = campo.caminho.split(".");
    const secao = partes.slice(0, -1).join(".");
    const chave = partes[partes.length - 1];
    if (!secoes.has(secao)) secoes.set(secao, []);
    secoes.get(secao)!.push(`${chave} = ${escalar(campo, bruto!)}`);
  }

  const linhas: string[] = [
    "# GERADO pelo console do operador — não editar à mão.",
    "#",
    "# Todo valor aqui é PROVISÓRIO: declarado pelo dono da decisão para ESTA rodada,",
    "# rotulado PROVISÓRIO na planilha e no Registro. Provisório não é adotado — adotar",
    "# exige decisão registrada em docs/decisoes.md e entrada no CHANGELOG.",
    `# ${saoUmaLinha(procedencia)}`,
    "",
  ];
  for (const [secao, atribuicoes] of secoes) {
    linhas.push(`[${secao}]`, ...atribuicoes, "");
  }
  return linhas.join("\n");
}
