---
name: verificar-contra-spec
description: Procedimento para checar uma implementação contra os documentos-fonte, incluindo quais números devem bater com os valores de referência medidos e quais não servem de conferência exata. Use ao concluir qualquer implementação de regra de decisão.
---

# Verificar contra a Spec

## Hierarquia

PRD > Spec > Ferramentas > código. Divergência entre código e documento é **bug do código** até prova em contrário. Divergência entre documentos: prevalece o superior, e a divergência é apontada (em conversa ou em `bug.md`), nunca resolvida em silêncio.

## Procedimento

1. **Localize a regra no documento.** Elegibilidade: Spec §6.1. Perfil: §6.2. Ranking e pesos: §6.3. Penalidades: §6.4. Alocação: §6.5. Relaxamento: §6.6. Rotação: §6.7. Estados e falhas: §7. Contratos entre agentes: §5.
2. **Compare literal por literal**: limiares (R$ 300.000, R$ 700.000, 10 fotos, 90 dias, 30 dias, 2 corretores, 180 dias), as cinco categorias aceitas, os pesos (60/25/15 e 80/10/10), a ordem de relaxamento (fotos → cadastro → atualização → gestor → distrito).
3. **Confira os invariantes** (CLAUDE.md): especialmente cotas como teto rígido e relaxamento restrito ao nível destaque.
4. **Confira que nenhum parâmetro pendente ganhou valor.** Os treze nulos da tabela do CLAUDE.md (quatorze itens; só o nº 1 foi resolvido, D-014) permanecem nulos. Valor inventado é erro grave, mesmo "provisório".
5. **Rode a implementação contra a base e compare com os números de referência** (abaixo).
6. Divergência encontrada: registre em `bug.md` (skill `registrar-bug`) se já houver comportamento em execução, ou corrija antes de integrar.

## Números que devem bater

Medidos em 28/08/2026 (`docs/mapa-de-dados.md`). Deriva da base é possível — divergência pequena e uniforme sugere deriva; divergência concentrada numa etapa sugere bug naquela regra.

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
