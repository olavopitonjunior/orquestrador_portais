# Registro de Decisões

Resoluções do dono da decisão (Olavo) para divergências e lacunas encontradas nos documentos-fonte. Cada decisão vale a partir da data registrada e prevalece sobre o trecho divergente dos documentos até que uma revisão deles a incorpore. Contexto completo das contradições: relatório de fundação de 2026-08-29.

---

## D-001 — Fonte de leitura da segunda-feira: o Registro, não a planilha

**Data**: 2026-08-29 · **Resolve**: contradição C3 (Spec §2 vs. Ferramentas §3 vs. Spec §5/§7.3)

O gestor da vitrine **não edita a planilha de decisão: apenas a aplica** manualmente no portal. Consequências:

- O **Registro é a fonte da verdade** do sistema. A rodada de segunda identifica os imóveis em posição paga lendo o Registro (rodada de decisão correspondente), nunca a planilha do Drive.
- Não existe passo de leitura de volta da planilha. A frase de Ferramentas §3 ("a planilha é entrada e saída... o sistema a lê de volta na segunda") fica **sem efeito**; prevalece a Spec §2.
- Onde a Spec diz "planilha aprovada vigente" (insumo do Monitor, §5; condição do relatório, §7.3), leia-se: **a lista da rodada de decisão registrada, com aprovação tácita confirmada por prazo**. A regra de abortar o relatório na ausência dela permanece.
- A aprovação tácita vira um carimbo de estado na rodada (aprovada em <momento>, por prazo), sem verificação de conteúdo.

**Risco aceito** (já catalogado em Ferramentas §5): se o gestor um dia alterar a planilha antes de aplicar, o Registro medirá contra uma lista que não foi a aplicada. A premissa "não edita, só aplica" é comportamental; se ela mudar, esta decisão deve ser revista antes de qualquer outra coisa.

## D-002 — O piso de R$ 700.000 é condição de nível, não regra eliminatória

**Data**: 2026-08-29 · **Resolve**: contradição C4 (Spec §6.1 vs. §6.5 e o funil medido)

A elegibilidade tem **oito regras binárias gerais**: status ativo, categoria, preço geral ≥ R$ 300.000, fotos ≥ 10, atualização em 90 dias, cadastro completo, gestor produtivo, capacidade do distrito. O piso de R$ 700.000 é **condição de candidatura ao super destaque**, aplicada na alocação (Spec §6.5), e não exclui ninguém do nível destaque. O funil medido confirma: 10.290 elegíveis, 4.852 acima do piso.

Onde os documentos disserem "nove regras", leia-se "oito regras gerais + piso de nível".

## D-003 — Status impeditivo é regra de saída imediata, não de elegibilidade

**Data**: 2026-08-29 · **Resolve**: contradição C5 (tabela do Estágio 1 do PRD vs. glossário do PRD e Spec §6.7)

"Vendido, reservado ou removido" (e alteração relevante de preço) são gatilhos de **saída imediata fora do ciclo** (rotação, Spec §6.7), não uma décima regra de elegibilidade. A décima linha da tabela do Estágio 1 do PRD deve ser lida nesse papel.

## D-004 — Lista única de ONZE parâmetros pendentes

**Data**: 2026-08-29 · **Resolve**: contradição C2 (Spec §8 vs. Ferramentas §6 vs. tabela de parâmetros do PRD)

A lista canônica de parâmetros sem valor consolida os nove bullets comuns mais os dois que aparecem em apenas um documento. São **onze**, mantidos no CLAUDE.md, todos nulos até definição:

1. Evidência mínima por combinação de perfil
2. Forma de normalização de cada fator do ranking
3. Intensidade das três penalidades e decaimento da penalidade por janela
4. Tentativas e intervalo de repetição do Orquestrador
5. Idade máxima aceitável da coleta externa de reserva
6. Limiar de variação de volume que dispara sinalização
7. Limiar mínimo de taxa de amarração
8. Horários exatos de execução na sexta e na segunda
9. Política de retenção do Registro
10. Prazo da aprovação tácita (só constava em Ferramentas §6)
11. Prazo de atendimento de lead e limite de inatividade (só constava na tabela do PRD)

## D-005 — Ganhos de relaxamento são ordem de grandeza, não conferência

**Data**: 2026-08-29 · **Resolve**: contradição C1 (PRD "Custo de cada regra" vs. Spec §6.6)

Os valores +133 / +569 / +1.680 / +1.747 / +5.686 foram medidos com mínimo de **três** corretores por distrito; o parâmetro adotado é **dois**. Prevalece a ressalva do PRD: são referência de ordem de grandeza e **nunca** entram em teste como valor exato. Já refletido em `docs/mapa-de-dados.md` e na skill `verificar-contra-spec`.

## D-006 — O modelo do Redator só vê agregados

**Data**: 2026-08-29 · **Resolve**: tensão entre o invariante 3 e o relatório de segunda

O relatório de segunda carrega dado pessoal (identificador de lead, corretor gestor, gestor de distrito) e o Redator é um dos três agentes com modelo. Fronteira dura de implementação: a chamada de modelo do Redator recebe **exclusivamente os números agregados do resumo da rodada** (contagens, percentuais, estado). Todas as abas com linhas nominais são geradas por template, sem passar por modelo. O subagente `auditor-de-invariantes` verifica essa fronteira.
