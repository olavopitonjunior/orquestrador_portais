# src/dominio

Regras de negócio puras e determinísticas — e os contratos de dado externo com que essas regras falam do mundo: elegibilidade (oito regras gerais mais o perfil de conversão, a nona desde a D-027; o piso de nível do super destaque fica na alocação, D-002/D-003), ranking (a nota do portal em pontos de 100, D-028), descontos (três), alocação nas cotas e relaxamento (ordem de cedência com o perfil primeiro).

Invariante: nenhuma chamada a modelo de linguagem neste pacote, em nenhuma circunstância. A mesma entrada, com os mesmos parâmetros, produz a mesma lista.

Além das regras, o pacote guarda os **contratos** com que elas falam do mundo — hoje `portal.py`. A tensão é aparente: `DesempenhoAnuncio` não é dado do coletor, é o VOCABULÁRIO com que a decisão fala de desempenho de anúncio. Quem define o que o dado significa é a camada de dentro; quem o produz é a de fora. Por isso `dados/coletor_externo.py` importa daqui, e não o contrário — é a direção da dependência que põe um contrato de dado externo num pacote de regras, e ela é a razão, não uma exceção.

**Nada aqui importa de fora de `dominio`** (stdlib à parte). Era propriedade acidental até 2026-09-06; hoje é travada por `tests/test_pureza_do_dominio.py`, que percorre os módulos deste pacote e falha se algum importar outra camada.

`portal.py`: o contrato de desempenho de anúncio no portal (`DesempenhoAnuncio`) — dataclass frozen de tipos primitivos, sem import nenhum. Produzido por `dados/coletor_externo.py`, consumido pelo ranking e pela entrega.

`elegibilidade.py`: as nove regras eliminatórias como funções puras — as oito gerais (D-002/D-003) mais o perfil de conversão (D-027), cujo veredito vem da costura e cujo `None` NÃO reprova —, o piso de nível do super destaque e a ordem de cedência do relaxamento. Testes em `tests/test_elegibilidade.py`, com valores-limite da Spec §6.1.
