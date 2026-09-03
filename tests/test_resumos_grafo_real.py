"""O relatório dos agentes contra o grafo REAL, pelo emissor de eventos de `executar`.

Os testes de `test_resumos.py` usam `SimpleNamespace`: um rename em `ResultadoDecisao`
passaria neles e apareceria ao dono como `indisponivel: AttributeError`. Aqui o grafo
de verdade (fontes falsas, sem raspagem) atravessa `executar` — o mesmo laço que
grava `nos_do_passo` — e o NDJSON é o que a tela leria. Nasceu de uma sondagem do
revisor de código, que mostrou a degradação do portal saindo sob `analista_perfil`.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from test_grafo import PARAMS, _candidato, _fontes

import executar.sexta as mod
from config.parametros import carregar
from grafo.fluxo import construir_grafo

EXEMPLO = Path(__file__).resolve().parent.parent / "docs" / "parametros-da-rodada.exemplo.toml"
PAR = {"analista_perfil", "coletor_externo"}


def _linhas(tmp_path: Path, monkeypatch, k: int) -> list[dict]:
    alvo = tmp_path / f"e{k}.ndjson"
    grafo = construir_grafo(_fontes([_candidato(1), _candidato(2)]), PARAMS)
    monkeypatch.setattr(mod, "construir_grafo", lambda *a, **kw: grafo)
    mod.executar(
        tmp_path / f"s{k}",
        carregar(EXEMPLO),
        hoje=date(2026, 9, 4),
        dry_run=True,
        ao_terminar_no=mod._emissor_de_eventos(alvo),
    )
    return [json.loads(linha) for linha in alvo.read_text(encoding="utf-8").splitlines()]


@pytest.mark.parametrize("k", range(5))
def test_nenhum_agente_fica_indisponivel_e_a_degradacao_do_portal_vai_ao_PAR(
    tmp_path, monkeypatch, k
):
    linhas = _linhas(tmp_path, monkeypatch, k)
    por_no = {linha["no"]: linha["resumo"] for linha in linhas}
    for no, resumo in por_no.items():
        assert "indisponivel" not in resumo, (no, resumo)
    # A rodada correu sem raspagem: a degradação do Coletor Externo existe e vai aos
    # DOIS nós do passo, qualquer que tenha sido a ordem de conclusão das threads.
    for no in PAR:
        assert any("Coletor Externo" in d for d in por_no[no]["degradacoes"]), por_no[no]
        assert por_no[no]["degradacoes_compartilhadas_com"] == [next(iter(PAR - {no}))]
    assert por_no["coletor_externo"]["entrou_no_ranking"] is False
    d = por_no["decisor"]
    assert d["elegiveis"] + d["reprovados"] == 2
    assert isinstance(d["reprovados_por_regra"], dict)
    assert por_no["crivo"]["passou"] is True
    assert por_no["coletor_interno"]["candidatos"] == 2
    assert por_no["coletor_interno"]["recorte_amostral"] is None
