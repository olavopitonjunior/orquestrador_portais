# src/config

Parâmetros de decisão. Toda alteração de parâmetro é registrada com data, autor e valor anterior (entidade `alteracao_parametro` do Registro) e no `CHANGELOG.md`.

Nove parâmetros seguem pendentes e devem permanecer nulos até serem definidos — a lista está no `CLAUDE.md`. Nenhum pode ser preenchido com valor inventado. Os catorze valores ADOTADOS (D-034) moram em `adotados.py`, cada um com decisão registrada: valor adotado não é valor inventado, e a rodada os usa quando a semana não declara outra coisa.

## O que mora aqui

`parametros.py` — o **carregador**. Resolve cada chave para o valor DECLARADO na semana ou, na falta dele, para o ADOTADO de `adotados.py`, e carrega a procedência de cada um até a planilha e o Registro. O que segue nulo não ganha default: a régua de resultado por nível (nº 14) só entra se a semana a declarar, nos dois níveis, e enquanto não entrar a penalidade por janela não incide e a rodada declara isso.

Três regras que o módulo **executa**, não apenas descreve:

1. **Nenhum default.** Chave ausente derruba a rodada, com o número do pendente na mensagem. `tests/test_config_parametros.py` remove cada chave obrigatória, uma a uma, e exige a quebra — sem essa varredura, um `bruto.get(chave, 0.5)` de conveniência nasceria com a suíte verde.
2. **Nenhuma chave desconhecida.** Um `decaimeto` digitado errado é erro, não valor descartado em silêncio.
3. **Tudo que entra é PROVISÓRIO.** Carregar não é adotar: a origem e o rótulo viajam para a planilha, e o TOML declarado vai verbatim para o Registro. Adotar um valor exige decisão em `docs/decisoes.md` e entrada no `CHANGELOG.md`.

Os parâmetros que são **escolha** e não número — o tratamento do imóvel sem anúncio raspado e a ordem quando a raspagem não entra — vêm de uma lista fechada de formas nomeadas. Expressão livre num arquivo de configuração seria código executável fora da revisão, e o invariante 5 (mesma entrada, mesma lista) deixaria de ser verificável. O perdão da penalidade por janela é número (por cento por carga) e vira função no carregador, não escolha.

Modelo comentado do arquivo: [`docs/parametros-da-rodada.exemplo.toml`](../../docs/parametros-da-rodada.exemplo.toml) — valores **ilustrativos, não adotados**.
