"""Produtor e leitor de `registro.janela_destaque` (D-021).

A tabela existia desde o 001 e **ninguém escrevia nela**. As consequências eram
duas, e as duas silenciosas: as colunas "semanas consecutivas" e "leads acumulados
na janela atual" da Spec §4.3 ficavam vazias indefinidamente — não "nas primeiras
semanas", como a D-020 previa —, e a penalidade por janela anterior sem resultado
(§6.4) não tinha insumo, saindo 0,0 para todo imóvel.

## A unidade de acumulação é a CARGA, não a execução da segunda

A D-021 é literal: "a cada **carga** em que ele permanece, a janela acumula os leads
do período e incrementa `semanas_consecutivas`". Por isso a guarda de idempotência é
`ultima_rodada_decisao_id` — a carga já acumulada — e não a rodada de acompanhamento.

A diferença não é de estilo. `gravar_acompanhamento` abre uma rodada nova a cada
execução (`INSERT ... RETURNING id`), então chavear pela rodada de acompanhamento não
guardaria nada: reprocessar a segunda somaria os leads de novo e contaria mais uma
semana. E duas segundas medindo a MESMA carga — cenário concreto enquanto nada
carimba `aprovada_em`, buraco já registrado em `docs/decisoes.md` — contariam duas
semanas para uma carga só. Chaveando pela carga, os dois casos ficam corretos pelo
mesmo mecanismo.

## As DATAS são as da carga, não as do relógio

`inicio` e `fim` são "datas de entrada e saída da vitrine" (Spec §2.1). O sistema não
publica nada — a carga é aplicada à mão — então a data real de entrada é
inobservável. O melhor proxy que o sistema tem é `aprovada_em` da carga, que chega
aqui como `data_da_carga`. Usar `datetime.now()` da execução, como esta fatia fazia
antes, deslocaria toda janela em alguns dias e, num reprocessamento, carimbaria o
Registro com a data de hoje — quebrando a reprodutibilidade. O resíduo (aprovação ≠
momento da aplicação manual) é limitação declarada, não absorvida.

## O que este módulo NÃO decide

Se a janela "atingiu o resultado esperado para o nível" (§6.4). Esse limiar é o
parâmetro pendente **nº 14** (D-022), nulo, com um valor por nível. Aqui só se grava
o acumulado; o julgamento é do leitor, com o limiar que o dono declarar.

## Limitação declarada: `leads_gerados` é AMOSTRA, não o total da janela

A segunda mede uma janela de três dias corridos (Spec §1) sobre um ciclo de carga de
sete. O que se acumula aqui é a soma dessas amostras, então **cerca de metade da
exposição nunca é contada** — a Spec §2.1 pede "acumulado durante a janela". Quando o
limiar nº 14 existir, a janela será julgada por um número sistematicamente
subestimado, o que penaliza a mais. A limitação é declarada na planilha da segunda
(ver `LIMITACOES_DO_ACUMULO`); fechá-la exige contar os leads do intervalo inteiro,
que é fatia própria.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import psycopg

from dominio.acompanhamento import DesempenhoImovel
from dominio.penalidades import JanelaCrua

# Ditas na planilha E no motivo gravado no Registro, não só em comentário: são
# números de aparência factual sobre coisas que o sistema não sabe.
#
# ESTRUTURAL: vale enquanto a segunda medir três dias de um ciclo de sete, o que só
# muda com outra fatia. Por isso é constante — ao contrário da limitação de história
# rasa, que precisa de predicado (ver `limitacoes_do_acumulo`).
LIMITACAO_AMOSTRA = (
    "leads acumulados na janela são AMOSTRA, não total: a segunda mede três dias "
    "corridos (Spec §1) sobre um ciclo de carga de sete, então parte da exposição "
    "não é contada. A §2.1 pede o acumulado da janela inteira. E uma segunda que "
    "rodou antes de decorridos os três dias mede um período truncado que NÃO é "
    "remedido depois — a acumulação é por carga. As duas subcontagens empurram na "
    "mesma direção: quando o limiar nº 14 existir, penalizam a mais"
)

# Também estrutural: o sistema não publica nada, então a data real de entrada na
# vitrine é inobservável e `aprovada_em` é o proxy. Vai ao artefato porque as datas
# alimentam as semanas da §4.3 e, adiante, o decaimento da §6.4 — e quem aprova a
# lista não teria como saber que a grandeza é aproximada.
LIMITACAO_DATA_APROXIMADA = (
    "as datas da janela são as da APROVAÇÃO da carga, não as da aplicação na "
    "vitrine: a carga é aplicada à mão e o sistema não observa esse instante. "
    "Duração e semanas carregam a diferença entre aprovar e aplicar"
)

LIMITACAO_HISTORIA_RASA = (
    "a contagem de semanas consecutivas COMEÇA no primeiro acúmulo do Registro: há "
    "janela em curso aberta na primeira carga que o produtor viu, e o que veio antes "
    "dela não existe aqui — é o que se sabe, não o que aconteceu"
)


def limitacoes_do_acumulo(conn: psycopg.Connection) -> tuple[str, ...]:
    """As limitações do acúmulo desta rodada, as estruturais e a DERIVADA.

    A de história rasa não pode ser constante. Emitida incondicionalmente, em seis
    meses a planilha ainda afirmaria que a contagem está começando, sobre janelas com
    histórico real — a mesma classe de limitação falsa que a degradação incondicional
    de portal produzia, e que este projeto já corrigiu duas vezes.

    O predicado é exato e se apaga sozinho: ela vale enquanto houver janela ABERTA
    que nasceu na primeira carga que o produtor viu. Só dessas se pode dizer que o
    histórico anterior pode existir e não estar aqui; uma janela aberta depois disso
    tem contagem completa por construção.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT EXISTS (SELECT 1 FROM registro.janela_destaque WHERE fim IS NULL "
            " AND inicio = (SELECT min(inicio) FROM registro.janela_destaque))"
        )
        linha = cur.fetchone()
        pioneira_aberta = bool(linha[0]) if linha else False
    return (
        (LIMITACAO_AMOSTRA, LIMITACAO_DATA_APROXIMADA, LIMITACAO_HISTORIA_RASA)
        if pioneira_aberta
        else (LIMITACAO_AMOSTRA, LIMITACAO_DATA_APROXIMADA)
    )


def _exigir_transacao(conn: psycopg.Connection) -> None:
    """A atualização é de várias linhas e precisa cair inteira ou não cair.

    `raise`, não `assert`: sob `python -O` o assert evapora e a garantia de
    atomicidade viraria comentário.
    """
    if conn.autocommit:
        raise ValueError(
            "atualizar_janelas exige transação explícita (autocommit=False): "
            "abrir uma janela sem fechar a anterior deixaria duas abertas para o "
            "mesmo imóvel, que o índice único da 005 recusa"
        )


def atualizar_janelas(
    conn: psycopg.Connection,
    *,
    rodada_decisao_id: int,
    rodada_acompanhamento_id: int,
    desempenho: Sequence[DesempenhoImovel],
    data_da_carga: date,
) -> dict[int, tuple[int, int]]:
    """Recusa carga retroativa, fecha, acumula, abre e relê (D-021).

    Devolve `{imovel_id: (semanas_consecutivas, leads_acumulados)}` para os imóveis
    da carga — é o histórico que preenche as duas colunas da §4.3 no relatório desta
    mesma segunda. Devolver o estado PÓS-atualização é deliberado: devolver o
    anterior faria o relatório dizer "2 semanas" na terceira semana de permanência.

    `data_da_carga` é `aprovada_em` da carga medida (ver o cabeçalho do módulo).
    """
    _exigir_transacao(conn)
    if not desempenho:
        # Fechar TODAS as janelas abertas seria o efeito de um `desempenho` vazio, e
        # isso apagaria o histórico em curso do sistema inteiro. A D-021 fecha janela
        # quando "uma carga aprovada nova não o traz mais" — medição vazia não é carga
        # nova, é ausência de carga, que a §7.3 manda declarar em outro lugar.
        raise ValueError(
            "desempenho vazio: sem posições não há carga a acumular. Ausência de "
            "carga é declarada por `declarar_ausencia_de_carga`, não fechando janelas"
        )

    nivel_na_carga = {d.imovel_id: d.nivel.value for d in desempenho}
    ids = list(nivel_na_carga)

    with conn.cursor() as cur:
        # 0. RECUSA carga retroativa. Rodar uma segunda antiga depois de uma nova
        #    (fila de retomada, correção de histórico, relógio torto) tentaria fechar
        #    janelas com `fim` anterior ao próprio `inicio`: o CHECK da 005 derruba a
        #    transação inteira com uma violação de constraint que não diz nada sobre a
        #    causa. Pior, o caso irmão passaria em silêncio — se ninguém saiu da
        #    carga, o passo 2 acumularia dado velho por cima do novo.
        cur.execute("SELECT max(inicio) FROM registro.janela_destaque WHERE fim IS NULL")
        linha = cur.fetchone()
        mais_recente = linha[0] if linha else None
        if mais_recente is not None and data_da_carga < mais_recente:
            raise ValueError(
                f"carga de {data_da_carga} é anterior à janela aberta mais recente "
                f"({mais_recente}): acumular fora de ordem sobrescreveria histórico "
                "mais novo com dado mais velho"
            )

        # 1. FECHA quem saiu da carga.
        cur.execute(
            "UPDATE registro.janela_destaque SET fim = %s "
            "WHERE fim IS NULL AND NOT (imovel_id = ANY(%s))",
            (data_da_carga, ids),
        )

        # 1b. FECHA quem MUDOU DE NÍVEL. A §6.4 julga "o resultado esperado PARA O
        #     NÍVEL" e o parâmetro nº 14 tem um valor por nível: uma janela que
        #     atravessasse destaque e super destaque não teria régua para ser julgada.
        #     Antes disto, o nível ficava congelado no da abertura e a janela inteira
        #     era julgada pela régua errada, em silêncio. Elaboração da D-021
        #     declarada em docs/decisoes.md — o documento não cobre o caso.
        cur.executemany(
            "UPDATE registro.janela_destaque SET fim = %s "
            "WHERE fim IS NULL AND imovel_id = %s AND nivel <> %s",
            [(data_da_carga, i, nivel) for i, nivel in nivel_na_carga.items()],
        )

        # 2. ACUMULA nas janelas que continuam abertas. A guarda é a CARGA: uma carga
        #    já acumulada nesta janela não acumula de novo, e o UPDATE simplesmente
        #    não casa nenhuma linha.
        cur.executemany(
            "UPDATE registro.janela_destaque "
            "SET leads_gerados = leads_gerados + %s, "
            "    semanas_consecutivas = semanas_consecutivas + 1, "
            "    ultima_rodada_decisao_id = %s, "
            "    ultima_rodada_acompanhamento_id = %s "
            "WHERE imovel_id = %s AND fim IS NULL "
            "  AND ultima_rodada_decisao_id IS DISTINCT FROM %s",
            [
                (
                    d.leads_gerados,
                    rodada_decisao_id,
                    rodada_acompanhamento_id,
                    d.imovel_id,
                    rodada_decisao_id,
                )
                for d in desempenho
            ],
        )

        # 3. ABRE janela para quem entrou agora (ou reabre, depois do 1b). `ON
        #    CONFLICT DO NOTHING` sobre o índice parcial da 005: se a janela já
        #    existia e continua válida, o passo 2 cuidou dela.
        cur.executemany(
            "INSERT INTO registro.janela_destaque "
            "(imovel_id, nivel, inicio, leads_gerados, semanas_consecutivas, "
            " rodada_decisao_id, ultima_rodada_decisao_id, ultima_rodada_acompanhamento_id) "
            "VALUES (%s, %s, %s, %s, 1, %s, %s, %s) "
            "ON CONFLICT (imovel_id) WHERE fim IS NULL DO NOTHING",
            [
                (
                    d.imovel_id,
                    d.nivel.value,
                    data_da_carga,
                    d.leads_gerados,
                    rodada_decisao_id,
                    rodada_decisao_id,
                    rodada_acompanhamento_id,
                )
                for d in desempenho
            ],
        )

        # 4. Relê o estado resultante — não o reconstrói em Python. Se o passo 2 não
        #    casou (carga já acumulada), os números devolvidos são os que já estavam
        #    lá, que é exatamente o que o relatório deve mostrar.
        cur.execute(
            "SELECT imovel_id, semanas_consecutivas, leads_gerados "
            "FROM registro.janela_destaque "
            "WHERE fim IS NULL AND imovel_id = ANY(%s)",
            (ids,),
        )
        return {int(i): (int(s), int(leads)) for i, s, leads in cur.fetchall()}


def janelas_encerradas(
    conn: psycopg.Connection, imoveis: Sequence[int], *, ate: date
) -> dict[int, tuple[tuple[str, int, date], ...]]:
    """Janelas ENCERRADAS por imóvel: `(nivel, leads_gerados, fim)`, mais recente
    primeiro.

    Só encerradas: o contrato de `ImovelPenalizavel` diz que `janelas_anteriores`
    contém apenas janelas com fim não nulo, e a janela em curso ainda não pode ser
    julgada — ela não terminou de acumular.

    `ate` é a data de referência da rodada, e o RECORTE vale aqui também, não só na
    contagem de ciclos. Sem ele, uma sexta reprocessada com `--hoje` no passado
    julgaria janelas que encerraram DEPOIS da sua data de referência — que não são
    "janela anterior" coisa nenhuma (§6.4) — e todas elas cairiam em `ciclos = 0`,
    empatadas. O desempate por "a que falhou vence" então faria a regra voltar a se
    comportar como o `any` que a D-023 removeu, em silêncio, com penalidade cheia
    (`razao ** 0 = 1`). O teto em metade do mecanismo era pior que nenhum.

    Devolve o dado CRU, sem julgar se atingiu resultado: o limiar por nível é o
    parâmetro pendente nº 14 (D-022) e não mora aqui. Imóvel sem janela encerrada
    simplesmente não aparece no dicionário — ausência, que a §6.4 manda distinguir
    de "teve janela e não foi penalizado".
    """
    if not imoveis:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            "SELECT imovel_id, nivel, leads_gerados, fim FROM registro.janela_destaque "
            "WHERE fim IS NOT NULL AND fim <= %s AND imovel_id = ANY(%s) "
            "ORDER BY imovel_id, fim DESC, id DESC",
            (ate, list(imoveis)),
        )
        por_imovel: dict[int, list[tuple[str, int, date]]] = {}
        for imovel_id, nivel, leads, fim in cur.fetchall():
            por_imovel.setdefault(int(imovel_id), []).append((str(nivel), int(leads), fim))
    return {i: tuple(js) for i, js in por_imovel.items()}


def ciclos_desde(conn: psycopg.Connection, fins: Sequence[date], *, ate: date) -> dict[date, int]:
    """Quantas cargas APROVADAS entraram no ar depois de cada data de fim.

    É o `ciclos_desde_encerramento` de `JanelaAnterior`, cuja docstring fixa
    "ciclo = rodada de decisão (sexta) completa" — leitura do código, não de
    documento (nenhum define "ciclo"). Duas precisões sobre essa leitura, declaradas:

    - conta só rodada **aprovada** (D-001: carga vigente é a aprovada). Uma sexta
      abortada ou reprovada não expôs imóvel nenhum, e fazer o decaimento da
      penalidade avançar por ela seria contar um ciclo que não aconteceu;
    - a data da carga é derivada em PYTHON, com `astimezone().date()`, e não por um
      `::date` no SQL. Parece detalhe e não é: `inicio`/`fim` da janela são gravados
      pelo runner com essa mesma conversão, no fuso do SISTEMA, enquanto um cast no
      servidor usaria o fuso da SESSÃO Postgres. Numa base com a sessão em UTC e a
      máquina em -03, toda carga aprovada depois das 21h cairia num dia diferente —
      e a carga que REMOVEU o imóvel passaria a contar como ciclo posterior ao
      fechamento que ela mesma produziu, deslocando o decaimento da §6.4 em um.
      Uma derivação só, no mesmo lugar, elimina a classe inteira.

    - a contagem tem TETO em `ate` (a data de referência da rodada). Sem ele, a
      mesma sexta reprocessada um mês depois contaria as cargas que entraram nesse
      intervalo, daria um decaimento maior e poderia produzir outra lista — enquanto
      o help de `--hoje` promete "fixa o recorte, tornando a rodada reproduzível".
      O teto é o que faz a promessa valer.

    As cargas aprovadas são uma por semana: trazê-las e contar em Python é barato, e
    a versão anterior fazia uma consulta por imóvel — milhares de idas ao banco.
    """
    unicas = sorted(set(fins))
    if not unicas:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            "SELECT aprovada_em FROM registro.rodada "
            "WHERE tipo = 'decisao' AND aprovada_em IS NOT NULL"
        )
        datas = [ts.astimezone().date() if ts.tzinfo else ts.date() for (ts,) in cur.fetchall()]
    return {fim: sum(1 for d in datas if fim < d <= ate) for fim in unicas}


def historico_para_penalidade(
    conn: psycopg.Connection, imoveis: Sequence[int], *, ate: date
) -> dict[int, tuple[JanelaCrua, ...]]:
    """O histórico de janelas encerradas por imóvel, no formato que a §6.4 consome.

    Compõe as duas leituras num só resultado — `janelas_encerradas` (o que aconteceu)
    e `ciclos_desde` (há quanto tempo) —, devolvendo `(nivel, leads_gerados, ciclos)`
    por janela. **Cru**: não julga se atingiu resultado, porque o limiar por nível é
    o parâmetro nº 14 e a decisão de julgar é do domínio, com o limiar injetado.

    É a leitura que a Spec §5 atribui ao Decisor — "o único agente que lê o Registro
    durante a rodada, e o faz para obter o histórico de janelas necessário ao cálculo
    da penalidade". Por isso vive aqui e é chamada pelo nó do Decisor, não pelo
    Coletor Interno, que lê só o Newcore.
    """
    encerradas = janelas_encerradas(conn, imoveis, ate=ate)
    if not encerradas:
        return {}
    ciclos = ciclos_desde(conn, [fim for js in encerradas.values() for _n, _l, fim in js], ate=ate)
    return {
        imovel_id: tuple((nivel, leads, ciclos[fim]) for nivel, leads, fim in js)
        for imovel_id, js in encerradas.items()
    }
