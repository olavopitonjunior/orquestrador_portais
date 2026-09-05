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

Medidos em 28/08/2026 (`docs/mapa-de-dados.md`). Deriva da base é possível — divergência pequena e uniforme sugere deriva; divergência concentrada numa etapa sugere bug naquela regra.

**Cuidado com esta última leitura:** "sugere" não é "prova". A etapa pode concentrar a diferença porque o INSUMO dela mudou, e não porque a regra quebrou — foi o que a conferência de 02/09/2026 encontrou (ver o aviso no topo dos números de referência do mapa). Confira a passagem por regra que a ferramenta imprime antes de concluir que há defeito.

| Conferência | Valor |
|---|---|
| Funil: ativos | 48.964 |
| Funil: nas cinco categorias | 41.478 |
| Funil: preço ≥ R$ 300.000 | 35.560 |
| Elegíveis ao final | 10.290 |
| Candidatos ao super destaque | 4.852 |
| Vendas assinadas em 180 dias (entrada do perfil) | 176 |
| Cotas — **exatas sempre, são contratuais** | 475 e 6.495 (total 6.970) |

## Números que NÃO servem de conferência exata

- **Ganhos de relaxamento** (+133 fotos, +569 cadastro, +1.680 atualização, +1.747 gestor, +5.686 distrito): medidos com mínimo de **três** corretores por distrito; o parâmetro adotado é **dois**. Ordem de grandeza apenas — o PRD é explícito nisso, a Spec §6.6 omite a ressalva (o PRD prevalece).
- **Estatísticas históricas** (88% de janelas sem lead, 0,21 lead/janela, 33 dias de duração média): descrevem o problema, não são alvo de teste.
