"""Os valores ADOTADOS dos parâmetros da rodada — a parametrização padrão (D-034).

Até 04/09/2026 este projeto não tinha nenhum valor de parâmetro em `src/config`:
catorze parâmetros eram nulos e o CLAUDE.md proibia preenchê-los com valor inventado.
Continua proibindo. O que mudou é que o dono da decisão APROVOU uma parametrização
padrão (plano de 04/09/2026, D-034), com a razão de cada número medida ou citada —
e valor com decisão registrada não é valor inventado: é valor adotado.

Este módulo é a única casa desses valores. O carregador (`config.parametros`) os
usa quando o arquivo da rodada não declara a chave, e ROTULA a procedência de cada
um ("adotado D-034" ou "declarado nesta rodada"), para a planilha e o Registro
dizerem de onde cada número veio. Mudar um valor aqui é mudar regra de decisão:
exige nova decisão em `docs/decisoes.md` e entrada no CHANGELOG.

Os que seguem NULOS não estão aqui, e nunca ganham default: a régua de resultado por
nível (nº 14) e a forma de normalização (nº 2, min-max provisório fixo no código).
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

# Chave = caminho no TOML da rodada. Valores em unidade concreta (dias, pontos de
# 100, %, contagem) — nunca em escala abstrata de 0 a 1.
ADOTADOS: Mapping[str, int | float | str] = MappingProxyType(
    {
        # --- quem entra: o banco -------------------------------------------------
        # A janela medida, com 176–184 vendas assinadas; em 30 dias seriam ~25 (PRD).
        "conversao.janela_dias": 180,
        # Mesma janela da produtividade (Spec §6.1), para a trava do login (D-029) ficar
        # coerente com a regra irmã.
        "corretor.login_janela_dias": 30,
        # D-015: passar de 3 para 2 elevou a cobertura de vendas de 62% para 75%.
        "corretor.minimo_no_distrito": 2,
        # --- em que ordem: o portal ---------------------------------------------
        # Único sinal com variância medida. Os 14 valores distintos citados pela D-034
        # eram da amostra de 300; a coleta completa (06/09/2026) achou 69 em 55.162, e
        # a nota vem preenchida em 100 % dos anúncios. A conclusão que sustenta este
        # peso ficou MAIS forte, não mais fraca — só o número envelheceu.
        "portal.peso_nota": 70,
        # "Sinal fraco mas real, e é intenção de compra, não curiosidade" (D-034). A
        # primeira metade da frase ficou MUITO mais fraca do que ela sugeria: na coleta
        # completa, algum clique aparece em 933 de 55.162 anúncios (1,69 %), e dois dos
        # cinco tipos — proposta e agendamento — são zero em 55.162 de 55.162. Na rodada
        # 30417, entre os 6.970 escolhidos, os cliques separaram 124 imóveis (1,8 %) com
        # 9 valores distintos, contra 1.550 (22,2 %) e 74 valores das visualizações, que
        # pesam ZERO. A segunda metade — intenção de compra — continua de pé e é
        # qualitativa: um clique vale mais por unidade que uma visualização.
        # A escolha entre as duas é do dono, e está na [P-25] junto com o peso das
        # visualizações: os três somam 100, então é uma alocação só.
        "portal.peso_cliques": 30,
        # PREMISSA CAÍDA, valor mantido. O zero foi adotado por uma medição de
        # 03/09/2026 sobre 300 anúncios, todos sem visualizações. A primeira coleta
        # COMPLETA (06/09/2026, 55.162 anúncios) achou 13.175 com visualizações —
        # 23,9 %. O campo não vinha vazio: a amostra é que era pequena. O valor
        # continua sendo o adotado da D-034 até o dono decidir ([P-25]); mudá-lo
        # aqui sem decisão seria trocar o número dele por um meu.
        "portal.peso_visualizacoes": 0,
        # Abaixo da metade, a ordem da vitrine seria decidida por menos da metade do
        # estoque. Em PERCENTUAL, não fração.
        "portal.cobertura_minima": 50,
        # A rodada raspa no mesmo dia; 2 tolera um retry sem aceitar dado da semana passada.
        "portal.idade_maxima_dias": 2,
        # O que já acontecia, só que em silêncio.
        "portal.sem_anuncio": "fim_da_fila",
        # O sinal de banco mais próximo do objetivo do destaque, que é gerar lead.
        "portal.ordem_quando_nao_entra": "leads_180d",
        # --- descontos, em pontos de 100 ----------------------------------------
        # Inerte enquanto a régua nº 14 for nula — e a planilha diz isso em toda linha.
        "desconto.janela_sem_resultado": 20,
        # Baixo de propósito: o pipeline de avaliação morreu em 16/10/2025 e 99,76% do
        # estoque novo não tem nota; descontar alto puniria o estoque novo por defeito da base.
        "desconto.sem_avaliacao": 5,
        "desconto.sem_lead_180d": 10,
        # O desconto cai pela metade a cada carga; some em cerca de três semanas. Em %.
        "desconto.perdao_por_semana": 50,
    }
)

DECISAO_DOS_ADOTADOS = "D-034"
