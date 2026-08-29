# Changelog

Todas as mudanças notáveis deste projeto são documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o versionamento segue [Semantic Versioning](https://semver.org/lang/pt-BR/).

## Convenção obrigatória deste projeto

**Toda mudança em regra de decisão — elegibilidade, pesos, penalidades, cotas, ordem de relaxamento — é obrigatoriamente registrada aqui.** A comparação entre semanas depende de saber qual configuração produziu cada lista; uma mudança de regra sem registro torna duas rodadas incomparáveis sem que ninguém saiba. O registro aqui complementa, não substitui, a entidade `alteracao_parametro` do Registro.

## [Unreleased]

### Added

- `src/dominio/ranking.py`: nota final por nível (Spec §6.3) como cálculo puro — os dois conjuntos de pesos DEFINIDOS como constantes validadas (60/25/15 super destaque, 80/10/10 destaque; soma 100 obrigatória, inteiros não negativos — a fronteira vale para a futura rehidratação via alteracao_parametro) e a soma ponderada literal menos o desconto de penalidades. A forma de normalização dos fatores (parâmetro pendente nº 2 da D-004) fica fora do módulo: fatores chegam já normalizados e só a finitude é validada — faixa nasce com a normalização, quando o dono a definir. Capacidade de distrito não participa do ranking (PRD: o distrito já atua como regra eliminatória). Leitura estrutural declarada: soma ponderada sem divisão pelo total (constante absorvida pela calibração dos nº 2 e nº 3); contrato de desempate determinístico declarado para a alocação. 26 testes, incluindo integração com `dominio.penalidades`.
- `docs/decisoes.md` D-008 (regra de decisão): a nota ponderada de cada nível é a operacionalização do objetivo daquele nível e é a chave de ordenação da alocação — resolve a ambiguidade entre Spec §6.3 e §6.5. Ratificada pelo dono em 29/08/2026.

- `src/dominio/penalidades.py`: as três penalidades da Spec §6.4 como predicados puros — janela anterior sem resultado, sem avaliação por categoria (ausência TOTAL; a assimetria do parcial segue registrada na D-007), sem lead em 180 dias — e o desconto da nota com intensidades e decaimento **injetados como argumentos obrigatórios, sem default** (parâmetro pendente nº 3 da D-004 permanece nulo; `src/config/` segue sem código). Caso explícito da Spec coberto: imóvel sem histórico de destaque não é penalizado por ausência de histórico. Leituras estruturais declaradas: o julgamento "atingiu o resultado esperado para o nível" chega pré-calculado na entrada, porque nenhum documento o quantifica (pendência apontada ao dono da decisão); a penalidade por janela aplica-se uma vez, dirigida pela janela sem resultado mais recente; o fator de decaimento é contratualmente limitado a [0, 1] ("decai" nunca amplifica nem vira bônus) e as intensidades exigem valor finito e não negativo — intensidade negativa converteria penalidade em bônus e NaN quebraria a ordenação total do ranking. 30 testes.

- `docs/decisoes.md` D-007 (regra de decisão): na regra de cadastro completo, apenas zero explícito reprova; categoria ausente não é zero. Ratificada pelo dono com fundamento empírico — sob a leitura estrita, zero imóveis avaliados passariam e o funil medido do PRD seria impossível. Assimetria do parcial sem penalidade registrada como calibração futura (parâmetro nº 3).

- `src/dominio/elegibilidade.py`: as oito regras eliminatórias gerais como funções puras e determinísticas (D-002/D-003 — o piso de R$ 700.000 é função separada de candidatura ao super destaque, consumida na alocação; status impeditivo fica na rotação), a ordem de cedência do relaxamento (Spec §6.6) e `elegivel_com_relaxamento` que rejeita cedência de regra não relaxável. Limiares conforme parâmetros definidos: R$ 300.000, 10 fotos, 90 dias, 30 dias, 2 corretores. Leitura registrada para avaliação parcial por categoria: apenas zero explícito reprova cadastro completo; categoria ausente não é zero (imóvel sem avaliação alguma passa e recebe penalidade, Spec §6.1). 28 testes com valores-limite, contratos explícitos (caixa/acento de categoria, data futura documentada, mensagem de erro determinística) e verificação de determinismo. Contrato de `ImovelCandidato`: instâncias não são hasháveis (deduplicar por `imovel_id`) e o mapping de notas é copiado na construção — mutação externa não vaza.
- Scaffolding Python: `mise.toml` (Python 3.12), `pyproject.toml` (uv; pytest e ruff como dev; sem dependência de runtime — o domínio é stdlib puro por desenho) e `uv.lock`.

- `src/dados/registro/001_registro.sql`: modelo de dados do Registro — as 8 entidades da Spec §2.1 em esquema `registro` (rodada, parametros_da_rodada, perfil_da_rodada, decisao_imovel, relaxamento, janela_destaque, resultado_carga, alteracao_parametro). D-001 aplicada (aprovação tácita como carimbo de estado na rodada; nada modela leitura de volta da planilha). Parâmetros pendentes preservados nulos: sem TTL/expurgo (retenção, nº 9) e sem prazo em DEFAULT/CHECK (aprovação tácita, nº 10). Imóveis excluídos não são guardados, conforme decisão explícita da Spec. O esquema impõe os invariantes 6 e 7: CHECK de faixa por nível (1–475 super destaque, 1–6.495 destaque) que, com o UNIQUE (rodada, nível, posição), limita a contagem à cota contratada sem trigger — se o contrato OLX mudar, as cotas exigem ALTER TABLE; e CHECK que impede `regra_relaxada` em super destaque. Sem `modo_aprovacao`: nenhum documento define aprovação explícita (D-001, Ferramentas §4), restando `aprovada_em` só na rodada de decisão.

- `docs/decisoes.md`: registro das resoluções do dono da decisão (D-001 a D-006) para as contradições encontradas na fundação — fonte de leitura da segunda-feira é o Registro e não a planilha (o gestor não edita, só aplica); piso de R$ 700.000 como condição de nível; status impeditivo como regra de saída; lista consolidada de onze parâmetros pendentes; ganhos de relaxamento como ordem de grandeza; modelo do Redator restrito a agregados.

- Fundação do repositório: estrutura de pastas (`src/grafo`, `src/dominio`, `src/dados`, `src/entrega`, `src/config`, `tests`), sem código de produto.
- `CLAUDE.md` com projeto, cadência, stack, os sete invariantes, hierarquia dos documentos, glossário e os nove parâmetros pendentes (todos nulos).
- `docs/` com os três documentos-fonte (PRD 5.0, Spec 1.0, Ferramentas 1.0) movidos da raiz, e `docs/mapa-de-dados.md` derivado da base factual do PRD.
- `bug.md` com formato de registro de defeitos.
- Subagentes de desenvolvimento em `.claude/agents/`: `revisor-de-regra`, `investigador-de-dados`, `revisor-de-codigo`, `auditor-de-invariantes`, `conferente-de-numeros`.
- Skills de desenvolvimento em `.claude/skills/`: `consultar-newcore`, `verificar-contra-spec`, `registrar-bug`.
- `.gitignore` e `.env.tmpl` (segredos via 1Password, `op://Personal/orquestrador_portais/<VAR>`).

### Changed

- `docs/mapa-de-dados.md` atualizado com as medições de 29/08/2026 que encerraram três das quatro investigações abertas: causa dos ~44% sem avaliação por categoria (pipeline de `realty_score_category_score` morto desde 16/10/2025 — a penalidade atingirá sistematicamente o estoque novo); tabela de relatórios da raspagem identificada (`webscraping_report_grupo_zap`, abandonada); **defeito 5 corrigido** — vagas existe em `realties.QtyVacancies` (96,1% com vaga >0, 0,4% nulo no recorte elegível). A quarta investigação (referência usada por quem aplica a carga) segue aberta como pergunta de processo. Skill `consultar-newcore` e agente `investigador-de-dados` alinhados.
- **Regra de decisão (interpretação)**: elegibilidade passa a ser lida como oito regras gerais + piso de nível do super destaque + gatilho de saída imediata (D-002/D-003). Nenhum limiar mudou de valor; mudou a estrutura de aplicação. Refletido em `CLAUDE.md` e no subagente `revisor-de-regra`.
- `CLAUDE.md`: lista de parâmetros pendentes consolidada de nove para onze (D-004); hierarquia de documentos passa a incluir `docs/decisoes.md`.
