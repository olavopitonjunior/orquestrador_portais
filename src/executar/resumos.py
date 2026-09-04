"""O relatório de cada agente — derivado do ESTADO, nunca escrito pelo nó.

O dono pediu "os relatórios gerados pelos agentes, as explicações, os logs do que eles
fizeram". Sem modelo de linguagem (nenhum SDK no repositório, provedor não escolhido —
[P-14]) e sem alucinação possível, a resposta honesta é a que o sistema já pratica: cada
agente reporta, de forma DETERMINÍSTICA, o que leu, o que produziu e o que não conseguiu.
Toda cifra aqui vem do cálculo; nenhuma é redigida.

Por que fora dos nós: os nós do grafo são o caminho da decisão (invariante 4) e não
mudam por causa de uma tela. O runner já recebe o estado acumulado a cada nó concluído
(`ao_terminar_no`); este módulo o lê e conta. Zero mudança em `src/grafo`.

Por que só contagens e rótulos: o resumo viaja para `operacao.trabalho_evento` e para a
tela. Nenhum id de imóvel, nenhum objeto de domínio, nenhum dado do Newcore além de
totais — a mesma disciplina do NDJSON, que "só leva nome do nó, instante e os prontos".
JSON puro por construção, e há teste que o serializa.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from dominio.perfil import EVIDENCIA_MINIMA

Resumo = dict[str, Any]


def _rotulo(regra: Any) -> str:
    return str(getattr(regra, "value", getattr(regra, "name", regra)))


def resumo_do_no(
    no: str,
    estado: Mapping[str, Any],
    *,
    degradacoes_novas: Sequence[str] = (),
    recorte_amostral: int | None = None,
) -> Resumo:
    """O que o nó `no` deixou no estado, contado. `degradacoes_novas` são as que
    surgiram desde a emissão anterior — atribuídas a este nó (no fan-out, ao par)."""
    r: Resumo
    if no == "coletor_interno":
        r = {
            "candidatos": len(estado.get("candidatos") or ()),
            "penalizaveis": len(estado.get("penalizaveis") or {}),
            "com_dimensoes": len(estado.get("dims") or {}),
            "recorte_amostral": recorte_amostral,
        }
    elif no == "analista_perfil":
        perfis = tuple(estado.get("perfis") or ())
        r = {
            "perfis": len(perfis),
            "frageis": sum(1 for p in perfis if p.num_vendas < EVIDENCIA_MINIMA),
            "evidencia_minima": EVIDENCIA_MINIMA,
            "de_uma_dimensao": sum(1 for p in perfis if len(p.dimensoes) == 1),
            "de_duas_dimensoes": sum(1 for p in perfis if len(p.dimensoes) == 2),
            "vendas_no_maior_perfil": max((p.num_vendas for p in perfis), default=0),
        }
    elif no == "coletor_externo":
        r = {
            "entrou_no_ranking": bool(estado.get("externo_presente")),
            "taxa_amarracao": estado.get("externo_taxa_amarracao"),
            "idade_dias": estado.get("externo_idade_dias"),
            "imoveis_com_anuncio": len(estado.get("anuncios_por_imovel") or {}),
        }
    elif no == "decisor":
        res = estado.get("resultado")
        if res is None:
            r = {"resultado": None}
        else:
            por_regra = Counter(
                _rotulo(regra) for regras in res.reprovados_regras.values() for regra in regras
            )
            r = {
                "elegiveis": res.n_elegiveis,
                "reprovados": res.n_reprovados,
                "reprovados_por_regra": dict(sorted(por_regra.items())),
                "super_destaque": len(res.alocacao.super_destaque),
                "destaque": len(res.alocacao.destaque),
                "recuperados_por_relaxamento": len(res.relaxamento.recuperados),
                "posicoes_vazias": res.relaxamento.deficit_restante,
                "janelas_lidas": estado.get("janelas_lidas"),
            }
    elif no == "crivo":
        v = estado.get("veredito")
        r = {
            "passou": bool(v is not None and v.pronta),
            "violacoes": [str(x.codigo) for x in v.violacoes] if v is not None else [],
        }
    else:  # redator, finalizar, registrar — e qualquer nó futuro: o mínimo honesto
        # Só o estado: os `prontos` já viajam na própria linha do NDJSON.
        r = {"estado": str(estado.get("estado"))}
    r["degradacoes"] = list(degradacoes_novas)
    outros = [x for x in (estado.get("nos_do_passo") or ()) if x != no]
    if outros:
        # As degradações acima são do PASSO, não só deste nó — ver AtribuidorDeDegradacoes.
        r["degradacoes_compartilhadas_com"] = outros
    return r


class AtribuidorDeDegradacoes:
    """Atribui a cada PASSO do grafo as degradações que surgiram nele.

    O estado acumula `degradacoes` por reducer; o nó não diz quais são suas. Mas o
    runner vê o estado a cada passo, e a diferença entre duas vistas é o que aquele
    passo acrescentou. Quando o passo tem mais de um nó (o fan-out perfil ∥ coleta
    externa), a ordem em que os dois são anunciados é a de conclusão das threads —
    NÃO determinística —, então as degradações do passo são atribuídas AO PAR: os
    dois nós recebem a mesma lista, e o resumo diz com quem ela é compartilhada. É
    isso que torna o relatório função só do grafo, e não do relógio.

    "Mesmo passo" é identificado pela tupla de nós: dois passos CONSECUTIVOS com a mesma
    tupla seriam fundidos. Inalcançável na topologia atual (sem laço, sem repetição de
    nó); quando o retry do Orquestrador (parâmetro nº 4, nulo) for fiado, esta chave
    precisa ganhar o número do passo."""

    def __init__(self) -> None:
        self._vistas = 0
        self._passo: tuple[str, ...] | None = None
        self._novas: list[str] = []

    def novas(self, estado: Mapping[str, Any], no: str) -> list[str]:
        """As degradações do passo em que `no` foi anunciado. `estado["nos_do_passo"]`
        (gravado pelo runner) diz quais nós saíram juntos; ausente, o passo é só `no`."""
        passo = tuple(estado.get("nos_do_passo") or (no,))
        if passo != self._passo:
            todas = list(estado.get("degradacoes") or ())
            self._novas = todas[self._vistas :]
            self._vistas = len(todas)
            self._passo = passo
        return list(self._novas)
