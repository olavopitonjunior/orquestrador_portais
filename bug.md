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

## O espelho lido pela coleta interna está defasado — a sexta pode propor imóvel já removido

**Data**: 2026-09-02 · **Severidade**: alta (gasta posição contratada) · **Onde**: Coletor Interno — `src/dados/coletor_interno.py`, a coluna `publicacao_ativa` e o `WHERE` de `_SQL_CANDIDATOS` (âncora textual de propósito: número de linha dessincroniza)

- **Esperado**: o universo de candidatos da sexta contém apenas imóveis efetivamente anunciáveis no momento da rodada.
- **Ocorrido**: contém imóveis já removidos ou já vendidos, por **duas causas medidas** em 2026-09-02.
- **Afetou carga publicada?**: **em apuração.** O mecanismo está presente hoje e nada indica que tenha começado agora; não foi verificado contra as cargas já aplicadas. Responder isto exige cruzar as decisões gravadas em `registro.decisao_imovel` com o histórico de status — não feito nesta fatia.
- **Estado da rodada no momento**: fora de rodada (medição direta no banco, somente leitura).
- **Situação**: **causa 1 resolvida** (a regra de status passa a ver o transacional); **causa 2 aberta**, contingente à [P-20].

**Causa 1 — o espelho atrasa (defeito sob qualquer leitura). RESOLVIDA em 02/09/2026.** A coleta lê `newcore_bi.FT_RealtyRelation`, mantido incrementalmente. Das 82 remoções (`Ativo → Removido`) das últimas 24 h, **70 ainda constavam `Ativo` no espelho — 85,4%**. Como sinal separado de defasagem corrente, `MAX(RealtyUpdate)` marcava 07:30 contra `MAX(realties.UpdatedAt)` às 18:38 do mesmo dia; são 11 h, e quem sustenta o "mais de 24 h" é o 70 de 82, não esse par.

**Causa 2 — a venda não move o status (contingente à [P-20]).** `FT_RealtyRelation.RealtyStatus` é binário (`Ativo` 48.881 / `Removido` 356.172): não existe "Vendido" nem "Reservado". **24,69% (40 de 162) dos imóveis distintos com venda assinada em 180 dias seguem `Ativo`.** Esta causa **deixa de ser defeito** sob a leitura 3 da [P-20] ("a saída é tratada fora do sistema"); a causa 1 é defeito em qualquer leitura.

**Por que não corrigi nesta fatia:** corrigir muda o universo de candidatos — cruzar com `newcore.realties`/`realtystatushistory_new` é **mudança em regra de decisão**, com CHANGELOG e revisão próprios. Registrado em `docs/decisoes.md` (seção da rotação) e aqui, porque é comportamento em execução e não divergência entre documentos.

**Como a causa 1 foi resolvida:** a coluna `publicacao_ativa` da coleta passou a exigir as duas fontes — `(f.RealtyStatus = 'Ativo' AND COALESCE(r.PublishStatus_Id, 0) = 1)` —, mantendo o `WHERE` no espelho. O imóvel defasado **entra** como candidato e **reprova** em `Regra.STATUS_ATIVO`, com motivo registrado na aba de excluídos, em vez de sumir do universo sem deixar linha. Não volta por relaxamento: status não é regra relaxável. Medido em 02/09: reprova **86** imóveis (0,176% do recorte), todos `Removido` e todos saídos do ar nas últimas 24 h; efeito no funil de **−12 elegíveis e −2 candidatos ao super** na definição de distrito adotada (`PRODUTIVOS`).

**O que a correção NÃO faz, declarado:** o caminho inverso segue descoberto — **54** imóveis publicados que o espelho ainda não viu (51 criados nas últimas 24 h, 44 com preço ≥ R$ 300.000) continuam invisíveis, porque sem linha no espelho não há distrito nem gestor para avaliar, e é o espelho que define quem é candidato. Não gasta posição paga — é oportunidade perdida, não desperdício —, mas é a mesma defasagem do espelho (~13,5 h na medição das 21:00; o parágrafo da causa 1 cita outro instante do mesmo dia). **Fatia própria.**

**Causa 2** segue aberta e depende da [P-20]. Achado do levantamento da fatia da rotação.

## Memoização das fontes não é thread-safe — amarrado ao parâmetro nº 4

**Data**: 2026-09-01 · **Severidade**: latente (sem corrida alcançável hoje) · **Onde**: `src/executar/sexta.py` (`_fontes`) e `src/executar/segunda.py` (`_fontes`)

Os dois runners memoizam com `if not cache: cache.append(...)`, sem trava. O `invoke` síncrono do LangGraph executa o fan-out em thread pool, então duas threads podem passar pelo teste antes de qualquer uma preencher o cache — e o Newcore seria consultado duas vezes, com as duas leituras podendo divergir.

**Por que não corrigi agora, e não é preguiça:** hoje só `no_analista_perfil` chama `coletar_vendas`, então não há corrida alcançável; o mesmo padrão já está mergeado na segunda, e consertar só a sexta cria assimetria entre os dois runners; e o gatilho real é o **retry do Orquestrador — parâmetro pendente nº 4, nulo**, que é a mesma fatia que torna vivo o problema de reexecução do nó de registro (hoje resolvido por `capturado[-1]`).

**Quando tratar**: junto da definição do parâmetro nº 4, com um `threading.Lock` nos dois runners de uma vez. Achado do `revisor-de-codigo`.
