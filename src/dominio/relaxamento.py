"""Relaxamento: cedência progressiva de regras para preencher déficit de destaque.

Fonte: Spec §6.6 e PRD Estágio 5. Aplica-se APENAS às posições de destaque —
as de super destaque nunca relaxam (invariante 7): não existe caminho de
super destaque nesta assinatura, e o resultado não carrega nível.

Ordem de cedência: a de ORDEM_RELAXAMENTO, importada de dominio.elegibilidade
(fonte única) — perfil de conversão (D-027, primeiro degrau), fotos, cadastro
completo, atualização em 90 dias, gestor produtivo, capacidade do distrito.

TRAVA DO LOGIN (D-029): o degrau `gestor_produtivo` NÃO recupera imóvel cujo gestor
não logou dentro da janela declarada — quem não entra no sistema não vai atender o
lead que a posição paga gerar. O imóvel fica irrecuperável em qualquer degrau que
ceda `gestor_produtivo` (inclusive `capacidade_distrito`, que vem depois), e o
resultado conta quantos foram travados, para a planilha declarar.

A cedência é progressiva e MÍNIMA: um grau
só é cedido se o déficit sobrou depois de esgotar o anterior, e a descida
para assim que o déficit zera ("cede regras progressivamente até completar").

O degrau mínimo de um imóvel é o maior índice, na ordem de cedência, entre
suas regras reprovadas — para admiti-lo é preciso ceder todas. Quem reprova
em regra NÃO relaxável (status, categoria, preço geral) nunca entra, em grau
algum: semântica da Spec, não anomalia.

Seleção dentro do grau por (-nota_destaque, -desempate, -imovel_id) — a mesma
chave da alocação (D-028: leads desempatam; D-009: cadastro mais novo por
último). Não é escolha nova: sob cedência progressiva
com preenchimento guloso, ao chegar ao grau k todos os recuperáveis dos
graus anteriores já entraram, então o pool do grau k é exatamente quem
depende dele — reordenar o acumulado por nota daria o mesmo resultado; as
duas leituras coincidem.

CONSEQUÊNCIA DISTRIBUTIVA, decorrente da ordem da Spec e visível na planilha:
um imóvel de nota ALTA que exige o grau 3 perde a vaga para um de nota BAIXA
que exige só o grau 1 — a ordem de cedência prevalece sobre a nota entre
graus. Ponto de atenção ao dono.

PRECONDIÇÕES NÃO VERIFICADAS AQUI (mesmo padrão da alocação): os candidatos
deste lote são os REPROVADOS da elegibilidade (regras_reprovadas vem de
dominio.elegibilidade.regras_reprovadas) e são DISJUNTOS dos já alocados
pela fase 2 — o módulo não tem como conferir a disjunção.

O relatório de cedência é parte inseparável do resultado: sem ele a etapa de
decisão não é considerada pronta (Spec §6.6). Ele lista APENAS os graus
efetivamente cedidos — linha com zero para grau cedido que não recuperou
ninguém, nenhuma linha para grau nunca alcançado. Déficit residual é
resultado legítimo quando os seis graus não bastam.

Invariantes 4 e 5: cálculo puro — sem I/O, sem relógio, sem aleatoriedade,
sem chamada a modelo.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from dominio.alocacao import COTA_DESTAQUE
from dominio.elegibilidade import ORDEM_RELAXAMENTO, Regra


@dataclass(frozen=True)
class CandidatoRelaxamento:
    """Um imóvel reprovado na elegibilidade, candidato à recuperação."""

    imovel_id: int
    nota_destaque: float
    regras_reprovadas: frozenset[Regra]
    # D-029: gestor sem login na janela declarada. Só importa se GESTOR_PRODUTIVO
    # está entre as reprovadas; então o candidato é irrecuperável.
    gestor_sem_login: bool = False
    # D-028: leads normalizados — a mesma chave secundária da alocação.
    desempate: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "regras_reprovadas", frozenset(self.regras_reprovadas))
        if not self.regras_reprovadas:
            raise ValueError(
                f"candidato {self.imovel_id} sem regra reprovada: elegível não entra no relaxamento"
            )
        estranhas = sorted(str(r) for r in self.regras_reprovadas if not isinstance(r, Regra))
        if estranhas:
            raise ValueError(f"regras_reprovadas com valor que não é Regra: {estranhas}")
        if not math.isfinite(self.nota_destaque):
            raise ValueError(f"nota não finita para nota_destaque: {self.nota_destaque}")
        if not math.isfinite(self.desempate):
            raise ValueError(f"desempate não finito: {self.desempate}")


@dataclass(frozen=True)
class ImovelRecuperado:
    """Um imóvel admitido por cedência. `degrau` é a última regra cedida de
    que ele dependeu — a justificativa da planilha."""

    imovel_id: int
    nota_destaque: float
    degrau: Regra


@dataclass(frozen=True)
class LinhaRelatorio:
    """Uma cedência efetivada: a regra e quantas posições dependeram dela."""

    regra: Regra
    posicoes_dependentes: int


@dataclass(frozen=True)
class ResultadoRelaxamento:
    """Recuperados na ordem de proposta (grau, depois nota), relatório
    obrigatório e o déficit que os seis graus não cobriram."""

    recuperados: tuple[ImovelRecuperado, ...]
    relatorio: tuple[LinhaRelatorio, ...]
    deficit_restante: int
    # D-029: quantos candidatos ficaram irrecuperáveis pela trava do login (gestor sem
    # login E reprovado em gestor_produtivo). Declarado na planilha.
    bloqueados_por_login: int = 0


def _travado_pelo_login(candidato: CandidatoRelaxamento) -> bool:
    return candidato.gestor_sem_login and Regra.GESTOR_PRODUTIVO in candidato.regras_reprovadas


def _degrau_minimo(candidato: CandidatoRelaxamento) -> int | None:
    """Índice do maior degrau exigido, ou None se alguma regra não relaxa — ou se a
    trava do login (D-029) o torna irrecuperável."""
    if not candidato.regras_reprovadas <= frozenset(ORDEM_RELAXAMENTO):
        return None
    if _travado_pelo_login(candidato):
        return None
    return max(ORDEM_RELAXAMENTO.index(regra) for regra in candidato.regras_reprovadas)


def relaxar(deficit: int, candidatos: Sequence[CandidatoRelaxamento]) -> ResultadoRelaxamento:
    """Desce a ordem de cedência até completar o déficit ou esgotar os graus."""
    if deficit < 0:
        raise ValueError(f"deficit negativo: {deficit}")
    if deficit > COTA_DESTAQUE:
        # Invariante 6 na fronteira: déficit maior que a cota denuncia bug de
        # integração no chamador — nunca produzir posições além do contrato.
        raise ValueError(f"deficit maior que a cota de destaque ({COTA_DESTAQUE}): {deficit}")
    contagem = Counter(c.imovel_id for c in candidatos)
    duplicados = sorted(i for i, n in contagem.items() if n > 1)
    if duplicados:
        raise ValueError(f"imovel_id duplicado no lote: {duplicados}")

    recuperados: list[ImovelRecuperado] = []
    relatorio: list[LinhaRelatorio] = []
    restante = deficit
    # Contado sempre, mesmo sem déficit: a trava é fato sobre os candidatos, não sobre
    # a cedência — e a planilha declara "N travados" ainda que ninguém tenha sido
    # cedido, para o dono ver o efeito da regra.
    bloqueados = sum(
        1
        for c in candidatos
        if c.regras_reprovadas <= frozenset(ORDEM_RELAXAMENTO) and _travado_pelo_login(c)
    )

    if restante > 0:
        por_degrau: dict[int, list[CandidatoRelaxamento]] = {}
        for candidato in candidatos:
            degrau = _degrau_minimo(candidato)
            if degrau is not None:
                por_degrau.setdefault(degrau, []).append(candidato)

        for indice, regra in enumerate(ORDEM_RELAXAMENTO):
            pool = sorted(
                por_degrau.get(indice, ()),
                key=lambda c: (-c.nota_destaque, -c.desempate, -c.imovel_id),
            )
            entram = pool[:restante]
            relatorio.append(LinhaRelatorio(regra=regra, posicoes_dependentes=len(entram)))
            recuperados.extend(
                ImovelRecuperado(imovel_id=c.imovel_id, nota_destaque=c.nota_destaque, degrau=regra)
                for c in entram
            )
            restante -= len(entram)
            if restante == 0:
                break

    return ResultadoRelaxamento(
        recuperados=tuple(recuperados),
        relatorio=tuple(relatorio),
        deficit_restante=restante,
        bloqueados_por_login=bloqueados,
    )
