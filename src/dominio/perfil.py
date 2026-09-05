"""Perfil de conversão: combinações de características que geram venda.

Fonte: Spec §6.2, lida conforme a D-014 (docs/decisoes.md): a evidência mínima
por combinação é `N ≥ 3` (parâmetro pendente nº 1, resolvido pelo dono em
31/08/2026). A entrada são as vendas assinadas nos últimos 180 dias (D-013:
177 casos), com identidades já removidas.

Este módulo faz APENAS a descoberta dos perfis — conta combinações de uma ou
duas dimensões e devolve cada perfil com o número de vendas que o sustenta.
Desde a D-027 o perfil não é fator de nota: é REGRA. Quem decide se um perfil
conta para o filtro é a costura (`piloto.semelhanca.perfis_que_contam`): conta o
robusto que contém a dimensão exigida. Aqui só se DESCOBRE e se rotula.

Perfil FRÁGIL (N abaixo da evidência mínima) NÃO é excluído deste resultado:
continua na saída, marcado, com seu número de casos — a planilha os mostra, e
sem eles não dá para ver que a evidência era pouca. Mas ele não pesa menos no
filtro: não pesa nada, porque o filtro é binário (D-027 sobrepõe o "não recebe
peso pleno" da Spec §6.2).

Além da descoberta, este módulo declara a ORDEM DE PRIORIDADE das dimensões
(`PRIORIDADE_DIMENSOES`), decisão do dono na D-017 que a D-027 preservou como
critério de EXIBIÇÃO — hoje sem efeito nenhum no cálculo. Ver o comentário
sobre a constante, que diz o que sobreviveu e o que a D-031 dissolveu.

Invariantes 4 e 5: cálculo puro — sem I/O, sem relógio, sem aleatoriedade,
sem chamada a modelo. Mesma entrada ⇒ mesmos perfis, em ordem canônica.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from itertools import combinations

# Parâmetro nº 1 COM valor definido (D-014). Mudar isto é mudança de regra de
# decisão: exige CHANGELOG e registro em alteracao_parametro. É limiar de
# FRAGILIDADE, não de exclusão.
EVIDENCIA_MINIMA = 3


class Dimensao(StrEnum):
    """As cinco dimensões de perfil da Spec §6.2.

    A ordem de declaração é a ordem canônica de saída (invariante 5).
    """

    REGIAO = "regiao"
    FAIXA_PRECO = "faixa_preco"
    FAIXA_METRAGEM = "faixa_metragem"
    DORMITORIOS = "dormitorios"
    VAGAS = "vagas"


# Ordem de PRIORIDADE das dimensões, nas palavras do dono (D-017): "preço,
# localização, metragem, quantidade de dormitórios e quantidade de vagas de
# garagem, nessa ordem". É a IMPORTÂNCIA de cada característica, e mudá-la exige
# decisão registrada.
#
# HOJE ELA NÃO TEM EFEITO NENHUM NO CÁLCULO. A D-027 fez o perfil virar regra
# binária e a D-031 dissolveu o decaimento por dimensão (o parâmetro nº 13) sem
# lhe dar valor; a própria D-027 diz que a ordem "sobrevive só como critério de
# exibição". O consumidor de exibição ainda não existe — ligá-lo é fatia própria,
# registrada na issue #73. Fica aqui para não se perder a única memória em código
# de uma decisão do dono.
#
# NÃO confundir com a ordem canônica do enum acima (região primeiro), que serve à
# saída determinística (invariante 5): esta é importância, aquela é ordenação.
PRIORIDADE_DIMENSOES: tuple[Dimensao, ...] = (
    Dimensao.FAIXA_PRECO,
    Dimensao.REGIAO,
    Dimensao.FAIXA_METRAGEM,
    Dimensao.DORMITORIOS,
    Dimensao.VAGAS,
)


# Valor de uma dimensão já bucketizado pela coleta (região/faixas como texto,
# dormitórios/vagas como inteiro). None = fonte não preenche para aquele imóvel
# (ex.: dormitórios, ~11% nulos): o imóvel não entra em nenhuma combinação que
# inclua a dimensão nula. O tipo é opaco para este módulo — só precisa ser
# hashável; a bucketização é responsabilidade do Coletor, não do domínio.
type ValorDimensao = str | int


@dataclass(frozen=True)
class ImovelVendido:
    """Um imóvel com venda assinada em 180 dias (D-013), sem identidade.

    As cinco dimensões chegam já bucketizadas pela coleta. Qualquer uma pode
    ser None quando a fonte não a preenche para este imóvel.
    """

    imovel_id: int
    regiao: str | None
    faixa_preco: str | None
    faixa_metragem: str | None
    dormitorios: int | None
    vagas: int | None

    def valores(self) -> dict[Dimensao, ValorDimensao]:
        """As dimensões preenchidas deste imóvel (as None ficam de fora)."""
        bruto: dict[Dimensao, ValorDimensao | None] = {
            Dimensao.REGIAO: self.regiao,
            Dimensao.FAIXA_PRECO: self.faixa_preco,
            Dimensao.FAIXA_METRAGEM: self.faixa_metragem,
            Dimensao.DORMITORIOS: self.dormitorios,
            Dimensao.VAGAS: self.vagas,
        }
        return {dim: v for dim, v in bruto.items() if v is not None}


@dataclass(frozen=True)
class PerfilConversao:
    """Uma combinação de uma ou duas dimensões observada nas vendas.

    `dimensoes` e `valores` são tuplas alinhadas (mesmo comprimento, 1 ou 2),
    com as dimensões em ordem canônica (ordem do enum). `num_vendas` é o
    número de vendas que caem exatamente nessa combinação.
    """

    dimensoes: tuple[Dimensao, ...]
    valores: tuple[ValorDimensao, ...]
    num_vendas: int

    def __post_init__(self) -> None:
        if not 1 <= len(self.dimensoes) <= 2:
            raise ValueError(f"perfil deve ter 1 ou 2 dimensões, tem {len(self.dimensoes)}")
        if len(self.dimensoes) != len(self.valores):
            raise ValueError("dimensoes e valores devem ter o mesmo comprimento")
        if self.num_vendas < 1:
            raise ValueError(f"num_vendas deve ser ≥ 1, é {self.num_vendas}")

    @property
    def fragil(self) -> bool:
        """Abaixo da evidência mínima (D-014): não conta para o filtro (D-027)."""
        return self.num_vendas < EVIDENCIA_MINIMA


def _chave_ordenacao(
    perfil: PerfilConversao,
) -> tuple[tuple[str, ...], tuple[tuple[str, ValorDimensao], ...]]:
    """Ordem total canônica (invariante 5): por dimensões, depois por valores.

    Cada valor entra na chave como (nome do tipo, valor). O nome do tipo à
    frente garante duas coisas: comparar dimensões de tipos diferentes sem
    TypeError (nunca se compara int com str diretamente), e injetividade —
    `2` (int) e `"2"` (str) produzem chaves distintas, então não colapsam num
    empate que o sort resolveria pela ordem de entrada (o que quebraria o
    invariante 5). Na prática a bucketização mantém tipo fixo por dimensão;
    a tag é a rede contra deriva futura, já que o valor é opaco aqui.
    """
    return (
        tuple(dim.value for dim in perfil.dimensoes),
        tuple((type(v).__name__, v) for v in perfil.valores),
    )


def perfis_de_conversao(vendas: Iterable[ImovelVendido]) -> tuple[PerfilConversao, ...]:
    """Descobre os perfis de conversão de uma e de duas dimensões (Spec §6.2).

    Conta, sobre as vendas, cada combinação de uma dimensão e cada combinação
    de duas dimensões (nunca três ou mais — Spec §6.2). Um imóvel só conta para
    uma combinação se tem TODAS as dimensões dela preenchidas. Perfis frágeis
    (N < EVIDENCIA_MINIMA) são mantidos e marcados, não excluídos.

    Devolve os perfis em ordem canônica (invariante 5).
    """
    contagem: dict[tuple[tuple[Dimensao, ...], tuple[ValorDimensao, ...]], int] = {}

    for venda in vendas:
        presentes = venda.valores()
        dims_presentes = [dim for dim in Dimensao if dim in presentes]
        # Uma dimensão e duas dimensões; a ordem canônica das dimensões vem de
        # dims_presentes (que segue a ordem do enum), então combinations preserva.
        for n in (1, 2):
            for combo in combinations(dims_presentes, n):
                chave = (combo, tuple(presentes[dim] for dim in combo))
                contagem[chave] = contagem.get(chave, 0) + 1

    perfis = [
        PerfilConversao(dimensoes=dims, valores=vals, num_vendas=n)
        for (dims, vals), n in contagem.items()
    ]
    return tuple(sorted(perfis, key=_chave_ordenacao))
