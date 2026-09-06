---
name: verificar-contra-spec
description: Procedimento para checar uma implementação contra os documentos-fonte, incluindo quais números devem bater com os valores de referência medidos e quais não servem de conferência exata. Use ao concluir qualquer implementação de regra de decisão.
---

# Verificar contra a Spec

## Hierarquia

PRD > Spec > Ferramentas > código. Divergência entre código e documento é **bug do código** até prova em contrário. Divergência entre documentos: prevalece o superior, e a divergência é apontada (em conversa ou em `bug.md`), nunca resolvida em silêncio.

## Procedimento

1. **Localize a regra no documento.** Elegibilidade (nove regras, o perfil incluído): Spec §6.1. Perfil: §6.2. Ranking (a nota do portal): §6.3. Descontos: §6.4. Alocação: §6.5. Relaxamento: §6.6. Rotação: §6.7. Estados e falhas: §7. Contratos entre agentes: §5.
2. **Compare literal por literal**: limiares (R$ 300.000, R$ 700.000, 10 fotos, 90 dias, 30 dias, 2 corretores, 180 dias), as cinco categorias aceitas, os pesos do portal em pontos de 100 (adotados 70/30/0, Spec §6.3 revisada em 2026-09-05, D-028/D-034), os descontos em pontos de 100 (20/5/10, perdão 50 % por carga, §6.4), a ordem de relaxamento (perfil de conversão → fotos → cadastro → atualização → gestor → distrito, D-027) e a trava do login no degrau do gestor (D-029).
3. **Confira os invariantes** (CLAUDE.md): especialmente cotas como teto rígido e relaxamento restrito ao nível destaque.
4. **Confira que nenhum parâmetro pendente ganhou valor.** Os nove nulos da tabela do CLAUDE.md permanecem nulos (resolvidos: nº 1 pela D-014; nº 3, 5 e 7 pela D-034; nº 12 e 13 deixaram de existir, D-031). Os adotados vivem só em `src/config/adotados.py`, com procedência. Valor inventado é erro grave, mesmo "provisório".
5. **Rode a implementação contra a base e compare com os números de referência**:
   `uv run python -m executar.referencias`. A ferramenta reaproveita o coletor e as
   regras do próprio sistema (nunca reimplementa o funil), lê os valores publicados do
   `docs/mapa-de-dados.md` (não guarda cópia) e aplica o diagnóstico abaixo. Ela **não
   altera número nenhum**; `--registrar` anexa o resultado datado ao mapa.
6. Divergência encontrada: registre em `bug.md` (skill `registrar-bug`) se já houver comportamento em execução, ou corrija antes de integrar.

## Números que devem bater

Medidos pelo PIPELINE em 06/09/2026 (`docs/mapa-de-dados.md`, seção "O funil pelo pipeline"). Deriva da base é possível — divergência pequena e uniforme sugere deriva; divergência concentrada numa etapa sugere bug naquela regra.

**Cuidado com esta última leitura:** "sugere" não é "prova". A etapa pode concentrar a diferença porque o INSUMO dela mudou, e não porque a regra quebrou — foi exatamente o caso das duas regras de corretor entre 28/08 e 06/09/2026: nada mudou nos predicados, e a atividade é que caiu — distritos com dois ou mais corretores produtivos foram de 61 para 46, e 21,4 % dos imóveis ativos estão hoje em distrito sem nenhum. Confira a passagem por regra que a ferramenta imprime antes de concluir que há defeito.

| Conferência | Valor | Tolerância |
|---|---|---|
| Funil: recorte ativo lido | 48.812 | ±1 % (o estoque se move) |
| Funil: nas cinco categorias | 41.312 | ±1 % |
| Funil: preço ≥ R$ 300.000 | 35.451 | ±1 % |
| Elegíveis, **oito degraus** (sem o perfil) | 8.197 | ±5 % |
| Elegíveis, **nove degraus** (com o perfil, D-027) | 6.854 | ±5 % |
| Candidatos ao super destaque (oito degraus) | 3.732 | ±5 % |
| Vendas assinadas em 180 dias (entrada do perfil) | 186 | ±10 % |
| Cotas — **exatas sempre, são contratuais** | 475 e 6.495 (total 6.970) | zero |

As três primeiras linhas são conferência dura: dependem só do estoque, mediram 0,3 a 0,4 % de diferença em nove dias, e divergência ali é defeito. As de baixo dependem de atividade de corretor nos últimos 30 dias e **mexem quando o mart de BI é reconstruído** — 155 imóveis, 2,2 %, entre 05/09 23h52 e 06/09 08h35. Número fora da tolerância pede remedição antes de acusar o código; a prévia do console dá o número do dia.

## Números que NÃO servem de conferência exata

- **Ganhos de relaxamento** (+133 fotos, +569 cadastro, +1.680 atualização, +1.747 gestor, +5.686 distrito): medidos com mínimo de **três** corretores por distrito; o parâmetro adotado é **dois**. Ordem de grandeza apenas — o PRD é explícito nisso, a Spec §6.6 omite a ressalva (o PRD prevalece).
- **Estatísticas históricas** (88% de janelas sem lead, 0,21 lead/janela, 33 dias de duração média): descrevem o problema, não são alvo de teste.
- **Os números de 28/08/2026** (10.290 elegíveis, 4.852 candidatos ao super, folga de 48 %, 10,2 por vaga): **a base mudou desde então** — distritos com dois ou mais corretores produtivos caíram de 61 para 46, e o universo elegível a um patamar 20 % menor. Continuam reprodutíveis como instante daquele dia, mas não conferem a implementação de hoje. A única mudança de predicado no período está medida e é pequena (`fe8a7c0`: −12 elegíveis). O PRD e a Spec ainda os publicam, com a ressalva de deriva datada (D-035).
