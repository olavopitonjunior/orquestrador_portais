"""O contrato do TOML da rodada, em forma de dado — para o formulário do console.

O console precisa saber, por campo: o tipo, a faixa, as escolhas fechadas, se é
obrigatório, de qual parâmetro pendente ele é, e o que explicar ao dono. Tudo isso
já existe em `config.parametros`, mas espalhado entre validadores, dataclasses de
domínio e mensagens de erro — nada que TypeScript consiga ler.

**Por que não é derivado por introspecção.** As faixas moram em `__post_init__` de
dataclasses de domínio (`PesosNivel`, `IntensidadesPenalidade`,
`ParametrosSemelhanca`) e em `if`s dos leitores. Extrair isso por reflexão exigiria
executar cada validação com valores-sonda e inferir a fronteira — frágil, e o
resultado ainda seria um palpite sobre a intenção. Aqui os limites estão escritos.

**Então o que impede a divergência?** Não é atenção: é
`tests/test_contrato.py`, que monta um TOML A PARTIR DESTE CONTRATO e exige que
`carregar()` o aceite; e que, para cada campo obrigatório, o remove e exige
`ParametroAusente`. Acrescentar chave ao carregador sem acrescentar aqui quebra o
teste. Descrever aqui um campo que o carregador ignora, também.

**O que este módulo NÃO faz:** não traz valor nenhum. Nem default, nem sugestão,
nem exemplo numérico. Catorze dos quinze parâmetros são nulos e o CLAUDE.md proíbe
preenchê-los — um "valor de exemplo" viajando até um campo de formulário é
exatamente como um número inventado entra numa planilha aprovada.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from config.parametros import PENDENTE_DE
from dados.coletor_externo import CLIQUES

Tipo = Literal["inteiro", "numero", "escolha"]


@dataclass(frozen=True)
class Campo:
    """Um campo do TOML, descrito para quem for renderizá-lo.

    `minimo_aberto` existe porque a diferença importa: `decaimento` em (0, 1] recusa
    zero, `desconto_fragil` em [0, 1] aceita. Um formulário que trate as duas como
    "entre 0 e 1" deixa passar um valor que o carregador recusa — e o dono descobre
    isso depois de submeter, não enquanto digita.
    """

    caminho: str
    tipo: Tipo
    ajuda: str
    # A seção do formulário (id de um `Grupo`): a função do campo na cadeia da decisão.
    grupo: str
    obrigatorio: bool = True
    minimo: float | None = None
    maximo: float | None = None
    minimo_aberto: bool = False
    escolhas: tuple[str, ...] | None = None
    # (caminho, valor): o campo só existe quando aquele outro tiver aquele valor.
    exige: tuple[str, str] | None = None
    # Rótulo do parâmetro pendente, vindo de `PENDENTE_DE` — nunca redigitado.
    pendencia: str | None = None


Funcao = Literal[
    "contrato",
    "excludente",
    "condicao_de_nivel",
    "relaxamento",
    "classificador",
    "desconto",
    "operacao",
]
Fonte = Literal["contrato", "banco_imovel", "banco_corretor", "raspagem", "registro"]


@dataclass(frozen=True)
class Grupo:
    """Uma seção do formulário, agrupada pela pergunta que responde.

    A ordem é de LEITURA, não de execução: primeiro quem entra (contrato, exclusões,
    condição de nível e a cedência que as relaxa), depois como se ordena
    (classificadores, pesos, normalização), depois o que desconta, depois o que
    governa a execução. Na cadeia real (invariante 4) o relaxamento é o último passo
    e a condição de nível é aplicada na alocação — aqui ficam junto das regras que
    relaxam e qualificam, porque é assim que se lê o critério.

    A estrutura do formulário cresce no GRUPO, não no campo: o dono pediu para saber
    "para que serve cada coisa", e a resposta é a função da seção na cadeia (contrato,
    excludente, condição de nível, relaxamento, classificador, desconto, operação) e a
    fonte do dado que ela consome. Cada campo aponta para o seu grupo (`Campo.grupo`); o
    console não tem taxonomia própria — tinha (`TITULO_DA_SECAO` + `secaoDe`), e duas
    taxonomias divergem.

    `fixos_no_codigo` são as regras da seção que hoje são constantes (PRD, Spec §6):
    texto de exibição dos valores adotados, para o dono ver o critério inteiro, não só
    a parte parametrizável. `pendentes_sem_campo` são os números dos parâmetros
    pendentes da tabela do CLAUDE.md que caem nesta seção e ainda NÃO têm campo no
    TOML — permanecem nulos; a seção diz isso em vez de sumir.
    """

    id: str
    ordem: int
    titulo: str
    funcao: Funcao
    fontes: tuple[Fonte, ...]
    explicacao: str
    fixos_no_codigo: tuple[str, ...] = ()
    pendentes_sem_campo: tuple[int, ...] = ()


GRUPOS: tuple[Grupo, ...] = (
    Grupo(
        id="contrato",
        ordem=1,
        titulo="Contrato com o portal",
        funcao="contrato",
        fontes=("contrato",),
        explicacao=(
            "As posições pagas que a decisão preenche. As cotas são teto rígido: nenhuma "
            "posição além delas é proposta (invariante 6). Hoje moram no código e na "
            "restrição do Registro; a noção de CONTRATO como dado vem em fatia própria."
        ),
        fixos_no_codigo=(
            "475 posições de super destaque e 6.495 de destaque — plano Exclusivo do Grupo "
            "OLX (OLX, Zap e Viva Real)",
        ),
    ),
    Grupo(
        id="excluidos_pelo_imovel",
        ordem=2,
        titulo="Excluídos pelo imóvel",
        funcao="excludente",
        fontes=("banco_imovel",),
        explicacao=(
            "Regras eliminatórias, binárias e sem compensação, sobre o cadastro do imóvel: "
            "reprovar em uma basta, e nenhuma nota recupera (Spec §6.1). Imóvel sem "
            "avaliação por categoria não é excluído — passa e recebe penalidade."
        ),
        fixos_no_codigo=(
            "Status: publicação ativa",
            "Categoria: Casa, Casa de condomínio, Sobrado, Cobertura ou Apartamento",
            "Preço igual ou superior a R$ 300.000",
            "Dez fotos ou mais",
            "Atualizado nos últimos 90 dias",
            "Cadastro completo: nenhuma das sete categorias da nota interna com valor zero",
        ),
    ),
    Grupo(
        id="excluidos_pelo_corretor",
        ordem=3,
        titulo="Excluídos pelo corretor",
        funcao="excludente",
        fontes=("banco_corretor",),
        explicacao=(
            "As duas regras que olham para quem cuida do imóvel, não para o imóvel. A "
            "definição de corretor ATIVO é decisão do dono, não detalhe de operação: mudá-la "
            "muda quem é elegível (D-015). O distrito vem da tabela analítica de relação de "
            "imóveis, não do endereço (zona de valor nula em 98% dos casos)."
        ),
        fixos_no_codigo=(
            "Gestor produtivo: captou ou vendeu nos últimos 30 dias",
            "Capacidade do distrito: dois ou mais corretores que captaram ou venderam nos "
            "últimos 30 dias",
        ),
    ),
    Grupo(
        id="condicao_de_nivel",
        ordem=4,
        titulo="Condição de nível",
        funcao="condicao_de_nivel",
        fontes=("banco_imovel",),
        explicacao=(
            "O que separa candidato ao super destaque do restante. Aplicada na alocação, não "
            "elimina do destaque (D-002)."
        ),
        fixos_no_codigo=(
            "Preço igual ou superior a R$ 700.000 para candidatura ao super destaque",
        ),
    ),
    Grupo(
        id="relaxamento",
        ordem=5,
        titulo="Relaxamento",
        funcao="relaxamento",
        fontes=("banco_imovel", "banco_corretor"),
        explicacao=(
            "Cedência controlada das regras eliminatórias, só nas posições de destaque, para "
            "não deixar benefício pago sem uso. Cada degrau cedido gera linha no relatório "
            "(Spec §6.6). As posições de super destaque nunca relaxam (invariante 7). "
            "Referência do quanto cada degrau recupera, medida na base e só como ordem de "
            "grandeza (medida com mínimo de TRÊS corretores por distrito; o adotado é dois): "
            "fotos ~133, cadastro ~569, atualização ~1.680, gestor ~1.747, distrito ~5.686."
        ),
        fixos_no_codigo=(
            "Ordem de cedência: fotos → cadastro completo → atualização em 90 dias → gestor "
            "produtivo → capacidade do distrito",
        ),
    ),
    Grupo(
        id="classificador_banco_imovel",
        ordem=6,
        titulo="Classificadores pelo banco: o imóvel (F1 e F2)",
        funcao="classificador",
        fontes=("banco_imovel",),
        explicacao=(
            "F1, semelhança com o perfil de conversão: combinações de características que "
            "venderam nos últimos 180 dias, analisadas uma ou duas dimensões por vez, cada uma "
            "com o número de vendas que a sustenta (Spec §6.2). F2, leads que o imóvel já "
            "atraiu em 180 dias."
        ),
        fixos_no_codigo=(
            "Entrada do perfil: vendas assinadas nos últimos 180 dias",
            "Evidência mínima por combinação: N ≥ 3 (D-014); abaixo disso o perfil é frágil",
            "Ordem das dimensões do F1: preço > localização > metragem > dormitórios > vagas "
            "(D-017); só a magnitude do decaimento é parâmetro",
            "F2: leads contados em 180 dias",
        ),
    ),
    Grupo(
        id="classificador_banco_corretor",
        ordem=7,
        titulo="Classificador pelo banco: o corretor (F4)",
        funcao="classificador",
        fontes=("banco_corretor",),
        explicacao=(
            "F4, produtividade do gestor nos últimos 30 dias, contínua: taxa semanal de "
            "captação mais a marca de venda recente (D-017). Não confundir com a regra "
            "binária 'gestor produtivo', que é eliminatória."
        ),
        fixos_no_codigo=(
            "Janela de 30 dias",
            "A base não expõe contagem de vendas em 30 dias: a venda entra como marca "
            "(sim/não) — limitação declarada na planilha",
        ),
    ),
    Grupo(
        id="classificador_raspagem",
        ordem=8,
        titulo="Classificador pela raspagem: o portal (F3)",
        funcao="classificador",
        fontes=("raspagem",),
        explicacao=(
            "F3, desempenho do anúncio no Canal Pro, lido da coleta feita antes da rodada. "
            "Só entra se a coleta estiver ok, amarrada acima do limiar e dentro da idade "
            "máxima; senão o fator não entra e a rodada sai degradada, com o motivo "
            "declarado. A forma do sinal é escolha sua com pendência aberta (P-15 em "
            "docs/perguntas-abertas.md): na primeira raspagem real, visualizações vieram "
            "zeradas e cliques quase todos zero."
        ),
    ),
    Grupo(
        id="mistura_por_nivel",
        ordem=9,
        titulo="Mistura por nível: os pesos",
        funcao="classificador",
        fontes=(),
        explicacao=(
            "Como os quatro fatores se combinam numa nota, por nível. Os níveis perseguem "
            "objetivos diferentes, e essa assimetria é a parte do modelo a preservar. Os "
            "pesos da Spec §6.3 (60/25/15 e 80/10/10) foram anulados pelo redesenho D-017."
        ),
        fixos_no_codigo=(
            "Objetivo do super destaque: valor esperado (probabilidade de conversão ponderada "
            "pelo ticket)",
            "Objetivo do destaque: probabilidade de gerar lead",
        ),
    ),
    Grupo(
        id="normalizacao",
        ordem=10,
        titulo="Normalização dos fatores",
        funcao="classificador",
        fontes=(),
        explicacao=(
            "Como cada fator vai para uma escala comparável antes da mistura (Spec §6.3). "
            "Não há campo no TOML: a forma em uso é a provisória da planilha-piloto, "
            "rotulada como tal, e o parâmetro segue nulo."
        ),
        pendentes_sem_campo=(2,),
    ),
    Grupo(
        id="descontos",
        ordem=11,
        titulo="Descontos: as três penalidades",
        funcao="desconto",
        fontes=("registro", "banco_imovel"),
        explicacao=(
            "Descontadas da nota final e sempre visíveis na planilha (Spec §6.4). Imóvel sem "
            "histórico de destaque não é penalizado por ausência de histórico."
        ),
        fixos_no_codigo=(
            "Janela anterior sem resultado: ocupou posição e não atingiu o resultado esperado "
            "do nível; decai ao longo dos ciclos",
            "Sem avaliação por categoria",
            "Sem lead em 180 dias",
        ),
    ),
    Grupo(
        id="historico",
        ordem=12,
        titulo="Histórico das janelas",
        funcao="desconto",
        fontes=("registro",),
        explicacao=(
            "O que conta como resultado de uma janela paga, por nível. Sem os dois valores "
            "nenhuma janela é julgada e a planilha declara isso — não penalizar por falta de "
            "régua não é o mesmo que passar no critério (D-022)."
        ),
    ),
    Grupo(
        id="cadencia",
        ordem=13,
        titulo="Cadência",
        funcao="operacao",
        fontes=(),
        explicacao=(
            "Sexta decide; segunda acompanha. Não existe execução diária. A hora exata de "
            "cada rodada é parâmetro pendente, sem campo aqui."
        ),
        fixos_no_codigo=(
            "Sexta-feira: rodada de decisão, a única que raspa o portal (uma tentativa)",
            "Segunda-feira: acompanhamento, lê só o banco",
        ),
        pendentes_sem_campo=(8,),
    ),
    Grupo(
        id="operacao",
        ordem=14,
        titulo="Operação",
        funcao="operacao",
        fontes=(),
        explicacao=(
            "O que governa a execução, não a lista: repetição do Orquestrador, sinalização de "
            "variação de volume, retenção do Registro, aprovação tácita, atendimento de lead "
            "e a saída por alteração de preço (§6.7). Nenhum tem campo ainda; todos seguem "
            "nulos."
        ),
        fixos_no_codigo=(
            "Saída imediata fora do ciclo: venda, reserva, despublicação ou alteração "
            "relevante de preço (§6.7)",
            "Aprovação humana antes da carga (D-001); nenhuma aprovação automática enquanto "
            "o prazo tácito é nulo",
        ),
        pendentes_sem_campo=(4, 6, 9, 10, 11, 15),
    ),
)

_IDS_DE_GRUPO = frozenset(g.id for g in GRUPOS)


def _pendencia(caminho: str) -> str | None:
    """O rótulo humano do parâmetro pendente, tal como o carregador o reporta.

    Lê `PENDENTE_DE` em vez de repetir o texto: é o mesmo mapa que compõe a mensagem
    `falta X — parâmetro pendente nº N`, então o formulário e o erro falam igual.
    Nem todo campo tem pendência (`semelhanca.desconto_fragil` é provisório sem
    número, `externo.desempenho.forma` idem) — daí o None.

    Busca por PREFIXO porque `PENDENTE_DE` é indexado ora pela folha
    (`intensidades.janela_sem_resultado`), ora pelo nó (`pesos.super_destaque`, que
    cobre os quatro fatores abaixo dele). Sem o passeio, os oito pesos ficariam sem
    rótulo — ou, pior, cada folha precisaria repetir à mão de qual nó ela herda.
    """
    partes = caminho.split(".")
    for corte in range(len(partes), 0, -1):
        rotulo = PENDENTE_DE.get(".".join(partes[:corte]))
        if rotulo is not None:
            return rotulo
    return None


def _campo(caminho: str, tipo: Tipo, ajuda: str, grupo: str, **resto: Any) -> Campo:
    """Fábrica única. Existe para que `pendencia` NÃO seja algo que se possa esquecer.

    A primeira versão deste módulo passava `pendencia=` à mão e só o fazia dentro do
    laço dos pesos: as catorze entradas literais saíam com `null`, e o formulário
    ficaria mudo sobre qual decisão pendente o dono está respondendo em dez dos vinte
    e dois campos. A ida e volta não via, porque o `caminho` estava certo. Derivar
    aqui torna o defeito irreproduzível.
    """
    if grupo not in _IDS_DE_GRUPO:
        raise ValueError(f"campo `{caminho}` aponta para grupo inexistente `{grupo}`")
    return Campo(
        caminho=caminho, tipo=tipo, ajuda=ajuda, grupo=grupo, pendencia=_pendencia(caminho), **resto
    )


_NIVEIS = ("super_destaque", "destaque")
_FATORES = (
    ("semelhanca_perfil", "Semelhança com o perfil de conversão (F1)"),
    ("leads_positivo", "Leads recebidos (F2)"),
    ("desempenho_proprio", "Desempenho de portal observado (F3)"),
    ("produtividade_gestor", "Produtividade do gestor do distrito (F4)"),
)


def _campos_de_pesos() -> list[Campo]:
    """Os oito pesos. Inteiros de VERDADE e somando 100 por nível.

    O tipo importa mais do que parece: o carregador usa `_inteiro`, que recusa
    `40.0`. JavaScript não distingue `40` de `40.0`, então o console precisa desta
    marcação para serializar sem casa decimal — sem ela, um formulário perfeitamente
    preenchido produz um TOML que o carregador rejeita com "esperava inteiro".
    """
    campos: list[Campo] = []
    for nivel in _NIVEIS:
        for fator, descricao in _FATORES:
            campos.append(
                _campo(
                    caminho=f"pesos.{nivel}.{fator}",
                    grupo="mistura_por_nivel",
                    tipo="inteiro",
                    ajuda=f"{descricao}. Os quatro pesos do nível somam exatamente 100.",
                    minimo=0,
                )
            )
    return campos


CAMPOS: tuple[Campo, ...] = (
    _campo(
        caminho="semelhanca.desconto_fragil",
        grupo="classificador_banco_imovel",
        tipo="numero",
        ajuda=(
            "Quanto vale um perfil FRÁGIL comparado a um robusto. A Spec §6.2 diz que "
            "perfil frágil 'não recebe peso pleno', sem quantificar. Fator que multiplica "
            "o número de vendas do perfil frágil: 0 o ignora, 1 o trata como robusto."
        ),
        minimo=0.0,
        maximo=1.0,
    ),
    _campo(
        caminho="semelhanca.decaimento",
        grupo="classificador_banco_imovel",
        tipo="numero",
        ajuda=(
            "Quanto o peso cai a cada degrau da ordem de dimensões adotada pela D-017 "
            "(preço > localização > metragem > dormitórios > vagas). A ORDEM é adotada; "
            "só esta magnitude é nula. Precisa ser menor que 1 para a ordem produzir "
            "efeito — foi a saturação por uma única dimensão (443 dos 475 super destaques "
            "puxados pelo mesmo perfil) que motivou a D-017."
        ),
        minimo=0.0,
        maximo=1.0,
        minimo_aberto=True,
    ),
    _campo(
        caminho="intensidades.janela_sem_resultado",
        grupo="descontos",
        tipo="numero",
        ajuda="Quanto desconta da nota ter tido janela de destaque anterior sem resultado.",
        minimo=0.0,
    ),
    _campo(
        caminho="intensidades.sem_avaliacao_por_categoria",
        grupo="descontos",
        tipo="numero",
        ajuda="Quanto desconta da nota não ter avaliação na categoria.",
        minimo=0.0,
    ),
    _campo(
        caminho="intensidades.sem_lead_180d",
        grupo="descontos",
        tipo="numero",
        ajuda="Quanto desconta da nota não ter recebido nenhum lead em 180 dias.",
        minimo=0.0,
    ),
    _campo(
        caminho="decaimento_janela.forma",
        grupo="descontos",
        tipo="escolha",
        ajuda=(
            "Como a penalidade por janela anterior decai ao longo dos ciclos (Spec §6.4). "
            "Uma forma só: geométrica."
        ),
        escolhas=("geometrica",),
    ),
    _campo(
        caminho="decaimento_janela.razao",
        grupo="descontos",
        tipo="numero",
        ajuda=(
            "Fator por ciclo: o desconto vale razao elevado ao número de ciclos desde a "
            "janela sem resultado mais recente. Razão 1 é aceita e significa NÃO decair — "
            "o que diverge da Spec §6.4, e a rodada declara essa divergência na planilha "
            "em vez de fingir que ela não existe."
        ),
        minimo=0.0,
        maximo=1.0,
        minimo_aberto=True,
    ),
    *_campos_de_pesos(),
    _campo(
        caminho="externo.limiar_amarracao",
        grupo="classificador_raspagem",
        tipo="numero",
        ajuda=(
            "Fração mínima dos candidatos que precisa ter anúncio correspondente na "
            "raspagem para o desempenho de portal ENTRAR no ranking. Abaixo dela o fator "
            "não entra e a rodada sai degradada, com o motivo declarado."
        ),
        minimo=0.0,
        maximo=1.0,
    ),
    _campo(
        caminho="externo.idade_maxima_dias",
        grupo="classificador_raspagem",
        tipo="inteiro",
        ajuda=(
            "Idade máxima aceitável da coleta externa, em dias, contada da data de "
            "referência da rodada. Mais velha que isso, o fator de portal não entra."
        ),
        minimo=0,
    ),
    _campo(
        caminho="externo.desempenho.forma",
        grupo="classificador_raspagem",
        tipo="escolha",
        ajuda=(
            "Como o sinal de desempenho é composto a partir do que a raspagem traz por "
            "anúncio. Cliques NUNCA são somados entre tipos: tipos diferentes medem "
            "intenções diferentes."
        ),
        escolhas=("visualizacoes", "nota", "cliques_do_tipo"),
    ),
    _campo(
        caminho="externo.desempenho.quando_ausente",
        grupo="classificador_raspagem",
        tipo="numero",
        ajuda=(
            "Valor do anúncio SEM nota. Obrigatório quando a forma é 'nota', e a escolha "
            "é declarada de propósito: um zero implícito puniria a ausência do dado como "
            "se fosse desempenho ruim."
        ),
        exige=("externo.desempenho.forma", "nota"),
    ),
    _campo(
        caminho="externo.desempenho.tipo",
        grupo="classificador_raspagem",
        tipo="escolha",
        ajuda="Qual clique conta como desempenho. Obrigatório quando a forma é 'cliques_do_tipo'.",
        escolhas=tuple(sorted(CLIQUES)),
        exige=("externo.desempenho.forma", "cliques_do_tipo"),
    ),
    _campo(
        caminho="resultado_esperado.super_destaque",
        grupo="historico",
        tipo="inteiro",
        ajuda=(
            "Quantos leads a janela de SUPER DESTAQUE precisa ter gerado para não ser "
            "penalizada (Spec §6.4). Seção OPCIONAL: omitida, o limiar é nulo, nenhuma "
            "janela é julgada e a planilha declara isso — porque não penalizar por falta "
            "de régua não é o mesmo que passar no critério. Se declarar, declare os DOIS "
            "níveis, e este precisa ser MAIOR que o de destaque."
        ),
        obrigatorio=False,
        minimo=1,
    ),
    _campo(
        caminho="resultado_esperado.destaque",
        grupo="historico",
        tipo="inteiro",
        ajuda=(
            "Quantos leads a janela de DESTAQUE precisa ter gerado para não ser "
            "penalizada. Ver a observação do nível acima: os dois, ou nenhum."
        ),
        obrigatorio=False,
        minimo=1,
    ),
)


TipoRegra = Literal["soma_igual", "todos_ou_nenhum", "maior_que"]


@dataclass(frozen=True)
class RegraCruzada:
    """Regra que nenhum campo isolado expressa. O formulário precisa delas para
    desabilitar o botão antes da submissão, em vez de deixar o dono descobrir pelo
    código de saída 5 depois de a rodada ser recusada.

    `tipo` e `valor` existem porque prosa não é executável. A primeira versão trazia
    só `descricao` e `campos` — e duas regras diferentes de `resultado_esperado`
    saíam com os MESMOS campos, distinguíveis apenas pelo texto. O console teria de
    reimplementar a semântica em TypeScript a partir de uma string, que é exatamente
    a duplicação que este módulo existe para evitar. Com o tipo, o formulário aplica
    a regra; a descrição vira o que ele MOSTRA quando ela é violada.
    """

    tipo: TipoRegra
    descricao: str
    campos: tuple[str, ...] = field(default_factory=tuple)
    # `soma_igual` usa como alvo; `maior_que` e `todos_ou_nenhum` ignoram.
    valor: int | None = None


REGRAS: tuple[RegraCruzada, ...] = (
    RegraCruzada(
        tipo="soma_igual",
        valor=100,
        descricao="Os quatro pesos de super_destaque somam exatamente 100.",
        campos=tuple(f"pesos.super_destaque.{f}" for f, _ in _FATORES),
    ),
    RegraCruzada(
        tipo="soma_igual",
        valor=100,
        descricao="Os quatro pesos de destaque somam exatamente 100.",
        campos=tuple(f"pesos.destaque.{f}" for f, _ in _FATORES),
    ),
    RegraCruzada(
        tipo="todos_ou_nenhum",
        descricao=(
            "A seção [resultado_esperado] é opcional, mas indivisível: ou os dois níveis, "
            "ou nenhum. Meio-declarada julgaria metade das janelas e deixaria a outra "
            "metade sem julgamento, com a planilha declarando limiar nulo numa rodada que "
            "penalizou parte do estoque."
        ),
        campos=("resultado_esperado.super_destaque", "resultado_esperado.destaque"),
    ),
    RegraCruzada(
        tipo="maior_que",
        descricao=(
            "resultado_esperado.super_destaque precisa ser MAIOR que destaque: o PRD fixa "
            "que o resultado esperado é proporcional ao nível."
        ),
        campos=("resultado_esperado.super_destaque", "resultado_esperado.destaque"),
    ),
)


def _json_puro(valor: Any) -> Any:
    """Tupla vira lista, recursivamente.

    JSON não tem tupla. Sem esta conversão, `contrato()` devolvia `("a", "b")` onde o
    arquivo relido devolve `["a", "b"]` — e a comparação com a cópia commitada falhava
    por diferença de TIPO, não de conteúdo. O passo de CI acusaria divergência sem que
    nada tivesse mudado, que é a pior espécie de portão: o que grita quando está tudo
    certo acaba desligado."""
    if isinstance(valor, tuple | list):
        return [_json_puro(v) for v in valor]
    if isinstance(valor, dict):
        return {k: _json_puro(v) for k, v in valor.items()}
    return valor


def contrato() -> dict[str, Any]:
    """O contrato inteiro, pronto para virar JSON — e comparável ao JSON relido.

    Ordem estável (a das tuplas acima) porque a saída é comparada contra a cópia
    commitada no console: ordem instável faria o passo de CI falhar sem que nada
    tivesse mudado de verdade.
    """
    return {
        # JSON não tem comentário, e o aviso de "arquivo gerado" só existe em módulos
        # Python que o próximo leitor pode nunca abrir. Editar a cópia à mão faz o
        # passo de CI reprovar sem dizer por quê; esta chave diz.
        "_gerado_por": "uv run rodada-contrato > console/lib/contrato-parametros.json",
        "grupos": [_json_puro(asdict(g)) for g in GRUPOS],
        "campos": [_json_puro(asdict(c)) for c in CAMPOS],
        "regras": [_json_puro(asdict(r)) for r in REGRAS],
    }
