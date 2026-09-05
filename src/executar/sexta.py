"""Ponto de entrada da rodada de SEXTA (decisão) — Spec §1.

Simétrico ao de segunda: até aqui o grafo da decisão existia e passava nos testes,
mas quem o invocava era script solto e não versionado — a planilha em `saida/piloto/`
saiu de um desses. Aqui a fiação é commitada, reproduzível e auditável.

    uv run python -m executar.sexta --parametros ARQUIVO.toml [--externo DIR]
                                    [--recorte-pela-raspagem] [--destino DIR]
                                    [--dry-run] [--hoje AAAA-MM-DD]

## `--parametros` é OPCIONAL desde a D-034: sem arquivo, valem os ADOTADOS

Os catorze parâmetros da decisão têm valor ADOTADO pelo dono (D-034, em
`src/config/adotados.py`, cada um com procedência). O arquivo da semana só precisa
declarar o que DIFERE — e o que declarar sai rotulado "declarado" na planilha, ao lado
do adotado, para o dono ver o que mudou. O que segue NULO (a régua de resultado, nº 14)
continua proibido de receber valor inventado: só entra se o TOML o declarar, nos dois
níveis, e enquanto não entrar a penalidade por janela não incide e a planilha diz isso.

A procedência (adotado / declarado / nulo) viaja para a planilha (nota de abertura) e o
efetivo vai para o Registro, junto da data de referência e da definição de gestor
ativo, para que **os parâmetros e o recorte** da rodada sejam reconstituíveis a partir
do que ficou gravado.

Note o que essa frase NÃO diz: que a rodada é reproduzível. O estoque não é
reconstituível — as janelas de 30 dias do gestor e as vendas de 180 dias saem de
`NOW()` no SQL, então reexecutar lê o banco de hoje (ver a ressalva de `--hoje`). O
invariante 5 vale sobre a mesma entrada, e "mesma entrada" inclui o banco no instante
da rodada.

## Por que o runner NÃO abre o fluxo de aprovação

A aprovação é grafo à parte (`grafo/aprovacao.py`), e o que a dispara sozinha é o
PRAZO da aprovação tácita — parâmetro pendente nº 10, **nulo**. Abrir aqui uma thread
de aprovação sem prazo seria afirmar um prazo que ninguém definiu. O runner termina
registrando a rodada e informando o `rodada_id`; quem tem o prazo (console ou
agendador) abre a aprovação com ele.

## Fiação dos sinks

Espelha a disciplina da segunda: falha de ESCRITA é distinta de falha de FONTE.
`registrar` é chamado de DENTRO do grafo (último nó); se o Postgres cair, avisa por
outro canal e propaga como `SinkFalhou` — a planilha não é escrita, porque uma
planilha sem rodada no Registro é uma decisão sem trilha. A planilha é escrita pelo
runner DEPOIS do `invoke`, então a ordem é sempre Registro → planilha.

**Essa ordem DIVERGE dos documentos e a divergência está declarada**, não resolvida
em silêncio: o PRD (fluxo de sexta, passos 6 e 7) e a Spec §5 ("Registro | Consome:
saídas do Decisor, DO REDATOR e do Monitor") põem o Redator antes. O contra-argumento
é real — sob a D-001 uma rodada gravada sem planilha pode ser aprovada por decurso de
prazo e virar a "carga vigente" contra a qual a segunda mede, uma lista que ninguém
recebeu. A pergunta está em `docs/decisoes.md`; até a resposta do dono, esta ordem
permanece.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Callable, Collection, Mapping, Sequence
from datetime import date, datetime
from functools import partial
from pathlib import Path
from typing import Any

from config.ambiente import carregar_env
from config.parametros import ParametroAusente, ParametroInvalido, ParametrosDaRodada, carregar
from config.recorte import DEFINICAO_ATIVO
from dados.candidatos_perfil import coletar_dimensoes_candidatos
from dados.coletor_externo import ColetaExterna, ler_coleta
from dados.coletor_interno import coletar
from dados.registro.conexao import conectar
from dados.registro.escrita import gravar_rodada_decisao
from dados.registro.janelas import LIMITACAO_AMOSTRA, historico_para_penalidade
from dados.vendas import coletar_vendas
from dominio.penalidades import JanelaCrua
from dominio.perfil import ImovelVendido
from entrega.planilha_piloto import ContextoApuracao, escrever_planilha
from executar.resumos import AtribuidorDeDegradacoes, resumo_do_no
from grafo.estado import Estado, EstadoRodada, Fontes
from grafo.fluxo import construir_grafo

# D-015 (definição de gestor ativo do distrito) vive em `config/recorte.py`, porque
# a medição dos números de referência precisa da MESMA constante e ponto de entrada
# não deve ser importado por outro. Reexportado aqui para os leitores da sexta.

# O modelo ilustrativo, recusado como entrada real (ver `main`). Num wheel instalado
# este caminho não existe, e a comparação simplesmente nunca casa — que é o correto:
# o modelo é documentação, não vai no pacote.
MODELO_DE_DOCS = (
    Path(__file__).resolve().parent.parent.parent / "docs" / "parametros-da-rodada.exemplo.toml"
)

log = logging.getLogger("rodada.sexta")


class SinkFalhou(RuntimeError):
    """Falha de ESCRITA (Registro ou planilha). Distinta de falha de fonte."""


class RecorteVazio(RuntimeError):
    """A raspagem não amarrou imóvel nenhum: não há amostra sobre a qual decidir.
    Sai com o código de "estoque vazio" (4) — é insumo ausente, não incidente."""


def _recorte_da_raspagem(externo: Path) -> tuple[frozenset[int], ColetaExterna]:
    """Os imóveis que a raspagem AMARROU — o universo da rodada amostral — e a
    leitura de onde saíram, para o nó do Coletor Externo não parsear o CSV de novo.

    Lido ANTES da coleta interna, de propósito: o recorte é o que define a amostra, e
    a coleta interna passa a responder só sobre ele (`WHERE Realty_Id IN`). A
    alternativa — `LIMIT n` na coleta interna — daria uma interseção aleatória com o
    que foi raspado, e a taxa de amarração (que divide pela lista-alvo inteira)
    reprovaria a coleta na porta.

    O que o recorte faz com a taxa de amarração precisa ficar dito: todo candidato da
    rodada amostral está na raspagem POR CONSTRUÇÃO, então a taxa sai 100% e não mede
    nada — a planilha a imprime, e a limitação AMOSTRAL diz isso ao lado. O número que
    mede a amostra é outro, `candidatos / recorte` (que fração do raspado é imóvel
    ativo no Newcore), e é ele que a limitação declara.

    Vazio é erro próprio: o motivo mais provável é o formato do `codigoImovel`, que a
    porta de amarração vazia já aponta — aqui ele aparece antes de a rodada começar.
    """
    coleta = ler_coleta(externo)
    ids = frozenset(coleta.por_imovel)
    if not ids:
        raise RecorteVazio(
            f"recorte pela raspagem VAZIO: {coleta.total_linhas} linhas lidas em {externo}, "
            f"{coleta.sem_amarracao} fora do formato {{Id}}{{letra}}, estado {coleta.estado!r} — "
            "nenhum imóvel amarrou, não há amostra sobre a qual decidir. Confira o "
            "codigoImovel (externalId): o formato esperado é {Id}{letra}"
        )
    return ids, coleta


def _contagem(candidatos: Any) -> int | None:
    """`len` que distingue AUSENTE de VAZIO: chave que não veio no estado é "não
    apurado" (None), e a limitação amostral diz isso em vez de imprimir "0 deles (0%)"
    sobre um dado que não existe."""
    return None if candidatos is None else len(candidatos)


def _estado_da_entrega(estado_do_grafo: Any, *, amostral: bool) -> Any:
    """Rodada AMOSTRAL nunca é COMPLETA.

    Decisão do RUNNER, não do grafo — como o modo seco: a amostragem é fiação, o grafo
    não a conhece, e `estado_final` é função só dos prontos. Sem isto, uma amostra em
    que todas as etapas ficaram prontas chegaria ao Registro como COMPLETA, e uma
    consulta por estado a tomaria por decisão sobre o estoque.
    """
    if amostral and estado_do_grafo == Estado.COMPLETA:
        return Estado.DEGRADADA
    return estado_do_grafo


def _fontes(
    externo: Path | None,
    *,
    dry_run: bool = False,
    recorte: Collection[int] | None = None,
    coleta: ColetaExterna | None = None,
    janela_conversao_dias: int = 180,
    login_janela_dias: int = 30,
) -> tuple[Fontes, list[tuple[list[ImovelVendido], int]]]:
    """As fontes da sexta, mais o cache das vendas.

    `coletar_vendas` é MEMOIZADO e o cache devolvido ao chamador porque o nó do
    Analista de Perfil descarta a contagem de vendas sem imóvel amarrado
    (`vendas, _descartadas = ...`) — e esse número é nota de coleta da planilha.
    Sem o cache, o runner teria de consultar o Newcore uma segunda vez para
    recuperá-lo, e as duas leituras poderiam divergir.
    """
    cache: list[tuple[list[ImovelVendido], int]] = []

    def vendas_memoizadas() -> tuple[list[ImovelVendido], int]:
        if not cache:
            cache.append(coletar_vendas(janela_conversao_dias))
        return cache[0]

    fontes = Fontes(
        # `coletar` recebe a definição de ativo; o grafo espera zero-argumento. O
        # recorte amostral vai junto: a coleta interna responde só sobre ele.
        coletar_interno=partial(
            coletar, DEFINICAO_ATIVO, recorte=recorte, login_janela_dias=login_janela_dias
        ),
        coletar_dimensoes=coletar_dimensoes_candidatos,
        coletar_vendas=vendas_memoizadas,
        # Tudo ou nada: o grafo recusa meia-fiação, e o nó declara a degradação
        # quando não há raspagem — rodada DEGRADADA nesse fator, nunca silenciosa.
        # Na amostral a coleta JÁ foi lida para montar o recorte: reusar a leitura é o
        # que garante que o nó e o recorte viram o mesmo arquivo.
        coletar_externo=(
            (lambda: coleta)
            if coleta is not None
            else ((lambda: ler_coleta(externo)) if externo else None)
        ),
        # A leitura que a Spec §5 atribui ao Decisor. Conexão por chamada, como as
        # demais leituras do Registro no runner: a rodada é curta e a alternativa
        # (segurar conexão aberta atravessando o grafo) traria estado de I/O para
        # dentro do fluxo.
        #
        # Em ENSAIO a fonte não é fiada: `--dry-run` promete "não grava nem escreve
        # nada" e antes não abria conexão nenhuma; fiá-la faria o ensaio falhar
        # inteiro com o Registro fora, que é justamente quando se quer ensaiar. O
        # ensaio então declara "Registro não consultado", que é a verdade sobre ele.
        coletar_janelas=None if dry_run else _janelas_do_registro,
    )
    return fontes, cache


def _janelas_do_registro(imoveis: Sequence[int], ate: date) -> Mapping[int, tuple[JanelaCrua, ...]]:
    """Histórico de janelas encerradas, cru. O julgamento é do domínio.

    `ate` é a data de referência da rodada, e ela TEM teto por isso: sem o teto, a
    mesma sexta reprocessada semanas depois contaria as cargas aprovadas nesse
    intervalo e daria outro decaimento — enquanto `--hoje` promete fixar o recorte.
    """
    with conectar() as conn:
        return historico_para_penalidade(conn, imoveis, ate=ate)


def _serializaveis(
    parametros: ParametrosDaRodada,
    hoje: date,
    externo: Path | None,
    *,
    recorte: Collection[int] | None = None,
) -> dict[str, object]:
    """O que vai para `parametros_da_rodada` do Registro.

    É o TOML declarado VERBATIM mais a procedência — não uma reconstrução a partir
    de `ParametrosDecisao`. O perdão da penalidade por janela vira função lá
    (`decaimento_janela`) e não sobrevive à dataclass: reconstruir os parâmetros a
    partir dela deixaria a rodada irreproduzível pelo Registro.

    Mas o TOML não é a entrada inteira. Quatro coisas fora dele também mudam a lista e
    por isso viajam junto (a quarta, o recorte amostral, está comentada no corpo):

    - `data_referencia` é entrada da decisão (decide a regra de atualização em 90
      dias) e o Registro não tem coluna para ela. Sem gravá-la, uma rodada feita com
      `--hoje` ficaria irreproduzível — justamente a opção cujo help promete "fixa o
      recorte, tornando a rodada reproduzível".
    - `definicao_ativo_distrito` é entrada de elegibilidade fixada em código (D-015):
      se a decisão mudar, as rodadas antigas precisam dizer sob qual regra saíram.
    - `coleta_externa` identifica a raspagem que alimentou a nota. Fica o CAMINHO, que
      é o que o runner tem; a identificação plena da coleta (`coletado_em`,
      `total_linhas`) mora na `ColetaExterna` dentro do grafo e ainda não sobe até
      aqui — lacuna DECLARADA, não resolvida.
    """
    return {
        # O que a rodada de fato USOU (adotados + declarados) e a procedência de cada
        # chave: é isto que torna a rodada reproduzível a partir do Registro.
        "efetivo": dict(parametros.efetivo),
        "procedencia": dict(parametros.procedencia),
        "origem": parametros.origem,
        "data_referencia": hoje.isoformat(),
        "definicao_ativo_distrito": DEFINICAO_ATIVO.value,
        "coleta_externa": str(externo) if externo else None,
        # A marca AMOSTRAL, como DADO e não como prosa: é por esta chave que
        # `rodada-aprovar` recusa promover a amostra a carga — casar o texto do
        # `motivo_degradacao` soltaria a guarda na primeira reescrita da mensagem. Só a
        # contagem: os ids são reconstituíveis do CSV cujo caminho está logo acima.
        "recorte_pela_raspagem": {"imoveis": len(recorte)} if recorte is not None else None,
        **parametros.declarado,
    }


def _avisar(destino: Path, *, dry_run: bool) -> Callable[[str], None]:
    def avisar(mensagem: str) -> None:
        log.warning(mensagem)  # o log sai SEMPRE, primeiro
        if dry_run:
            return
        try:
            destino.mkdir(parents=True, exist_ok=True)
            with (destino / "aviso.txt").open("a", encoding="utf-8") as f:
                f.write(f"{datetime.now().isoformat()} {mensagem}\n")
        except OSError as e:
            # Chamado de dentro de handlers de falha: se levantasse, trocaria a
            # exceção original por outra e esconderia a causa.
            log.error("não foi possível gravar aviso.txt (%s); o aviso está no log", e)

    return avisar


def _registrador(
    parametros: ParametrosDaRodada,
    hoje: date,
    externo: Path | None,
    agora: datetime,
    *,
    dry_run: bool,
    avisar: Callable[[str], None],
    recorte: Collection[int] | None = None,
) -> tuple[Callable[[EstadoRodada], object], list[int]]:
    """O sink `registrar` do grafo, mais a caixa onde o `rodada_id` é capturado.

    O grafo descarta o retorno de `registrar`, e o `rodada_id` é o que o dono precisa
    para aprovar a rodada — por isso a captura por closure. A caixa é lida com
    `[-1]`, nunca `[0]`: se o nó for reexecutado (o retry do Orquestrador é o
    parâmetro nº 4, ainda nulo, e `no_registrar` já o registra como fatia futura),
    `gravar_rodada_decisao` cria uma SEGUNDA linha — não há chave natural para
    deduplicar — e informar a primeira mandaria o dono aprovar a rodada órfã.
    """
    capturado: list[int] = []

    def registrar(estado: EstadoRodada) -> object:
        resultado = estado.get("resultado")
        if resultado is None:
            # Chegar ao nó de registro sem resultado é incoerência de topologia, não
            # rodada vazia: gravar a linha assim mesmo produziria uma "carga vigente"
            # sem decisão, que a segunda mediria como se fosse real.
            raise RuntimeError("rodada chegou ao Registro sem resultado da decisão")
        # As limitações da FIAÇÃO entram no motivo gravado, não só na planilha: sob a
        # D-001 o Registro é a fonte da verdade, e quem auditasse pelo banco — que é
        # como a rodada de segunda enxerga — não veria "histórico de janelas ausente"
        # nem "distrito a 45,9%". Planilha e Registro precisam dizer a mesma coisa.
        degradacoes = [
            *estado.get("degradacoes", []),
            *limitacoes_da_fiacao(
                parametros,
                estado.get("janelas_lidas"),
                recorte=recorte,
                candidatos=_contagem(estado.get("candidatos")),
            ),
        ]
        # Uma por LINHA, não "; ": as próprias limitações têm "; " no meio (a da definição
        # de gestor ativo, incondicional), e o console lista uma por linha. Prosa, nunca
        # parseada pelo caminho da decisão — `aprovar.py` se recusa a casar este texto.
        motivo = "\n".join(degradacoes) or None
        estado_gravado = _estado_da_entrega(estado.get("estado"), amostral=recorte is not None)
        if dry_run:
            log.info("[dry-run] rodada NÃO gravada (estado=%s)", estado_gravado)
            return None
        try:
            with conectar() as conn, conn.transaction():
                rodada_id = gravar_rodada_decisao(
                    conn,
                    resultado=resultado,
                    estado=str(estado_gravado),
                    etapas=estado.get("prontos", {}),
                    parametros=_serializaveis(parametros, hoje, externo, recorte=recorte),
                    inicio=agora,
                    fim=datetime.now(),
                    motivo_degradacao=motivo,
                    perfis=tuple(estado.get("perfis") or ()),
                )
        except Exception as e:
            # Só o TIPO: a mensagem pode ecoar valor vindo do banco, e a saída do
            # agendador vira e-mail/log capturado.
            avisar(f"FALHA ao gravar a rodada de sexta no Registro: {type(e).__name__}")
            raise SinkFalhou("falha ao gravar no Registro") from e
        capturado.append(rodada_id)
        log.info("rodada de decisão gravada no Registro: id=%s", rodada_id)
        return rodada_id

    return registrar, capturado


def limitacoes_da_fiacao(
    parametros: ParametrosDaRodada,
    janelas_lidas: int | None,
    *,
    recorte: Collection[int] | None = None,
    candidatos: int | None = None,
) -> list[str]:
    """Limitações que nascem de COMO a rodada foi fiada, não do que o grafo achou.

    A §7.2 quer a limitação visível na planilha, e estas três não apareciam em lugar
    nenhum — quem lesse a lista não teria como saber que existiam:

    1. **Não há histórico de janelas: a penalidade da §6.4 fica inerte.** O Coletor
       sexta LÊ `registro.janela_destaque` (é esta a fatia do consumidor), mas o
       Registro pode não ter janela ENCERRADA nenhuma para os imóveis da rodada — e
       aí a penalidade da §6.4 não incide e a coluna sai 0,0 para todos,
       indistinguível de "imóvel sem histórico", que o PRD manda identificar como
       tal.

       O predicado é "o produtor entregou ALGUM histórico?", não "algum imóvel foi
       penalizado". A primeira versão perguntava a segunda coisa, e as duas divergem
       no dia em que o produtor existir e todas as janelas tiverem dado resultado:
       ali a planilha declararia "dado ausente" sobre um dado presente — a mesma
       classe de limitação falsa que a degradação incondicional de portal produzia,
       reintroduzida a prazo. Perguntando pelo histórico, a linha some sozinha
       quando o produtor chegar, que é o que o comentário promete.
    2. **Razão 1.0 não decai.** A §6.4 diz que a penalidade decai ao longo dos
       ciclos; a razão 1.0 é aceita, mas a divergência é declarada em vez de o código
       fingir que ela não existe.
    3. **A definição de gestor ativo do distrito** (D-015) cobre 45,9% — a D-016
       manda essa limitação aparecer na aba, e ela não aparecia.
    """
    limitacoes = []
    if recorte is not None:
        # PRIMEIRA da lista, sempre: é a que muda a leitura de todas as outras. Quem
        # abrir a planilha precisa saber antes de qualquer número que ele é sobre uma
        # amostra, não sobre o estoque.
        n = len(recorte)
        # O número que MEDE a amostra: que fração do raspado é imóvel ativo no Newcore.
        # A taxa de amarração, ao contrário, sai 100% por construção aqui (todo
        # candidato veio da raspagem) — e a planilha a imprime, então a mesma linha
        # tem de dizer que ela não mede nada nesta rodada.
        cobertura = (
            f"{candidatos} deles ({candidatos / n:.0%}) são imóveis ativos no Newcore — essa é "
            "a cobertura real da amostra"
            if candidatos is not None and n
            else "a cobertura (quantos são imóveis ativos no Newcore) não foi apurada"
        )
        limitacoes.append(
            f"RODADA AMOSTRAL: o universo desta rodada é o recorte de {n} imóveis que a "
            f"raspagem trouxe — NÃO é decisão sobre o estoque; {cobertura}. A taxa de "
            "amarração anúncio↔imóvel sai 100% POR CONSTRUÇÃO nesta rodada e não mede nada. "
            "As cotas contratadas continuam as mesmas, então as posições que a amostra não "
            "cobre saem VAZIAS, e o relaxamento tenta cobri-las. Esta rodada existe para ver "
            "a corrente inteira funcionar, com o fator de portal entrando de verdade; ela "
            "nunca é COMPLETA e `rodada-aprovar` a recusa — não pode virar carga"
        )
    if janelas_lidas is None:
        limitacoes.append(
            "REGISTRO NÃO CONSULTADO para o histórico de janelas: a rodada correu sem a "
            "fonte fiada, então a penalidade por janela anterior sem resultado (Spec §6.4) "
            "não pôde nem ser avaliada. Não é 'não há histórico' — é que ninguém perguntou"
        )
    elif janelas_lidas == 0:
        limitacoes.append(
            "HISTÓRICO DE JANELAS vazio: o Registro não devolveu nenhuma janela ENCERRADA "
            "para os imóveis desta rodada, então a penalidade por janela anterior sem "
            "resultado (Spec §6.4) não pode incidir. A coluna sai 0,0 para todos — não é "
            "'nenhum imóvel penalizado', é dado ausente. A rodada de segunda acumula as "
            "janelas (D-021), mas só as ENCERRADAS são julgáveis: a janela em curso ainda "
            "não terminou de acumular"
        )
    if janelas_lidas:
        # A §7.2 quer a limitação visível NA PLANILHA, e a planilha em que a penalidade
        # sai é esta. O acumulado que a §6.4 julga vem de amostras de três dias num
        # ciclo de sete (limitação declarada na segunda, D-021) — quem aprova a lista
        # precisa saber que o número que penalizou é subestimado. Derivada: só sai
        # quando o insumo foi de fato usado, e some sozinha quando a fatia do
        # intervalo inteiro chegar.
        limitacoes.append(f"insumo da penalidade §6.4 — {LIMITACAO_AMOSTRA}")
    if parametros.resultado_esperado is None:
        # A outra metade da D-022: "enquanto nulo... a rodada DECLARA 'limiar de
        # resultado não definido' na planilha. Nunca 0,0 silencioso". Sem esta linha,
        # a ausência de penalidade por falta de limiar seria indistinguível de uma
        # janela que passou no critério.
        limitacoes.append(
            "LIMIAR DE RESULTADO não definido (parâmetro pendente nº 14, D-022): a §6.4 "
            "penaliza a janela que não atingiu 'o resultado esperado para o nível', e os "
            "dois valores seguem nulos. Nenhuma janela é julgada — não é 'todas passaram'"
        )
    if parametros.efetivo.get("desconto.perdao_por_semana") == 0:
        limitacoes.append(
            "perdão por semana = 0%: o desconto da janela anterior NÃO decai ao longo dos "
            "ciclos, divergindo da Spec §6.4 — escolha declarada nesta rodada"
        )
    limitacoes.append(
        f"gestor ativo do distrito = {DEFINICAO_ATIVO.value} (D-015): cobertura de "
        "45,9% da base; imóveis cujo distrito não casa ficam de fora da regra"
    )
    return limitacoes


def notas_da_planilha(
    parametros: ParametrosDaRodada,
    estado: Estado | None,
    degradacoes: Sequence[str],
    *,
    data_referencia: date | None = None,
    vendas_descartadas: int | None = None,
    taxa_amarracao: float | None = None,
    idade_dias: int | None = None,
    posicoes_vazias: int | None = None,
    posicoes_preenchidas: int | None = None,
) -> list[str]:
    """As notas que abrem a aba de parâmetros e limitações.

    O ESTADO e as limitações vêm PRIMEIRO: a §7.2 exige a limitação declarada de
    forma visível, e quem lê a lista precisa saber, antes dos números, se a rodada
    foi completa ou degradada.

    Depois vêm os quatro itens que a §3.1 e o PRD exigem NOMINALMENTE na aba de
    resumo: idade do dado do portal, taxa de amarração, posições não preenchidas e —
    ainda sem produtor — a variação de volume. Cada um que falta é DECLARADO como
    ausente: uma linha faltando é indistinguível de um número que ninguém calculou.
    """
    notas = []
    if data_referencia is not None:
        # A §3.1 pede a DATA no resumo. A subpasta datada não serve: quem abre o CSV
        # solto — que é como ele viaja por e-mail — não vê o nome da pasta.
        notas.append(f"DATA DE REFERÊNCIA DA RODADA: {data_referencia.isoformat()}")
    notas.append(f"ESTADO DA RODADA: {str(estado).upper()}")
    notas += [f"LIMITAÇÃO {i}: {d}" for i, d in enumerate(degradacoes, 1)] or [
        "LIMITAÇÕES: nenhuma"
    ]
    declarados = parametros.declarados_diferentes_do_adotado
    adotados = len(parametros.procedencia) - len(declarados)
    notas.append(
        # A procedência de cada valor está na aba (ADOTADO / PROVISÓRIO); aqui o resumo.
        f"parâmetros da rodada: {adotados} adotados (D-034)"
        + (
            f" e {len(declarados)} PROVISÓRIOS declarados nesta rodada, diferentes do "
            f"adotado ({', '.join(declarados)}), carregados de {parametros.origem}"
            if declarados
            else f"; nenhum declarado diferente do adotado (origem: {parametros.origem})"
        )
    )
    notas.append(
        f"idade do dado do portal: {idade_dias} dia(s)"
        if idade_dias is not None
        else "idade do dado do portal: AUSENTE (sem coleta externa nesta rodada, ou "
        "coleta sem carimbo de tempo)"
    )
    notas.append(
        f"taxa de amarração anúncio↔imóvel: {taxa_amarracao:.1%}"
        if taxa_amarracao is not None
        else "taxa de amarração anúncio↔imóvel: AUSENTE (sem coleta externa)"
    )
    notas.append(
        f"posições de destaque não preenchidas: {posicoes_vazias}"
        if posicoes_vazias is not None
        else "posições não preenchidas: não apuradas"
    )
    notas.append(
        f"posições preenchidas: {posicoes_preenchidas}"
        if posicoes_preenchidas is not None
        else "posições preenchidas: não apuradas"
    )
    notas.append(
        "variação do estoque elegível em relação à semana anterior: NÃO APURADA — a "
        "comparação exige a rodada anterior no Registro e ainda não tem produtor "
        "(Spec §3.1 a exige; limitação declarada, não omitida)"
    )
    if vendas_descartadas:
        notas.append(
            f"{vendas_descartadas} venda(s) do período descartada(s) por não amarrar "
            "a imóvel — não sustentaram nenhum perfil de conversão"
        )
    return notas


def executar(
    destino: Path,
    parametros: ParametrosDaRodada,
    *,
    externo: Path | None = None,
    hoje: date | None = None,
    dry_run: bool = False,
    recorte_pela_raspagem: bool = False,
    ao_terminar_no: Callable[[str, Mapping[str, Any]], None] | None = None,
) -> tuple[dict[str, Any], int | None]:
    """Roda a sexta de ponta a ponta. Devolve o estado final e o `rodada_id`.

    `ao_terminar_no` é chamado a cada nó concluído, com o nome do nó e o estado
    acumulado. Serve à tela de acompanhamento: o grafo da decisão não tem
    checkpointer (o estado carrega objetos de domínio não-serializáveis), então não
    há de onde ler progresso — ele precisa ser emitido enquanto acontece.

    `recorte_pela_raspagem` faz a rodada AMOSTRAL: o universo passa a ser o que a
    raspagem em `externo` amarrou (exige `externo`; o parser já recusa sem ele).
    """
    hoje = hoje or date.today()
    agora = datetime.now()

    # Subpasta por data: sem isto, a sexta seguinte APAGA a planilha da anterior — e a
    # planilha é o artefato contratual, o que foi de fato aprovado e carregado.
    destino_da_rodada = destino / f"{hoje:%Y-%m-%d}"
    avisar = _avisar(destino_da_rodada, dry_run=dry_run)
    if recorte_pela_raspagem and externo is None:
        raise ValueError("recorte pela raspagem exige o diretório da raspagem (externo)")
    recorte, coleta = (
        _recorte_da_raspagem(externo) if recorte_pela_raspagem and externo else (None, None)
    )
    amostral = recorte is not None
    fontes, cache_vendas = _fontes(
        externo,
        dry_run=dry_run,
        recorte=recorte,
        coleta=coleta,
        janela_conversao_dias=parametros.coleta.janela_conversao_dias,
        login_janela_dias=parametros.coleta.login_janela_dias,
    )
    registrar, capturado = _registrador(
        parametros, hoje, externo, agora, dry_run=dry_run, avisar=avisar, recorte=recorte
    )

    grafo = construir_grafo(
        fontes,
        parametros.decisao,
        parametros_externo=parametros.externo if externo else None,
        resultado_esperado=parametros.resultado_esperado,
        registrar=registrar,
    )
    # `stream`, não `invoke`, e SEMPRE — não só quando alguém observa.
    #
    # O argumento é mais forte do que "os dois convergem": `Pregel.invoke` É este laço.
    # Por dentro ele chama `self.stream(..., stream_mode=["updates","values"])` e
    # devolve o último `values`. Não há dois motores a manter em sincronia; há um, e
    # antes só se descartava o progresso que ele já emitia.
    #
    # Uma diferença sobra, e está tratada abaixo: `invoke` retira `__interrupt__` do
    # fluxo de updates e o funde no retorno. Este laço filtra a chave; fundi-la não é
    # preciso enquanto o grafo da decisão não tiver checkpointer.
    #
    # Zero mudança nos nós: `updates` dá o nome do que terminou, `values` dá o estado
    # acumulado, e o último deles é o retorno.
    entrada = {
        "data_referencia": hoje,
        "estado": Estado.EM_ANDAMENTO,
        "prontos": {},
        "degradacoes": [],
    }
    final: dict[str, Any] = {}
    # Os nós concluídos esperam o `values` seguinte antes de serem anunciados.
    #
    # O LangGraph emite `updates` ANTES do `values` do mesmo passo, então anunciar na
    # hora reportaria cada nó com o estado de ANTES dele — o `coletor_interno` saía com
    # zero etapas prontas, e a tela mostraria sempre um passo atrás. Medido na primeira
    # execução instrumentada; a defasagem não aparece em teste de topologia porque lá
    # ninguém olha os `prontos`.
    pendentes: list[str] = []
    for modo, pedaco in grafo.stream(entrada, stream_mode=["updates", "values"]):
        if modo == "values":
            final = pedaco
            # Rodada AMOSTRAL nunca é COMPLETA — decisão do runner, como o modo seco: a
            # amostragem é fiação, o grafo não a conhece. Aplicado AQUI, a cada estado
            # emitido, e não só no fim: quem observa (`ao_terminar_no`) vê o mesmo estado
            # que o Registro, o log e o arquivo de resultado vão dizer.
            final["estado"] = _estado_da_entrega(final.get("estado"), amostral=amostral)
            # Para o resumo por nó (`executar/resumos.py`): o emissor nasce em `main`,
            # antes de o recorte existir, então a contagem viaja no estado observado.
            final["recorte_amostral"] = None if recorte is None else len(recorte)
            # Quais nós saem juntos deste `values`: no fan-out são dois, e a ordem entre
            # eles é a de conclusão das threads — o resumo atribui as degradações do
            # passo ao par, não ao que terminou primeiro.
            final["nos_do_passo"] = list(pendentes)
            if ao_terminar_no is not None:
                for no in pendentes:
                    ao_terminar_no(no, final)
                pendentes.clear()
        else:
            # Chaves com `__` não são nós: o LangGraph usa `__interrupt__` para as
            # interrupções, e `invoke` a retira do estado antes de devolver. Este laço
            # não a retira, então sem o filtro ela sairia no NDJSON como se um nó
            # chamado `__interrupt__` tivesse terminado. Não alcançável hoje — o grafo
            # da decisão não tem checkpointer e não chama `interrupt()`, que vive só no
            # grafo separado da aprovação —, e é por isso que custa uma linha agora.
            pendentes.extend(no for no in pedaco if not no.startswith("__"))
    if ao_terminar_no is not None:
        # O que sobrar não teve `values` depois — anuncia com o último estado conhecido,
        # senão o nó final sumiria da tela justamente quando ela é mais consultada.
        final["nos_do_passo"] = list(pendentes)
        for no in pendentes:
            ao_terminar_no(no, final)

    # `estado_da_rodada`, não `estado`: neste módulo `estado` é o dicionário do grafo
    # (o parâmetro dos nós), e reusar o nome para o enum faria as duas coisas terem o
    # mesmo nome no mesmo arquivo.
    estado_da_rodada = final.get("estado")
    if estado_da_rodada == Estado.ABORTADA:
        # Sem estoque (ou veto do crivo) não há entrega: Spec §7.2, "não há entrega;
        # sem estoque não há decisão possível". A ausência é declarada por log,
        # Registro e aviso — o aviso importa: no disco, uma sexta abortada seria
        # indistinguível de uma máquina desligada.
        avisar(f"rodada de sexta ABORTADA: {final.get('motivo_aborto') or 'motivo não informado'}")
        return final, None

    resultado = final.get("resultado")
    if resultado is None:
        # Estado não-abortado sem resultado é incoerência: o nó de registro já rodou.
        # Sair 0 aqui diria ao agendador que a sexta entregou.
        raise RuntimeError(f"rodada terminou {estado_da_rodada} sem resultado — nada a entregar")

    if not dry_run:
        try:
            caminhos = escrever_planilha(
                final["resultado"],
                parametros,
                destino_da_rodada,
                notas_coleta=notas_da_planilha(
                    parametros,
                    estado_da_rodada,
                    [
                        *final.get("degradacoes", []),
                        # A MESMA lista que foi para o motivo gravado no Registro.
                        *limitacoes_da_fiacao(
                            parametros,
                            final.get("janelas_lidas"),
                            recorte=recorte,
                            candidatos=_contagem(final.get("candidatos")),
                        ),
                    ],
                    data_referencia=hoje,
                    vendas_descartadas=cache_vendas[0][1] if cache_vendas else None,
                    taxa_amarracao=final.get("externo_taxa_amarracao"),
                    idade_dias=final.get("externo_idade_dias"),
                    posicoes_vazias=resultado.relaxamento.deficit_restante,
                    posicoes_preenchidas=(
                        len(resultado.alocacao.super_destaque)
                        + len(resultado.alocacao.destaque)
                        + len(resultado.relaxamento.recuperados)
                    ),
                ),
                perfis=tuple(final.get("perfis") or ()),
                # O histórico CRU e o limiar, para a coluna que os critérios de aceite
                # do PRD exigem. `None` já significa "não consultado" na origem — sem
                # guarda aqui, porque duas chaves permitiam a combinação incoerente
                # (mapa vazio marcado como consultado) que produzia justamente a
                # afirmação falsa que a coluna existe para eliminar.
                historico_janelas=final.get("historico_janelas"),
                resultado_esperado=parametros.resultado_esperado,
                # O sexto arquivo: uma linha por candidato, inclusive os excluídos, com o
                # que o estado da rodada já carrega — nada é relido do banco aqui.
                contexto=ContextoApuracao(
                    candidatos=final.get("candidatos") or (),
                    dims=final.get("dims") or {},
                    penalizaveis=final.get("penalizaveis") or {},
                    anuncios=final.get("anuncios_por_imovel") or {},
                    externo_entrou=bool(final.get("externo_presente")),
                ),
            )
        except Exception as e:
            # A rodada JÁ está no Registro: avisa que a planilha não saiu e propaga.
            # Quem opera precisa saber que existe rodada gravada sem artefato — não
            # é uma sexta que não aconteceu.
            avisar(
                f"Rodada {capturado[-1] if capturado else '?'} gravada, mas a PLANILHA "
                f"não foi escrita: {type(e).__name__}"
            )
            raise SinkFalhou("falha ao escrever a planilha") from e
        log.info("planilha escrita: %s", ", ".join(p.name for p in caminhos))
    else:
        log.info("[dry-run] planilha NÃO escrita")

    return final, capturado[-1] if capturado else None


def construir_parser() -> argparse.ArgumentParser:
    """Público para que o teste leia os DEFAULTS daqui em vez de redigitá-los — um
    teste que reafirma o literal que ele mesmo escreve continua verde com o default
    trocado, e foi o que aconteceu com `--destino`."""
    p = argparse.ArgumentParser(description="Rodada de sexta (decisão)")
    p.add_argument(
        "--parametros",
        type=Path,
        help="TOML com parâmetros declarados para ESTA rodada, por cima dos adotados "
        "(D-034). Ausente, a rodada usa só os adotados; a régua de resultado (nº 14) "
        "segue nula. Modelo em docs/.",
    )
    p.add_argument(
        "--externo",
        type=Path,
        help="pasta de saída do raspador (out/). Ausente, a nota do portal "
        "não entra e a rodada sai DEGRADADA nesse fator, com a limitação declarada.",
    )
    p.add_argument(
        "--recorte-pela-raspagem",
        action="store_true",
        help="rodada AMOSTRAL: o universo de candidatos passa a ser só o que a raspagem "
        "em --externo amarrou. Serve para ver a corrente inteira funcionar com poucos "
        "imóveis e o fator de portal entrando de verdade. A amostra é declarada na "
        "planilha e no Registro, a rodada nunca sai COMPLETA, e rodada-aprovar a recusa: "
        "não é decisão sobre o estoque e não pode virar carga. Exige --externo.",
    )
    p.add_argument("--destino", type=Path, default=Path("saida/sexta"))
    p.add_argument("--dry-run", action="store_true", help="não grava nem escreve nada")
    p.add_argument(
        "--eventos",
        type=Path,
        help="arquivo NDJSON com uma linha por nó do grafo concluído. Contrato de "
        "ARQUIVO, no mesmo idioma do status.json do raspador: sobrevive à morte de "
        "quem observa e é inspecionável à mão.",
    )
    p.add_argument(
        "--resultado",
        type=Path,
        help="arquivo JSON com o desfecho da rodada, escrito em TODOS os caminhos de "
        "saída. É por aqui que o `rodada_id` chega a quem disparou — a alternativa "
        "seria parsear a prosa do log, que muda sem aviso.",
    )
    p.add_argument(
        "--hoje",
        type=date.fromisoformat,
        help="data de referência (AAAA-MM-DD); default é hoje. Governa a regra de "
        "atualização em 90 dias e a idade aceitável da coleta. ATENÇÃO: NÃO retrocede "
        "a rodada inteira — as janelas de 30 dias do gestor e as vendas de 180 dias "
        "saem de NOW() no SQL, então reprocessar uma sexta antiga mistura "
        "elegibilidade datada no passado com produtividade e perfis de hoje.",
    )
    return p


def _emissor_de_eventos(caminho: Path | None) -> Callable[[str, Mapping[str, Any]], None] | None:
    """Uma linha JSON por nó concluído, com `flush` a cada uma.

    Sem o flush, o buffer só desceria ao fim da rodada — e a tela de acompanhamento
    existe para mostrar o que acontece AGORA. Nome do nó, instante, os prontos e o
    RESUMO do agente (`executar/resumos.py`: só contagens, rótulos e limitações):
    nada do estado em si, que carrega objetos de domínio e dados do Newcore.

    **Limitação em fan-out, e ela é do `momento`, não dos `prontos`.**
    `analista_perfil` e `coletor_externo` terminam no MESMO superstep do LangGraph, e
    o estado acumulado só chega depois dos dois. Os `prontos` reportados são reais —
    ambos terminaram mesmo —, mas o `momento` é o instante em que o MAIS LENTO
    terminou, atribuído igualmente ao mais rápido. Hoje os dois são rápidos (o coletor
    externo apenas LÊ um arquivo já raspado; a raspagem acontece fora da rodada), então
    o efeito é imperceptível. Deixa de ser se um deles ficar lento: o rápido apareceria
    como não-pronto durante toda a espera do outro, e os dois saltariam juntos — o
    oposto de "ao vivo". Emitir por nó exigiria `stream_mode="updates"` sozinho e
    reconstruir o estado à mão, o que troca uma imprecisão de carimbo por uma segunda
    fonte de verdade sobre os prontos. Fica assim, e escrito.
    """
    if caminho is None:
        return None
    caminho.parent.mkdir(parents=True, exist_ok=True)
    # Começa limpo. O arquivo é aberto em modo de acréscimo a cada linha, e o desfecho
    # (`--resultado`) trunca — assimetria que hoje é inofensiva porque nenhum trabalho
    # roda duas vezes. Deixa de ser no dia em que houver recuperação de trabalho órfão:
    # o NDJSON da segunda tentativa concatenaria no da primeira, e o progresso da tela
    # andaria PARA TRÁS, contra a monotonicidade que um teste desta fatia exige.
    caminho.unlink(missing_ok=True)
    atribuidor = AtribuidorDeDegradacoes()

    def emitir(no: str, estado: Mapping[str, Any]) -> None:
        # O relatório do agente: contado a partir do estado, nunca escrito pelo nó.
        # Só contagens e limitações — nada do estado em si, que carrega objetos de
        # domínio e dados do Newcore (ver `executar/resumos.py`).
        # Fora do `try`: as degradações do passo não podem sumir do relatório porque o
        # resumo daquele nó falhou.
        novas = atribuidor.novas(estado, no)
        try:
            resumo = resumo_do_no(
                no,
                estado,
                degradacoes_novas=novas,
                recorte_amostral=estado.get("recorte_amostral"),
            )
        except Exception as e:  # noqa: BLE001 — o relatório é conveniência; a rodada é o trabalho
            # Declarado, não silencioso: a tela mostra que o resumo deste nó não saiu e
            # por que tipo de erro. Só o TIPO — a mensagem poderia ecoar dado do estado.
            resumo = {"indisponivel": type(e).__name__, "degradacoes": novas}
        linha = {
            "momento": datetime.now().isoformat(timespec="seconds"),
            "no": no,
            "prontos": dict(estado.get("prontos") or {}),
            "resumo": resumo,
        }
        with caminho.open("a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")
            f.flush()

    return emitir


def _escrever_resultado(
    caminho: Path | None,
    *,
    codigo: int,
    estado: object = None,
    rodada_id: int | None = None,
    falha: str | None = None,
) -> None:
    """O desfecho, em TODOS os caminhos de saída — inclusive os de falha.

    É assim que o `rodada_id` chega a quem disparou. A alternativa seria parsear a
    frase "rodada de decisão gravada no Registro: id=N" do log, que muda sem aviso e
    faria uma mudança de redação virar defeito de integração. E é o único jeito de
    uma rodada ABORTADA ser contada: ela não deixa NENHUMA linha no Registro.

    `falha` carrega só o TIPO da exceção, nunca a mensagem: a mensagem pode ecoar
    dado do Newcore, e este arquivo é lido por outro processo e mostrado numa tela.
    """
    if caminho is None:
        return
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps(
            {
                "codigo": codigo,
                "estado": str(estado) if estado is not None else None,
                "rodada_id": rodada_id,
                "falha": falha,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    # Ambiente do `.env` do diretório CORRENTE — ver o docstring de config.ambiente.
    carregar_env()
    p = construir_parser()
    args = p.parse_args(argv)
    if args.hoje and args.hoje > date.today():
        # Escreve ANTES do `p.error`, que sai por SystemExit(2) sem passar por nenhum
        # `return`. Sem isto, a guarda estrutural abaixo ficaria com o nome mentindo:
        # ela casa `return`, e este caminho não é um. Teste cujo nome afirma mais do
        # que ele checa é o que deixa a próxima lacuna passar.
        _escrever_resultado(args.resultado, codigo=2, falha="HojeNoFuturo")
        p.error("--hoje no futuro decidiria sobre um estoque que ainda não existe")
    if args.recorte_pela_raspagem and args.externo is None:
        _escrever_resultado(args.resultado, codigo=2, falha="RecorteSemExterno")
        p.error(
            "--recorte-pela-raspagem exige --externo: o recorte É a lista de imóveis que a "
            "raspagem trouxe, e sem a pasta dela não há de onde lê-la"
        )
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.parametros is not None and args.parametros.resolve() == MODELO_DE_DOCS:
        # O modelo carrega com sucesso e mora no repositório: sem esta recusa, sairia
        # dele uma planilha completa, de aparência normal, construída sobre números
        # que o próprio arquivo declara ilustrativos.
        log.error(
            "%s é o MODELO ilustrativo, não uma declaração de parâmetros. Copie-o para "
            "fora do repositório e substitua os valores antes de rodar.",
            args.parametros,
        )
        _escrever_resultado(args.resultado, codigo=5, falha="ModeloComoEntrada")
        return 5

    try:
        parametros = carregar(args.parametros)
    except (ParametroAusente, ParametroInvalido) as e:
        # Código próprio: nada rodou e nada foi tocado. É o arquivo de quem opera,
        # corrigível em segundos — não é incidente, e tratá-lo como falha de fonte
        # mandaria alguém investigar o Newcore por causa de um typo no TOML.
        log.error("parâmetros da rodada: %s", e)
        _escrever_resultado(args.resultado, codigo=5, falha=type(e).__name__)
        return 5
    except OSError as e:
        log.error("não foi possível ler %s: %s", args.parametros, e)
        _escrever_resultado(args.resultado, codigo=5, falha=type(e).__name__)
        return 5

    try:
        final, rodada_id = executar(
            args.destino,
            parametros,
            externo=args.externo,
            hoje=args.hoje,
            dry_run=args.dry_run,
            recorte_pela_raspagem=args.recorte_pela_raspagem,
            ao_terminar_no=_emissor_de_eventos(args.eventos),
        )
    except SinkFalhou as e:
        log.error("%s (detalhe no log do servidor)", e)
        log.debug("causa completa", exc_info=True)
        _escrever_resultado(args.resultado, codigo=1, falha=type(e).__name__)
        return 1
    except RecorteVazio as e:
        # Mesmo código de "estoque vazio": é insumo ausente, não incidente. A mensagem
        # é segura para fora — só contagens, estado e o caminho local da raspagem.
        log.error("%s", e)
        _escrever_resultado(args.resultado, codigo=4, falha=type(e).__name__)
        return 4
    except Exception as e:
        # Falha de FONTE (Newcore fora, saída do raspador ilegível) ou incoerência da
        # rodada. Só o tipo para fora: a mensagem pode ecoar dado do banco.
        log.error("falha ao coletar ou decidir: %s (detalhe no log do servidor)", type(e).__name__)
        log.debug("causa completa", exc_info=True)
        _escrever_resultado(args.resultado, codigo=3, falha=type(e).__name__)
        return 3

    estado = final.get("estado")
    log.info("ESTADO DA RODADA: %s", str(estado).upper())
    for d in final.get("degradacoes", []):
        log.info("  limitação: %s", d)
    if final.get("motivo_aborto"):
        log.info("  motivo do aborto: %s", final["motivo_aborto"])

    if estado == Estado.ABORTADA:
        # ABORTADA tem duas causas de gravidade OPOSTA e o agendador precisa
        # distingui-las. Estoque vazio é insumo ausente (benigno, código 4). Veto do
        # crivo é a auditoria apanhando violação de cota, de piso ou de relaxamento em
        # super destaque — invariantes 6 e 7 — e sai com código PRÓPRIO: sob um código
        # só, uma violação de invariante chegaria ao monitoramento com a mesma cara de
        # "não havia imóvel para decidir", e ninguém iria olhar.
        codigo = 6 if final.get("prontos", {}).get("crivo") is False else 4
        _escrever_resultado(args.resultado, codigo=codigo, estado=estado)
        return codigo
    if rodada_id is not None:
        log.info(
            "rodada %s pendente de APROVAÇÃO (D-001) — o prazo da tácita é o parâmetro "
            "nº 10, nulo; quem o define abre o fluxo de aprovação com este id",
            rodada_id,
        )
    _escrever_resultado(args.resultado, codigo=0, estado=estado, rodada_id=rodada_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
