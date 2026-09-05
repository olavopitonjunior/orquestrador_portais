"""A PRÉVIA: o funil de elegibilidade com os parâmetros da tela, antes de rodar.

    python -m executar.previa --resultado <arquivo.json> [--parametros <arquivo.toml>]
                              [--hoje AAAA-MM-DD]

Responde à pergunta que a tela de parâmetros não conseguia responder: "com estes
valores, quantos imóveis sobram para as 6.970 posições?" — e onde cada regra corta.
É o elo entre DEFINIR e RODAR (plano da Fatia 5): o dono mexe num número, pede a
prévia, e vê o funil antes de gastar a única raspagem da semana.

O que ela É: as mesmas leituras do Newcore que a sexta faz (candidatos com o login na
janela declarada, vendas na janela declarada, dimensões dos candidatos), o MESMO filtro
de perfil (`piloto.decisao.aplicar_filtro_de_perfil`) e as MESMAS regras
(`dominio.elegibilidade.regras_reprovadas`, com o mínimo do distrito declarado). Nada
é reimplementado aqui: se a prévia e a rodada divergissem no funil, a prévia mentiria
— e há teste que as compara sobre a mesma entrada.

O que ela NÃO é: não raspa o portal, não ordena, não aloca, não escreve no Registro
nem em planilha. A projeção de posições preenchidas é aritmética sobre contagens
(quantos elegíveis acima do piso cabem nas 475; quantos sobram para as 6.495), não a
alocação de verdade — e é rotulada assim na tela.

Só lê o Newcore (invariante 1). Só contagens, rótulos e parâmetros saem daqui — nenhum
id de imóvel, nenhum nome (invariante 3, e o resultado vira `trabalho_evento.resumo`).
Cálculo puro sobre o que foi lido (invariantes 4 e 5): `montar_previa` não tem I/O.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from config.parametros import ParametroAusente, ParametroInvalido, ParametrosDaRodada, carregar
from config.recorte import DEFINICAO_ATIVO
from dados.candidatos_perfil import coletar_dimensoes_candidatos
from dados.coletor_interno import coletar
from dados.vendas import coletar_vendas
from dominio.alocacao import COTA_DESTAQUE, COTA_SUPER_DESTAQUE
from dominio.elegibilidade import (
    JANELA_ATUALIZACAO_DIAS,
    MINIMO_FOTOS,
    ORDEM_RELAXAMENTO,
    PRECO_MINIMO_GERAL,
    PRECO_MINIMO_SUPER_DESTAQUE,
    ImovelCandidato,
    Regra,
    regras_reprovadas,
)
from dominio.perfil import PerfilConversao, perfis_de_conversao
from piloto.decisao import aplicar_filtro_de_perfil
from piloto.semelhanca import DimensoesImovel

log = logging.getLogger("rodada.previa")

# A ordem de LEITURA do funil: os três blocos da tela (quem entra — o imóvel, o perfil,
# o corretor), na ordem dos grupos do contrato. É acumulado: cada linha conta quem
# passou também em todas as anteriores. `grupo` é a âncora em `/parametros`.
ORDEM_DO_FUNIL: tuple[tuple[Regra, str, str], ...] = (
    (Regra.STATUS_ATIVO, "publicação ativa", "quem_entra_imovel"),
    (Regra.CATEGORIA, "nas cinco categorias", "quem_entra_imovel"),
    (
        Regra.PRECO_GERAL,
        f"preço de R$ {PRECO_MINIMO_GERAL:,} ou mais".replace(",", "."),
        "quem_entra_imovel",
    ),
    (Regra.FOTOS, f"{MINIMO_FOTOS} fotos ou mais", "quem_entra_imovel"),
    (Regra.CADASTRO_COMPLETO, "cadastro completo", "quem_entra_imovel"),
    (
        Regra.ATUALIZACAO_90D,
        f"atualizado nos últimos {JANELA_ATUALIZACAO_DIAS} dias",
        "quem_entra_imovel",
    ),
    (Regra.PERFIL_DE_CONVERSAO, "parece com o que vendeu", "quem_entra_perfil"),
    (Regra.GESTOR_PRODUTIVO, "gestor captou ou vendeu em 30 dias", "quem_entra_corretor"),
    (Regra.CAPACIDADE_DISTRITO, "distrito com corretores produtivos", "quem_entra_corretor"),
)
# Toda regra do domínio tem linha no funil — nova regra sem linha é erro na importação,
# não na tela. `if`/`raise`, não `assert`: sob `python -O` o assert some.
if {r for r, _, _ in ORDEM_DO_FUNIL} != set(Regra):
    raise RuntimeError("regra do domínio sem linha em ORDEM_DO_FUNIL da prévia")


def montar_previa(
    candidatos: Sequence[ImovelCandidato],
    dims_por_imovel: Mapping[int, DimensoesImovel],
    perfis: Sequence[PerfilConversao],
    parametros: ParametrosDaRodada,
    hoje: date,
) -> dict[str, Any]:
    """O funil, a projeção de posições e o que o relaxamento poderia recuperar.
    FUNÇÃO PURA — só contagens; nenhum id sai daqui."""
    contagem = Counter(c.imovel_id for c in candidatos)
    duplicados = sorted(i for i, n in contagem.items() if n > 1)
    if duplicados:
        # A mesma recusa de `decidir`: entrada duplicada não pode produzir contagem
        # diferente da rodada em silêncio.
        raise ValueError(f"imovel_id duplicado no lote de candidatos: {duplicados}")
    p = parametros.decisao
    filtro = aplicar_filtro_de_perfil(
        candidatos, dims_por_imovel, perfis, p.exigir_dimensao_no_perfil
    )
    reprovadas = {
        c.imovel_id: regras_reprovadas(
            c, hoje, minimo_corretores_distrito=p.minimo_corretores_distrito
        )
        for c in filtro.candidatos
    }

    restantes = list(filtro.candidatos)
    funil: list[dict[str, Any]] = []
    for regra, rotulo, grupo in ORDEM_DO_FUNIL:
        antes = len(restantes)
        restantes = [c for c in restantes if regra not in reprovadas[c.imovel_id]]
        funil.append(
            {
                "regra": regra.value,
                "rotulo": rotulo,
                "grupo": grupo,
                "sobram": len(restantes),
                "cortou": antes - len(restantes),
            }
        )
    elegiveis = restantes
    n_elegiveis = len(elegiveis)
    candidatos_super = sum(1 for c in elegiveis if c.preco >= PRECO_MINIMO_SUPER_DESTAQUE)

    # Projeção ARITMÉTICA, não a alocação: quem está acima do piso disputa as 475 e o
    # resto dos elegíveis vai para as 6.495. A alocação real ordena por nota e pode
    # mandar um imóvel acima do piso para o destaque; para contar posições vazias a
    # aritmética basta, e é rotulada assim na tela.
    super_preenchido = min(candidatos_super, COTA_SUPER_DESTAQUE)
    destaque_preenchido = min(n_elegiveis - super_preenchido, COTA_DESTAQUE)
    vazias_super = COTA_SUPER_DESTAQUE - super_preenchido
    vazias_destaque = COTA_DESTAQUE - destaque_preenchido

    # O que a cedência (Spec §6.6, só no destaque) poderia recuperar, degrau a degrau,
    # com a trava do login (D-029) aplicada — a mesma regra de `dominio.relaxamento`.
    relaxaveis = frozenset(ORDEM_RELAXAMENTO)
    travados = 0
    degrau_minimo: Counter[int] = Counter()
    for c in filtro.candidatos:
        r = reprovadas[c.imovel_id]
        if not r or not r <= relaxaveis:
            continue
        if c.gestor_logou_na_janela is False and Regra.GESTOR_PRODUTIVO in r:
            travados += 1
            continue
        degrau_minimo[max(ORDEM_RELAXAMENTO.index(x) for x in r)] += 1
    por_degrau: list[dict[str, Any]] = []
    acumulado = 0
    for indice, regra in enumerate(ORDEM_RELAXAMENTO):
        acumulado += degrau_minimo.get(indice, 0)
        por_degrau.append({"regra": regra.value, "recuperaveis_ate_aqui": acumulado})

    reprovados_por_regra = Counter(x.value for r in reprovadas.values() for x in r)
    exigencia = p.exigir_dimensao_no_perfil
    return {
        "hoje": hoje.isoformat(),
        "candidatos": len(candidatos),
        "funil": funil,
        "reprovados_por_regra": dict(sorted(reprovados_por_regra.items())),
        "elegiveis": n_elegiveis,
        "candidatos_super_destaque": candidatos_super,
        "posicoes": {
            "super_destaque": COTA_SUPER_DESTAQUE,
            "destaque": COTA_DESTAQUE,
            "total": COTA_SUPER_DESTAQUE + COTA_DESTAQUE,
        },
        "projecao": {
            "super_destaque_preenchido": super_preenchido,
            "destaque_preenchido": destaque_preenchido,
            "vazias_super_destaque": vazias_super,
            "vazias_destaque": vazias_destaque,
            "vazias_total": vazias_super + vazias_destaque,
        },
        "relaxamento": {
            "recuperaveis": acumulado,
            "travados_pelo_login": travados,
            "por_degrau": por_degrau,
            "vazias_destaque_depois": max(0, vazias_destaque - acumulado),
        },
        "perfil": {
            "perfis": len(perfis),
            "robustos": sum(1 for x in perfis if not x.fragil),
            "que_contam": len(filtro.perfis_que_contam),
            "exigencia": exigencia.value if exigencia is not None else None,
            "sem_dimensoes": filtro.sem_dimensoes,
            "filtro_incide": bool(filtro.perfis_que_contam),
        },
        "degradacoes": list(filtro.degradacoes),
        "parametros": {
            "origem": parametros.origem,
            "efetivo": dict(parametros.efetivo),
            "procedencia": dict(parametros.procedencia),
            "declarados_diferentes_do_adotado": list(parametros.declarados_diferentes_do_adotado),
        },
    }


def _escrever(caminho: Path, *, codigo: int, falha: str | None = None, **resto: Any) -> None:
    """O desfecho, em TODOS os caminhos de saída. `falha` é só o TIPO da exceção:
    a mensagem pode ecoar dado do Newcore, e este arquivo vira tela."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps({"codigo": codigo, "falha": falha, **resto}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m executar.previa", description=__doc__)
    parser.add_argument("--resultado", type=Path, required=True, help="JSON com a prévia")
    parser.add_argument(
        "--parametros", type=Path, default=None, help="TOML declarado; sem ele, os adotados"
    )
    parser.add_argument("--hoje", type=date.fromisoformat, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    # A MESMA data de referência da sexta (`date.today()`, local): com UTC, entre 21h e
    # meia-noite a prévia decidiria com o "amanhã" da rodada e a regra dos 90 dias
    # cortaria diferente na fronteira. E a mesma recusa de data no futuro.
    if args.hoje and args.hoje > date.today():
        log.error("--hoje %s está no futuro", args.hoje)
        _escrever(args.resultado, codigo=2, falha="HojeNoFuturo")
        return 2
    hoje = args.hoje or date.today()

    try:
        parametros = carregar(args.parametros)
    except (ParametroAusente, ParametroInvalido) as e:
        log.error("parâmetros recusados: %s", e)
        _escrever(args.resultado, codigo=5, falha=type(e).__name__)
        return 5

    inicio = time.monotonic()
    coleta = parametros.coleta
    try:
        log.info(
            "lendo os candidatos do Newcore (login do gestor em %d dias) — leva minutos",
            coleta.login_janela_dias,
        )
        candidatos, _penalizaveis = coletar(
            DEFINICAO_ATIVO, login_janela_dias=coleta.login_janela_dias
        )
        log.info("%d candidatos lidos", len(candidatos))
        log.info("lendo as vendas assinadas em %d dias", coleta.janela_conversao_dias)
        vendas, descartadas = coletar_vendas(coleta.janela_conversao_dias)
        log.info("%d vendas ancoráveis (%d descartadas)", len(vendas), descartadas)
        log.info("lendo as dimensões dos candidatos")
        dims = coletar_dimensoes_candidatos()
    except Exception as e:  # noqa: BLE001 — a fonte pode falhar de mil jeitos; o código diz
        log.error("falha ao ler o Newcore: %s", type(e).__name__)
        _escrever(args.resultado, codigo=3, falha=type(e).__name__)
        return 3

    try:
        perfis = perfis_de_conversao(vendas)
        previa = montar_previa(candidatos, dims, perfis, parametros, hoje)
        previa["vendas"] = {
            "assinadas": len(vendas),
            "descartadas": descartadas,
            "janela_dias": coleta.janela_conversao_dias,
        }
        previa["duracao_s"] = round(time.monotonic() - inicio, 1)
        _escrever(args.resultado, codigo=0, previa=previa)
    except Exception as e:  # noqa: BLE001 — o desfecho precisa sair mesmo com bug aqui
        log.error("falha ao montar ou escrever a prévia: %s", type(e).__name__)
        _escrever(args.resultado, codigo=1, falha=type(e).__name__)
        return 1
    log.info(
        "prévia: %d elegíveis para %d posições; %d ficariam vazias antes do relaxamento",
        previa["elegiveis"],
        previa["posicoes"]["total"],
        previa["projecao"]["vazias_total"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
