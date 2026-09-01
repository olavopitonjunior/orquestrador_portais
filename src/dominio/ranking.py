"""Ranking: nota final por nível — soma ponderada de QUATRO fatores menos penalidades.

Fonte: Spec §6.3, lida conforme a D-008 (docs/decisoes.md) e REDESENHADA pela
D-017: a nota ponderada de cada nível é a operacionalização do objetivo daquele
nível (valor esperado no super destaque, probabilidade de lead no destaque —
objetivos PRESERVADOS) e é a chave de ordenação da alocação (Spec §6.5). O que
a D-017 mudou é o CONJUNTO de fatores e os pesos: semelhança com perfil, LEADS
positivo (F2, novo — antes lead só existia como penalidade §6.4), desempenho de
portal (reforço) e produtividade do gestor.

Os pesos por nível deixaram de ser parâmetros DEFINIDOS: a D-017 os tornou
parâmetro NULO (provisório run-local, injetado, nunca adotado aqui). As
constantes deste módulo são default-ponte PROVISÓRIO com leads dormente
(peso 0), não a decisão do dono. A forma de normalização de cada fator segue
sendo o parâmetro pendente nº 2 (D-004), FORA deste módulo: os fatores chegam
já normalizados para escala comparável pela camada a montante — aqui se exige
apenas que sejam números finitos. A ponderação da semelhança pela evidência do
perfil e a ponderação por dimensão (F1, D-017) também são a montante.

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
    """Um conjunto de pesos por nível. QUATRO fatores após o redesenho D-017 —
    semelhança com perfil, LEADS positivo, desempenho de portal, produtividade
    do gestor. A soma deve ser 100 (convenção de escala — ver nota_bruta).

    Os VALORES dos pesos são parâmetro NULO (D-017: os pesos da §6.3 deixaram de
    ser adotados): injetados run-local, nunca constante adotada. `leads_positivo`
    é o fator novo (F2): peso 0 mantém o comportamento pré-D-017 (leads dormente)
    até a fatia da costura injetar o esquema novo.
    """

    semelhanca_perfil: int
    leads_positivo: int
    desempenho_proprio: int
    produtividade_gestor: int

    def __post_init__(self) -> None:
        # Os pesos um dia serão rehidratados do Registro (alteracao_parametro):
        # a fronteira de validação é aqui, como nas intensidades de penalidade.
        # Peso negativo converteria fator em penalidade.
        for campo in (
            "semelhanca_perfil",
            "leads_positivo",
            "desempenho_proprio",
            "produtividade_gestor",
        ):
            valor = getattr(self, campo)
            if not isinstance(valor, int) or valor < 0:
                raise ValueError(f"peso inválido para {campo}: {valor!r}")
        soma = (
            self.semelhanca_perfil
            + self.leads_positivo
            + self.desempenho_proprio
            + self.produtividade_gestor
        )
        if soma != 100:
            raise ValueError(f"pesos devem somar 100, somam {soma}")


# PROVISÓRIOS run-local — NÃO adotados (D-017 tornou os pesos parâmetro nulo).
# Valores-ponte herdados do esquema pré-D-017 da Spec §6.3, com LEADS DORMENTE
# (peso 0) para manter o CI e a costura já mergeada compilando/verdes até a
# fatia da costura injetar os pesos do novo esquema de 4 fatores. NÃO são a
# decisão do dono — são o default provisório do piloto. Mudança aqui (ou adoção
# de qualquer valor) exige CHANGELOG e registro em alteracao_parametro.
PESOS_SUPER_DESTAQUE = PesosNivel(
    semelhanca_perfil=60, leads_positivo=0, desempenho_proprio=25, produtividade_gestor=15
)
PESOS_DESTAQUE = PesosNivel(
    semelhanca_perfil=80, leads_positivo=0, desempenho_proprio=10, produtividade_gestor=10
)


@dataclass(frozen=True)
class FatoresNormalizados:
    """As notas dos quatro fatores de um imóvel (D-017), já em escala comparável.

    A normalização (parâmetro pendente nº 2), a ponderação da semelhança pela
    evidência do perfil e a ponderação por dimensão (F1) acontecem a montante;
    este módulo valida apenas finitude — NaN/inf quebraria a ordenação total do
    invariante 5. O fator de capacidade de distrito não existe aqui de
    propósito: o PRD o exclui do ranking porque o distrito já atua como regra
    eliminatória. `leads` é o F2 (D-017), default 0.0 = dormente.
    """

    imovel_id: int
    semelhanca_perfil: float
    desempenho_proprio: float
    produtividade_gestor: float
    # F2 (D-017): sinal POSITIVO de leads, normalizado. Default 0.0 = dormente,
    # o que preserva o comportamento pré-D-017 de quem ainda não o preenche
    # (costura já mergeada); a fiação viva (norm(Leads180D)) é da fatia da costura.
    leads: float = 0.0

    def __post_init__(self) -> None:
        for campo in ("semelhanca_perfil", "leads", "desempenho_proprio", "produtividade_gestor"):
            valor = getattr(self, campo)
            if not math.isfinite(valor):
                raise ValueError(f"fator não finito para {campo}: {valor}")


def nota_bruta(fatores: FatoresNormalizados, pesos: PesosNivel) -> float:
    """Soma ponderada das notas dos quatro fatores (Spec §6.3 + D-017), antes das penalidades.

    Finitude do RESULTADO não é revalidada: com fatores finitos, só estouraria
    com magnitudes da ordem de 1e307, impossíveis numa "escala comparável" —
    a garantia de faixa nasce com a normalização (parâmetro pendente nº 2).
    """
    return (
        pesos.semelhanca_perfil * fatores.semelhanca_perfil
        + pesos.leads_positivo * fatores.leads
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
