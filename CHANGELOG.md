# Changelog

Todas as mudanças notáveis deste projeto são documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o versionamento segue [Semantic Versioning](https://semver.org/lang/pt-BR/).

## Convenção obrigatória deste projeto

**Toda mudança em regra de decisão — elegibilidade, pesos, penalidades, cotas, ordem de relaxamento — é obrigatoriamente registrada aqui.** A comparação entre semanas depende de saber qual configuração produziu cada lista; uma mudança de regra sem registro torna duas rodadas incomparáveis sem que ninguém saiba. O registro aqui complementa, não substitui, a entidade `alteracao_parametro` do Registro.

## [Unreleased]

### Added

- `src/dados/registro/001_registro.sql`: modelo de dados do Registro — as 8 entidades da Spec §2.1 em esquema `registro` (rodada, parametros_da_rodada, perfil_da_rodada, decisao_imovel, relaxamento, janela_destaque, resultado_carga, alteracao_parametro). D-001 aplicada (aprovação tácita como carimbo de estado na rodada; nada modela leitura de volta da planilha). Parâmetros pendentes preservados nulos: sem TTL/expurgo (retenção, nº 9) e sem prazo em DEFAULT/CHECK (aprovação tácita, nº 10). Imóveis excluídos não são guardados, conforme decisão explícita da Spec.

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
