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

`--parametros` é **obrigatório e não tem default**. Treze dos quatorze parâmetros da
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
quem decide invoca `rodada-aprovar` com ele (abaixo).

Cada rodada escreve numa subpasta por data (`saida/sexta/AAAA-MM-DD`) — a planilha é
o artefato contratual, o que foi de fato aprovado e carregado.

## Aprovação da rodada de decisão

```bash
uv run python -m executar.aprovar abrir   RODADA_ID
uv run python -m executar.aprovar aprovar RODADA_ID --por NOME
uv run python -m executar.aprovar tacita  RODADA_ID
# ou, instalado:  uv run rodada-aprovar aprovar 12 --por olavo
```

Precisa de `POSTGRES_URL`. Carimba `registro.rodada.aprovada_em` — **o elo entre a
sexta e a segunda**: `ultima_carga_aprovada` filtra por `aprovada_em IS NOT NULL`, então
enquanto ninguém carimba, toda rodada de segunda declara ausência de carga e sai
pelo código de "insumo ausente", que o agendador trata como no-op benigno.

- `abrir` cria a pausa de aprovação sem decidir. É opcional hoje: a fila que o
  console monta (`console/lib/registro.ts::rodadasAguardandoAprovacao`) sai do
  **Registro** (`aprovada_em IS NULL`), não do checkpointer — `aprovar` e `tacita`
  abrem sozinhos se ainda não houver pausa.
- `tacita` é a aprovação por decurso de prazo (D-001). **Quem invoca AFIRMA que o
  prazo decorreu**: o prazo é o parâmetro nº 10, nulo, e nada aqui o calcula. O
  Registro guarda `aprovada_por = "tácita"` para que essa afirmação fique
  distinguível de uma aprovação que o dono deu olhando a lista.
- `--em AAAA-MM-DDTHH:MM` declara **quando a carga entrou no ar**, que é o que
  `aprovada_em` significa (a carga é manual; o sistema não publica nada). Sem ele o
  default é agora — e aprovar na segunda uma carga aplicada na sexta deslocaria em
  três dias a janela que a segunda mede, sem nada acusar.
- `--dry-run` roda todas as guardas e não grava. Recusa o que recusaria de verdade.
- `--refazer` (em `aprovar` e `tacita`) descarta uma thread de aprovação **já
  decidida** e decide de novo. É a saída do código `9`. Só age quando o Registro NÃO
  tem carimbo, então não produz carimbo duplo.
- `--fora-de-ordem` libera as duas recusas de ORDEM, que são opostas e ambas fazem
  a segunda medir a lista errada. A eleição da vigente é por `(aprovada_em, id)`
  (`ultima_carga_aprovada`), não por id, então há dois jeitos de errar: aprovar uma
  rodada **antiga** havendo outra mais nova já aprovada (o carimbo novo promoveria a
  velha a vigente); e carimbar uma rodada **nova** num instante ANTERIOR a um carimbo
  existente (o `--em` torna isso alcançável) — aí a lista nova é aprovada e a vigente
  continua sendo a outra, sem aviso. As duas são recusadas por default, com a
  mensagem dizendo qual é o caso.
- Código de saída:
  - `0` carimbou (ou abriu, no `abrir`);
  - `4` rodada **não aprovável**: não existe, não é de decisão, tem estado
    inaproveitável, ou o instante declarado é impossível (futuro, ou anterior ao fim
    da rodada). A recusa de estado ABORTADA é hoje **inalcançável pelo caminho de
    produção** — o grafo só grava rodadas não-abortadas, então não há id para
    aprovar; existe porque a pendência do dono sobre gravar cabeçalho de abortada
    segue aberta e porque `estado` é `NULL`-ável no DDL;
  - `7` **já aprovada** — recusa de RE-carimbo. Código próprio porque o carimbo é o
    início da janela que a segunda mede E a chave que elege a carga vigente:
    sobrescrevê-lo desloca a medição e pode trocar a carga, sem deixar rastro;
  - `5` **valor impossível declarado pelo operador**: `--em` no futuro, ou anterior
    ao fim da rodada. Mesmo sentido do `5` da sexta ("o que o operador declarou é
    inválido"). Não sai por `4` de propósito: `4` é insumo ausente, que o agendador
    trata como no-op benigno — um `--em` digitado errado numa chamada automatizada
    nunca aprovaria nada e ninguém saberia;
  - `8` **fora de ordem** (uma das duas descritas acima);
  - `9` **estado inconsistente**: a thread do grafo foi decidida e o Registro não tem
    carimbo — o veredito não chegou lá (sink que falhou, ou reprovação, que o esquema
    não representa). Código próprio, não o `7`: aqui não há aprovação nenhuma, e o
    monitoramento lê o número, não a mensagem. **Saída:** `--refazer` descarta a
    thread e decide de novo. Para inspecionar antes, o estado vive no checkpointer:
    `psql "$POSTGRES_URL" -c "SELECT checkpoint_id, thread_id FROM checkpoints WHERE
    thread_id = 'rodada-N'"`;
  - `3` Postgres fora do ar ou `POSTGRES_URL` ausente;
  - `1` falha de ESCRITA;
  - `2` é do **argparse** — reservado, como nos outros runners.

`6` (veto do crivo) fica reservado ao que já significa na sexta: reusá-lo faria o
mesmo número querer dizer duas coisas conforme o programa que saiu.

**Não existe `reprovar`.** `grafo/aprovacao.py` sabe representar a reprovação, mas
`registro.rodada` não a distingue de "ainda não decidida" — as duas deixam
`aprovada_em` nulo. Expor o comando daria sensação de ter agido: o console
continuaria mostrando "Aprove a rodada N" para sempre. É buraco de esquema,
registrado em `docs/decisoes.md` como pergunta ao dono.

## Medição dos números de referência

```bash
uv run python -m executar.referencias [--registrar] [--hoje AAAA-MM-DD]
```

Precisa das `NEWCORE_MYSQL_*`. Roda o passo 5 da skill `verificar-contra-spec` —
"rodar a implementação contra a base e comparar com os números de referência" — que
até aqui era feito à mão, com o resultado vivendo como prosa num documento.

Três compromissos, e cada um evita um jeito de a conferência mentir:

- **Reaproveita o coletor e as regras do sistema**, nunca reimplementa o funil. Uma
  segunda implementação em SQL poderia divergir da primeira, e aí a conferência
  passaria a medir a própria cópia.
- **Lê os valores publicados do `docs/mapa-de-dados.md`**, não guarda cópia. Uma
  quarta cópia (PRD, mapa, skill, ferramenta) é mais uma para esquecer de atualizar.
- **Não altera número nenhum.** `--registrar` anexa um bloco de deriva datado, no
  formato que o mapa já usa, declarando que nada foi adotado. Incorporar exige
  repetir a contagem noutro dia — uma medição só não separa deriva de oscilação — e
  conciliar PRD, `CLAUDE.md` e mapa, que publicam os mesmos números.

Além do funil acumulado, imprime a **passagem por regra**: quantos dos que chegam à
etapa final passam em cada uma das cinco regras restantes, isoladamente. Um funil
acumulado só diz que encolheu; isso diz onde.

**A banda de ruído é 1%**, e é escolha desta ferramenta — não é parâmetro de decisão,
não entra em `src/config` e não toca o caminho da decisão. Está calibrada contra a
deriva já documentada: as variações diárias do estoque ficam em torno de 0,05%, e a
divergência medida em 02/09 passa de 24%. **Vendas assinadas fica fora dessa régua**:
não é etapa do funil, não passa por regra de elegibilidade nenhuma, e com base de 176
o mesmo 1% vale menos de duas vendas — sai como nota à parte, com o motivo.

Código de saída: `0` mediu; `1` não conseguiu ler o mapa; `3` não conseguiu medir
contra a base.

## Agendamento

Fora do escopo: quem dispara é o agendador do sistema operacional (Ferramentas §4).
Os horários exatos são o parâmetro pendente nº 8 — nulo, nada aqui os embute.
