"""Ranking: o portal classifica — nota 0–100 de sinais do anúncio, menos descontos.

Fonte: decisão do dono em 04/09/2026 (D-028, docs/decisoes.md): "o banco manda, o
portal classifica". O banco decide QUEM entra (elegibilidade, agora com o perfil de
conversão como regra); o portal decide EM QUE ORDEM. Supera, nesse ponto, a Spec §6.3
e a D-017, que compunham a nota de quatro fatores com pesos por nível — a divergência
está registrada, não resolvida em silêncio.

A nota do portal é a soma ponderada de TRÊS sinais do anúncio, cada um normalizado
para [0, 1] a montante (min-max sobre os elegíveis, forma do parâmetro nº 2):
nota do anúncio (LQS), cliques (somados entre tipos — divergência registrada com o
contrato anterior do coletor, que nunca os somava) e visualizações. Os pesos são
PONTOS DE 100 e somam 100, então a nota bruta vive em [0, 100]; os descontos das
penalidades (Spec §6.4) são também pontos de 100 e são subtraídos. O peso zero é
legítimo e declarado: visualizações mediram 0 em 300/300 anúncios (03/09/2026).

Os dois níveis usam a MESMA nota (a alocação separa super destaque pelo piso de
preço, não por nota diferente). Os fatores de banco (leads, produtividade do
gestor, casamento com o perfil) continuam no `FatoresNormalizados` porque o Registro
os grava, a planilha os mostra e o desempate os usa — não porque pesem na nota.

Invariantes 4 e 5: cálculo puro — sem I/O, sem relógio, sem aleatoriedade, sem
chamada a modelo.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PesosPortal:
    """Os três pesos do classificador, em PONTOS DE 100 (somam exatamente 100).

    Os VALORES são parâmetro da rodada (provisórios, rotulados; adotados só por
    decisão registrada). Zero é permitido e é o caso medido para visualizações.
    """

    nota_anuncio: int
    cliques: int
    visualizacoes: int

    def __post_init__(self) -> None:
        for campo in ("nota_anuncio", "cliques", "visualizacoes"):
            valor = getattr(self, campo)
            if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
                raise ValueError(f"peso inválido para {campo}: {valor!r}")
        soma = self.nota_anuncio + self.cliques + self.visualizacoes
        if soma != 100:
            raise ValueError(f"os pesos do portal devem somar 100, somam {soma}")


@dataclass(frozen=True)
class FatoresNormalizados:
    """Os sinais de um imóvel, já em escala comparável [0, 1] (min-max a montante).

    `nota_anuncio`, `cliques` e `visualizacoes` são o portal — os que pesam.
    `leads` e `produtividade_gestor` são o banco — desempate, Registro e planilha.
    `casa_perfil` é o veredito do filtro de perfil (regra, não fator), carregado
    aqui porque o Registro guarda uma "nota de perfil" e o valor honesto é 1/0.
    None = não avaliado (nenhum perfil que conte, ou candidato sem dimensões).
    """

    imovel_id: int
    nota_anuncio: float
    cliques: float
    visualizacoes: float
    leads: float
    produtividade_gestor: float
    casa_perfil: bool | None

    def __post_init__(self) -> None:
        for campo in ("nota_anuncio", "cliques", "visualizacoes", "leads", "produtividade_gestor"):
            valor = getattr(self, campo)
            if not math.isfinite(valor):
                raise ValueError(f"fator não finito para {campo}: {valor}")


def nota_portal(fatores: FatoresNormalizados, pesos: PesosPortal) -> float:
    """Soma ponderada dos três sinais do portal: em [0, 100] por construção."""
    return (
        pesos.nota_anuncio * fatores.nota_anuncio
        + pesos.cliques * fatores.cliques
        + pesos.visualizacoes * fatores.visualizacoes
    )


def nota_final(nota_bruta: float, desconto_penalidades: float) -> float:
    """Nota bruta menos o desconto das penalidades — a chave de ordenação da alocação.

    `nota_bruta` é a do portal ou, quando o portal não entrou, a do desempate de banco
    (escolha declarada da rodada). O desconto vem de `dominio.penalidades`, que já
    garante finito e não negativo; revalidado aqui porque o valor também pode vir
    rehidratado do Registro. A nota pode ficar negativa — a ordenação só compara.

    Contrato para a alocação: empates são esperados; o desempate é declarado lá
    (leads do banco, depois cadastro mais novo — D-009), sob pena de ferir o
    invariante 5.
    """
    if not math.isfinite(nota_bruta):
        raise ValueError(f"nota bruta não finita: {nota_bruta}")
    if not math.isfinite(desconto_penalidades) or desconto_penalidades < 0:
        raise ValueError(f"desconto de penalidades inválido: {desconto_penalidades}")
    return nota_bruta - desconto_penalidades
