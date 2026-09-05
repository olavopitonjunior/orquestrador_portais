import Link from "next/link";

import {
  ETAPAS,
  LIMITE_DO_LOG,
  eventosDoTrabalho,
  resumosDoTrabalho,
  trabalhoDaRodada,
} from "@/lib/operacao";
import { cedenciaDaAba, montarBlocos } from "@/lib/blocos-da-rodada";
import { ABAS, lerPlanilha, type Aba, type Tabela } from "@/lib/planilha";
import { cotasDoRegistro } from "@/lib/cotas";
import { lerRodada, limitacoesDe, parametrosDaRodada } from "@/lib/registro";
import { dataHora, duracao, PilulaEstado } from "../../estado";
import { IconeAlerta } from "../../icones";
import { BlocosRealizados } from "../../trabalho/[id]/blocos";
import { RelatorioDosAgentes } from "../../trabalho/[id]/relatorio";

export const dynamic = "force-dynamic";

// O que cada aba é, e o que cada coluna de justificativa quer dizer — para o dono ler
// a planilha sem precisar da Spec ao lado. Texto de exibição, não regra.
const SOBRE_A_ABA: Record<Aba, string> = {
  apuracao:
    "O resultado total: uma linha por imóvel candidato, inclusive os que ficaram fora, com o " +
    "desfecho (super destaque, destaque, não coube na cota, reprovado, não avaliado), a regra " +
    "que reprovou, as características do imóvel (preço, distrito, metragem, dormitórios, vagas) e " +
    "o que o portal trouxe. Quem não foi pontuado tem as colunas de nota VAZIAS — nunca zeradas — e " +
    "a coluna notas_entre diz se a nota foi normalizada entre os elegíveis ou entre os reprovados.",
  super_destaque:
    "As posições do nível de topo, na ordem do ranking. Disputa real (mais de dez candidatos " +
    "por vaga) e objetivo de valor esperado. Nunca relaxa.",
  destaque:
    "As posições do nível de base, na ordem do ranking. Folga contratual: o objetivo é não " +
    "deixar benefício pago sem uso, e o relaxamento pode preencher o que a lista não cobriu " +
    "(origem = relaxamento, com a regra cedida).",
  excluidos_por_regra:
    "Quem NÃO entrou e por qual regra eliminatória. Reprovar em uma basta; nenhuma nota compensa.",
  relaxamento:
    "A ordem de cedência aplicada nas posições de destaque e quantas posições cada degrau " +
    "cobriu. A última linha diz quantas ficaram vazias mesmo assim.",
  perfis:
    "Os padrões de imóvel que venderam na janela, com quantas vendas sustentam cada um. " +
    "Robusto é o que tem ao menos três vendas; e só conta para o filtro — a nona regra de " +
    "elegibilidade — quem é robusto E contém a faixa de preço, o que a última coluna diz.",
  parametros_e_limitacoes:
    "O que produziu esta lista: os parâmetros PROVISÓRIOS declarados, e cada limitação que " +
    "a rodada declarou sobre si mesma. Leia esta aba antes das outras.",
};

const SOBRE_A_COLUNA: Record<string, string> = {
  nota_portal: "a nota bruta: soma ponderada dos sinais do anúncio (ou o desempate de banco, se a raspagem não entrou)",
  nota_anuncio: "nota do anúncio no portal, reescalada entre os elegíveis",
  cliques: "cliques no anúncio, somados entre tipos, reescalados",
  visualizacoes: "visualizações do anúncio, reescaladas (peso adotado zero)",
  leads: "leads já atraídos em 180 dias (banco) — desempate",
  produtividade_gestor: "produtividade do gestor em 30 dias (banco) — desempate",
  casa_perfil: "se o imóvel se parece com o que vendeu (a nona regra)",
  gestor_logou_na_janela: "se o gestor entrou no sistema na janela declarada (trava a cedência)",
  pen_janela_sem_resultado: "penalidade · janela anterior sem resultado",
  pen_sem_avaliacao_por_categoria: "penalidade · sem avaliação por categoria",
  pen_sem_lead_180d: "penalidade · sem lead em 180 dias",
  desconto_total: "soma das penalidades",
  ultima_janela: "a última janela paga deste imóvel, e como foi julgada",
  perfil_que_puxou: "o perfil de conversão de mais vendas que o imóvel casa",
  perfil_num_vendas: "vendas que sustentam esse perfil",
  perfil_fragil: "perfil com menos vendas que a evidência mínima",
  origem: "ranking, ou relaxamento (recuperado por cedência)",
  degrau_cedido: "a regra cedida para este imóvel entrar",
};

// A ordem de LEITURA, explícita: limitações antes de qualquer número; depois o nível com
// disputa; depois o de folga; excluídos e relaxamento por último.
// A apuração NÃO entra aqui: são dezenas de milhares de linhas numa rodada inteira, e a
// tela não é o lugar de lê-las — ela ganha um cartão próprio no topo, com a contagem e o
// botão, e o arquivo se lê no Sheets.
const ORDEM_DAS_ABAS: readonly Aba[] = [
  "parametros_e_limitacoes",
  "super_destaque",
  "destaque",
  "excluidos_por_regra",
  "relaxamento",
  "perfis",
];

const LINHAS_NA_TELA = 300;

function Tabela({ aba, t }: { aba: Aba; t: Tabela }) {
  if (t.vazia) return <p className="vazio">A etapa rodou e não produziu linha nesta rodada.</p>;
  if (t.semConteudo)
    return (
      <div className="banner" role="alert">
        Arquivo de 0 bytes: não é "sem linhas" (isso teria a sentinela) — a escrita não aconteceu
        ou foi truncada.
      </div>
    );
  const mostradas = t.linhas.slice(0, LINHAS_NA_TELA);
  return (
    <>
      <div className="tabela-wrap">
        <table>
          <thead>
            <tr>
              {t.colunas.map((c) => (
                <th key={c} scope="col" title={SOBRE_A_COLUNA[c]}>
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {mostradas.map((linha, i) => (
              <tr key={`${aba}-${i}`}>
                {linha.map((cel, j) => (
                  <td key={j}>{cel}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="nota" style={{ margin: 0, padding: "10px 20px", borderTop: "1px solid var(--border)" }}>
        {t.linhas.length > LINHAS_NA_TELA
          ? `${LINHAS_NA_TELA} de ${t.linhas.length} linhas na tela; o CSV inteiro está em disco`
          : `${t.linhas.length} ${t.linhas.length === 1 ? "linha" : "linhas"}`}
        . Passe o mouse no cabeçalho para ver o que cada coluna significa.
      </p>
    </>
  );
}

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const bruto = (await params).id;
  if (!/^\d+$/.test(bruto)) return <h1>Rodada inválida</h1>;
  const id = Number(bruto);

  const [rodada, parametros, trabalhoId, cotas] = await Promise.all([
    lerRodada(id).catch(() => null),
    parametrosDaRodada(id).catch(() => null),
    trabalhoDaRodada(id).catch(() => null),
    cotasDoRegistro().catch(() => null),
  ]);
  if (rodada === null) {
    return (
      <>
        <h1>Rodada {id}</h1>
        <div className="banner" role="alert">
          Não encontrada no Registro. Ou o id está errado, ou o Postgres está fora — e uma rodada
          ABORTADA não deixa linha nenhuma: o que existe dela é o log do trabalho.
        </div>
      </>
    );
  }

  // Tudo num lugar só: o relatório dos agentes e o log da execução que produziu esta
  // rodada vêm para cá — quem lê a planilha não deveria ter de sair dela para saber o
  // que cada agente fez. As mesmas consultas de /trabalho/[id]; sem trabalho (rodada
  // disparada pela CLI), as seções dizem isso em vez de sumir.
  const [resumos, eventos] = trabalhoId
    ? await Promise.all([
        resumosDoTrabalho(trabalhoId).catch(() => new Map<string, Record<string, unknown>>()),
        eventosDoTrabalho(trabalhoId).catch(() => []),
      ])
    : [new Map<string, Record<string, unknown>>(), []];
  const dataReferencia =
    typeof parametros?.data_referencia === "string" ? parametros.data_referencia : null;
  const planilha = dataReferencia ? await lerPlanilha(dataReferencia) : null;
  const recorte = parametros?.recorte_pela_raspagem as { imoveis?: number } | null | undefined;
  const amostral = recorte != null;
  const limitacoes = limitacoesDe(rodada.motivoDegradacao);
  const efetivo =
    parametros && typeof parametros.efetivo === "object" && parametros.efetivo !== null
      ? (parametros.efetivo as Record<string, unknown>)
      : null;
  const abaRelax = planilha?.abas.relaxamento;
  const blocos =
    rodada.tipo === "decisao"
      ? montarBlocos({
          resumos,
          efetivo,
          // Abortada não deixa decisão nenhuma: as contagens do Registro seriam zeros
          // que parecem contagem. Nulo, e os blocos dizem "—".
          contagens:
            rodada.estado === "abortada"
              ? null
              : {
                  superDestaque: rodada.superDestaque,
                  destaque: rodada.destaque,
                  vaziasDestaque: rodada.posicoesVaziasDestaque,
                },
          relaxamento: abaRelax && !abaRelax.vazia && !abaRelax.semConteudo ? cedenciaDaAba(abaRelax.colunas, abaRelax.linhas) : [],
        })
      : null;

  // "pelo ranking + por relaxamento": contado na aba `destaque` da planilha (coluna
  // `origem`), quando ela está em disco. O Registro só guarda a contagem por nível.
  const abaDestaque = planilha?.abas.destaque;
  const iOrigem = abaDestaque ? abaDestaque.colunas.indexOf("origem") : -1;
  const relaxados =
    abaDestaque && iOrigem >= 0 ? abaDestaque.linhas.filter((l) => l[iOrigem] === "relaxamento").length : null;

  return (
    <>
      <nav className="migalhas" aria-label="Caminho">
        <Link href="/">Painel</Link>
        <span>/</span>
        <Link href="/#rodadas">Rodadas</Link>
        <span>/</span>
        <b>{rodada.id}</b>
      </nav>

      <header className="cabecalho">
        <div>
          <h1>
            Rodada {rodada.id}
            <PilulaEstado estado={rodada.estado} />
            {amostral ? <span className="pill pill-bad">amostral</span> : null}
          </h1>
          <p className="subtitulo">
            {rodada.tipo === "decisao" ? "Decisão" : "Acompanhamento"} · {dataHora(rodada.inicio)}
            {rodada.fim ? ` · ${duracao(rodada.inicio, rodada.fim)}` : ""}
            {dataReferencia ? ` · referência ${dataReferencia}` : ""}
            {trabalhoId ? (
              <>
                {" · trabalho "}
                <Link href={`/trabalho/${trabalhoId}`}>{trabalhoId}</Link>
              </>
            ) : (
              " · disparada pela linha de comando"
            )}
          </p>
        </div>
        <div className="cabecalho-acoes">
          {/* A apuração é o que se leva para aplicar a carga: fica no topo. */}
          {planilha?.abas.apuracao && !planilha.abas.apuracao.semConteudo ? (
            <a
              className="botao"
              href={`/rodada/${rodada.id}/planilha/apuracao.csv`}
              download={`rodada-${rodada.id}-apuracao.csv`}
            >
              Baixar a apuração (CSV)
            </a>
          ) : null}
          {/* Só quando há pelo menos uma aba com conteúdo em disco: a rota devolveria 404. */}
          {planilha && ORDEM_DAS_ABAS.some((a) => planilha.abas[a] && !planilha.abas[a].semConteudo) ? (
            <a
              className="botao-secundario"
              href={`/rodada/${rodada.id}/planilha/todas.zip`}
              download={`rodada-${rodada.id}-planilha-${dataReferencia ?? ""}.zip`}
            >
              Baixar as abas (.zip)
            </a>
          ) : null}
          {rodada.aprovadaEm ? (
            <span className="pill pill-ok" style={{ padding: "6px 12px" }}>
              aprovada {dataHora(rodada.aprovadaEm)} por {rodada.aprovadaPor ?? "?"}
            </span>
          ) : rodada.tipo !== "decisao" ? null : amostral || rodada.estado === "abortada" ? (
            <button
              type="button"
              className="botao"
              disabled
              title={amostral ? "Rodada amostral não pode ser aprovada" : "Rodada abortada não entrega"}
            >
              Aprovar · indisponível
            </button>
          ) : (
            <span
              className="pill pill-muted"
              style={{ padding: "6px 12px" }}
              title="A aprovação é pelo comando rodada-aprovar (D-001)"
            >
              pendente de aprovação · rodada-aprovar
            </span>
          )}
        </div>
      </header>

      {amostral ? (
        <div className="banner banner-com-icone" role="alert">
          <IconeAlerta />
          <div>
            <b>Rodada amostral.</b> O universo foi restrito aos {recorte?.imoveis ?? "?"} imóveis que
            a raspagem trouxe. Não é decisão sobre o estoque, nunca é COMPLETA e não pode virar carga.
            Serve para conferir a cadeia inteira com dado real.
          </div>
        </div>
      ) : null}

      <nav className="abas" aria-label="Seções">
        {blocos ? (
          <>
            <a className="aba" href="#quem-entrou">Quem entrou</a>
            <a className="aba" href="#em-que-ordem">Em que ordem</a>
            <a className="aba" href="#quantos">Quantos</a>
            <a className="aba" href="#resumo">Detalhes</a>
          </>
        ) : (
          <a className="aba" href="#resumo">Resumo</a>
        )}
        <a className="aba" href="#agentes">Agentes</a>
        <a className="aba" href="#planilha">Planilha</a>
        <a className="aba" href="#parametros">Parâmetros</a>
        <a className="aba" href="#log">Log</a>
      </nav>

      {blocos ? <BlocosRealizados b={blocos} emCurso={false} /> : null}

      <div className="grade-2-inversa ancora" id="resumo">
        <section className="caixa">
          <div className="caixa-cabecalho">
            <h2>O que a rodada propôs</h2>
          </div>
          <div className="caixa-corpo">
            {rodada.tipo === "acompanhamento" ? (
              <p className="nota" style={{ margin: 0 }}>
                Rodada de acompanhamento não propõe posições: mede a carga aprovada contra o Registro.
              </p>
            ) : blocos ? null : (
              <div className="grade-3">
                <div className="kpi">
                  <div className="lbl">Super destaque</div>
                  <div className="kpi-valor">
                    {rodada.superDestaque.toLocaleString("pt-BR")}
                    {cotas ? <small> / {cotas.superDestaque.toLocaleString("pt-BR")}</small> : null}
                  </div>
                </div>
                <div className="kpi">
                  <div className="lbl">Destaque</div>
                  <div className="kpi-valor">
                    {rodada.destaque.toLocaleString("pt-BR")}
                    {cotas ? <small> / {cotas.destaque.toLocaleString("pt-BR")}</small> : null}
                  </div>
                  {relaxados !== null ? (
                    <div className="kpi-sub">
                      {(rodada.destaque - relaxados).toLocaleString("pt-BR")} pelo ranking +{" "}
                      {relaxados.toLocaleString("pt-BR")} por relaxamento
                    </div>
                  ) : null}
                </div>
                <div className={rodada.posicoesVaziasDestaque > 0 ? "kpi kpi-warn" : "kpi"}>
                  <div className="lbl">Vazias (destaque)</div>
                  <div className="kpi-valor">{rodada.posicoesVaziasDestaque.toLocaleString("pt-BR")}</div>
                  {amostral && rodada.posicoesVaziasDestaque > 0 ? (
                    <div className="kpi-sub">esperado num recorte de {recorte?.imoveis ?? "?"}</div>
                  ) : null}
                </div>
              </div>
            )}
            <div className="linhas-kv">
              <div className="linha-kv">
                <span>Estado</span>
                <b>{rodada.estado ?? "em andamento"}</b>
              </div>
              {rodada.tipo === "acompanhamento" ? (
                <div className="linha-kv">
                  <span>Posições de destaque vazias</span>
                  <b>{rodada.posicoesVaziasDestaque.toLocaleString("pt-BR")}</b>
                </div>
              ) : null}
              <div className="linha-kv">
                <span>Recorte pela raspagem</span>
                <b>{amostral ? `${recorte?.imoveis ?? "?"} imóveis` : "não · estoque inteiro"}</b>
              </div>
              <div className="linha-kv">
                <span>Planilha em disco</span>
                <b>{planilha ? planilha.diretorio : "não encontrada"}</b>
              </div>
            </div>
          </div>
        </section>

        <section className="caixa">
          <div className="caixa-cabecalho">
            <h2>O que ela declarou sobre si mesma</h2>
            <span className="pill pill-muted">
              {limitacoes.length === 0
                ? "nenhuma limitação"
                : `${limitacoes.length} ${limitacoes.length === 1 ? "limitação" : "limitações"}`}
            </span>
          </div>
          <div className="caixa-corpo">
            {limitacoes.length === 0 ? (
              <p className="nota" style={{ margin: 0 }}>
                Nenhuma limitação gravada.
              </p>
            ) : (
              <ol className="limitacoes">
                {limitacoes.map((l, i) => (
                  <li key={i}>
                    <span className={/AMOSTRAL/.test(l) ? "limitacao-n limitacao-n-forte" : "limitacao-n"}>
                      {i + 1}
                    </span>
                    <span>{l}</span>
                  </li>
                ))}
              </ol>
            )}
            <p className="nota" style={{ margin: 0 }}>
              É o <code>motivo_degradacao</code> do Registro — a mesma lista que foi para a aba de
              limitações da planilha.
            </p>
          </div>
        </section>
      </div>

      {trabalhoId ? (
        <RelatorioDosAgentes etapas={ETAPAS} porNo={resumos} />
      ) : (
        <section className="secao ancora" id="agentes">
          <h2>O que cada agente fez</h2>
          <p className="nota" style={{ margin: 0 }}>
            Esta rodada não veio da fila do console (foi disparada pela linha de comando), então
            não há relatório de agentes nem log gravados para ela.
          </p>
        </section>
      )}

      <section className="secao ancora" id="planilha">
      <div className="secao-cabecalho">
        <h2>A planilha</h2>
        <span className="nota">nota do portal · leads e produtividade como desempate · três descontos · a regra cedida</span>
      </div>
      {rodada.tipo === "acompanhamento" ? (
        <p className="nota" style={{ margin: 0 }}>
          Rodada de acompanhamento não tem planilha: produz o relatório de segunda em{" "}
          <code>saida/segunda/</code> (resumo, desempenho por imóvel e leads sem tratamento) e não
          grava parâmetros — mede a carga aprovada contra o Registro. A leitura desse relatório
          no console é fatia própria.
        </p>
      ) : planilha === null ? (
        <div className="banner" role="alert">
          {dataReferencia
            ? `Não há planilha em disco para ${dataReferencia}. Rodada em modo seco não escreve planilha; e uma planilha de outra máquina não está aqui.`
            : "Sem data de referência gravada, não há como localizar a planilha desta rodada."}
        </div>
      ) : (
        <>
          <p className="nota" style={{ margin: 0 }}>
            Lida de <code>{planilha.diretorio}</code>. Atenção: a planilha é por DATA — duas rodadas
            no mesmo dia escrevem no mesmo lugar, e o que está em disco é a última. Cada aba tem
            o botão "Baixar CSV": o arquivo vai como foi entregue (UTF-8, sem BOM) — o Google
            Sheets importa direto; no Excel use "Dados › De texto/CSV" para acentos e vírgulas
            saírem certos.
          </p>
          {planilha.ausentes.length ? (
            <div className="banner" role="alert">
              Abas ausentes em disco: {planilha.ausentes.join(", ")}.
            </div>
          ) : null}
          {planilha.abas.apuracao ? (
            <section className="caixa">
              <div className="caixa-cabecalho">
                <h2>
                  A apuração completa{" "}
                  <span className="pill pill-muted">
                    {planilha.abas.apuracao.vazia || planilha.abas.apuracao.semConteudo
                      ? "0"
                      : planilha.abas.apuracao.linhas.length.toLocaleString("pt-BR")}{" "}
                    imóveis
                  </span>
                </h2>
                <div style={{ display: "flex", alignItems: "center", gap: 14, minWidth: 0 }}>
                  <span className="nota" style={{ maxWidth: 560 }}>{SOBRE_A_ABA.apuracao}</span>
                  {planilha.abas.apuracao.semConteudo ? null : (
                    <span className="nota">o botão de baixar está no topo da página</span>
                  )}
                </div>
              </div>
            </section>
          ) : null}
          {ORDEM_DAS_ABAS.map((aba) => {
            const t = planilha.abas[aba];
            if (!t) return null;
            return (
              <section className="caixa" key={aba}>
                <div className="caixa-cabecalho">
                  <h2>
                    {aba.replace(/_/g, " ")}{" "}
                    <span className="pill pill-muted">{t.vazia || t.semConteudo ? "0" : t.linhas.length.toLocaleString("pt-BR")}</span>
                  </h2>
                  <div style={{ display: "flex", alignItems: "center", gap: 14, minWidth: 0 }}>
                    <span className="nota" style={{ maxWidth: 560 }}>{SOBRE_A_ABA[aba]}</span>
                    {/* Só quando há arquivo com conteúdo: aba ausente ou de 0 bytes não ganha
                        link — a rota devolveria 404, e o alarme da tela é o que importa. */}
                    {t.semConteudo ? null : (
                      <a
                        className="botao-secundario botao-pequeno"
                        href={`/rodada/${rodada.id}/planilha/${aba}.csv`}
                        download={`rodada-${rodada.id}-${aba}.csv`}
                      >
                        Baixar CSV
                      </a>
                    )}
                  </div>
                </div>
                <Tabela aba={aba} t={t} />
              </section>
            );
          })}
        </>
      )}

      </section>

      <section className="caixa ancora" id="parametros">
        <div className="caixa-cabecalho">
          <h2>Parâmetros que a produziram</h2>
          <span className="nota" style={{ maxWidth: 640 }}>
            verbatim, como gravado: o TOML declarado (PROVISÓRIO) mais data de referência, definição de gestor ativo, pasta da coleta e recorte
          </span>
        </div>
        {parametros === null ? (
          <p className="vazio">
            {rodada.tipo === "acompanhamento"
              ? "Rodada de acompanhamento não grava parâmetros: mede a carga aprovada, não decide."
              : "A rodada não gravou parâmetros."}
          </p>
        ) : (
          <div className="caixa-corpo">
            <pre>{JSON.stringify(parametros, null, 2)}</pre>
          </div>
        )}
      </section>

      {trabalhoId ? (
        <section className="caixa ancora" id="log">
          <div className="caixa-cabecalho">
            <h2>Log da execução</h2>
            <span className="nota">
              trabalho <Link href={`/trabalho/${trabalhoId}`}>{trabalhoId}</Link>
              {eventos.length === 0
                ? " · nada gravado"
                : eventos.length >= LIMITE_DO_LOG
                  ? ` · as ${LIMITE_DO_LOG} últimas linhas de um log maior; o relatório dos agentes não depende deste corte`
                  : ` · o log inteiro, ${eventos.length} linhas`}
            </span>
          </div>
          {eventos.length === 0 ? null : (
            <>
            <div className="tabela-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">hora</th>
                    <th scope="col">nó</th>
                    <th scope="col">linha</th>
                  </tr>
                </thead>
                <tbody>
                  {eventos.map((e) => (
                    <tr key={e.id} className={e.nivel === "erro" ? "linha-erro" : undefined}>
                      <td>{new Date(e.momento).toLocaleTimeString("pt-BR")}</td>
                      <td>{e.no_grafo ?? ""}</td>
                      <td>{e.texto}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            </>
          )}
        </section>
      ) : null}
    </>
  );
}
