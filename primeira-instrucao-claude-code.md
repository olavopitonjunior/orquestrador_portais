Você vai iniciar a construção do sistema de curadoria automatizada da vitrine de destaques de imóveis da Newcore.

Esta primeira tarefa é exclusivamente de fundação. Nenhuma linha de código de produto deve ser escrita agora.

## Passo zero, obrigatório

Leia integralmente, antes de criar qualquer arquivo, os três documentos que estão em `docs/`:

- `vitrine-destaque-prd.md` — o que o produto faz e por quê
- `vitrine-destaque-spec.md` — comportamento dos agentes, contratos, regras de cálculo
- `vitrine-destaque-ferramentas.md` — decisões de tecnologia e ônus assumidos

Esses documentos são a fonte da verdade. Se algo nesta instrução contradisser qualquer um deles, **pare e me avise** em vez de decidir sozinho.

## Aviso de nomenclatura, leia com atenção

A palavra "agente" tem dois significados neste projeto, e confundi-los produz um repositório inutilizável.

**Agentes do produto** são sete: Orquestrador, Coletor Interno, Coletor Externo, Analista de Perfil de Conversão, Decisor, Redator da Entrega e Monitor Operacional. Eles serão nós de um grafo LangGraph, escritos em Python, executados em produção às sextas e segundas. **Não devem virar arquivos em `.claude/agents/`.**

**Subagentes de desenvolvimento** existem apenas para ajudar a construir este projeto. Vivem em `.claude/agents/` e nunca rodam em produção.

O mesmo vale para "skills". As skills em `.claude/skills/` são ferramentas de desenvolvimento. As competências dos agentes do produto estão descritas no PRD e viram código Python.

## O que criar

### 1. Estrutura de pastas

```
CLAUDE.md
CHANGELOG.md
bug.md
docs/
  vitrine-destaque-prd.md
  vitrine-destaque-spec.md
  vitrine-destaque-ferramentas.md
  mapa-de-dados.md
.claude/
  agents/
  skills/
src/
  grafo/       nós do LangGraph e definição do fluxo
  dominio/     regras de elegibilidade, ranking, penalidades, alocação, relaxamento
  dados/       acesso de leitura ao Newcore e acesso ao Registro em Postgres
  entrega/     geração da planilha e do relatório
  config/      parâmetros de decisão
tests/
```

Crie as pastas com um arquivo de marcação onde ainda não houver conteúdo. Não crie módulos vazios com nomes inventados.

### 2. CLAUDE.md

Deve conter, nesta ordem:

- **O que é o projeto**, em no máximo três parágrafos, escritos a partir do PRD e não copiados dele.
- **Cadência**: sexta é decisão e carga; segunda é acompanhamento. Não existe execução diária.
- **Stack**: Python, LangGraph, um único PostgreSQL servindo o checkpointer do grafo e o Registro em esquemas separados, leitura direta do MySQL do Newcore, automação de navegador para a raspagem, um provedor comercial de modelo por API.
- **Invariantes**, transcritos exatamente como estão na seção abaixo desta instrução.
- **Estrutura de pastas** e o que vive em cada uma.
- **Hierarquia dos documentos**: PRD acima da Spec, Spec acima do documento de ferramentas, e todos acima do código. Divergência entre código e documento é bug do código até prova em contrário.
- **Glossário mínimo**, incluindo obrigatoriamente a distinção entre agente do produto e subagente de desenvolvimento, e os termos elegibilidade, perfil de conversão, janela de destaque, relaxamento, rodada degradada e pronto.
- **Parâmetros ainda sem valor**: liste os nove parâmetros pendentes que constam da Spec e do documento de ferramentas. Nenhum deles pode ser preenchido com valor inventado; devem ficar explicitamente nulos até serem definidos.

### 3. docs/mapa-de-dados.md

Extraia da seção "Base factual" do PRD um mapa de dados de referência, para que ninguém precise redescobrir o banco. Deve conter:

- As duas bases do Newcore e o que cada uma serve.
- As tabelas relevantes com sua contagem de registros e o papel de cada uma.
- `FT_RealtyRelation` destacada como tabela central, com os campos que o produto usa.
- A seção de defeitos de dado confirmados, integralmente. Esses defeitos são armadilhas conhecidas: campo de tipo de comercialização nulo em 96% dos casos, zona de valor nula em 98%, ciclo de conversão com valores negativos, 44% do estoque sem avaliação por categoria, campo de vagas ausente da tabela principal, campos de placa e impulsionamento vazios.
- Os números de referência medidos: 10.290 imóveis elegíveis, 4.852 candidatos ao super destaque, 6.970 posições contratadas, 176 vendas em 180 dias.

Não invente nenhum número. Se precisar de um que não esteja nos documentos, aponte a lacuna em vez de estimar.

### 4. CHANGELOG.md

Formato Keep a Changelog, com versionamento semântico. Crie a primeira entrada registrando a fundação do repositório. Estabeleça no próprio arquivo a convenção de que toda mudança em regra de decisão — elegibilidade, pesos, penalidades, cotas, ordem de relaxamento — é obrigatoriamente registrada, porque a comparação entre semanas depende de saber qual configuração produziu cada lista.

### 5. bug.md

Arquivo de registro de defeitos, com formato definido no topo. Cada entrada deve ter:

- Identificador e data
- Onde ocorreu: qual agente ou etapa
- O que se esperava e o que aconteceu
- **Se afetou alguma carga publicada**, e qual
- Se a rodada foi marcada como completa, degradada ou abortada quando o defeito ocorreu
- Situação: aberto, em correção, resolvido

O campo sobre carga publicada é o mais importante: um defeito que alterou uma vitrine que foi ao ar tem consequência diferente de um que quebrou antes da entrega.

### 6. .claude/agents/

Crie subagentes de desenvolvimento. Proponha os que fizerem sentido depois de ler os documentos, e justifique cada um em uma linha. No mínimo estes três:

- **revisor-de-regra**: compara uma implementação com a Spec, com atenção às nove regras de elegibilidade, aos dois conjuntos de pesos, às três penalidades e à ordem de relaxamento. Deve tratar divergência como erro do código.
- **investigador-de-dados**: consulta o MySQL do Newcore em leitura para validar suposições sobre campos, preenchimento e volume antes de qualquer implementação depender deles. Nunca escreve.
- **revisor-de-codigo**: revisa Python e o uso do LangGraph, com atenção especial a determinismo no caminho da decisão.

### 7. .claude/skills/

Crie skills de desenvolvimento. No mínimo:

- **consultar-newcore**: como consultar o banco com segurança, quais tabelas usar para cada pergunta, e a lista de defeitos conhecidos que invalidam campos aparentemente úteis.
- **verificar-contra-spec**: procedimento para checar uma implementação contra o documento, incluindo quais números devem bater com os valores de referência medidos.
- **registrar-bug**: como preencher uma entrada de `bug.md`.

## Invariantes

Transcreva estes sete itens no CLAUDE.md, sem alterar o sentido. Eles não podem ser violados por nenhuma implementação futura.

1. O Newcore é somente leitura. Nenhuma escrita em nenhuma tabela dele, em nenhuma circunstância.
2. Toda escrita do sistema acontece no PostgreSQL próprio.
3. Nenhum dado pessoal de lead, comprador ou corretor é enviado a modelo de linguagem. A análise de perfil recebe apenas características de imóvel, com identidades removidas antes do envio.
4. O caminho da decisão é determinístico. Elegibilidade, ranking, penalidades, alocação e relaxamento são cálculo, não julgamento de modelo. Nenhuma chamada a modelo de linguagem nesse caminho.
5. A mesma entrada, com os mesmos parâmetros, produz a mesma lista.
6. Nenhuma posição além da cota contratada é proposta: 475 super destaques e 6.495 destaques.
7. O relaxamento de regras aplica-se apenas às posições de destaque. As posições de super destaque nunca relaxam.

## O que não fazer agora

- Não escreva código de produto.
- Não crie o modelo de dados do Postgres.
- Não implemente nenhum dos sete agentes.
- Não preencha nenhum parâmetro que esteja marcado como pendente.
- Não escolha o provedor de modelo.
- Não crie subagente de desenvolvimento com o nome de um agente do produto.

## Ao terminar

Produza dois relatórios curtos, separados:

**O que foi criado**: lista dos arquivos, com uma linha sobre o propósito de cada um.

**Dúvidas e contradições**: tudo que você encontrou nos documentos que esteja ambíguo, contraditório ou faltando. Não invente resposta para lacuna — aponte. Este segundo relatório é mais importante que o primeiro, porque os documentos foram escritos em conversa e podem ter inconsistências que ninguém notou.
