# tests

Estratégia de testes ainda não definida (fora do escopo da spec 1.0 e do documento de ferramentas 1.0).

Referências que os testes de domínio deverão usar quando existirem: os números medidos em `docs/mapa-de-dados.md` — com atenção ao aviso de que os ganhos de relaxamento foram medidos com parâmetro diferente do adotado e não servem de conferência exata.

## Os testes de I/O rodam contra o Postgres do ambiente — inclusive o vigente

Desde 02/09/2026 o `conftest.py` carrega o `.env` no início da sessão, então na máquina
do gestor a suíte **conecta no mesmo banco que guarda as rodadas reais**. Antes disso
esses testes só rodavam no CI, contra um contêiner efêmero; agora rodam em toda parte, e
o ganho é grande (a metade de I/O do Registro deixou de ser exercitada só na nuvem).

**O isolamento hoje é por transação.** Os fixtures abrem com `autocommit = False` e dão
`rollback` no teardown; conferido em 02/09 que a suíte completa não altera contagem
(8 rodadas e 13.940 decisões antes e depois, idênticas).

**Onde isso quebra, e é previsível:** um teste que faça `commit` próprio — exercitar um
runner ponta a ponta, por exemplo — **persiste no banco vigente** e ninguém percebe,
porque o teste passa. O `rollback` do fixture não desfaz o que já foi commitado.

Duas saídas, quando alguém precisar desse tipo de teste: um banco separado
(`orquestrador_portais_test`) escolhido por variável própria, ou uma guarda que recuse
I/O contra base que já tenha rodadas sem um opt-in explícito. **Nenhuma das duas está
implementada.** Registrado aqui enquanto o motivo está fresco, e não em `bug.md`, porque
ainda não há defeito: há uma armadilha esperando o primeiro teste que commitar.
