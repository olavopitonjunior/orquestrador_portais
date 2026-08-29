# Definição de Ferramentas: Curadoria Orquestrada da Vitrine de Destaques

**Versão**: 1.0
**Data**: 2026-08-28
**Documentos de origem**: PRD versão 5.0, Spec funcional versão 1.0
**Escopo**: escolhas de tecnologia, o que cada uma resolve, o que elas custam em operação e o que permanece em aberto.

---

## 1. Princípio que orientou as escolhas

Uma constatação feita ao escrever a spec determinou tudo o que vem abaixo: **apenas um dos sete agentes precisa de inteligência artificial.**

| Agente | Natureza | Usa modelo de linguagem |
|---|---|---|
| Orquestrador | Controle de fluxo | Não |
| Coletor Interno | Consulta ao banco | Não |
| Coletor Externo | Navegação em portal instável | Sim, no caminho de erro |
| Analista de Perfil | Estatística sobre 176 vendas | Sim, para interpretar |
| Decisor | Nove regras e soma ponderada | Não, e não deve |
| Redator | Geração de planilha | Sim, apenas no resumo da rodada |
| Monitor Operacional | Duas consultas ao banco | Não |

Dois agentes ficam explicitamente sem modelo por decisão de projeto, não por economia. O Decisor precisa dar a mesma resposta para a mesma entrada, porque a decisão tem que ser reproduzível e explicável. O Analista precisa ser capaz de dizer que não há evidência suficiente, e modelo de linguagem é bom justamente em encontrar padrão onde não há.

A arquitetura de sete agentes com isolamento de falha continua valendo. O que muda é que a maior parte dela é código convencional dentro de uma estrutura de orquestração, não uma frota de agentes autônomos.

---

## 2. Escolhas fechadas

| Camada | Escolha | O que resolve |
|---|---|---|
| Orquestração | LangGraph | Estado explícito, etapas com critério de pronto, repetição antes de desistir, estados completa, degradada e abortada, e pausa para aprovação humana |
| Linguagem | Python | Decorrência do LangGraph |
| Persistência | Um único PostgreSQL | Serve o estado do grafo e as oito entidades do Registro, em esquemas separados. Uma peça para provisionar, monitorar e fazer backup |
| Leitura do Newcore | Conexão direta ao MySQL | Os nós de código consultam diretamente. O MCP de MySQL permanece disponível para exploração fora da rodada, não dentro dela |
| Raspagem | Uma base de automação de navegador, com dois caminhos | Caminho determinístico por seletores tenta primeiro; quando falha, o modelo assume interpretando a página. Mesma sessão autenticada nos dois |
| Modelo de linguagem | Um provedor comercial por API | Critério de escolha: qualidade em visão e navegação, porque é a tarefa que decide. Perfil e resumo usam o mesmo |
| Observabilidade | Painel sobre o Registro, mais rastreio mínimo do agente com IA | O Registro já guarda estado da rodada, situação de cada etapa, tentativas e motivo de degradação |
| Agendamento | Agendador do sistema operacional | Chama o grafo nos horários de sexta e segunda. Nenhuma dependência adicional |
| Entregáveis | Planilha do Google no Drive, com link por e-mail | Permite filtrar e comentar sem baixar, o que importa numa aba de quase sete mil linhas |
| Acesso ao Google | Autorização na conta do gestor da vitrine | O sistema age em nome dele |
| Sessão do Canal Pro | Login automatizado a cada rodada | Dispensa intervenção semanal |
| Hospedagem | Máquina física do gestor da vitrine | Custo fixo e controle total |

### Por que LangGraph, e não outra coisa

A spec descreve uma máquina de estados: etapas que precisam ficar prontas, repetição controlada, três estados finais de rodada e uma pausa para aprovação que pode durar horas ou dias. O LangGraph existe para esse formato, com estado explícito e persistência.

O checkpointer não é detalhe de implementação: é o que permite a rodada de sexta pausar para aprovação e retomar depois. Sem estado persistido, essa interrupção não sobrevive.

Nós de LangGraph não precisam ser modelos de linguagem — podem ser funções comuns. É isso que permite os seis agentes determinísticos existirem dentro da mesma estrutura sem custo de inteligência artificial.

### Por que o Hermes ficou fora

O Hermes Agent, da Nous Research, é um agente pronto e não um framework: assistente autônomo auto-hospedado, com memória persistente entre sessões, geração automática de skills, integrações de mensageria, cron próprio e automação de navegador.

As qualidades que o definem são incompatíveis com o requisito central deste sistema. Autonomia, memória que evolui e skills que ele mesmo reescreve tornam a decisão irreprodutível. Este produto precisa que a mesma entrada gere a mesma lista, e que qualquer semana passada possa ser explicada.

Isso não é julgamento sobre o Hermes, apenas sobre o encaixe. Ele permanece candidato para outros problemas da operação.

---

## 3. Regras de desenho que decorrem das escolhas

**Nenhum dado pessoal sai para modelo de linguagem.** Nomes e telefones de leads e compradores vivem no Monitor Operacional, que é consulta pura ao banco. A análise de perfil recebe apenas características de imóvel, com identidades removidas antes do envio. A raspagem processa páginas de anúncio. O resumo processa números agregados.

**O Newcore permanece somente leitura.** Toda escrita acontece no Postgres próprio. O sistema não grava em nenhuma tabela de produção.

**A decisão é determinística.** Elegibilidade, ranking, penalidades, alocação e relaxamento são cálculo, não julgamento de modelo.

**A planilha é entrada e saída.** O sistema a gera na sexta e a lê de volta na segunda, para saber o que estava em vitrine. Isso decorre da aprovação registrada na própria planilha.

---

## 4. Fluxo de aprovação

A aprovação é **tácita por prazo**: se a planilha não for alterada até um horário definido, ela é considerada aprovada como saiu.

Isso não publica nada. A carga continua sendo aplicada manualmente por uma pessoa. O prazo apenas registra o aceite para efeito de Registro e para que a rodada de segunda saiba contra qual lista medir.

---

## 5. Custos operacionais desta configuração

Escolhas conscientes que trazem ônus. Registradas para não serem redescobertas como surpresa.

| Escolha | Ônus assumido |
|---|---|
| Máquina física, com conferência manual | Se o equipamento estiver desligado ou sem rede na sexta, a rodada não acontece e ninguém é avisado. Depende de você notar a ausência da planilha |
| Login automatizado no portal | Exige credenciais armazenadas na máquina. Portal com instabilidade costuma ter proteção contra automação, e login semanal repetido é o padrão que essas proteções procuram |
| Aprovação tácita mais ausência de verificação da carga | Dois riscos que se somam: o Registro pode afirmar aprovação não dada, e a rodada de segunda pode medir contra uma lista que não foi a aplicada |
| Autorização na conta pessoal | O acesso ao Drive e ao e-mail quebra se a conta mudar de senha ou sair da organização. Uma conta de serviço não teria esse vínculo |
| Operação por uma única pessoa | Não há segunda pessoa capaz de destravar o sistema. Ponto único de falha humana |
| Observabilidade reduzida ao essencial | Custo por execução, latência e versão de prompt do agente com IA ficam com visibilidade limitada |

Nenhum desses ônus é impeditivo. Todos são reversíveis: migrar para servidor em nuvem, trocar por conta de serviço, adicionar aviso externo de ausência e ampliar observabilidade são mudanças posteriores que não exigem redesenho.

---

## 6. Pendências

**Escolha ainda aberta**

- Provedor específico do modelo. O critério está definido: qualidade em navegação por visão, que é a tarefa determinante. A comparação deve ser feita contra o portal real, não em benchmark genérico.

**Parâmetros sem valor, herdados da spec**

- Evidência mínima por combinação de perfil.
- Forma de normalização de cada fator do ranking.
- Intensidade das três penalidades e decaimento da penalidade por janela.
- Tentativas e intervalo de repetição do Orquestrador.
- Idade máxima aceitável da coleta externa de reserva.
- Limiar de variação de volume que dispara sinalização.
- Limiar mínimo de taxa de amarração.
- Horários exatos de execução na sexta e na segunda, e prazo da aprovação tácita.
- Política de retenção do Registro.

**Investigações abertas, que podem alterar regras já definidas**

- Por que cerca de 44% do estoque elegível não possui avaliação por categoria registrada.
- Se a tabela de relatórios da raspagem, com 43 registros, todos com erro e todos de dezembro de 2025, ainda é usada por alguma coisa.
- Se quem aplica a carga localiza o imóvel apenas pelo identificador interno ou depende de outra referência.
- Confirmação da localização do campo de vagas, hoje ausente da tabela principal de imóveis.

---

## 7. O que este documento não define

- Modelo de dados físico do Postgres.
- Estrutura do código e organização do repositório.
- Estratégia de testes.
- Forma de instalação e atualização na máquina.
- Plano de construção e ordem das entregas.

---

*Documento derivado do PRD versão 5.0 e da Spec funcional versão 1.0, com escolhas tomadas em conversa e verificação atualizada das ferramentas em 28 de agosto de 2026.*
