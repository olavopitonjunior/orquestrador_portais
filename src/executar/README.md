# src/executar

Pontos de entrada das rodadas. É a camada que **fia** o que as outras constroem —
nenhuma regra vive aqui.

## Rodada de segunda (acompanhamento)

```bash
uv run python -m executar.segunda [--destino DIR] [--dry-run] [--hoje AAAA-MM-DD]
# ou, instalado:  uv run rodada-segunda --dry-run
```

Precisa de `POSTGRES_URL` (Registro) e das `NEWCORE_MYSQL_*` (leads) no ambiente —
gere com `op inject -i .env.tmpl -o .env`, nunca DSN no repo.

- `--dry-run` roda tudo e **não grava nem escreve nada**: serve para conferir o
  estado da rodada e as limitações antes de valer.
- Código de saída:
  - `0` entregou (completa ou degradada — a limitação vai declarada na planilha);
  - `4` **não havia carga aprovada**: insumo ausente, não erro (Spec §7.3). A rodada
    fica registrada como abortada e o gestor é avisado;
  - `3` **falha ao coletar ou apurar** (Newcore fora do ar, ou dado malformado na
    carga). Também declarado, mas é incidente — não trate como no-op benigno;
  - `1` falha de ESCRITA (Registro ou relatório);
  - `2` é do **argparse** (uso inválido da linha de comando) — reservado de
    propósito: sem a reserva, um argumento digitado errado sairia com o código de
    "não havia carga" e o agendador o trataria como no-op benigno.

A janela é **derivada** de `aprovada_em` da carga medida (Spec §1: três dias
corridos, "sem misturar com a anterior"), nunca recebida por argumento — aceitar a
janela do chamador deixaria o recorte que a Spec chama de deliberado à mercê de quem
invoca. O fim nunca passa de hoje — e **janela truncada é declarada** como limitação na
planilha (§7.2), porque medir menos que os três dias é dado parcial.

Cada rodada escreve numa **subpasta por data** (`saida/segunda/AAAA-MM-DD`): sem
isso, a segunda seguinte apagaria o relatório da anterior, e a planilha é o artefato
que a §7.2 quer auditável.

## Rodada de sexta (decisão)

Ainda **não** tem ponto de entrada commitado: o grafo (`grafo.fluxo`) e a aprovação
(`grafo.aprovacao`) existem e são exercitados por teste, mas quem os invoca hoje é
script local. É a próxima fatia desta pasta.

## Agendamento

Fora do escopo: quem dispara é o agendador do sistema operacional (Ferramentas §4).
Os horários exatos são o parâmetro pendente nº 8 — nulo, nada aqui os embute.
