"""Leitura dos leads do período para a rodada de SEGUNDA (Spec §4).

Somente leitura do Newcore (invariante 1), via a guarda SELECT/SHOW de
`dados.newcore.consultar`. Monta os `LeadDoPeriodo` que `dominio.acompanhamento`
apura — nenhuma regra vive aqui: esta camada só busca e converte.

Fonte e armadilhas medidas em 01/09/2026 (detalhe em `docs/mapa-de-dados.md`,
seção "Fonte dos campos da RODADA DE SEGUNDA"):

- Tudo vem de `newcore_bi.FT_Leads`, cujo grão é **`FacId`** (o par lead↔imóvel),
  não `LeadID`: a mesma pessoa aparece em várias linhas (17.741 FacId para 14.331
  LeadID em 90 dias). O `lead_id` do domínio é o `FacId` — usar `LeadID` produziria
  linhas duplicadas na aba de leads sem tratamento.
- A coluna do imóvel é **`IdImovel`** (no transacional e em `FT_RealtyRelation` o
  mesmo campo se chama `Realty_Id`).
- A data de distribuição é **`DIstributedAt`** — grafia irregular, com "I" maiúsculo.
- `FT_LeadsAttendance` NÃO serve: seu grão é corretor × período, não tem `FacId`.
- O filtro é por **`CreatedAt`**, o único caminho indexado (`IDX_FT_Leads_CreatedAt`);
  filtrar por `DIstributedAt` varreria mais de um milhão de linhas.

D-018: "atendimento registrado" inclui o HISTÓRICO, não só o estado atual —
`AttendedAt` é apagado quando o lead sai do atendimento, e a regra ingênua acusaria
de abandono quem foi atendido (46% dos "sem tratamento" de 90 dias).
D-019: "gestor de distrito" da Spec §4.2 é o **embaixador**.

LIMITAÇÃO DECLARADA — a janela é de DIAS INTEIROS, a carga entra no ar numa HORA.
A rodada é gravada com hora (`registro.rodada.inicio` é timestamptz), mas este
recorte é `CreatedAt >= inicio 00:00`. Um lead de sexta ANTES de a carga ser
aplicada é atribuído a ela: infla `leads_gerados` e pode pôr na aba de cobrança um
lead que nenhum destaque gerou. O desenho dia-a-dia é coerente de ponta a ponta (o
domínio também compara `date`), então fica assim — mas é atribuição otimista, não
exatidão. Estreitar para hora exigiria `inicio`/`fim` como `datetime` aqui e no
domínio; é fatia própria, se o dono quiser o recorte exato.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from dados.newcore import consultar
from dominio.acompanhamento import LeadDoPeriodo

# `StatusAfter = 12` é 'Atendimento' em `newcore.facstatushistory` (D-018).
STATUS_ATENDIMENTO = 12

_SQL_LEADS = """
SELECT
    f.FacId                AS lead_id,
    f.IdImovel             AS imovel_id,
    f.CreatedAt            AS entrada,
    f.DIstributedAt        AS distribuicao,
    f.AttendedAt           AS atendido_em,
    COALESCE(f.QtdeContatos, 0) AS qtde_contatos,
    f.Gestor               AS corretor_gestor,
    f.embaixador           AS gestor_distrito,
    f.District             AS distrito,
    EXISTS (
        SELECT 1 FROM newcore.facstatushistory h
        WHERE h.Fac_Id = f.FacId AND h.StatusAfter = %(status_atendimento)s
    ) AS atendeu_algum_dia
FROM newcore_bi.FT_Leads f
WHERE f.CreatedAt >= %(inicio)s
  AND f.CreatedAt < %(fim_exclusivo)s
ORDER BY f.FacId
"""


def _para_date(valor: Any) -> date | None:
    if valor is None:
        return None
    return valor.date() if isinstance(valor, datetime) else valor


def _para_lead(linha: dict[str, Any]) -> LeadDoPeriodo:
    entrada = _para_date(linha["entrada"])
    if entrada is None:  # `CreatedAt` é NOT NULL na origem; se vier nulo, é deriva
        raise ValueError(f"lead {linha['lead_id']} sem CreatedAt — origem mudou")
    return LeadDoPeriodo(
        lead_id=int(linha["lead_id"]),
        imovel_id=int(linha["imovel_id"]),
        entrada=entrada,
        # D-018: o sinal é o estado atual OU a passagem histórica por 'Atendimento'.
        atendimento_registrado=(
            linha["atendido_em"] is not None
            # int(), não bool(): se o driver devolvesse a string "0",
            # bool("0") seria True e a lista de cobrança esvaziaria em silêncio.
            or int(linha["atendeu_algum_dia"] or 0) == 1
        ),
        contato_registrado=int(linha["qtde_contatos"] or 0) > 0,
        distribuicao=_para_date(linha["distribuicao"]),
        corretor_gestor=linha["corretor_gestor"] or None,
        gestor_distrito=linha["gestor_distrito"] or None,  # D-019: o embaixador
        distrito=linha["distrito"] or None,
    )


def coletar_leads(inicio: date, fim: date) -> tuple[list[LeadDoPeriodo], int]:
    """Leads criados no período [inicio, fim] — ambos INCLUSIVOS, como o domínio
    filtra (o SQL usa `< fim + 1 dia` porque `CreatedAt` tem hora).

    Devolve `(leads, descartados_sem_imovel)`: lead sem `IdImovel` não pode estar em
    posição paga, mas o descarte é CONTADO em vez de sumir na cláusula WHERE (são
    ~3,4% das linhas) — mesma disciplina do domínio, onde todo descarte é contado.

    Ordenado por `FacId` na origem: sem `ORDER BY` o colapso de duplicatas do
    domínio ficaria exposto à ordem de chegada do banco (invariante 5) — o domínio
    já é robusto a isso, mas a consulta não deve ser a fonte da instabilidade.
    """
    if fim < inicio:
        raise ValueError("fim do período anterior ao início")
    linhas = consultar(
        _SQL_LEADS,
        {
            "inicio": inicio,
            # `CreatedAt` é datetime: para incluir o dia `fim` inteiro, corta no dia
            # seguinte com `<` em vez de `<=` na data.
            "fim_exclusivo": date.fromordinal(fim.toordinal() + 1),
            "status_atendimento": STATUS_ATENDIMENTO,
        },
    )
    com_imovel = [linha for linha in linhas if linha["imovel_id"] is not None]
    return [_para_lead(linha) for linha in com_imovel], len(linhas) - len(com_imovel)
