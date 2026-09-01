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

## Memoização das fontes não é thread-safe — amarrado ao parâmetro nº 4

**Data**: 2026-09-01 · **Severidade**: latente (sem corrida alcançável hoje) · **Onde**: `src/executar/sexta.py` (`_fontes`) e `src/executar/segunda.py` (`_fontes`)

Os dois runners memoizam com `if not cache: cache.append(...)`, sem trava. O `invoke` síncrono do LangGraph executa o fan-out em thread pool, então duas threads podem passar pelo teste antes de qualquer uma preencher o cache — e o Newcore seria consultado duas vezes, com as duas leituras podendo divergir.

**Por que não corrigi agora, e não é preguiça:** hoje só `no_analista_perfil` chama `coletar_vendas`, então não há corrida alcançável; o mesmo padrão já está mergeado na segunda, e consertar só a sexta cria assimetria entre os dois runners; e o gatilho real é o **retry do Orquestrador — parâmetro pendente nº 4, nulo**, que é a mesma fatia que torna vivo o problema de reexecução do nó de registro (hoje resolvido por `capturado[-1]`).

**Quando tratar**: junto da definição do parâmetro nº 4, com um `threading.Lock` nos dois runners de uma vez. Achado do `revisor-de-codigo`.
