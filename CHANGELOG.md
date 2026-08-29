# Changelog

Todas as mudanças notáveis deste projeto são documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o versionamento segue [Semantic Versioning](https://semver.org/lang/pt-BR/).

## Convenção obrigatória deste projeto

**Toda mudança em regra de decisão — elegibilidade, pesos, penalidades, cotas, ordem de relaxamento — é obrigatoriamente registrada aqui.** A comparação entre semanas depende de saber qual configuração produziu cada lista; uma mudança de regra sem registro torna duas rodadas incomparáveis sem que ninguém saiba. O registro aqui complementa, não substitui, a entidade `alteracao_parametro` do Registro.

## [Unreleased]

### Added

- Fundação do repositório: estrutura de pastas (`src/grafo`, `src/dominio`, `src/dados`, `src/entrega`, `src/config`, `tests`), sem código de produto.
- `CLAUDE.md` com projeto, cadência, stack, os sete invariantes, hierarquia dos documentos, glossário e os nove parâmetros pendentes (todos nulos).
- `docs/` com os três documentos-fonte (PRD 5.0, Spec 1.0, Ferramentas 1.0) movidos da raiz, e `docs/mapa-de-dados.md` derivado da base factual do PRD.
- `bug.md` com formato de registro de defeitos.
- Subagentes de desenvolvimento em `.claude/agents/`: `revisor-de-regra`, `investigador-de-dados`, `revisor-de-codigo`, `auditor-de-invariantes`, `conferente-de-numeros`.
- Skills de desenvolvimento em `.claude/skills/`: `consultar-newcore`, `verificar-contra-spec`, `registrar-bug`.
- `.gitignore` e `.env.tmpl` (segredos via 1Password, `op://Personal/orquestrador_portais/<VAR>`).
