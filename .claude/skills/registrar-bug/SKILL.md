---
name: registrar-bug
description: Como preencher uma entrada de bug.md. Use sempre que um defeito for encontrado em qualquer agente ou etapa do sistema.
---

# Registrar um bug

As entradas vivem em `bug.md`, na raiz, mais recente primeiro, com identificador sequencial `BUG-NNN`.

## Modelo

```markdown
## BUG-NNN — AAAA-MM-DD

- **Onde ocorreu**: <agente ou etapa>
- **Esperado**: <o que deveria ter acontecido>
- **Ocorrido**: <o que aconteceu>
- **Afetou carga publicada?**: <sim/não/em apuração; se sim, qual rodada e qual planilha>
- **Estado da rodada no momento**: <completa | degradada | abortada | fora de rodada>
- **Situação**: <aberto | em correção | resolvido>
```

## Como preencher

- **Onde ocorreu**: um dos sete agentes do produto (Orquestrador, Coletor Interno, Coletor Externo, Analista de Perfil, Decisor, Redator, Monitor Operacional), o Registro, a entrega, ou infraestrutura. Seja específico: "Decisor, etapa de alocação" é melhor que "Decisor".
- **Esperado / Ocorrido**: cite o documento que define o esperado (ex.: "Spec §6.5: nenhuma posição excedente") e o fato observado, com números.
- **Afetou carga publicada?** — **o campo mais importante.** Determine ANTES de fechar a entrada:
  - O defeito ocorreu numa rodada de decisão cuja planilha foi aprovada (inclusive por prazo, tacitamente) e aplicada? Então **sim** — identifique a rodada e a planilha. Um defeito que alterou uma vitrine que foi ao ar tem consequência diferente de um que quebrou antes da entrega: pode exigir correção da carga e invalida a comparação da segunda-feira.
  - Quebrou antes da entrega, ou fora de rodada? Então **não**.
  - Ainda não se sabe? **"em apuração"** — nunca em branco, e a entrada não pode ir a "resolvido" enquanto estiver assim.
- **Estado da rodada no momento**: completa, degradada ou abortada (Spec §7.2), ou "fora de rodada". Um defeito durante rodada degradada importa: a degradação pode ser causa ou máscara do defeito.
- **Situação**: aberto → em correção → resolvido. Ao resolver, anote na entrada o que corrigiu e, se a correção mudou regra de decisão, registre também no `CHANGELOG.md`.
