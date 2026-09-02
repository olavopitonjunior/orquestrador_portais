"""A fila do dono (`docs/perguntas-abertas.md`) não pode dessincronizar em silêncio.

A fila é ÍNDICE: o texto integral de cada pendência vive em `docs/decisoes.md`, e os
parâmetros sem valor vivem na tabela do `CLAUDE.md`. Índice que depende de disciplina
apodrece — e o modo de apodrecer não é duplicação, é OMISSÃO: alguém registra
pendência nova e esquece a linha da fila. Aí o documento que o dono lê para decidir
passa a mentir por ausência, que é pior que não existir, porque parece completo.

Estes testes são a trava. Não conferem redação; conferem que os conjuntos casam.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FILA = RAIZ / "docs" / "perguntas-abertas.md"
DECISOES = RAIZ / "docs" / "decisoes.md"
CLAUDE_MD = RAIZ / "CLAUDE.md"

_P = re.compile(r"\[(P-\d{2})\]")
# Linha da tabela de parâmetros do CLAUDE.md: `| 14 | Nome do parâmetro | valor |`
_PARAMETRO = re.compile(r"^\|\s*(\d{1,2})\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$", re.M)
# Como a fila cita um parâmetro: `**nº 14** — nome`
_CITADO = re.compile(r"\*\*nº (\d{1,2})\*\*")


def _ids(caminho: Path) -> set[str]:
    return set(_P.findall(caminho.read_text(encoding="utf-8")))


def test_toda_pendencia_registrada_tem_linha_na_fila():
    """A metade que importa. Registrar pendência em `decisoes.md` sem pôr linha na
    fila deixa o dono sem saber que ela existe — e é o único jeito de a fila ficar
    errada sem ninguém perceber, porque nada mais a lê."""
    faltando = _ids(DECISOES) - _ids(FILA)
    assert not faltando, (
        f"pendências registradas em decisoes.md e AUSENTES da fila do dono: "
        f"{sorted(faltando)}. Quem registra a pendência acrescenta a linha na mesma mudança."
    )


def test_a_fila_nao_inventa_pendencia():
    """O outro sentido: a fila é índice, não fonte. Um `P-NN` que só existe aqui é
    pendência criada dentro de um índice — inversão da hierarquia documental, e o
    dono decidiria sobre algo que nenhum registro sustenta."""
    orfas = _ids(FILA) - _ids(DECISOES)
    assert not orfas, (
        f"a fila cita {sorted(orfas)}, que não existe em decisoes.md. "
        "A pendência precisa de entrada própria lá antes de ser indexada aqui."
    )


def test_ha_pendencias_a_conferir():
    """Contraprova dos dois acima: com zero identificadores dos dois lados, ambos
    passariam sem guardar nada."""
    assert len(_ids(FILA)) >= 8, "poucos identificadores — o casamento estaria vazio"


def _tabela_de_parametros() -> dict[int, tuple[str, str]]:
    texto = CLAUDE_MD.read_text(encoding="utf-8")
    return {
        int(n): (nome, valor)
        for n, nome, valor in _PARAMETRO.findall(texto)
        if n.isdigit() and nome != "Parâmetro"
    }


def test_a_fila_so_cita_parametro_que_existe_na_tabela():
    """A tabela do CLAUDE.md é a fonte da verdade dos parâmetros. Citar um número que
    não existe lá é apontar para o vazio."""
    tabela = _tabela_de_parametros()
    citados = {int(n) for n in _CITADO.findall(FILA.read_text(encoding="utf-8"))}
    assert citados, "a fila deveria citar parâmetros"
    ausentes = citados - set(tabela)
    assert not ausentes, f"a fila cita parâmetros inexistentes na tabela: {sorted(ausentes)}"


def test_a_fila_so_cobra_parametro_que_continua_NULO():
    """A pior falha possível deste documento: mandar o dono decidir o que ele já
    decidiu. O nº 1 foi resolvido pela D-014 e não pode reaparecer na fila."""
    tabela = _tabela_de_parametros()
    citados = {int(n) for n in _CITADO.findall(FILA.read_text(encoding="utf-8"))}
    resolvidos = {n for n in citados if "nulo" not in tabela[n][1].lower()}
    assert not resolvidos, (
        f"a fila cobra parâmetros JÁ RESOLVIDOS na tabela do CLAUDE.md: {sorted(resolvidos)} "
        f"({', '.join(tabela[n][1] for n in sorted(resolvidos))})"
    )


def test_todo_parametro_NULO_da_tabela_aparece_na_fila():
    """O simétrico: um parâmetro que segue nulo e não está na fila é exatamente o
    passivo invisível que esta fatia existe para acabar."""
    tabela = _tabela_de_parametros()
    nulos = {n for n, (_, valor) in tabela.items() if "nulo" in valor.lower()}
    citados = {int(n) for n in _CITADO.findall(FILA.read_text(encoding="utf-8"))}
    faltando = nulos - citados
    assert not faltando, f"parâmetros nulos ausentes da fila do dono: {sorted(faltando)}"


def test_a_fila_declara_que_a_ordem_e_julgamento():
    """Uma priorização sem etiqueta é lida como fato. O dono precisa saber que a
    ordem é minha e sob qual critério, para poder discordar dela sem discordar dos
    itens."""
    texto = FILA.read_text(encoding="utf-8")
    assert "julgamento meu" in texto and "critério" in texto


# O registro tem uma convenção: uma pendência REAL é declarada em negrito
# (`**Vai ao dono.**`, `**Pendência do dono:**`) ou num cabeçalho próprio. Menção em
# prosa corrida — um título que descreve a seção, ou o ponteiro para a fila — não é
# declaração de pendência, e exigir identificador dela geraria falso positivo, que é
# como um teste vira ruído e depois vira `skip`.
_MARCADORES = (
    "**vai ao dono",
    "**pendência do dono",
    "**pergunta ao dono",
    "# pergunta ao dono",
    "# pergunta aberta ao dono",
    "# divergência aberta",
)
# Trecho riscado = pendência resolvida; não exige identificador.
_RISCADO = re.compile(r"~~.*?~~", re.S)


def _secoes(texto: str) -> list[tuple[str, str]]:
    """Quebra o registro em seções por cabeçalho `##`/`###`, devolvendo (título, corpo)."""
    secoes: list[tuple[str, list[str]]] = [("(topo)", [])]
    for linha in texto.split("\n"):
        if re.match(r"^#{2,3} ", linha):
            secoes.append((linha, []))
        else:
            secoes[-1][1].append(linha)
    return [(t, "\n".join(c)) for t, c in secoes]


def test_todo_trecho_que_pede_decisao_do_dono_tem_identificador():
    """Fecha o buraco que o portão de regra apontou: os testes de casamento acima só
    veem o que está MARCADO, então uma pendência registrada sem `[P-NN]` — que é como
    P-01 a P-07 viveram até esta fatia — escaparia dos dois e nunca chegaria à fila.

    Aqui a exigência é na origem: todo trecho que diga "vai ao dono" (ou variante)
    precisa de identificador, e aí os testes de casamento o alcançam. Trechos
    ~~riscados~~ são pendências já resolvidas e ficam de fora."""
    texto = _RISCADO.sub("", DECISOES.read_text(encoding="utf-8"))
    sem_id = [
        titulo
        for titulo, corpo in _secoes(texto)
        if any(m in (titulo + corpo).lower() for m in _MARCADORES) and not _P.search(titulo + corpo)
    ]
    assert not sem_id, (
        "seções de decisoes.md que pedem decisão do dono e não têm identificador "
        f"[P-NN] — logo, invisíveis para a fila e para os testes de casamento: {sem_id}"
    )


def test_o_teste_de_marcador_tem_o_que_olhar():
    """Contraprova: se nenhum marcador fosse encontrado, o teste acima passaria vazio."""
    texto = _RISCADO.sub("", DECISOES.read_text(encoding="utf-8")).lower()
    assert sum(texto.count(m) for m in _MARCADORES) >= 5
