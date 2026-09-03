"""Nenhum arquivo versionado afirma fato sobre uma credencial VIVA.

Existe por incidente, três vezes. Em 31/08/2026 a investigação do `1045` foi
transcrita para `docs/mapa-de-dados.md` com o caractere não-ASCII da senha
NOMEADO, e dali se espalhou para `CHANGELOG.md` e para o docstring de
`src/dados/newcore.py` — num repositório **público** (D-012). Em 02/09, ao portar
outro relatório de investigação, um segundo fato quase entrou pelo mesmo caminho;
foi barrado na revisão, não por ferramenta. Na mesma data, a limpeza que removeu
os quatro primeiros pontos **deixou o quinto** (a política de transporte do
servidor) — achado de auditoria independente, e a razão de a lista abaixo cobrir
mais que caractere de senha.

**Por que teste e não hook.** O gitleaks casa PADRÃO DE SEGREDO: uma chave AWS,
um token, um DSN. Prosa que descreve o segredo — "a senha tem X" — não casa com
padrão nenhum e passa por ele intacta. Nem por isso é menos vazamento: reduz o
espaço de busca de uma credencial viva, e o histórico público não desfaz.

**A linha que este teste traça** é entre o FATO sobre o segredo vigente (proibido)
e a MECÂNICA (obrigatória). Documentar que senha não-ASCII quebra o pymysql, ou
que o shell expande metacaractere ao carregar o `.env`, é o que faz a manutenção
funcionar — vale para qualquer senha e **sobrevive à rotação**. Toda vez que as
duas formas foram comparadas, a geral era a documentação melhor. Por isso o
fraseio hipotético ou geral ("a senha PODE conter…") passa de propósito: não
afirma nada sobre o segredo em uso.

**A fronteira REAL, para ninguém confiar mais do que deve.** Fora os padrões de
identidade de conta e de política de transporte, o resto exige uma
**palavra-segredo por perto** — condição necessária, longe de suficiente:
mesmo com ela presente, verbo, notação ou substantivo fora das listas ainda
escapam, e a janela de proximidade é um teto duro. Na direção oposta, a mera
presença da palavra basta para reprovar frase genuinamente inócua, e é para isso
que existe a isenção de linha (`senha`, `password`, `credencial`, `chave de
acesso`). Um vazamento que não use nenhuma delas — "o valor do campo do cofre
termina em til" — **passa ileso**. Não é prova de ausência de vazamento: é lista
de negação, e lista de negação nunca fica completa. Ela encarece a reincidência e
pega as formas conhecidas; o que carrega o resto é a regra escrita em
`docs/decisoes.md` ("relatório de investigação é insumo, não texto pronto:
atravessa a mecânica, nunca o segredo") e a revisão humana. Uma auditoria hostil
em 02/09 furou a primeira versão com onze frases; as classes que ela apontou estão
cobertas abaixo, e mesmo assim esta ressalva continua valendo.

**Este arquivo é o único que contém os literais vazados**, em `LITERAIS`, por
necessidade: sem eles não há detecção de revert exato. Logo ele é versionado e
público como qualquer outro, e a exposição desses quatro literais **continua** —
igual à de hoje, não pior. Quem a neutralizaria é a rotação da senha — **recusada
pelo dono em 02/09, risco aceito na D-026**. Não há "depois da rotação": estes
quatro literais acompanham segredo VIVO por tempo indeterminado, e esta guarda
deixou de ser complemento para ser o único controle. Logo a fronteira declarada
acima não é ressalva: é o teto do risco residual.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent

# Este arquivo cita o que proíbe; sem a isenção, a guarda reprovaria a si mesma.
ISENTOS = {"tests/test_sem_vazamento_de_credencial.py"}

# (A) O que JÁ vazou. Impede que um revert ressuscite exatamente estes.
LITERAIS = ("U+00A8", "0xC2 0xA8", "¨", "olavo@%")

# `\b` nas duas pontas: sem ele, `password` casa dentro de `caching_sha2_password` —
# nome de plugin de autenticação, não referência a segredo — e a guarda reprova a
# própria documentação de mecânica que existe para preservar.
_SEGREDO = r"\b(?:senhas?|passwords?|pwd|credencia(?:l|is)|chave de acesso|segredos?)\b"
# Verbos de AFIRMAÇÃO, conjugados E no infinitivo. O infinitivo é indispensável: sem
# ele `_MODAL` seria código morto, porque em português modal rege infinitivo
# ("pode conter"), e a frase passaria por não casar o verbo — não pela exclusão.
# A primeira versão desta guarda tinha exatamente esse defeito: funcionava pelo
# motivo errado, e a mensagem do commit descrevia um mecanismo que não operava.
_AFIRMA = (
    r"\b(?:cont[ée]m|conter|t[êe]m|tem|ter|possui|possuir|inclui|incluir|traz|trazer"
    r"|carrega|carregar|usa|usar|termina|terminar|come[çc]a|come[çc]ar"
    r"|é compost[ao]|é formad[ao])\b"
)
# Modal = hipótese, não afirmação sobre o segredo em uso. Cada lookbehind tem
# largura fixa (exigência do `re`); a lista é fechada de propósito.
_MODAL = (
    r"(?<!pode )(?<!podem )(?<!poderia )(?<!poderiam )(?<!deve )(?<!devem )"
    r"(?<!deveria )(?<!costuma )(?<!costumam )(?<!pudesse )(?<!precisa )"
    r"(?<!deva )(?<!devam )(?<!possa )(?<!possam )(?<!venha a )(?<!v[ãa]o )"
)
# Notação de VALOR concreto, em qualquer grafia. Nenhuma regra geral precisa de uma.
_VALOR = (
    r"(?:U\+[0-9A-Fa-f]{4,6}|\\u[0-9A-Fa-f]{4}|\\x[0-9A-Fa-f]{2}|0x[0-9A-Fa-f]{2}"
    r"|&#x?[0-9A-Fa-f]{2,6};|\\N\{[A-Z ]+\}"
    r"|(?:ponto de c[óo]digo|c[óo]digo|codepoint)\s+\d{2,6})"
)
# Substantivo que CARACTERIZA o segredo sem citar valor ("um metacaractere").
_CARACTERIZA = (
    r"(?:metacaractere|caractere|s[íi]mbolo|acento|trema|cedilha|til|circunflexo"
    r"|diacr[íi]tico|di[ée]rese|emoji|d[íi]gito|letra|byte|espa[çc]o"
    r"|ponto de c[óo]digo|pontua[çc][ãa]o)"
)

FORMAS = (
    # valor concreto na vizinhança da palavra-segredo, atravessando linhas
    re.compile(_SEGREDO + r"[\s\S]{0,100}?" + _VALOR, re.I),
    re.compile(_VALOR + r"[\s\S]{0,100}?" + _SEGREDO, re.I),
    # afirmação sobre a composição do segredo, sem citar valor
    re.compile(
        _SEGREDO + r"[\s\S]{0,60}?" + _MODAL + _AFIRMA + r"[\s\S]{0,40}?" + _CARACTERIZA, re.I
    ),
    # identidade da conta, como o servidor a devolve
    re.compile(r"CURRENT_USER\(\)\s*=\s*\S", re.I),
    # política de transporte do servidor de produção
    re.compile(r"require_secure_transport\s*=\s*0", re.I),
    re.compile(r"n[ãa]o (?:exige|for[çc]a|obriga|requer)\s+\**(?:SSL|TLS)", re.I),
)

# As frases com que a auditoria hostil de 02/09 furou a primeira versão. Cada uma
# precisa reprovar; é a contraprova de que a ampliação valeu.
FUROS_FECHADOS = (
    "A credencial de leitura do Newcore possui, entre seus caracteres, o U+00E7.",
    "O password de leitura do MySQL contém U+00E7.",
    "A senha do Newcore\ntem o ponto de código U+00E7 nela.",
    "A senha do Newcore tem o caractere \\u00e7 dentro dela.",
    "A senha do Newcore tem um trema espremido nela.",
    "A PASSWORD do usuário contém o byte 0xC3 0xA7 em UTF-8.",
    "CURRENT_USER() = fulano@10.0.%",
    "O servidor RDS do Newcore não exige TLS; a conexão vai em texto claro.",
    # segunda rodada: lacunas de vocabulário achadas na revisão de 02/09
    "A senha do Newcore carrega um til.",
    "A senha do Newcore é composta por um diacrítico incomum.",
    "O segredo de leitura do Newcore contém U+2603.",
    "O pwd do Newcore tem U+2603.",
    "A chave de acesso tem um circunflexo nela.",
    "A senha do Newcore usa o ponto de código 9731.",
)
# Fraseio que precisa PASSAR: mecânica geral e hipótese. Se um destes reprovar, a
# guarda virou atrito em trabalho legítimo — e guarda que atrapalha é guarda desligada.
LEGITIMOS = (
    "senha não-ASCII quebra o pymysql, que força latin-1 em senha `str`",
    "a senha do Canal Pro pode conter emoji, o que quebraria o parser de login",
    "nunca carregue o .env com `set -a`: o shell expande metacaracteres do valor",
    # falsos-positivos que a revisão de 02/09 demonstrou; se voltarem a reprovar, a
    # guarda vira atrito em trabalho de rotina e alguém a desliga
    "a política exige que a senha deva ter no mínimo 12 caracteres",
    "a senha do Canal Pro poderia conter emoji, o que quebraria o parser",
    "o segredo pode terminar com qualquer caractere; não presuma ASCII",
)


def _legivel(caminho: Path) -> bool:
    try:
        caminho.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return False
    return True


def _versionados() -> list[Path]:
    """Binário sai AQUI, não no corpo do teste. O passo "nenhum pode ser pulado" do
    CI reprova a build ao ver qualquer skip — e reprova com a mensagem "o Postgres do
    CI não está sendo usado", diagnóstico falso que custaria horas a quem depurasse.
    Hoje o repositório não versiona binário nenhum; esta linha é para o dia em que
    versionar."""
    saida = subprocess.run(
        ["git", "ls-files", "-z"], cwd=RAIZ, capture_output=True, text=True, check=True
    ).stdout
    todos = [RAIZ / n for n in saida.split("\0") if n and n not in ISENTOS]
    return [p for p in todos if _legivel(p)]


ARQUIVOS = _versionados()


# Isenção de UMA linha, com motivo obrigatório. Existe porque a alternativa real não
# é "escrever melhor": é alguém comentar o teste inteiro no dia em que for barrado por
# uma frase legítima ("a senha tem pelo menos um dígito"; uma faixa de bytes em hex num
# validador). `ISENTOS` só isenta arquivo inteiro, o que é grosso demais. Aqui a
# cedência é de uma linha, fica visível no diff e leva motivo escrito — revisável, ao
# contrário de um teste desligado.
_ISENCAO = re.compile(r"nao-vaza:([^\n]*)")
# Fechadores de comentário não são motivo. Sem isto, `<!-- nao-vaza: -->` passava por
# isenção justificada — o `-->` contava como texto (verificado por mutação).
_FECHADORES = ("-->", "*/", "#}", "]]>", "*)", "-}")


def _motivo(bruto: str) -> str:
    limpo = bruto.strip()
    for fim in _FECHADORES:
        if limpo.endswith(fim):
            limpo = limpo[: -len(fim)].strip()
    return limpo if sum(c.isalpha() for c in limpo) >= 3 else ""


def _acusacoes(texto: str) -> list[str]:
    linhas = texto.split("\n")
    sem_motivo = [
        i + 1
        for i, linha in enumerate(linhas)
        if (m := _ISENCAO.search(linha)) and not _motivo(m.group(1))
    ]
    if sem_motivo:
        return [f"isenção sem motivo na(s) linha(s) {sem_motivo} — `nao-vaza:` exige o porquê"]
    limpo = "\n".join("" if _ISENCAO.search(linha) else linha for linha in linhas)
    achados = [lit for lit in LITERAIS if lit in limpo]
    achados += [m.group(0) for f in FORMAS if (m := f.search(limpo))]
    return achados


# Os quatro arquivos onde o vazamento de 31/08 morou. A checagem agregada abaixo não
# os cobre: se um deles fosse renomeado, ficasse ilegível ou entrasse em `ISENTOS`, a
# contagem continuaria alta e a guarda pararia de proteger exatamente o que a motivou.
HISTORICAMENTE_AFETADOS = (
    "docs/mapa-de-dados.md",
    "CHANGELOG.md",
    "docs/decisoes.md",
    "src/dados/newcore.py",
)


def test_a_varredura_enxerga_o_repositorio():
    """Contraprova: sem isto, tudo abaixo passaria vazio se `git ls-files` mudasse de
    forma, se o cwd escorregasse ou se a isenção engolisse a lista."""
    assert len(ARQUIVOS) >= 50, f"esperava dezenas de arquivos versionados, vi {len(ARQUIVOS)}"
    assert any(a.name == "CLAUDE.md" for a in ARQUIVOS), "a varredura não alcançou a raiz"
    assert any(a.suffix == ".py" for a in ARQUIVOS), "a varredura não alcançou o código"
    varridos = {str(a.relative_to(RAIZ)) for a in ARQUIVOS}
    fora = [f for f in HISTORICAMENTE_AFETADOS if f not in varridos]
    assert not fora, (
        f"os arquivos que originaram esta guarda saíram da varredura: {fora}. Renomeados, "
        "ilegíveis ou isentados — de qualquer modo, deixaram de ser protegidos."
    )


def test_as_contraprovas_nao_estao_vazias():
    """Contraprova das contraprovas. `parametrize` sobre tupla vazia gera ZERO casos e a
    suíte reporta sucesso — o mesmo vácuo que `ARQUIVOS` já evitava e estas duas listas
    não evitavam. São elas que provam o poder discriminatório da guarda: uma que ela
    morde, outra que não morde demais."""
    assert len(FUROS_FECHADOS) >= 8, f"lista de furos encolheu para {len(FUROS_FECHADOS)}"
    assert len(LEGITIMOS) >= 3, f"lista de legítimos encolheu para {len(LEGITIMOS)}"


@pytest.mark.parametrize("frase", FUROS_FECHADOS, ids=range(len(FUROS_FECHADOS)))
def test_a_guarda_morde_os_furos_que_a_auditoria_encontrou(frase: str):
    """Contraprova do outro lado: os padrões precisam MORDER. Cada frase aqui passou
    ilesa pela primeira versão desta guarda numa auditoria hostil."""
    assert _acusacoes(frase), f"furo reaberto: {frase!r} passa pela guarda"


@pytest.mark.parametrize("frase", LEGITIMOS, ids=range(len(LEGITIMOS)))
def test_a_guarda_deixa_passar_a_mecanica_e_a_hipotese(frase: str):
    """Contraprova do falso-positivo. A guarda existe para separar fato de mecânica;
    se reprovar a mecânica, alguém a desliga e o projeto fica sem nada."""
    assert not _acusacoes(frase), f"falso-positivo: {frase!r} é legítimo e foi reprovado"


@pytest.mark.parametrize("arquivo", ARQUIVOS, ids=lambda p: str(p.relative_to(RAIZ)))
def test_arquivo_versionado_nao_descreve_a_credencial_vigente(arquivo: Path):
    achados = _acusacoes(arquivo.read_text(encoding="utf-8"))
    assert not achados, (
        f"{arquivo.relative_to(RAIZ)} bateu no padrão de vazamento: {achados!r}.\n"
        "Isto é heurística, não veredito — há duas leituras, e a saída é diferente:\n"
        "  (1) É fato sobre uma credencial VIVA. Reescreva citando a MECÂNICA geral — o "
        "que vale para qualquer segredo e sobrevive à rotação —, nunca característica do "
        "segredo em uso.\n"
        "  (2) É frase legítima que só coincidiu (política de senha, validação de "
        "entrada, segredo de outro sistema). Afaste a palavra-segredo do verbo ou do "
        "valor que disparou; se a reescrita ficar forçada, marque a linha com "
        "`nao-vaza: <motivo>` — a isenção é de uma linha só, fica no diff e é revisável.\n"
        "Fronteira do padrão: docstring de tests/test_sem_vazamento_de_credencial.py."
    )
