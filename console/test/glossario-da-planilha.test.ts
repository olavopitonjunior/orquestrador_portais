import { strict as assert } from "node:assert";
import { readdirSync, readFileSync, existsSync } from "node:fs";
import { join, resolve } from "node:path";
import { test } from "node:test";
import { ORDEM_DAS_ABAS } from "../lib/abas-da-rodada";
import { COLUNAS_LEGADAS, COLUNAS_SEM_TOOLTIP, SOBRE_A_COLUNA } from "../lib/glossario-da-planilha";

test("as colunas que SAÍRAM da geração continuam explicadas", () => {
  // O defeito que este teste impede, e que só apareceu ao abrir o console: quando
  // `nota_portal` virou `nota_bruta` e `perfil_fragil` saiu, as chaves velhas foram
  // removidas do glossário. Mas a página lê o ARTEFATO em disco, e artefato é
  // registro histórico — as planilhas já entregues mantêm para sempre os nomes que
  // tinham. O tooltip sumiu justamente das colunas de TODAS as rodadas existentes,
  // incluindo a que aguarda aprovação do dono.
  for (const coluna of COLUNAS_LEGADAS) {
    const texto = SOBRE_A_COLUNA[coluna];
    assert.ok(texto, `a coluna legada ${coluna} perdeu a explicação`);
    // Não basta existir: tem de DIZER que é legada, senão o operador lê a explicação
    // de uma coluna que o sistema não gera mais como se fosse do mundo atual.
    assert.match(
      texto,
      /ANTIGO|REMOVIDA/,
      `${coluna} precisa dizer que é nome antigo ou coluna removida`,
    );
    // E tem de dizer ATÉ QUANDO, para o leitor saber se a planilha que abriu é
    // dessas ou não. A data varia: são DOIS cortes — 05/09 quando o desenho de
    // quatro fatores caiu, 06/09 nas fatias da issue #73 —, então o que se exige é
    // que date, não qual data. Exigir uma só foi o meu primeiro erro aqui.
    assert.match(texto, /até \d{2}\/\d{2}\/\d{4}/, `${coluna} precisa datar o corte`);
  }
});

test("toda coluna legada aponta para o que a substituiu, ou diz que nada substituiu", () => {
  assert.match(SOBRE_A_COLUNA.nota_portal, /nota bruta/);
  assert.match(SOBRE_A_COLUNA.portal_pesou, /origem_da_nota/);
  // `perfil_fragil` não tem sucessora — foi removida por não carregar informação —,
  // então tem de mandar o leitor para a coluna que já respondia a pergunta.
  assert.match(SOBRE_A_COLUNA.perfil_fragil, /coluna ao lado|perfil que puxou/);
});

test("as colunas legadas NÃO são geradas mais — o glossário não vira lista de desejos", () => {
  // Contraprova: se alguém reintroduzir uma delas na geração, a explicação "coluna
  // removida" passa a mentir. O produtor é o Python; aqui checamos o que dá para
  // checar deste lado — que nenhuma legada está na lista das colunas vivas.
  const vivas = ["nota_bruta", "origem_da_nota", "perfil_que_puxou", "tem_anuncio"];
  for (const legada of COLUNAS_LEGADAS) {
    assert.ok(!vivas.includes(legada), `${legada} está viva e legada ao mesmo tempo`);
  }
});

test("a lista de dispensadas não INFLA: toda entrada tem de existir em disco", () => {
  // Whitelist que ninguém confere silencia coluna nova. A primeira versão desta
  // lista trazia 26 nomes, 19 dos quais só existem na apuração — que a página mostra
  // como card, sem `title` no cabeçalho. Cada nome a mais é uma coluna que poderia
  // aparecer amanhã numa aba renderizada e passar batido, já dispensada por engano.
  // Achado da revisão.
  const raiz = resolve(process.cwd(), "..", "saida", "sexta");
  if (!existsSync(raiz)) return;
  const datas = readdirSync(raiz).filter((n) => /^\d{4}-\d{2}-\d{2}$/.test(n));
  if (datas.length === 0) return;

  const emDisco = new Set<string>();
  for (const data of datas) {
    for (const aba of ORDEM_DAS_ABAS) {
      const arquivo = join(raiz, data, `${aba}.csv`);
      if (!existsSync(arquivo)) continue;
      for (const col of readFileSync(arquivo, "utf-8").split(/\r?\n/, 1)[0].split(",")) {
        emDisco.add(col);
      }
    }
  }
  assert.ok(emDisco.size > 0, "esperava colunas em disco para conferir a lista");
  assert.deepEqual(
    COLUNAS_SEM_TOOLTIP.filter((c) => !emDisco.has(c)),
    [],
    "dispensada que não existe em nenhuma aba renderizada — tire da lista",
  );
});

test("NENHUMA coluna em disco fica sem explicação nem declarada como dispensada", () => {
  // A guarda de realidade — reescrita, porque a primeira versão era TAUTOLOGIA.
  //
  // Ela montava o conjunto das colunas em disco ausentes do glossário e então só
  // perguntava sobre `COLUNAS_LEGADAS`, que o primeiro teste já garante estarem
  // presentes: a asserção não podia ficar vermelha sozinha. A prova de que não
  // protegia é que ela passou VERDE com `semelhanca_perfil` e `desempenho_proprio`
  // órfãs em disco desde 05/09 — o defeito seguinte da mesma família, já presente,
  // e a guarda não o viu. Achado do orquestrador no portão.
  //
  // Agora a afirmação é forte E do tamanho certo: toda coluna das abas que a página
  // RENDERIZA COMO TABELA ou está explicada, ou está
  // declarada em `COLUNAS_SEM_TOOLTIP`. Uma coluna nova que ninguém explicou nem
  // dispensou faz este teste falhar, que é o ponto.
  //
  // Pula quando não há `saida/` — o diretório é ignorado pelo git e o CI não o tem.
  // Por isso ela COMPLEMENTA os testes acima, não os substitui.
  const raiz = resolve(process.cwd(), "..", "saida", "sexta");
  if (!existsSync(raiz)) return;
  const datas = readdirSync(raiz).filter((n) => /^\d{4}-\d{2}-\d{2}$/.test(n));
  if (datas.length === 0) return;

  const conhecidas = new Set([...Object.keys(SOBRE_A_COLUNA), ...COLUNAS_SEM_TOOLTIP]);
  const orfas = new Map<string, string>();
  let arquivosLidos = 0;
  for (const data of datas) {
    // ORDEM_DAS_ABAS, importada e não recopiada: é a lista de abas que a página
    // RENDERIZA COMO TABELA, e portanto as únicas cujos cabeçalhos ganham `title`.
    // A primeira versão desta guarda tinha lista própria — varria `apuracao`, que a
    // página mostra como card e não como tabela, e ignorava `relaxamento`, `perfis` e
    // `parametros_e_limitacoes`, que ela mostra. Dez colunas estavam órfãs na tela e
    // a guarda passava verde. Uma terceira fonte de verdade sobre "quais abas viram
    // tabela" foi exatamente o que criou o buraco.
    for (const aba of ORDEM_DAS_ABAS) {
      const arquivo = join(raiz, data, `${aba}.csv`);
      if (!existsSync(arquivo)) continue;
      arquivosLidos++;
      const cabecalho = readFileSync(arquivo, "utf-8").split(/\r?\n/, 1)[0].split(",");
      for (const col of cabecalho) if (!conhecidas.has(col)) orfas.set(col, `${data}/${aba}`);
    }
  }
  // Contraprova: sem isto o teste passaria vazio se o glob quebrasse.
  assert.ok(
    arquivosLidos >= ORDEM_DAS_ABAS.length,
    `esperava ao menos uma planilha completa em disco, li ${arquivosLidos} arquivo(s)`,
  );
  assert.deepEqual(
    [...orfas].map(([c, onde]) => `${c} (${onde})`),
    [],
    "coluna em disco sem tooltip e sem estar declarada como dispensada",
  );
});

