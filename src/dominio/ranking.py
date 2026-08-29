"""Ranking: nota final por nível — soma ponderada de três fatores menos penalidades.

Fonte: Spec §6.3, lida conforme a D-008 (docs/decisoes.md): a nota ponderada
de cada nível é a operacionalização do objetivo daquele nível (valor esperado
no super destaque, probabilidade de lead no destaque) e é a chave de ordenação
da alocação (Spec §6.5).

Os pesos por nível são parâmetros DEFINIDOS (Spec §6.3 e PRD, Estágio 3,
somas 100). A forma de normalização de cada fator é o parâmetro pendente
nº 2 (D-004) e fica FORA deste módulo: os fatores chegam já normalizados
para escala comparável pela camada que o dono da decisão vier a definir —
aqui se exige apenas que sejam números finitos. A ponderação da semelhança
pela evidência do perfil (PRD) também é responsabilidade do fator, a montante.

Leitura estrutural declarada: "soma ponderada" é a forma literal
Σ peso × nota, sem divisão pelo total — como os pesos somam 100 nos dois
níveis, dividir seria só um fator constante, absorvido pela calibração
conjunta dos parâmetros pendentes nº 2 (escala dos fatores) e nº 3
(intensidade das penalidades).

Invariantes 4 e 5: cálculo puro — sem I/O, sem relógio, sem aleatoriedade,
sem chamada a modelo. O desconto de penalidades vem pronto de
dominio.penalidades.desconto_total.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PesosNivel:
    """Um conjunto de pesos por nível (Spec §6.3). A soma deve ser 100."""

    semelhanca_perfil: int
    desempenho_proprio: int
    produtividade_gestor: int

    def __post_init__(self) -> None:
        # Os pesos um dia serão rehidratados do Registro (alteracao_parametro):
        # a fronteira de validação é aqui, como nas intensidades de penalidade.
        # Peso negativo converteria fator em penalidade.
        for campo in ("semelhanca_perfil", "desempenho_proprio", "produtividade_gestor"):
            valor = getattr(self, campo)
            if not isinstance(valor, int) or valor < 0:
                raise ValueError(f"peso inválido para {campo}: {valor!r}")
        soma = self.semelhanca_perfil + self.desempenho_proprio + self.produtividade_gestor
        if soma != 100:
            raise ValueError(f"pesos devem somar 100, somam {soma}")


# Parâmetros COM valor definido (Spec §6.3; PRD, Estágio 3 — "pesos iniciais,
# revistos depois da primeira lista"). Mudança aqui é mudança de regra de
# decisão: exige CHANGELOG e registro em alteracao_parametro.
PESOS_SUPER_DESTAQUE = PesosNivel(
    semelhanca_perfil=60, desempenho_proprio=25, produtividade_gestor=15
)
PESOS_DESTAQUE = PesosNivel(semelhanca_perfil=80, desempenho_proprio=10, produtividade_gestor=10)


@dataclass(frozen=True)
class FatoresNormalizados:
    """As notas dos três fatores de um imóvel, já em escala comparável.

    A normalização (parâmetro pendente nº 2) e a ponderação da semelhança
    pela evidência do perfil acontecem a montante; este módulo valida
    apenas finitude — NaN/inf quebraria a ordenação total do invariante 5.
    O fator de capacidade de distrito não existe aqui de propósito: o PRD
    o exclui do ranking porque o distrito já atua como regra eliminatória.
    """

    imovel_id: int
    semelhanca_perfil: float
    desempenho_proprio: float
    produtividade_gestor: float

    def __post_init__(self) -> None:
        for campo in ("semelhanca_perfil", "desempenho_proprio", "produtividade_gestor"):
            valor = getattr(self, campo)
            if not math.isfinite(valor):
                raise ValueError(f"fator não finito para {campo}: {valor}")


def nota_bruta(fatores: FatoresNormalizados, pesos: PesosNivel) -> float:
    """Soma ponderada das notas dos três fatores (Spec §6.3), antes das penalidades.

    Finitude do RESULTADO não é revalidada: com fatores finitos, só estouraria
    com magnitudes da ordem de 1e307, impossíveis numa "escala comparável" —
    a garantia de faixa nasce com a normalização (parâmetro pendente nº 2).
    """
    return (
        pesos.semelhanca_perfil * fatores.semelhanca_perfil
        + pesos.desempenho_proprio * fatores.desempenho_proprio
        + pesos.produtividade_gestor * fatores.produtividade_gestor
    )


def nota_final(
    fatores: FatoresNormalizados, pesos: PesosNivel, desconto_penalidades: float
) -> float:
    """Nota bruta menos o desconto de penalidades (Spec §6.3) — a chave de
    ordenação da alocação (D-008).

    `desconto_penalidades` vem de dominio.penalidades.desconto_total, que já
    garante valor finito e não negativo; a fronteira é revalidada aqui porque
    esta função também pode receber o valor rehidratado do Registro. A nota
    pode ficar negativa — a Spec não impõe piso, e a ordenação só compara.

    Contrato para a alocação: empates de nota são esperados e a ordenação
    apenas pela nota não é total — o desempate exige critério determinístico
    declarado (por exemplo, imovel_id), sob pena de ferir o invariante 5.
    """
    if not math.isfinite(desconto_penalidades) or desconto_penalidades < 0:
        raise ValueError(f"desconto de penalidades inválido: {desconto_penalidades}")
    return nota_bruta(fatores, pesos) - desconto_penalidades
