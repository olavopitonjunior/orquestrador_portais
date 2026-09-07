// O que cada coluna da planilha quer dizer, para o `title` do cabeçalho.
//
// Por que isto é um módulo e não uma constante dentro da página: a página lê o
// ARTEFATO em disco, e artefato é registro histórico — as planilhas já entregues
// mantêm para sempre os nomes de coluna que tinham quando foram geradas. Isso faz
// deste glossário um contrato com o PASSADO, não só com o presente, e contrato
// merece teste. (É a terceira vez nesta série que lógica dentro de `page.tsx`
// escapou da rede; ver `abas-da-rodada.ts` e `portao-da-coleta.ts`.)

export const SOBRE_A_COLUNA: Record<string, string> = {
  nota_bruta:
    "a nota antes dos descontos: soma ponderada dos sinais do anúncio (ou o desempate de banco, se a raspagem não entrou)",
  origem_da_nota:
    "de onde veio a nota desta linha: portal (medida no anúncio), banco (a raspagem não entrou) ou sem_anuncio (o imóvel não tinha anúncio e recebeu o pior valor declarado)",
  tem_anuncio: "se o imóvel tinha anúncio na coleta — eixo independente da origem da nota",
  nota_anuncio: "nota do anúncio no portal, reescalada entre os elegíveis",
  cliques: "cliques no anúncio, somados entre tipos, reescalados",
  visualizacoes: "visualizações do anúncio, reescaladas (peso adotado zero)",
  leads: "leads já atraídos em 180 dias (banco) — desempate",
  produtividade_gestor: "produtividade do gestor em 30 dias (banco) — desempate",
  casa_perfil: "se o imóvel se parece com o que vendeu (a nona regra)",
  gestor_logou_na_janela: "se o gestor entrou no sistema na janela declarada (trava a cedência)",
  pen_janela_sem_resultado: "penalidade · janela anterior sem resultado",
  pen_sem_avaliacao_por_categoria: "penalidade · sem avaliação por categoria",
  pen_sem_lead_180d: "penalidade · sem lead em 180 dias",
  desconto_total: "soma das penalidades",
  ultima_janela: "a última janela paga deste imóvel, e como foi julgada",
  perfil_que_puxou: "o perfil de conversão de mais vendas que o imóvel casa",
  perfil_num_vendas: "vendas que sustentam esse perfil",
  origem: "ranking, ou relaxamento (recuperado por cedência)",
  degrau_cedido: "a regra cedida para este imóvel entrar",

  // --- Abas que não são de imóvel, e que a página também renderiza com tooltip ---
  //
  // Estas dez estavam ÓRFÃS na tela, hoje, quando esta correção foi escrita: a
  // primeira versão da guarda varria `apuracao` — que a página nem renderiza como
  // tabela — e ignorava `relaxamento`, `perfis` e `parametros_e_limitacoes`, que ela
  // renderiza. Corrigir o glossário olhando a lista errada de abas é o mesmo defeito
  // uma camada acima; achado da revisão, provado injetando uma coluna falsa numa
  // dessas abas e vendo os 175 testes passarem.
  ordem:
    "a ordem em que a etapa produziu as linhas — nos perfis é a ordem canônica, a mesma que o Registro grava; no relaxamento é a ordem de cedência aplicada",
  posicoes_dependentes: "quantas posições de destaque aquele degrau de cedência encheu",
  tipo: "ADOTADO (decisão registrada), PROVISÓRIO (sem valor do dono ainda) ou a limitação que a rodada declarou sobre si mesma",
  dimensoes: "as características que formam este perfil, na ordem de importância do dono (D-017)",
  valores: "os valores dessas características, pareados com a coluna ao lado, posição a posição",
  vendas_sustentam: "quantas vendas assinadas na janela sustentam este perfil",
  classificacao: "robusto (ao menos três vendas, D-014) ou frágil — frágil não conta para o filtro",
  conta_para_o_filtro:
    "se este perfil ELIMINA candidatos, que é a nona regra (D-027): conta quem é robusto E contém a faixa de preço. Um perfil robusto sem a faixa de preço não filtra ninguém, só descreve",

  // --- Colunas que não são mais GERADAS, e que o glossário continua explicando ---
  //
  // Sair da geração não as apaga do disco. Cada uma está num conjunto DIFERENTE de
  // arquivos, medido em `saida/sexta/` — dizer "estão nas três planilhas" seria
  // cômodo e falso, e a primeira versão deste comentário dizia isso:
  //
  //   perfil_fragil       7 arquivos  03/09 e 04/09 (super, destaque) + 06/09 (as três)
  //   semelhanca_perfil   5 arquivos  03/09 (super, destaque) + 04/09 (as três)
  //   desempenho_proprio  5 arquivos  idem
  //   nota_portal         3 arquivos  só 06/09
  //   portal_pesou        2 arquivos  só as apurações de 04/09 e 06/09
  //
  // São DOIS cortes, não um: `semelhanca_perfil` e `desempenho_proprio` saíram em
  // 05/09 (`da58897`), quando o desenho de quatro fatores caiu; as outras três em
  // 06/09, nas fatias da issue #73. Por isso há duas datas aqui embaixo.
  //
  // Quando as chaves saíram, o tooltip sumiu das colunas de rodadas JÁ ENTREGUES,
  // inclusive a que aguarda aprovação. Defeito visto ao abrir o console, não ao ler
  // o código: quem raciocina sobre o artefato futuro não vê o artefato que já existe.
  //
  // A regra que fica: chave de glossário nunca é removida quando a coluna sai — ela
  // ganha a explicação de por que saiu.
  nota_portal:
    "nome ANTIGO da nota bruta, nas planilhas geradas até 06/09/2026 — mesmo número, e o rótulo 'do portal' enganava quando a raspagem não entrava, porque aí a nota vinha do banco",
  perfil_fragil:
    "coluna REMOVIDA (planilhas até 06/09/2026): era sempre falsa por construção desde a D-027, porque o perfil que puxou só é escolhido entre os que contam. Quem quer saber se algum perfil puxou lê a coluna ao lado",
  portal_pesou:
    "nome ANTIGO de origem_da_nota, nas planilhas geradas até 06/09/2026 — dizia sim/não lendo o sinal do grafo, e não o valor efetivo usado no cálculo",
  semelhanca_perfil:
    "coluna REMOVIDA (planilhas até 05/09/2026): era o fator F1 do desenho de quatro fatores, a semelhança com o perfil que vendeu. A D-027 transformou o perfil em regra eliminatória, então ele deixou de ser fator e passou a decidir quem entra — quem quer o perfil hoje lê perfil_que_puxou e casa_perfil",
  desempenho_proprio:
    "coluna REMOVIDA (planilhas até 05/09/2026): era o fator F3 do desenho de quatro fatores, o desempenho do anúncio no portal. A D-028 fez o portal virar a nota inteira em vez de um fator entre quatro — o que era este número hoje está em nota_bruta e nos sinais que a compõem",
};

/** As colunas que saíram da geração e que o glossário mantém DE PROPÓSITO.
 *
 *  Dois cortes: `semelhanca_perfil` e `desempenho_proprio` em 05/09/2026, quando o
 *  desenho de quatro fatores caiu (D-027/D-028); as outras três em 06/09/2026, nas
 *  fatias da issue #73. */
export const COLUNAS_LEGADAS = [
  "nota_portal",
  "perfil_fragil",
  "portal_pesou",
  "semelhanca_perfil",
  "desempenho_proprio",
] as const;

/** Colunas que NUNCA tiveram tooltip, de propósito: explicam-se pelo nome.
 *
 *  Existe para a guarda de realidade poder afirmar algo forte — "toda coluna em
 *  disco ou está explicada ou está NESTA lista". Sem ela a guarda só conseguia
 *  perguntar sobre as chaves que ela mesma já garantia existir, e passava verde com
 *  colunas órfãs no disco. Foi o que aconteceu. */
export const COLUNAS_SEM_TOOLTIP: readonly string[] = [
  // MEDIDA contra o disco, e ENXUTA: só o que aparece de fato nas abas que a página
  // renderiza como tabela. A primeira versão trazia 26 nomes, 19 dos quais só
  // existem na apuração — que a página mostra como card, sem cabeçalho com `title`.
  // Whitelist que ninguém confere é whitelist que silencia coluna nova, então há
  // teste proibindo entrada sem uso.
  "imovel_id", "posicao", "nota", "regra_cedida", "regras_reprovadas", "item", "valor",
];
