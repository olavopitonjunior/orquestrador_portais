"""O contrato de desempenho de anúncio no portal.

Por que um contrato de dado EXTERNO vive num pacote de REGRAS, que é a tensão
óbvia deste arquivo: `DesempenhoAnuncio` não é dado do coletor — é o VOCABULÁRIO
com que a decisão fala de desempenho de anúncio. Quem define o que o dado
significa é a camada de dentro; quem o produz é a de fora. Por isso
`dados/coletor_externo.py` importa daqui, e não o contrário.

É a direção da dependência que põe este arquivo aqui, e ela é a razão, não uma
exceção. Antes o caminho da decisão (`piloto/decisao.py`) importava de
`dados/coletor_externo.py`, enquanto `dados/registro/escrita.py` importava de
`piloto/decisao.py` — acoplamento nos dois sentidos entre a camada que decide e a
que faz I/O. Mover o símbolo elimina a aresta errada: sobram `dados → dominio` e
`piloto → dominio`, que apontam para dentro.

Puro por construção, e travado por `tests/test_pureza_do_dominio.py`: dataclass
frozen de tipos primitivos, sem import nenhum de fora do domínio.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class DesempenhoAnuncio:
    """Sinais de portal de UM anúncio, amarrado ao imóvel interno. Crus (a nota é
    o LQS sem reescala); a composição na nota é do consumidor (§6.3)."""

    imovel_id: int
    id_portal: str
    nota: float | None  # LQS cru (~5.580–9.580); None se ausente
    visualizacoes: int
    cliques: Mapping[str, int]  # por tipo, nunca somados
    url: str | None  # sempre None na listagem do Canal Pro
