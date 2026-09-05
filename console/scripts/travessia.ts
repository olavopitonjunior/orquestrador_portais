// Emite um TOML de sondagem a partir do contrato, para provar a TRAVESSIA.
//
//   node --import tsx scripts/travessia.ts [com_opcionais] <destino.toml>
//
// Existe por uma lacuna que nenhum teste de um lado só cobre: o console valida e
// serializa em TypeScript, a rodada valida e carrega em Python, e os dois lados podem
// concordar consigo mesmos enquanto discordam entre si. O passo de CI gera o TOML aqui
// e manda `config.parametros.carregar()` aceitá-lo — se a serialização derivar (uma
// casa decimal num inteiro, uma seção condicional emitida fora de hora, uma escolha
// escrita sem aspas), a build cai antes de o dono descobrir pelo código de saída 5.
//
// Os valores são SONDAS: satisfazem faixas e provam estrutura, e nada mais. Não são
// sugestão nem default, e nunca saem daqui — os adotados vivem em `config/adotados.py`.

import { writeFileSync } from "node:fs";

import { CAMPOS, campoAtivo } from "../lib/contrato";
import { paraToml, validar } from "../lib/toml";

// Duas variações: com ou sem a SEÇÃO OPCIONAL (a régua nº 14). Sem a segunda,
// `_ler_resultado_esperado` — o único ramo condicional do carregador — nunca seria
// exercitado pela travessia.
const caso = process.argv[2] ?? "sem_opcionais";
const comOpcionais = caso === "com_opcionais";
// `vazio`: o TOML que o disparo gera SOZINHO quando não há declaração (rodada com os
// adotados, D-034). Não passa por `validar` — o validador do console cobraria os 14
// obrigatórios, e é justamente por isso que a rede é a travessia, não o validador.
const vazio = caso === "vazio";
const destino = process.argv[3] ?? "/tmp/travessia.toml";

const valores = new Map<string, string>();
for (const campo of CAMPOS) {
  if (vazio) break;
  if (!campo.obrigatorio || valores.has(campo.caminho) || !campoAtivo(campo, valores)) continue;
  if (campo.tipo === "escolha") {
    valores.set(campo.caminho, (campo.escolhas ?? [])[0]);
  } else if (campo.caminho.startsWith("portal.peso_")) {
    // ASSIMÉTRICOS de propósito: sondas iguais deixariam uma troca de campo passar.
    const escala: Record<string, string> = {
      "portal.peso_nota": "60",
      "portal.peso_cliques": "30",
      "portal.peso_visualizacoes": "10",
    };
    valores.set(campo.caminho, escala[campo.caminho]);
  } else if (campo.tipo === "inteiro") {
    valores.set(campo.caminho, String(campo.minimo ?? 1));
  } else {
    const minimo = campo.minimo ?? 0;
    const maximo = campo.maximo ?? minimo + 2;
    valores.set(campo.caminho, String((minimo + maximo) / 2));
  }
}
if (comOpcionais) {
  // A regra cruzada exige super > destaque, estrito.
  valores.set("resultado_esperado.super_destaque", "3");
  valores.set("resultado_esperado.destaque", "1");
}

const problemas = vazio ? [] : validar(valores);
if (problemas.length > 0) {
  console.error("o validador do console reprovou o próprio preenchimento:", problemas);
  process.exit(1);
}
writeFileSync(destino, paraToml(valores, `travessia (${comOpcionais ? "com" : "sem"} opcionais)`));
// Os valores PRETENDIDOS, ao lado do TOML. É o que permite ao lado Python conferir
// DESTINO, não só estrutura: trocar `portal.peso_nota` por `portal.peso_cliques` na
// serialização geraria um TOML válido, que carrega limpo, com os pesos trocados — e
// o CI ficaria verde.
writeFileSync(
  destino.replace(/\.toml$/, ".esperado.json"),
  JSON.stringify(Object.fromEntries(valores), null, 2),
);
console.log(`TOML de travessia escrito em ${destino} (${caso})`);
