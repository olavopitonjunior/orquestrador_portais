# src/executar

Pontos de entrada das rodadas. É a camada que **fia** o que as outras constroem —
nenhuma regra vive aqui.

## Rodada de segunda (acompanhamento)

```bash
uv run python -m executar.segunda [--destino DIR] [--dry-run] [--hoje AAAA-MM-DD]
# ou, instalado:  uv run rodada-segunda --dry-run
```

Precisa de `POSTGRES_URL` (Registro) e das `NEWCORE_MYSQL_*` (leads) no ambiente —
gere com `op inject -i .env.tmpl -o .env`, nunca DSN no repo.

- `--dry-run` roda tudo e **não grava nem escreve nada**: serve para conferir o
  estado da rodada e as limitações antes de valer.
- Código de saída:
  - `0` entregou (completa ou degradada — a limitação vai declarada na planilha);
  - `4` **não havia carga aprovada**: insumo ausente, não erro (Spec §7.3). A rodada
    fica registrada como abortada e o gestor é avisado;
  - `3` **falha ao coletar ou apurar** (Newcore fora do ar, ou dado malformado na
    carga). Também declarado, mas é incidente — não trate como no-op benigno;
  - `1` falha de ESCRITA (Registro ou relatório);
  - `2` é do **argparse** (uso inválido da linha de comando) — reservado de
    propósito: sem a reserva, um argumento digitado errado sairia com o código de
    "não havia carga" e o agendador o trataria como no-op benigno.

A janela é **derivada** de `aprovada_em` da carga medida (Spec §1: três dias
corridos, "sem misturar com a anterior"), nunca recebida por argumento — aceitar a
janela do chamador deixaria o recorte que a Spec chama de deliberado à mercê de quem
invoca. O fim nunca passa de hoje — e **janela truncada é declarada** como limitação na
planilha (§7.2), porque medir menos que os três dias é dado parcial.

Cada rodada escreve numa **subpasta por data** (`saida/segunda/AAAA-MM-DD`): sem
isso, a segunda seguinte apagaria o relatório da anterior, e a planilha é o artefato
que a §7.2 quer auditável.

## Rodada de sexta (decisão)

```bash
uv run python -m executar.sexta --parametros ARQUIVO.toml [--externo DIR] \
    [--destino DIR] [--dry-run] [--hoje AAAA-MM-DD]
# ou, instalado:  uv run rodada-sexta --parametros ~/parametros.toml
```

Precisa das `NEWCORE_MYSQL_*` (estoque, vendas, dimensões) e de `POSTGRES_URL`
(Registro) no ambiente.

`--parametros` é **obrigatório e não tem default**. Doze dos treze parâmetros da
decisão são nulos, e a sexta não calcula nada sem eles; embutir um valor aqui seria
inventá-lo — com o agravante de ficar invisível numa planilha aprovada. O arquivo é
escrito pelo **dono da decisão**, mora **fora do repositório**, e o carregador recusa
a rodada se faltar qualquer chave ou se houver chave desconhecida (um nome digitado
errado vira erro, nunca um valor descartado em silêncio). Modelo comentado em
[`docs/parametros-da-rodada.exemplo.toml`](../../docs/parametros-da-rodada.exemplo.toml)
— os valores de lá são **ilustrativos e não adotados**.

Tudo que entra por ali é rotulado PROVISÓRIO na planilha, com a origem do arquivo; o
TOML declarado vai verbatim para `parametros_da_rodada` do Registro, junto da data de
referência e da definição de gestor ativo, para que **os parâmetros e o recorte** da
rodada sejam reconstituíveis a partir do que ficou gravado.

Isso é menos que "a rodada é reproduzível", e a diferença importa: o **estoque** não é
reconstituível. As janelas de 30 dias do gestor e as vendas de 180 dias saem de
`NOW()` no SQL, então uma reexecução lê o banco de hoje. Reproduzir a lista exigiria
snapshot do estoque, que não existe. O invariante 5 continua valendo — mesma entrada,
mesmos parâmetros, mesma lista — mas "mesma entrada" inclui o banco no instante da
rodada.

O próprio arquivo-modelo é **recusado** como entrada real (código 5): ele carrega com
sucesso, então sem a recusa sairia dele uma planilha de aparência normal construída
sobre números que o próprio arquivo declara ilustrativos.

`--hoje` governa a regra de atualização em 90 dias e a idade aceitável da coleta —
mas **não retrocede a rodada inteira**: as janelas de 30 dias do gestor e as vendas de
180 dias saem de `NOW()` no SQL, então reprocessar uma sexta antiga mistura
elegibilidade datada no passado com produtividade e perfis de hoje.

`--externo` aponta a pasta de saída do raspador. Ausente, o desempenho de portal (F3)
não entra e a rodada sai **degradada nesse fator**, com a limitação declarada — nunca
em silêncio. A fiação é tudo-ou-nada: o grafo recusa meia-fiação.

- Código de saída:
  - `0` entregou (completa ou degradada — a limitação vai declarada na planilha);
  - `5` **parâmetros ausentes, fora de faixa, de forma desconhecida, ou o arquivo-modelo**.
    Nada rodou e nada foi tocado: é o arquivo de quem opera, corrigível em segundos.
    Código próprio de propósito — tratá-lo como falha de fonte mandaria alguém
    investigar o Newcore por causa de um typo no TOML;
  - `4` rodada **abortada por estoque vazio**: sem estoque não há decisão (Spec §7.2);
  - `6` rodada **abortada por VETO DO CRIVO**: a auditoria apanhou violação de cota,
    de piso ou de relaxamento em super destaque — invariantes 6 e 7. Código separado
    do `4` de propósito: sob um código só, uma violação de invariante chegaria ao
    monitoramento com a mesma cara de "não havia imóvel para decidir";
  - `3` **falha ao coletar ou decidir** (Newcore fora do ar, saída do raspador
    ilegível, rodada incoerente) — incidente, não no-op;
  - `1` falha de ESCRITA (Registro ou planilha);
  - `2` é do **argparse**, reservado como na segunda.

A **aprovação não é aberta aqui**. O que dispara a aprovação tácita sozinha é o prazo
— parâmetro pendente nº 10, **nulo**; abrir uma thread de aprovação sem prazo seria
afirmar um prazo que ninguém definiu. O runner termina informando o `rodada_id`, e
quem tem o prazo (console ou agendador) abre `grafo.aprovacao` com ele.

Cada rodada escreve numa subpasta por data (`saida/sexta/AAAA-MM-DD`) — a planilha é
o artefato contratual, o que foi de fato aprovado e carregado.

## Agendamento

Fora do escopo: quem dispara é o agendador do sistema operacional (Ferramentas §4).
Os horários exatos são o parâmetro pendente nº 8 — nulo, nada aqui os embute.
