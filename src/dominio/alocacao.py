"""Alocação: preenchimento das cotas contratadas a partir das notas finais.

Fonte: Spec §6.5, lida conforme a D-008 (a nota final por nível é a chave de
ordenação). Primeiro o super destaque: aplica o piso de R$ 700.000, ordena
por nota de super destaque e preenche até 475 posições. Depois o destaque:
entre TODOS os candidatos restantes — inclusive os que disputaram o super
destaque e não couberam —, ordena por nota de destaque e preenche até 6.495.
Nenhuma posição excedente é proposta (invariante 6): o corte é por fatia,
estruturalmente incapaz de exceder a cota.

PRECONDIÇÃO NÃO VERIFICADA AQUI: a entrada JÁ é o conjunto elegível
(dominio.elegibilidade aplicada pelo Decisor antes). Este módulo não reaplica
as oito regras; o piso de R$ 700.000 é o único filtro que ele aplica, e só
para o nível super. Alimentá-lo com estoque não filtrado distribui posição
paga a imóvel inelegível sem erro algum.

Déficit é resultado legítimo: com menos candidatos que a cota, a lista sai
curta — é o sinal que o relaxamento (Spec §6.6, módulo futuro, apenas nível
destaque) existe para atacar. Nada aqui preenche artificialmente.

Leitura estrutural declarada: nenhum documento define desempate. O critério
adotado é nota decrescente com desempate por imovel_id crescente — total e
determinístico (invariante 5), mas NÃO neutro: em todo empate favorece
sistematicamente o cadastro mais antigo. Ponto de calibração para o dono.

Invariantes 4 e 5: cálculo puro — sem I/O, sem relógio, sem aleatoriedade,
sem chamada a modelo. As cotas também vivem em CHECK no DDL do Registro
(src/dados/registro/001_registro.sql); o teste de amarração garante que os
dois lados não divergem em silêncio.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from dominio.elegibilidade import PRECO_MINIMO_SUPER_DESTAQUE

# Cotas contratadas (contrato OLX, plano Exclusivo) — invariante 6. Mudança
# aqui é mudança contratual: exige CHANGELOG e ALTER TABLE no Registro
# (constraint posicao_dentro_da_cota), amarrados por teste.
COTA_SUPER_DESTAQUE = 475
COTA_DESTAQUE = 6_495


@dataclass(frozen=True)
class CandidatoAlocacao:
    """Um imóvel elegível com as duas notas finais, uma por nível.

    As notas são campos distintos de propósito: os pesos diferem por nível
    (Spec §6.3) e nota de super destaque nunca se compara com nota de
    destaque — a fase 1 só lê `nota_super_destaque`, a fase 2 só lê
    `nota_destaque`. Abaixo do piso de R$ 700.000, `nota_super_destaque` é
    obrigatória porém ignorada: o candidato nunca entra na fase 1.
    """

    imovel_id: int
    preco: int  # em REAIS, como em elegibilidade.ImovelCandidato
    nota_super_destaque: float
    nota_destaque: float

    def __post_init__(self) -> None:
        if self.preco < 0:
            raise ValueError(f"preco negativo: {self.preco}")
        for campo in ("nota_super_destaque", "nota_destaque"):
            valor = getattr(self, campo)
            if not math.isfinite(valor):
                raise ValueError(f"nota não finita para {campo}: {valor}")


@dataclass(frozen=True)
class PosicaoAlocada:
    """Uma posição paga proposta: 1-indexada dentro do nível, como no Registro."""

    posicao: int
    imovel_id: int
    nota: float  # a nota do nível em que a posição foi alocada


@dataclass(frozen=True)
class Alocacao:
    """Resultado das duas fases. Um imóvel aparece em NO MÁXIMO uma lista."""

    super_destaque: tuple[PosicaoAlocada, ...]
    destaque: tuple[PosicaoAlocada, ...]


def alocar(candidatos: Sequence[CandidatoAlocacao]) -> Alocacao:
    """Executa as duas fases da Spec §6.5 e devolve as posições propostas."""
    contagem = Counter(c.imovel_id for c in candidatos)
    duplicados = sorted(i for i, n in contagem.items() if n > 1)
    if duplicados:
        raise ValueError(f"imovel_id duplicado no lote: {duplicados}")

    # Fase 1 — super destaque: piso de nível, nota do nível, cota 475.
    aptos_super = [c for c in candidatos if c.preco >= PRECO_MINIMO_SUPER_DESTAQUE]
    ordem_super = sorted(aptos_super, key=lambda c: (-c.nota_super_destaque, c.imovel_id))
    escolhidos_super = ordem_super[:COTA_SUPER_DESTAQUE]
    super_ids = {c.imovel_id for c in escolhidos_super}

    # Fase 2 — destaque: TODOS os restantes, nota do nível, cota 6.495.
    restantes = [c for c in candidatos if c.imovel_id not in super_ids]
    ordem_destaque = sorted(restantes, key=lambda c: (-c.nota_destaque, c.imovel_id))
    escolhidos_destaque = ordem_destaque[:COTA_DESTAQUE]

    return Alocacao(
        super_destaque=tuple(
            PosicaoAlocada(posicao=i, imovel_id=c.imovel_id, nota=c.nota_super_destaque)
            for i, c in enumerate(escolhidos_super, start=1)
        ),
        destaque=tuple(
            PosicaoAlocada(posicao=i, imovel_id=c.imovel_id, nota=c.nota_destaque)
            for i, c in enumerate(escolhidos_destaque, start=1)
        ),
    )
