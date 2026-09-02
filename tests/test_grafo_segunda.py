"""Testes do fluxo da rodada de segunda (M3).

Rodam com fontes e sinks FALSOS (sem banco): provam o caminho feliz, o caminho de
ausência de carga (Spec §7.3, as duas metades) e — o mais importante — que a PII
NUNCA entra no estado do grafo, que é a precondição registrada em docs/decisoes.md.
"""

import re
from dataclasses import fields
from datetime import date

import pytest

from dados.registro.acompanhamento import AcumuloDaJanela
from dominio.acompanhamento import LeadDoPeriodo, Nivel, PosicaoPaga, ResultadoAcompanhamento
from grafo.estado import Estado
from grafo.segunda import (
    EstadoSegunda,
    FontesSegunda,
    SinksSegunda,
    construir_grafo_segunda,
)

INICIO, FIM = date(2026, 8, 28), date(2026, 8, 31)
PII = "Corretor Fulano"  # sentinela: não pode aparecer no estado do grafo


def _lead(
    lead_id,
    imovel_id,
    *,
    atendido=False,
    contatado=False,
    gestor=PII,
    distribuicao=date(2026, 8, 29),  # o caminho feliz TEM distribuição (88,4% têm)
    **extra,
):
    return LeadDoPeriodo(
        lead_id=lead_id,
        imovel_id=imovel_id,
        entrada=date(2026, 8, 29),
        atendimento_registrado=atendido,
        contato_registrado=contatado,
        corretor_gestor=gestor,
        distribuicao=distribuicao,
        **extra,
    )


class _Sinks:
    """Sinks falsos que registram o que receberam."""

    def __init__(self, historico=None, limitacoes=()):
        self.historico = historico or {}
        self.limitacoes = limitacoes
        self.entregues: list[tuple[ResultadoAcompanhamento, str, tuple[str, ...]]] = []
        self.registrados: list[tuple[ResultadoAcompanhamento, str, str | None, dict]] = []
        self.ausencias: list[str] = []
        self.avisos: list[str] = []

    def como_sinks(self) -> SinksSegunda:
        return SinksSegunda(
            entregar=lambda r, e, d: self.entregues.append((r, e, d)),
            registrar=lambda r, e, m, p: (
                self.registrados.append((r, e, m, p)),
                (77, AcumuloDaJanela(historico=self.historico, limitacoes=self.limitacoes)),
            )[1],
            declarar_ausencia=lambda motivo, prontos: (self.ausencias.append(motivo), 88)[1],
            avisar=self.avisos.append,
        )


def _fontes(*, carga=7, posicoes=None, leads=None, descartados=0):
    pos = posicoes if posicoes is not None else [PosicaoPaga(1, Nivel.DESTAQUE)]
    lds = leads if leads is not None else [_lead(100, 1)]
    return FontesSegunda(
        carga_aprovada=lambda: carga,
        posicoes_da_carga=lambda _rid: pos,
        coletar_leads=lambda _i, _f: (lds, descartados),
    )


def _inicial() -> EstadoSegunda:
    return {
        "inicio_periodo": INICIO,
        "fim_periodo": FIM,
        "estado": Estado.EM_ANDAMENTO,
        "prontos": {},
        "degradacoes": [],
    }


# --- caminho feliz -------------------------------------------------------------


def test_mede_a_carga_e_entrega():
    s = _Sinks()
    final = construir_grafo_segunda(_fontes(), s.como_sinks()).invoke(_inicial())
    assert final["estado"] == Estado.COMPLETA
    assert final["prontos"] == {"carga": True, "monitor": True}  # redator não é afirmado
    assert len(s.entregues) == 1  # a planilha saiu
    assert len(s.registrados) == 1  # e o Registro guardou
    assert final["rodada_id"] == 77
    assert final["payload"].resumo.leads_gerados == 1


def test_registro_recebe_o_estado_declarado():
    s = _Sinks()
    construir_grafo_segunda(_fontes(), s.como_sinks()).invoke(_inicial())
    _resultado, estado, motivo, _prontos = s.registrados[0]
    assert estado == Estado.COMPLETA
    assert motivo is None


# --- a PII não entra no estado do grafo (precondição da M3) --------------------


def test_pii_nunca_entra_no_estado_no_caminho_feliz():
    """O checkpointer serializa o estado no Postgres: se a identidade entrasse aqui,
    reintroduziria no banco a PII que o Registro deliberadamente não grava."""
    s = _Sinks()
    final = construir_grafo_segunda(_fontes(), s.como_sinks()).invoke(_inicial())
    # a sentinela existe no resultado que foi para a planilha...
    assert any(PII in repr(r) for r, _e, _d in s.entregues)
    # ...e NÃO existe em nenhum canto do estado do grafo
    assert PII not in repr(final)


@pytest.mark.parametrize(
    "rota",
    [
        pytest.param(dict(), id="feliz"),
        pytest.param(dict(leads=[_lead(100, 1, gestor=None)]), id="sem-responsavel"),
        pytest.param(dict(descartados=5), id="com-descartes"),
        pytest.param(dict(leads=[_lead(100, 1, distribuicao=None)]), id="sem-distribuicao"),
        pytest.param(dict(leads=[_lead(100, 1, atendido=True)]), id="todos-tratados"),
        pytest.param(dict(carga=None), id="sem-carga"),
        pytest.param(dict(posicoes=[]), id="carga-vazia"),
    ],
)
def test_pii_nunca_entra_no_estado_em_NENHUMA_rota(rota):
    """A sentinela do caminho feliz não basta: um campo populado só em rota
    condicional passaria despercebido (provado por mutação na revisão). Toda rota
    do fluxo tem de terminar com o estado limpo de identidade."""
    s = _Sinks()
    final = construir_grafo_segunda(_fontes(**rota), s.como_sinks()).invoke(_inicial())
    assert PII not in repr(final), f"PII vazou para o estado na rota {rota}"


def _tipos_com_pii() -> set[str]:
    """Deriva os tipos PROIBIDOS do domínio: qualquer dataclass de
    `dominio.acompanhamento` com campo de identidade de PESSOA, mais os que contêm um
    desses. Cobre o previsível — mas a lista não sumiu, migrou de nomes de tipo para
    nomes de CAMPO: um campo batizado fora dela (`nome_corretor`) ainda escaparia. O
    invariante 3 fala em lead, COMPRADOR e corretor, daí os campos de contato."""
    import dataclasses
    import inspect

    from dominio import acompanhamento as dom

    campos_pii = {
        "lead_id",
        "corretor_gestor",
        "gestor_distrito",
        "distrito",
        "nome",
        "email",
        "telefone",
        "cpf",
        "comprador",
    }
    direto = {
        nome
        for nome, obj in inspect.getmembers(dom, dataclasses.is_dataclass)
        if campos_pii & {f.name for f in dataclasses.fields(obj)}
    }
    # fecho transitivo: quem carrega um tipo com PII também está contaminado
    contaminados = set(direto)
    while True:  # até ponto fixo: não sub-aproxima se o domínio ganhar profundidade
        novos = {
            nome
            for nome, obj in inspect.getmembers(dom, dataclasses.is_dataclass)
            if any(p in str(f.type) for f in dataclasses.fields(obj) for p in contaminados)
        }
        if novos <= contaminados:
            return contaminados
        contaminados |= novos


def test_estado_nao_tem_campo_capaz_de_carregar_pii():
    """Cadeado ESTRUTURAL: nenhum campo do estado é (ou contém) tipo com identidade.

    Varre o nome de tipo inteiro, não só o prefixo: `ResultadoAcompanhamento | None`,
    `list[LeadDoPeriodo]` e `Annotated[list[LeadSemTratamento], ...]` têm de ser
    pegos — foi assim que uma versão anterior deste teste passou verde com PII
    declarada no estado.
    """
    proibidos = _tipos_com_pii()
    assert {"LeadDoPeriodo", "LeadSemTratamento", "ResultadoAcompanhamento"} <= proibidos, (
        f"a derivação perdeu tipos com PII conhecidos: {proibidos}"
    )
    for nome, tipo in EstadoSegunda.__annotations__.items():
        achados = set(re.findall(r"\w+", str(tipo))) & proibidos
        assert not achados, f"campo '{nome}' carrega tipo com PII: {achados}"


# --- Spec §7.3: sem carga aprovada, as DUAS metades ---------------------------


def test_sem_carga_aprovada_declara_e_avisa():
    s = _Sinks()
    final = construir_grafo_segunda(_fontes(carga=None), s.como_sinks()).invoke(_inicial())
    assert final["estado"] == Estado.ABORTADA
    assert s.entregues == []  # relatório NÃO é emitido
    assert s.registrados == []
    assert len(s.ausencias) == 1  # ...e a ausência É declarada
    assert len(s.avisos) == 1  # ...e o gestor é avisado
    assert "aprovada" in s.ausencias[0]
    assert final["rodada_id"] == 88


def test_carga_aprovada_sem_posicoes_tambem_declara():
    s = _Sinks()
    final = construir_grafo_segunda(_fontes(posicoes=[]), s.como_sinks()).invoke(_inicial())
    assert final["estado"] == Estado.ABORTADA
    assert len(s.ausencias) == 1
    assert "não tem posições" in s.ausencias[0]


# --- degradações declaradas ----------------------------------------------------


def test_lead_sem_responsavel_degrada_e_nao_fica_pronto():
    s = _Sinks()
    fontes = _fontes(leads=[_lead(100, 1, gestor=None)])
    final = construir_grafo_segunda(fontes, s.como_sinks()).invoke(_inicial())
    assert final["estado"] == Estado.DEGRADADA
    assert final["prontos"]["monitor"] is False
    assert any("responsável nomeado" in d for d in final["degradacoes"])
    _r, estado, motivo, _p = s.registrados[0]
    assert estado == Estado.DEGRADADA and motivo  # o Registro recebe o motivo


def test_descartados_sem_imovel_viram_degradacao_declarada():
    s = _Sinks()
    final = construir_grafo_segunda(_fontes(descartados=5), s.como_sinks()).invoke(_inicial())
    assert final["leads_descartados_sem_imovel"] == 5
    assert any("sem imóvel" in d or "imóvel de" in d for d in final["degradacoes"])
    assert final["estado"] == Estado.DEGRADADA


def test_sem_distribuicao_e_declarado():
    s = _Sinks()
    # lead sem tratamento E sem distribuição na origem → a coluna da §4.2 fica
    # vazia, e isso é DECLARADO em vez de a planilha sair com o campo mudo.
    fontes = _fontes(leads=[_lead(100, 1, distribuicao=None)])
    final = construir_grafo_segunda(fontes, s.como_sinks()).invoke(_inicial())
    assert any("distribuição" in d for d in final["degradacoes"])
    assert final["estado"] == Estado.DEGRADADA


# --- falha de fonte: aborta DECLARANDO, e sem vazar a mensagem ----------------


def test_falha_de_fonte_declara_em_vez_de_terminar_calada():
    """MySQL fora numa segunda de manhã: a rodada não pode sumir. Vira aborto
    declarado (Registro + aviso), como manda a §7.3 — o mesmo silêncio, outra porta."""

    def _explode(_i, _f):
        raise ConnectionError(f"conexão perdida ao ler o lead de {PII}")  # msg com PII

    s = _Sinks()
    fontes = FontesSegunda(
        carga_aprovada=lambda: 7,
        posicoes_da_carga=lambda _r: [PosicaoPaga(1, Nivel.DESTAQUE)],
        coletar_leads=_explode,
    )
    final = construir_grafo_segunda(fontes, s.como_sinks()).invoke(_inicial())
    assert final["estado"] == Estado.ABORTADA
    assert len(s.ausencias) == 1 and len(s.avisos) == 1  # declarou E avisou
    assert s.entregues == [] and s.registrados == []  # nada foi entregue nem gravado
    # a mensagem da exceção pode ecoar dado de lead: só o TIPO entra no motivo
    assert "ConnectionError" in final["motivo"]  # o TIPO, não a mensagem
    assert PII not in repr(final)


def test_medir_sem_carga_e_erro_de_roteamento():
    """Invariante topológico: `no_medir` só roda depois de `carga` aprovar."""
    from grafo.segunda import no_medir

    s = _Sinks()
    with pytest.raises(RuntimeError, match="roteamento"):
        no_medir(
            {
                "inicio_periodo": INICIO,
                "fim_periodo": FIM,
                "rodada_decisao_id": None,
                "posicoes": [],
            },
            fontes=_fontes(),
            sinks=s.como_sinks(),
        )


# --- funções puras (testáveis sem grafo) --------------------------------------


def test_estado_terminal_so_e_completa_sem_limitacao():
    from grafo.segunda import estado_terminal

    assert estado_terminal([]) == Estado.COMPLETA
    assert estado_terminal(["qualquer limitação"]) == Estado.DEGRADADA


def test_monitor_pode_estar_pronto_e_a_rodada_degradar():
    """O caso real da primeira execução: pronto do Monitor cumprido, mas descartes
    e distribuição ausente degradam a rodada."""
    s = _Sinks()
    final = construir_grafo_segunda(_fontes(descartados=5), s.como_sinks()).invoke(_inicial())
    assert final["prontos"]["monitor"] is True  # o pronto VALE...
    assert final["estado"] == Estado.DEGRADADA  # ...e ainda assim degradou


def test_registro_vem_antes_da_planilha():
    """Ordem deliberada: falha da planilha deixa rastro no Registro (visível);
    o inverso deixaria planilha no Drive sem rodada registrada (silencioso)."""
    ordem = []
    sinks = SinksSegunda(
        entregar=lambda r, e, d: ordem.append("entregar"),
        registrar=lambda r, e, m, p: (
            ordem.append("registrar"),
            (77, AcumuloDaJanela(historico={}, limitacoes=())),
        )[1],
        declarar_ausencia=lambda m, p: 88,
        avisar=lambda m: None,
    )
    construir_grafo_segunda(_fontes(), sinks).invoke(_inicial())
    assert ordem == ["registrar", "entregar"]


def test_limitacao_vinda_do_estado_inicial_chega_a_planilha():
    """Uma limitação posta ANTES do grafo (ex.: janela truncada, que só o runner
    sabe) tem de chegar à planilha e ao estado terminal — a §7.2 fala da rodada
    inteira, não só do que o nó descobriu."""
    s = _Sinks()
    inicial = {**_inicial(), "degradacoes": ["janela TRUNCADA: 0 de 3 dias"]}
    final = construir_grafo_segunda(_fontes(), s.como_sinks()).invoke(inicial)
    _r, estado, degradacoes = s.entregues[0]
    assert any("TRUNCADA" in d for d in degradacoes)  # chegou à planilha
    assert estado == Estado.DEGRADADA  # e degradou a rodada
    assert final["degradacoes"].count("janela TRUNCADA: 0 de 3 dias") == 1  # sem duplicar


def test_planilha_recebe_a_limitacao_da_rodada():
    """Spec §7.2: a limitação da rodada degradada aparece NA PLANILHA, não só no
    Registro — quem lê a planilha precisa saber que a rodada foi degradada."""
    s = _Sinks()
    construir_grafo_segunda(_fontes(descartados=5), s.como_sinks()).invoke(_inicial())
    _resultado, estado, degradacoes = s.entregues[0]
    assert estado == Estado.DEGRADADA
    assert degradacoes and any("imóvel de origem" in d for d in degradacoes)


# --- determinismo --------------------------------------------------------------


def test_mesma_entrada_mesmo_payload():
    leads = [_lead(100, 1), _lead(101, 1, atendido=True)]
    pos = [PosicaoPaga(1, Nivel.DESTAQUE), PosicaoPaga(2, Nivel.SUPER_DESTAQUE)]
    saidas = []
    for _ in range(3):
        s = _Sinks()
        final = construir_grafo_segunda(_fontes(posicoes=pos, leads=leads), s.como_sinks()).invoke(
            _inicial()
        )
        saidas.append(final["payload"])
    assert saidas[0] == saidas[1] == saidas[2]


def test_payload_e_o_recorte_sem_identidade():
    """O que o estado carrega é o mesmo recorte que a M1 autorizou a ir a modelo."""
    s = _Sinks()
    final = construir_grafo_segunda(_fontes(), s.como_sinks()).invoke(_inicial())
    campos = {f.name for f in fields(final["payload"])}
    assert campos == {"resumo", "desempenho"}  # sem leads_sem_tratamento


def test_historico_da_janela_chega_a_PLANILHA():
    """A costura entre `registrar` e `entregar`: o histórico de janelas nasce dentro
    da transação que grava a rodada e precisa atravessar até a planilha, porque são
    duas colunas que a Spec §4.3 exige NELA.

    Sem esta trava, quebrar a costura deixaria a planilha declarando `None` nas duas
    colunas numa semana em que a janela acumulou — indistinguível de "imóvel sem
    histórico", que é justamente a distinção que a D-020 mandou preservar.
    """
    sinks = _Sinks(historico={1: (3, 12)})
    construir_grafo_segunda(_fontes(), sinks.como_sinks()).invoke(_inicial())

    resultado_entregue = sinks.entregues[0][0]
    (d,) = resultado_entregue.desempenho
    assert (d.semanas_consecutivas, d.leads_acumulados_janela) == (3, 12)

    # E o que foi REGISTRADO não carrega as colunas: elas são relato da planilha
    # (§4.3), e o Registro guarda a janela em tabela própria — gravar as duas ali
    # seria a mesma verdade em dois lugares, livre para divergir.
    registrado = sinks.registrados[0][0]
    assert registrado.desempenho[0].semanas_consecutivas is None


def test_limitacoes_do_acumulo_chegam_a_PLANILHA():
    """Num projeto cujo argumento central é "limitação declarada, nunca silenciosa",
    a declaração recém-criada era a única parte da fatia sem trava: removê-la da
    chamada de `entregar` passava nos 521 testes."""
    sinks = _Sinks(limitacoes=("leads são AMOSTRA, não total",))
    construir_grafo_segunda(_fontes(), sinks.como_sinks()).invoke(_inicial())

    _resultado, _estado, declaradas = sinks.entregues[0]
    assert "leads são AMOSTRA, não total" in declaradas


def test_limitacoes_do_acumulo_NAO_mudam_o_estado_da_rodada():
    """Elas não são falha de fonte — são o que o produtor de janelas ainda não sabe.
    Somá-las ao estado tornaria TODA segunda degradada enquanto durarem, e um estado
    que nunca varia deixa de informar. Decisão declarada, com pergunta aberta ao dono
    em docs/decisoes.md — este teste trava a decisão, não a esconde."""
    sinks = _Sinks(limitacoes=("limitação estrutural qualquer",))
    final = construir_grafo_segunda(_fontes(), sinks.como_sinks()).invoke(_inicial())

    assert final["estado"] == Estado.COMPLETA
    assert "limitação estrutural qualquer" not in final.get("degradacoes", [])
