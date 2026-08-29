# Registro de defeitos

## Formato

Cada entrada usa o modelo abaixo. O identificador é sequencial: `BUG-001`, `BUG-002`, …

O campo **Afetou carga publicada?** é o mais importante da entrada: um defeito que alterou uma vitrine que foi ao ar tem consequência diferente de um que quebrou antes da entrega. Nenhuma entrada é fechada sem esse campo respondido — se ainda não se sabe, a resposta é "em apuração", não em branco.

```markdown
## BUG-NNN — AAAA-MM-DD

- **Onde ocorreu**: <agente do produto ou etapa: Orquestrador, Coletor Interno, Coletor Externo,
  Analista de Perfil, Decisor, Redator, Monitor Operacional, Registro, entrega, infraestrutura>
- **Esperado**: <o que deveria ter acontecido>
- **Ocorrido**: <o que aconteceu>
- **Afetou carga publicada?**: <sim/não/em apuração; se sim, qual rodada e qual planilha>
- **Estado da rodada no momento**: <completa | degradada | abortada | fora de rodada>
- **Situação**: <aberto | em correção | resolvido>
```

---

<!-- Entradas abaixo desta linha, mais recente primeiro. -->
