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

from config.adotados import ADOTADOS
from config.parametros import PENDENTE_DE
from piloto.decisao import FORMAS_DE_ORDEM_SEM_PORTAL, FORMAS_SEM_ANUNCIO

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
    # A UNIDADE em que o dono lê o número (dias, pontos de 100, %, corretores, leads).
    # Nunca uma escala abstrata: é o que faz o campo ser julgável sem a Spec ao lado.
    unidade: str = ""
    # O valor ADOTADO (D-034) que a rodada usa se o campo não for declarado; None
    # para o que segue NULO. Vem de `config.adotados`, nunca redigitado aqui.
    adotado: int | float | str | None = None
    # Uma linha, no imperativo: o que muda se você AUMENTAR.
    se_aumentar: str = ""


Funcao = Literal["excludente", "classificatorio", "decisorio"]
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
    # ----------------------------------------------------------- QUEM ENTRA (o banco)
    Grupo(
        id="quem_entra_imovel",
        ordem=1,
        titulo="Quem entra: o imóvel",
        funcao="excludente",
        fontes=("banco_imovel",),
        explicacao=(
            "Estas regras excluem. Reprovar em uma basta, e nenhuma nota compensa (Spec §6.1). "
            "São seis, sobre o cadastro do imóvel, e todas seguem fixas: imóvel sem avaliação "
            "por categoria não é excluído — passa e recebe desconto."
        ),
        fixos_no_codigo=(
            "Publicação ativa",
            "Categoria: Casa, Casa de condomínio, Sobrado, Cobertura ou Apartamento",
            "Preço igual ou superior a R$ 300.000",
            "Dez fotos ou mais",
            "Atualizado nos últimos 90 dias",
            "Cadastro completo: nenhuma das sete categorias da nota interna com valor zero",
        ),
    ),
    Grupo(
        id="quem_entra_perfil",
        ordem=2,
        titulo="Quem entra: parece com o que vendeu",
        funcao="excludente",
        fontes=("banco_imovel",),
        explicacao=(
            "O perfil de conversão FILTRA (D-027): só entra quem se parece com o que vendeu "
            "na janela. Um perfil é uma combinação de uma ou duas características (região, "
            "faixa de preço, faixa de metragem, dormitórios, vagas) observada nas vendas "
            "assinadas; conta se tem pelo menos 3 vendas E contém a faixa de preço — sem "
            "essa exigência o filtro deixava passar 100% do estoque (medido em 04/09/2026). "
            "Com ela, passam 84% dos elegíveis e 64% dos candidatos ao super destaque. No "
            "destaque, é o PRIMEIRO degrau cedido pelo relaxamento quando faltam imóveis; "
            "no super destaque nunca cede."
        ),
        fixos_no_codigo=(
            "Evidência mínima por perfil: 3 vendas (D-014)",
            "O perfil precisa conter a faixa de preço (D-027)",
            "Entrada do perfil: só vendas assinadas — leads não entram, porque a base os traz "
            "pré-agregados em 180 dias e 'mais leads' sem régua seria regra inventada",
        ),
    ),
    Grupo(
        id="quem_entra_corretor",
        ordem=3,
        titulo="Quem entra: o corretor",
        funcao="excludente",
        fontes=("banco_corretor",),
        explicacao=(
            "As regras que olham para quem cuida do imóvel. 'Gestor produtivo' (captou ou "
            "vendeu em 30 dias) e 'capacidade do distrito' excluem. 'Gestor sem login' NÃO "
            "exclui — medido em 04/09/2026, quem não loga também não captou nem vendeu, "
            "então excluiria zero imóveis a mais; ele TRAVA o relaxamento: o degrau do gestor "
            "produtivo não traz de volta imóvel de gestor que nem entra no sistema (105 "
            "imóveis por rodada, D-029)."
        ),
        fixos_no_codigo=(
            "Gestor produtivo: captou ou vendeu nos últimos 30 dias — a janela NÃO é "
            "configurável: a base só traz a captação pré-agregada em 30 dias",
            "O distrito vem da tabela analítica de relação de imóveis, não do endereço",
        ),
    ),
    # ------------------------------------------------------- EM QUE ORDEM (o portal)
    Grupo(
        id="em_que_ordem_portal",
        ordem=4,
        titulo="Em que ordem: o portal",
        funcao="classificatorio",
        fontes=("raspagem",),
        explicacao=(
            "Estas não excluem ninguém: ordenam quem passou (D-028). A nota vai de 0 a 100 e "
            "é a soma ponderada de três sinais do anúncio no Canal Pro — nota do anúncio, "
            "cliques (somados entre tipos) e visualizações — cada um reescalado entre os "
            "elegíveis. Medido em 03/09/2026: visualizações vieram zero em 300 de 300 anúncios "
            "e só a nota tem variância; por isso o peso adotado das visualizações é zero, "
            "declarado. A raspagem só entra se cobrir a fração mínima dos candidatos e for "
            "recente; senão a ordem cai para o desempate de banco e a rodada declara isso."
        ),
        pendentes_sem_campo=(2,),
    ),
    Grupo(
        id="em_que_ordem_descontos",
        ordem=5,
        titulo="Em que ordem: os descontos",
        funcao="classificatorio",
        fontes=("registro", "banco_imovel"),
        explicacao=(
            "Três descontos, em pontos de 100, subtraídos da nota (Spec §6.4). O da janela "
            "anterior sem resultado só incide quando a régua de resultado por nível existir "
            "(nº 14, ainda nula) — até lá fica declarado como inerte. O de 'sem avaliação por "
            "categoria' é baixo de propósito: o pipeline de avaliação está morto desde "
            "16/10/2025 e quase todo o estoque novo não tem nota."
        ),
    ),
    # ------------------------------------------------------------ QUANTOS (o contrato)
    Grupo(
        id="quantos",
        ordem=6,
        titulo="Quantos e onde",
        funcao="decisorio",
        fontes=("contrato",),
        explicacao=(
            "As cotas contratadas são teto rígido (invariante 6). Primeiro o super destaque, "
            "entre quem tem preço acima do piso; depois o destaque, com o que sobrou. Se "
            "faltar imóvel no destaque, o relaxamento cede regras na ordem fixa; o super "
            "destaque nunca relaxa (invariante 7). A régua de resultado por nível (quantos "
            "leads uma janela paga precisa gerar para não ser descontada) segue nula por "
            "decisão do dono: 88% das janelas históricas geraram zero lead, e qualquer régua "
            "de 1 puniria quase todo mundo."
        ),
        fixos_no_codigo=(
            "475 posições de super destaque e 6.495 de destaque — plano Exclusivo do Grupo "
            "OLX (OLX, Zap e Viva Real)",
            "Piso de R$ 700.000 para candidatura ao super destaque (D-002)",
            "Ordem de cedência no destaque: perfil → fotos → cadastro completo → atualização "
            "em 90 dias → gestor produtivo (travado para gestor sem login) → capacidade do "
            "distrito",
        ),
    ),
    Grupo(
        id="operacao",
        ordem=7,
        titulo="Operação",
        funcao="decisorio",
        fontes=(),
        explicacao=(
            "O que governa a execução, não a lista: sexta decide e segunda acompanha (a hora "
            "é pendente); repetição do Orquestrador, sinalização de variação de volume, "
            "retenção do Registro, aprovação tácita, atendimento de lead e a saída por "
            "alteração de preço (§6.7). Nenhum tem campo; seguem nulos."
        ),
        fixos_no_codigo=(
            "Sexta-feira: rodada de decisão, a única que raspa o portal (uma tentativa); "
            "segunda-feira: acompanhamento, lê só o banco",
            "Aprovação humana antes da carga (D-001); nenhuma aprovação automática enquanto "
            "o prazo tácito é nulo",
        ),
        pendentes_sem_campo=(4, 6, 8, 9, 10, 11, 15),
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
        caminho=caminho,
        tipo=tipo,
        ajuda=ajuda,
        grupo=grupo,
        pendencia=_pendencia(caminho),
        adotado=ADOTADOS.get(caminho),
        **resto,
    )


CAMPOS: tuple[Campo, ...] = (
    # --- quem entra ----------------------------------------------------------------
    _campo(
        caminho="conversao.janela_dias",
        grupo="quem_entra_perfil",
        tipo="inteiro",
        ajuda=(
            "Olhamos para trás quantos dias para descobrir o que vende? A janela medida tem "
            "cerca de 180 vendas assinadas; em 30 dias seriam cerca de 25 — evidência de menos "
            "para sustentar perfis."
        ),
        unidade="dias",
        se_aumentar="Mais vendas sustentam os perfis, mas o padrão fica menos recente.",
        minimo=1,
    ),
    _campo(
        caminho="corretor.login_janela_dias",
        grupo="quem_entra_corretor",
        tipo="inteiro",
        ajuda=(
            "Gestor que não entra no sistema há mais dias que isto conta como 'sem login': o "
            "relaxamento não traz de volta os imóveis dele (D-029)."
        ),
        unidade="dias",
        se_aumentar="Menos gestores contam como sem login; o relaxamento trava menos imóveis.",
        minimo=1,
    ),
    _campo(
        caminho="corretor.minimo_no_distrito",
        grupo="quem_entra_corretor",
        tipo="inteiro",
        ajuda=(
            "Quantos corretores ativos (captaram ou venderam em 30 dias) o distrito precisa "
            "ter para os imóveis dele entrarem. Passar de 3 para 2 elevou a cobertura de "
            "vendas de 62% para 75% e os distritos elegíveis de 39 para 61 (D-015)."
        ),
        unidade="corretores",
        se_aumentar="Exige distritos com mais equipe: menos imóveis entram, mais concentrados.",
        minimo=1,
    ),
    # --- em que ordem: o portal ----------------------------------------------------
    _campo(
        caminho="portal.peso_nota",
        grupo="em_que_ordem_portal",
        tipo="inteiro",
        ajuda="Quanto a nota do anúncio no portal pesa na ordem. Os três pesos somam 100.",
        unidade="pontos de 100",
        se_aumentar="A ordem passa a seguir mais a qualidade do anúncio que o interesse medido.",
        minimo=0,
        maximo=100,
    ),
    _campo(
        caminho="portal.peso_cliques",
        grupo="em_que_ordem_portal",
        tipo="inteiro",
        ajuda=(
            "Quanto os cliques no anúncio (contato, telefone, WhatsApp, proposta, agendamento, "
            "somados) pesam na ordem. É intenção de compra, não curiosidade."
        ),
        unidade="pontos de 100",
        se_aumentar=(
            "Anúncio com clique sobe mesmo com nota baixa; sinal fraco hoje, quase todos zero."
        ),
        minimo=0,
        maximo=100,
    ),
    _campo(
        caminho="portal.peso_visualizacoes",
        grupo="em_que_ordem_portal",
        tipo="inteiro",
        ajuda=(
            "Quanto as visualizações pesam. Medido zero em 300 de 300 anúncios em 03/09/2026: "
            "o peso adotado é zero, declarado — não omitido. Volta a valer quando o raspador "
            "achar o campo."
        ),
        unidade="pontos de 100",
        se_aumentar="Hoje, nada: o campo vem zerado do portal, e o peso cairia num sinal vazio.",
        minimo=0,
        maximo=100,
    ),
    _campo(
        caminho="portal.cobertura_minima",
        grupo="em_que_ordem_portal",
        tipo="numero",
        ajuda=(
            "A raspagem precisa cobrir pelo menos esta fração dos candidatos para a ordem vir "
            "do portal. Abaixo disso a ordem cai para o desempate de banco e a rodada declara."
        ),
        unidade="%",
        se_aumentar="Exige raspagem mais completa; mais rodadas saem sem ordem de portal.",
        minimo=0,
        maximo=100,
    ),
    _campo(
        caminho="portal.idade_maxima_dias",
        grupo="em_que_ordem_portal",
        tipo="inteiro",
        ajuda=(
            "Dado do portal mais velho que isto não entra. A rodada raspa no mesmo dia; 2 "
            "tolera um retry sem aceitar dado da semana passada."
        ),
        unidade="dias",
        se_aumentar="Aceita raspagem mais velha; a ordem pode refletir a semana anterior.",
        minimo=0,
    ),
    _campo(
        caminho="portal.sem_anuncio",
        grupo="em_que_ordem_portal",
        tipo="escolha",
        ajuda=(
            "O que vale o imóvel elegível que a raspagem não trouxe: 'fim_da_fila' recebe o "
            "pior sinal de quem tem anúncio; 'mediana' recebe o do meio. Antes era zero em "
            "silêncio."
        ),
        unidade="",
        se_aumentar="",
        escolhas=FORMAS_SEM_ANUNCIO,
    ),
    _campo(
        caminho="portal.ordem_quando_nao_entra",
        grupo="em_que_ordem_portal",
        tipo="escolha",
        ajuda=(
            "Se a raspagem não entrar (cobertura baixa, dado velho, sessão caída), o que "
            "ordena: leads em 180 dias, produtividade do gestor, ou só o cadastro mais novo."
        ),
        unidade="",
        se_aumentar="",
        escolhas=FORMAS_DE_ORDEM_SEM_PORTAL,
    ),
    # --- em que ordem: os descontos ------------------------------------------------
    _campo(
        caminho="desconto.janela_sem_resultado",
        grupo="em_que_ordem_descontos",
        tipo="numero",
        ajuda=(
            "Quanto desconta ter ocupado posição paga e não ter atingido o resultado esperado. "
            "Inerte enquanto a régua nº 14 for nula — a planilha diz isso em toda linha."
        ),
        unidade="pontos de 100",
        se_aumentar="Imóvel que já falhou numa janela cai mais na ordem (quando a régua existir).",
        minimo=0,
        maximo=100,
    ),
    _campo(
        caminho="desconto.sem_avaliacao",
        grupo="em_que_ordem_descontos",
        tipo="numero",
        ajuda=(
            "Quanto desconta não ter nenhuma avaliação por categoria. Baixo de propósito: o "
            "pipeline morreu em 16/10/2025 e 99,76% do estoque novo não tem nota."
        ),
        unidade="pontos de 100",
        se_aumentar="Pune o estoque novo por um defeito da base.",
        minimo=0,
        maximo=100,
    ),
    _campo(
        caminho="desconto.sem_lead_180d",
        grupo="em_que_ordem_descontos",
        tipo="numero",
        ajuda="Quanto desconta não ter recebido nenhum lead em 180 dias.",
        unidade="pontos de 100",
        se_aumentar="Imóvel sem lead recente cai mais na ordem.",
        minimo=0,
        maximo=100,
    ),
    _campo(
        caminho="desconto.perdao_por_semana",
        grupo="em_que_ordem_descontos",
        tipo="numero",
        ajuda=(
            "Quanto o desconto da janela anterior encolhe a cada carga aprovada. 50% = cai "
            "pela metade por semana e some em cerca de três. 0% = nunca perdoa, o que diverge "
            "da Spec §6.4 e a rodada declara."
        ),
        unidade="% por carga",
        se_aumentar="O tropeço passado é esquecido mais rápido.",
        minimo=0,
        maximo=100,
    ),
    # --- quantos: a régua nula -----------------------------------------------------
    _campo(
        caminho="resultado_esperado.super_destaque",
        grupo="quantos",
        tipo="inteiro",
        ajuda=(
            "Quantos leads a janela de SUPER DESTAQUE precisa ter gerado para não ser "
            "descontada (Spec §6.4). NULA por decisão do dono (04/09/2026). Se declarar, "
            "declare os DOIS níveis, e este MAIOR que o de destaque."
        ),
        unidade="leads",
        se_aumentar="Mais janelas de super destaque contam como sem resultado.",
        obrigatorio=False,
        minimo=1,
    ),
    _campo(
        caminho="resultado_esperado.destaque",
        grupo="quantos",
        tipo="inteiro",
        ajuda=(
            "Quantos leads a janela de DESTAQUE precisa ter gerado para não ser descontada. "
            "NULA por decisão do dono. Os dois níveis, ou nenhum."
        ),
        unidade="leads",
        se_aumentar="Mais janelas de destaque contam como sem resultado (88% geraram zero).",
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
        descricao="Os três pesos do portal somam exatamente 100.",
        campos=("portal.peso_nota", "portal.peso_cliques", "portal.peso_visualizacoes"),
    ),
    RegraCruzada(
        tipo="todos_ou_nenhum",
        descricao=(
            "A régua de resultado é opcional, mas indivisível: ou os dois níveis, ou nenhum. "
            "Meio-declarada julgaria metade das janelas e deixaria a outra metade sem "
            "julgamento."
        ),
        campos=("resultado_esperado.super_destaque", "resultado_esperado.destaque"),
    ),
    RegraCruzada(
        tipo="maior_que",
        descricao=(
            "resultado_esperado.super_destaque precisa ser MAIOR que destaque: o resultado "
            "esperado é proporcional ao nível."
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
