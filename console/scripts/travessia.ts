// Emite um TOML de sondagem a partir do contrato, para provar a TRAVESSIA.
//
//   node --import tsx scripts/travessia.ts <forma> <destino.toml>
//
// Existe por uma lacuna que nenhum teste de um lado só cobre: o console valida e
// serializa em TypeScript, a rodada valida e carrega em Python, e os dois lados podem
// concordar consigo mesmos enquanto discordam entre si. O passo de CI gera o TOML aqui
// e manda `config.parametros.carregar()` aceitá-lo — se a serialização derivar (uma
// casa decimal num inteiro, uma seção condicional emitida fora de hora, uma escolha
// escrita sem aspas), a build cai antes de o dono descobrir pelo código de saída 5.
//
// Os valores são SONDAS: satisfazem faixas e provam estrutura, e nada mais. Não são
// sugestão nem default, e nunca saem daqui — os catorze parâmetros seguem nulos.

import { writeFileSync } from "node:fs";

import { CAMPOS, campoAtivo } from "../lib/contrato";
import { paraToml, validar } from "../lib/toml";

// A quarta "forma" não é forma de desempenho: é o pedido para preencher a SEÇÃO
// OPCIONAL. Sem ela, `_ler_resultado_esperado` — o único ramo condicional do
// carregador, e o do parâmetro nº 14 — nunca era exercitado pela travessia.
const forma = process.argv[2] === "com_opcionais" ? "visualizacoes" : (process.argv[2] ?? "visualizacoes");
const comOpcionais = process.argv[2] === "com_opcionais";
const destino = process.argv[3] ?? "/tmp/travessia.toml";

const valores = new Map<string, string>([["externo.desempenho.forma", forma]]);
for (const campo of CAMPOS) {
  if (!campo.obrigatorio || valores.has(campo.caminho) || !campoAtivo(campo, valores)) continue;
  if (campo.tipo === "escolha") {
    valores.set(campo.caminho, (campo.escolhas ?? [])[0]);
  } else if (campo.caminho.startsWith("pesos.")) {
    // ASSIMÉTRICAS entre os níveis, e é o ponto todo. Com os oito pesos valendo 25, uma
    // troca de `pesos.super_destaque` por `pesos.destaque` na serialização produziria
    // valores IDÊNTICOS no destino errado — o check de valores do CI ficaria verde com
    // os dois níveis do ranking invertidos, que é a assimetria central do produto.
    // Medido: com sondas iguais, a troca passava. Cada nível soma 100, em ordem oposta.
    const ordem = ["semelhanca_perfil", "leads_positivo", "desempenho_proprio", "produtividade_gestor"];
    const posicao = ordem.indexOf(campo.caminho.split(".")[2]);
    const escala = campo.caminho.includes("super_destaque") ? [40, 30, 20, 10] : [10, 20, 30, 40];
    valores.set(campo.caminho, String(escala[posicao]));
  } else if (campo.tipo === "inteiro") {
    valores.set(campo.caminho, String(campo.minimo ?? 1));
  } else {
    const minimo = campo.minimo ?? 0;
    const maximo = campo.maximo ?? minimo + 2;
    valores.set(campo.caminho, String((minimo + maximo) / 2));
  }
}
// Segunda passada: os campos condicionais só ficam ativos depois da forma escolhida.
for (const campo of CAMPOS) {
  if (campo.obrigatorio && campoAtivo(campo, valores) && !valores.has(campo.caminho)) {
    valores.set(campo.caminho, campo.tipo === "escolha" ? (campo.escolhas ?? [])[0] : "1");
  }
}

if (comOpcionais) {
  // A regra cruzada exige super > destaque, estrito.
  valores.set("resultado_esperado.super_destaque", "3");
  valores.set("resultado_esperado.destaque", "1");
}

const problemas = validar(valores);
if (problemas.length > 0) {
  console.error("o validador do console reprovou o próprio preenchimento:", problemas);
  process.exit(1);
}
writeFileSync(destino, paraToml(valores, `travessia (forma=${forma})`));
// Os valores PRETENDIDOS, ao lado do TOML. É o que permite ao lado Python conferir
// DESTINO, não só estrutura: trocar `pesos.super_destaque` por `pesos.destaque` na
// serialização geraria um TOML válido, que carrega limpo, com os dois níveis
// invertidos — a assimetria central do produto — e o CI ficaria verde.
writeFileSync(
  destino.replace(/\.toml$/, ".esperado.json"),
  JSON.stringify(Object.fromEntries(valores), null, 2),
);
console.log(`TOML de travessia escrito em ${destino} (forma=${forma})`);
