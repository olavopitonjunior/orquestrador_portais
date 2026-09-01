# src/config

Parâmetros de decisão. Toda alteração de parâmetro é registrada com data, autor e valor anterior (entidade `alteracao_parametro` do Registro) e no `CHANGELOG.md`.

Doze parâmetros seguem pendentes (consolidação D-004, mais os dois da D-017) e devem permanecer nulos até serem definidos — a lista está no `CLAUDE.md`. Nenhum pode ser preenchido com valor inventado.

## O que mora aqui

`parametros.py` — o **carregador**. Nenhum valor de parâmetro mora neste pacote, e é essa a razão de o carregador existir: a rodada de sexta não calcula nada sem os pendentes, e a saída honesta não é embutir um default "razoável" (seria o valor inventado que a regra proíbe, ainda por cima invisível numa planilha aprovada) mas exigir que o dono da decisão os declare num arquivo TOML fora do repositório.

Três regras que o módulo **executa**, não apenas descreve:

1. **Nenhum default.** Chave ausente derruba a rodada, com o número do pendente na mensagem. `tests/test_config_parametros.py` remove cada chave obrigatória, uma a uma, e exige a quebra — sem essa varredura, um `bruto.get(chave, 0.5)` de conveniência nasceria com a suíte verde.
2. **Nenhuma chave desconhecida.** Um `decaimeto` digitado errado é erro, não valor descartado em silêncio.
3. **Tudo que entra é PROVISÓRIO.** Carregar não é adotar: a origem e o rótulo viajam para a planilha, e o TOML declarado vai verbatim para o Registro. Adotar um valor exige decisão em `docs/decisoes.md` e entrada no `CHANGELOG.md`.

Os dois parâmetros que são **forma** e não número (o decaimento da penalidade por janela, do nº 3, e a composição do sinal F3) escolhem-se numa lista fechada de formas nomeadas. Expressão livre num arquivo de configuração seria código executável fora da revisão, e o invariante 5 (mesma entrada, mesma lista) deixaria de ser verificável.

Modelo comentado do arquivo: [`docs/parametros-da-rodada.exemplo.toml`](../../docs/parametros-da-rodada.exemplo.toml) — valores **ilustrativos, não adotados**.
