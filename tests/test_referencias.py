"""A medição dos números de referência (`executar/referencias.py`).

O que estes testes provam sem banco: que os valores publicados são LIDOS do mapa
(não copiados), que o funil conta pelas mesmas regras da rodada, que a passagem por
regra localiza onde a diferença nasce, e que o diagnóstico da skill
`verificar-contra-spec` separa deriva de suspeita de bug. O que exige banco — as
contagens reais — está fora daqui por construção, como todo I/O do projeto.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from dominio.elegibilidade import ImovelCandidato
from executar.referencias import (
    ETAPAS_DO_FUNIL,
    MAPA,
    ROTULO_ELEGIVEIS,
    ROTULO_SUPER,
    ROTULO_VENDAS,
    Comparacao,
    MedicaoFalhou,
    bloco_para_o_mapa,
    comparar,
    contar_funil,
    data_publicada,
    diagnosticar,
    inserir_no_mapa,
    medir,
    nota_sobre_vendas,
    passagem_por_regra,
    referencias_publicadas,
)

HOJE = date(2026, 9, 2)


def _imovel(imovel_id: int, **kw: object) -> ImovelCandidato:
    """Um candidato que passa em TUDO; cada teste reprova o que quer testar."""
    base: dict[str, object] = {
        "imovel_id": imovel_id,
        "publicacao_ativa": True,
        "categoria": "Apartamento",
        "preco": 800_000,
        "qtd_fotos": 12,
        "atualizado_em": date(2026, 8, 30),
        "notas_por_categoria": None,
        "gestor_captou_ou_vendeu_30d": True,
        "produtividade_gestor_30d": 2,
        "corretores_ativos_no_distrito": 3,
    }
    base.update(kw)
    return ImovelCandidato(**base)  # type: ignore[arg-type]


# --- os valores publicados vêm do mapa, não de uma cópia ------------------------


def test_TRAVA_os_seis_valores_que_o_mapa_publica_hoje():
    """TRAVA DE CONTEÚDO, não teste de parser. Estes seis literais são deliberadamente
    uma cópia: existem para que ninguém mude os números de referência do
    `docs/mapa-de-dados.md` sem que o CI acuse.

    **Se este teste falhar, pergunte primeiro se o MAPA mudou de propósito.** Se sim
    — é o que a fatia de incorporação da deriva vai fazer —, atualize estes literais
    na mesma mudança, junto do PRD e do CLAUDE.md, que publicam os mesmos números. O
    que NÃO se faz é editar só este arquivo para o CI ficar verde: aí a trava vira
    enfeite. Os testes de PARSER usam mapa sintético e não dependem destes valores."""
    r = referencias_publicadas()
    assert r[ROTULO_ELEGIVEIS] == 10_290
    assert r[ROTULO_SUPER] == 4_852
    assert r[ROTULO_VENDAS] == 176
    assert r["Ativos"] == 48_964
    assert r["Nas cinco categorias"] == 41_478
    assert r["Preço ≥ R$ 300.000"] == 35_560


def test_rotulo_ausente_e_ERRO_nao_zero(tmp_path: Path):
    """Comparar contra zero produziria um "delta" enorme e falso, e a ferramenta
    diria que o sistema desabou quando quem mudou foi o documento."""
    parcial = tmp_path / "mapa.md"
    parcial.write_text("| Imóveis elegíveis | **10.290** |\n", encoding="utf-8")
    with pytest.raises(MedicaoFalhou, match="rótulos não encontrados"):
        referencias_publicadas(parcial)


def test_mapa_ilegivel_e_ERRO_com_mensagem(tmp_path: Path):
    with pytest.raises(MedicaoFalhou, match="não consegui ler"):
        referencias_publicadas(tmp_path / "nao-existe.md")


def test_o_mapa_de_verdade_e_o_alvo():
    """Contraprova: os testes acima passariam apontando para qualquer arquivo."""
    assert MAPA.name == "mapa-de-dados.md" and MAPA.exists()


# --- o funil conta pelas MESMAS regras da rodada --------------------------------


def test_funil_e_ACUMULADO_como_o_mapa_publica():
    """Comparar acumulado contra por-etapa daria diferença inteiramente artificial."""
    candidatos = [
        _imovel(1),  # passa em tudo
        _imovel(2, categoria="Sítio"),  # cai na categoria
        _imovel(3, preco=250_000),  # passa categoria, cai no preço
        _imovel(4, qtd_fotos=2),  # passa categoria e preço, cai nas fotos
    ]
    f = contar_funil(candidatos, HOJE)
    assert f["Ativos"] == 4
    assert f["Nas cinco categorias"] == 3  # o sítio saiu
    assert f["Preço ≥ R$ 300.000"] == 2  # o barato saiu
    assert f[ROTULO_ELEGIVEIS] == 1  # o de poucas fotos saiu
    assert f[ROTULO_SUPER] == 1


def test_super_destaque_conta_so_ELEGIVEL_acima_do_piso():
    """O piso de R$ 700.000 é condição de NÍVEL (D-002), aplicada sobre quem já é
    elegível — não é uma nona regra de elegibilidade."""
    candidatos = [
        _imovel(1, preco=800_000),  # elegível e acima do piso
        _imovel(2, preco=500_000),  # elegível, abaixo do piso
        _imovel(3, preco=900_000, qtd_fotos=1),  # acima do piso, INELEGÍVEL
    ]
    f = contar_funil(candidatos, HOJE)
    assert f[ROTULO_ELEGIVEIS] == 2
    assert f[ROTULO_SUPER] == 1  # o inelegível não conta, mesmo caro


def test_passagem_por_regra_localiza_onde_a_diferenca_nasce():
    """Um funil acumulado só diz que encolheu; esta contagem diz onde."""
    candidatos = [
        _imovel(1),
        _imovel(2, corretores_ativos_no_distrito=1),
        _imovel(3, corretores_ativos_no_distrito=0),
        _imovel(4, qtd_fotos=3),
    ]
    p = passagem_por_regra(candidatos, HOJE)
    assert p["capacidade_distrito"] == 2  # dois reprovam
    assert p["fotos"] == 3  # um reprova
    assert p["cadastro_completo"] == 4  # nenhum reprova (nota None passa, D-007)


def test_passagem_por_regra_ignora_quem_nem_chegou_na_etapa_final():
    """Contar sobre a base inteira misturaria quem saiu por categoria ou preço, e a
    "passagem" de cada regra viraria um número sobre outro universo."""
    candidatos = [_imovel(1), _imovel(2, categoria="Sítio", qtd_fotos=1)]
    assert passagem_por_regra(candidatos, HOJE)["fotos"] == 1


# --- o diagnóstico da skill -----------------------------------------------------


def _c(rotulo: str, publicado: int, medido: int) -> Comparacao:
    return Comparacao(rotulo=rotulo, publicado=publicado, medido=medido)


def test_diferenca_uniforme_e_lida_como_DERIVA():
    comps = [_c("Ativos", 1000, 950), _c("Nas cinco categorias", 800, 760)]
    assert "deriva uniforme" in diagnosticar(comps).lower()


def test_diferenca_CONCENTRADA_nomeia_a_etapa_e_nao_conclui_bug():
    """A skill diz que concentração SUGERE bug. Sugerir não é concluir: a etapa pode
    concentrar a diferença porque o insumo dela mudou — foi o caso de 02/09/2026,
    com o código correto. Uma ferramenta que concluísse mandaria caçar defeito onde
    não há."""
    comps = [_c("Ativos", 1000, 999), _c(ROTULO_ELEGIVEIS, 500, 380)]
    texto = diagnosticar(comps)
    assert ROTULO_ELEGIVEIS in texto
    assert "sugere bug" in texto and "INSUMO" in texto
    assert "é bug" not in texto  # não conclui


def test_tudo_dentro_do_ruido_diz_que_as_referencias_VALEM():
    comps = [_c("Ativos", 10_000, 10_050)]  # +0,5%
    assert "continuam válidos" in diagnosticar(comps)


def test_o_ruido_tem_limite_e_ele_morde():
    """Contraprova do teste acima: 2% já é sinal, não ruído."""
    assert not _c("Ativos", 10_000, 10_200).dentro_do_ruido
    assert _c("Ativos", 10_000, 10_050).dentro_do_ruido


def test_publicado_zero_nao_estoura_a_fracao():
    assert _c("X", 0, 5).fracao == 0.0


# --- o registro no mapa ---------------------------------------------------------


def test_o_bloco_registrado_declara_que_NAO_alterou_referencia():
    """O ato de medir e o de publicar são diferentes, e o registro precisa dizer
    isso — senão o leitor seguinte trata a medição como valor adotado."""
    bloco = bloco_para_o_mapa([_c("Ativos", 48_964, 48_881)], HOJE, "diagnóstico", "28/08")
    assert "02/09/2026" in bloco
    assert "Nenhum valor de referência acima foi alterado" in bloco
    assert "repetir a contagem noutro dia" in bloco
    assert "48.964" in bloco and "48.881" in bloco


def test_comparar_ignora_rotulo_que_falta_de_um_dos_lados():
    assert comparar({"Ativos": 10}, {}) == []
    assert len(comparar({"Ativos": 10}, {"Ativos": 9})) == 1


# --- onde o bloco é gravado -----------------------------------------------------


def test_o_bloco_entra_DENTRO_da_secao_de_referencias():
    """Anexar no fim do arquivo — o que a primeira versão fazia — punha o bloco sob
    um título alheio, longe do bloco de deriva que ele imita. Formato certo, lugar
    errado: ninguém repara até confundir alguém."""
    doc = (
        "# Mapa\n\n## Números de referência medidos\n\nMedidos em 28/08/2026.\n\n"
        "| Ativos | 48.964 |\n\n## Lacunas apontadas\n\n- outra coisa\n"
    )
    novo = inserir_no_mapa(doc, "\nBLOCO\n")
    assert novo.index("BLOCO") < novo.index("## Lacunas apontadas")
    assert novo.index("## Números de referência medidos") < novo.index("BLOCO")


def test_secao_ausente_e_ERRO_em_vez_de_bloco_orfao():
    with pytest.raises(MedicaoFalhou, match="não encontrada"):
        inserir_no_mapa("# Mapa\n\n## Outra coisa\n", "\nBLOCO\n")


def test_secao_no_fim_do_arquivo_recebe_o_bloco():
    """Contraprova: sem o `find` devolvendo -1 tratado, a seção final quebraria."""
    doc = "# Mapa\n\n## Números de referência medidos\n\n| Ativos | 1 |\n"
    assert inserir_no_mapa(doc, "\nBLOCO\n").endswith("BLOCO\n")


def test_a_data_da_coluna_vem_do_MAPA_nao_do_codigo(tmp_path: Path):
    """Fixada no código, a coluna afirmaria a data velha depois de a fatia seguinte
    incorporar a deriva e mudar a medição publicada.

    Contra mapa SINTÉTICO, com data que o mapa real não tem: cravar aqui a data real
    seria a própria cópia que este teste proíbe — e foi o que a primeira versão fez,
    apanhada pelo portão de números."""
    doc = tmp_path / "m.md"
    doc.write_text("Medidos em 15/09/2027.\n", encoding="utf-8")
    assert data_publicada(doc) == "15/09"


def test_data_ausente_no_mapa_e_ERRO(tmp_path: Path):
    doc = tmp_path / "m.md"
    doc.write_text("## Números de referência medidos\n| Ativos | 1 |\n", encoding="utf-8")
    with pytest.raises(MedicaoFalhou, match="Medidos em"):
        data_publicada(doc)


def test_o_cabecalho_da_coluna_usa_a_data_recebida():
    bloco = bloco_para_o_mapa([_c("Ativos", 1, 1)], HOJE, "x", "15/09")
    assert "Publicado (15/09)" in bloco and "28/08" not in bloco


def test_inserir_no_mapa_cai_JUNTO_do_bloco_irmao_no_documento_REAL():
    """A versão anterior deste teste só comparava índices entre títulos `##` — e por
    isso não viu que o bloco caía DEPOIS do `---` que fecha a seção e abaixo de
    `### Aviso sobre os ganhos de relaxamento`, um nível abaixo e sobre outro
    assunto. Achado do portão de código, que simulou contra o documento real.

    A afirmação certa é de VIZINHANÇA, não de ordem: o bloco novo fica entre a tabela
    de deriva de 29/08 e o primeiro título ou régua que vier depois dela."""
    real = MAPA.read_text(encoding="utf-8")
    novo = inserir_no_mapa(real, "\n<<<BLOCO>>>\n")
    assert real in novo.replace("\n<<<BLOCO>>>\n", "")  # nada foi perdido
    pos = novo.index("<<<BLOCO>>>")
    assert novo.index("Deriva medida em 29/08/2026") < pos, "não ficou junto do irmão"
    assert pos < novo.index("### Aviso sobre os ganhos"), "caiu sob título alheio"
    assert pos < novo.index("\n---\n\n## Lacunas"), "caiu depois da régua da seção"


def test_registrar_a_MESMA_data_duas_vezes_e_recusado():
    """Dois blocos com a mesma data se contradizem quando o estoque mudou entre as
    execuções, e nada diz qual vale. Recusar é mais coerente com o módulo do que
    sobrescrever em silêncio."""
    doc = (
        "## Números de referência medidos\n\nMedidos em 28/08/2026.\n\n"
        "Deriva medida em 02/09/2026:\n\n| a | b |\n\n### Outra coisa\n"
    )
    with pytest.raises(MedicaoFalhou, match="já existe bloco de deriva"):
        inserir_no_mapa(doc, "\nX\n", data="02/09/2026")


def test_data_diferente_e_aceita():
    """Contraprova: a guarda não pode barrar o registro legítimo do dia seguinte."""
    doc = (
        "## Números de referência medidos\n\nDeriva medida em 02/09/2026:\n\n"
        "| a | b |\n\n### Outra coisa\n"
    )
    assert "X" in inserir_no_mapa(doc, "\nX\n", data="03/09/2026")


def test_o_diagnostico_declara_a_banda_de_ruido():
    """`--registrar` grava o veredito no mapa. Sem o critério junto, quem ler daqui a
    três meses vê "dentro do ruído" sem saber o que é ruído."""
    assert "1%" in diagnosticar([_c("Ativos", 10_000, 10_050)])


def test_vendas_FORA_do_diagnostico_de_concentracao():
    """Vendas não é etapa do funil e não passa por regra nenhuma. Sob a régua do
    funil, duas vendas de deriva (base 176) acusariam bug numa regra inexistente e
    mandariam conferir uma tabela onde a linha nem aparece."""
    comps = [_c("Ativos", 10_000, 10_000), _c(ROTULO_VENDAS, 176, 190)]
    assert "continuam válidos" in diagnosticar(comps)  # o funil está intacto
    nota = nota_sobre_vendas(comps)
    assert nota is not None
    assert "não é etapa do funil" in nota.lower() and "176" in nota


def test_vendas_dentro_do_ruido_nao_gera_nota():
    assert nota_sobre_vendas([_c(ROTULO_VENDAS, 10_000, 10_000)]) is None


# --- o caminho de `main`, que não era percorrido por teste nenhum ---------------


def test_a_linha_de_vendas_soma_as_DESCARTADAS(monkeypatch):
    """`coletar_vendas` devolve só as ancoráveis; o valor publicado no mapa é a
    métrica INTEIRA. Comparar uma contra a outra mede populações diferentes — ~2 de
    diferença sobre 176 é 1,1%, acima da banda, e a ferramenta acusaria deriva em
    toda rodada, para sempre, por construção."""
    assert medir([], ancoraveis=174, descartadas=2, hoje=HOJE)[ROTULO_VENDAS] == 176


def test_main_compara_o_que_MEDIU_com_o_que_o_mapa_publica(monkeypatch, caplog):
    """O caminho inteiro do `main` sem banco: com os coletores trocados por falsos,
    prova que os dois dicionários casam pelos mesmos rótulos e que a linha de vendas
    chega somada. Sem isto, a fiação de `main` era 0% coberta."""
    import executar.referencias as mod

    candidatos = [_imovel(1), _imovel(2, categoria="Sítio")]
    monkeypatch.setattr(mod, "coletar", lambda _def: (candidatos, []))
    monkeypatch.setattr(mod, "coletar_vendas", lambda: ([object()] * 174, 2))
    with caplog.at_level("INFO"):
        assert mod.main(["--hoje", "2026-09-02"]) == 0
    texto = caplog.text
    # os seis rótulos publicados aparecem no relatório, nenhum órfão
    for rotulo in (*ETAPAS_DO_FUNIL, ROTULO_ELEGIVEIS, ROTULO_SUPER, ROTULO_VENDAS):
        assert rotulo in texto, f"{rotulo} não saiu no relatório"
    assert "medido      176" in texto.replace("  ", "  ")  # 174 ancoráveis + 2 descartadas


def test_comparar_devolve_os_SEIS_rotulos_na_ordem():
    """Mata a mutação que tirava vendas de `ordem`: a linha sumia do log e do bloco
    gravado no mapa e nada acusava."""
    publicado = dict.fromkeys(
        (*ETAPAS_DO_FUNIL, ROTULO_ELEGIVEIS, ROTULO_SUPER, ROTULO_VENDAS), 100
    )
    comps = comparar(publicado, dict(publicado))
    assert [c.rotulo for c in comps] == [
        *ETAPAS_DO_FUNIL,
        ROTULO_ELEGIVEIS,
        ROTULO_SUPER,
        ROTULO_VENDAS,
    ]


def test_a_coluna_do_MEDIDO_e_a_que_vem_em_negrito():
    """Mata a mutação que trocava as colunas publicado/medido no bloco gravado: o
    mapa passaria a chamar o medido de publicado, com a coluna Deriva contradizendo
    a própria tabela — e os dois números aparecem nas duas versões, então afirmar
    presença não bastava."""
    bloco = bloco_para_o_mapa([_c("Ativos", 48_964, 48_881)], HOJE, "x", "28/08")
    linha = next(a for a in bloco.split("\n") if a.startswith("| Ativos "))
    assert linha == "| Ativos | 48.964 | **48.881** | -83 (-0,2%) |"


def test_main_IMPRIME_a_nota_quando_vendas_sai_da_banda(monkeypatch, caplog):
    """A nota existia e nunca era chamada — função morta com dois testes verdes por
    cima. Sem esta trava, removê-la do `main` passa a suíte, e a linha de vendas sai
    marcada como fora do ruído sem uma palavra de explicação, enquanto o veredito
    logo abaixo a ignora deliberadamente."""
    import executar.referencias as mod

    monkeypatch.setattr(mod, "coletar", lambda _def: ([_imovel(1)], []))
    # 200 contra as 176 publicadas: bem fora da banda
    monkeypatch.setattr(mod, "coletar_vendas", lambda: ([object()] * 198, 2))
    with caplog.at_level("INFO"):
        assert mod.main(["--hoje", "2026-09-02"]) == 0
    assert "não é etapa do funil" in caplog.text.lower()
