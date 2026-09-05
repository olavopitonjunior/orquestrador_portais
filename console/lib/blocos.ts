// Os TRÊS blocos da jornada — os mesmos nomes, na mesma ordem, em /parametros,
// /rodada/nova, /trabalho e /rodada. Cada um abre com a frase que diz o que as regras
// dele fazem; os sete grupos do contrato se distribuem por eles. Dado puro: o teste em
// test/blocos.test.ts garante que TODO grupo do contrato tem bloco, e nenhum bloco cita
// grupo que não existe — um grupo novo no contrato não pode sumir da tela em silêncio.

export type Bloco = { id: string; titulo: string; tese: string; grupos: string[] };

export const BLOCOS: readonly Bloco[] = [
  {
    id: "quem-entra",
    titulo: "Quem entra",
    tese: "Estas regras excluem. Reprovar em uma basta, e nenhuma nota compensa. Vêm do banco.",
    grupos: ["quem_entra_imovel", "quem_entra_perfil", "quem_entra_corretor"],
  },
  {
    id: "em-que-ordem",
    titulo: "Em que ordem",
    tese: "Estas não excluem ninguém. Ordenam quem passou: a nota vem do portal; os descontos, do banco.",
    grupos: ["em_que_ordem_portal", "em_que_ordem_descontos"],
  },
  {
    id: "quantos",
    titulo: "Quantos",
    tese: "Onde cada um vai parar, e quantos: cotas, piso e ordem de cedência vêm do contrato e não se declaram. O resto é operação.",
    grupos: ["quantos", "operacao"],
  },
];
