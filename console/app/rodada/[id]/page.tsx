import Link from "next/link";

import {
  ETAPAS,
  LIMITE_DO_LOG,
  eventosDoTrabalho,
  resumosDoTrabalho,
  trabalhoDaRodada,
} from "@/lib/operacao";
import { ABAS, lerPlanilha, type Aba, type Tabela } from "@/lib/planilha";
import { lerRodada, limitacoesDe, parametrosDaRodada } from "@/lib/registro";
import { dataHora, PilulaEstado } from "../../estado";
import { RelatorioDosAgentes } from "../../trabalho/[id]/relatorio";

export const dynamic = "force-dynamic";

// O que cada aba é, e o que cada coluna de justificativa quer dizer — para o dono ler
// a planilha sem precisar da Spec ao lado. Texto de exibição, não regra.
const SOBRE_A_ABA: Record<Aba, string> = {
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
  parametros_e_limitacoes:
    "O que produziu esta lista: os parâmetros PROVISÓRIOS declarados, e cada limitação que " +
    "a rodada declarou sobre si mesma. Leia esta aba antes das outras.",
};

const SOBRE_A_COLUNA: Record<string, string> = {
  semelhanca_perfil: "F1 · semelhança com o perfil que vendeu (banco)",
  leads: "F2 · leads já atraídos em 180 dias (banco)",
  desempenho_proprio: "F3 · desempenho do anúncio no portal (raspagem)",
  produtividade_gestor: "F4 · produtividade do gestor em 30 dias (banco)",
  pen_janela_sem_resultado: "penalidade · janela anterior sem resultado",
  pen_sem_avaliacao_por_categoria: "penalidade · sem avaliação por categoria",
  pen_sem_lead_180d: "penalidade · sem lead em 180 dias",
  desconto_total: "soma das penalidades",
  ultima_janela: "a última janela paga deste imóvel, e como foi julgada",
  perfil_que_puxou: "o perfil de conversão que mais contribuiu para o F1",
  perfil_num_vendas: "vendas que sustentam esse perfil",
  perfil_fragil: "perfil com menos vendas que a evidência mínima",
  origem: "ranking, ou relaxamento (recuperado por cedência)",
  degrau_cedido: "a regra cedida para este imóvel entrar",
};

// A ordem de LEITURA, explícita: limitações antes de qualquer número; depois o nível com
// disputa; depois o de folga; excluídos e relaxamento por último.
const ORDEM_DAS_ABAS: readonly Aba[] = [
  "parametros_e_limitacoes",
  "super_destaque",
  "destaque",
  "excluidos_por_regra",
  "relaxamento",
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
      <p className="campo-ajuda">
        {t.linhas.length} linhas
        {t.linhas.length > LINHAS_NA_TELA ? ` — as ${LINHAS_NA_TELA} primeiras na tela; o CSV inteiro está em disco` : ""}
        . Passe o mouse no cabeçalho para ver o que cada coluna significa.
      </p>
    </>
  );
}

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const bruto = (await params).id;
  if (!/^\d+$/.test(bruto)) return <h1>Rodada inválida</h1>;
  const id = Number(bruto);

  const [rodada, parametros, trabalhoId] = await Promise.all([
    lerRodada(id).catch(() => null),
    parametrosDaRodada(id).catch(() => null),
    trabalhoDaRodada(id).catch(() => null),
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

  return (
    <>
      <h1>
        Rodada {rodada.id} · {rodada.tipo} <PilulaEstado estado={rodada.estado} />
      </h1>
      <p className="subtitulo">
        executada {dataHora(rodada.inicio)}
        {dataReferencia ? ` · data de referência ${dataReferencia}` : ""}
        {rodada.aprovadaEm ? ` · aprovada ${dataHora(rodada.aprovadaEm)} por ${rodada.aprovadaPor ?? "?"}` : " · pendente de aprovação"}
        {trabalhoId ? (
          <>
            {" · "}
            <Link href={`/trabalho/${trabalhoId}`}>log da execução</Link>
          </>
        ) : null}
      </p>

      {amostral ? (
        <div className="banner" role="alert">
          <strong>RODADA AMOSTRAL</strong> — decidiu sobre o recorte de{" "}
          {recorte?.imoveis ?? "?"} imóveis que a raspagem trouxe, não sobre o estoque. Existe
          para ver a corrente inteira funcionar; nunca é COMPLETA e não pode ser aprovada.
        </div>
      ) : null}

      <section className="secao">
        <h2>O que a rodada declarou sobre si mesma</h2>
        {limitacoes.length === 0 ? (
          <p className="vazio">Nenhuma limitação gravada.</p>
        ) : (
          <ol>
            {limitacoes.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ol>
        )}
        <p className="campo-ajuda">
          É o <code>motivo_degradacao</code> do Registro — a mesma lista que foi para a aba de
          limitações da planilha. Posições de destaque vazias: {rodada.posicoesVaziasDestaque}.
        </p>
      </section>

      <section className="secao">
        <h2>Parâmetros que a produziram</h2>
        {parametros === null ? (
          <p className="vazio">
            {rodada.tipo === "acompanhamento"
              ? "Rodada de acompanhamento não grava parâmetros: mede a carga aprovada, não decide."
              : "A rodada não gravou parâmetros."}
          </p>
        ) : (
          <pre>{JSON.stringify(parametros, null, 2)}</pre>
        )}
        <p className="campo-ajuda">
          Verbatim, como gravado: o TOML declarado (PROVISÓRIO) mais as entradas fora dele —
          data de referência, definição de gestor ativo, pasta da coleta, recorte.
        </p>
      </section>

      {trabalhoId ? (
        <RelatorioDosAgentes etapas={ETAPAS} porNo={resumos} />
      ) : (
        <section className="secao">
          <h2>Relatório dos agentes</h2>
          <p className="vazio">
            Esta rodada não veio da fila do console (foi disparada pela linha de comando), então
            não há relatório de agentes nem log gravados para ela.
          </p>
        </section>
      )}

      <h2>A planilha</h2>
      {rodada.tipo === "acompanhamento" ? (
        <p className="campo-ajuda">
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
          <p className="campo-ajuda">
            Lida de <code>{planilha.diretorio}</code>. Atenção: a planilha é por DATA — duas rodadas
            no mesmo dia escrevem no mesmo lugar, e o que está em disco é a última.
          </p>
          {planilha.ausentes.length ? (
            <div className="banner" role="alert">
              Abas ausentes em disco: {planilha.ausentes.join(", ")}.
            </div>
          ) : null}
          {ORDEM_DAS_ABAS.map((aba) => {
            const t = planilha.abas[aba];
            if (!t) return null;
            return (
              <section className="secao" key={aba}>
                <h3>{aba.replace(/_/g, " ")}</h3>
                <p className="campo-ajuda">{SOBRE_A_ABA[aba]}</p>
                <Tabela aba={aba} t={t} />
              </section>
            );
          })}
        </>
      )}

      {trabalhoId ? (
        <section className="secao">
          <h2>Log da execução</h2>
          {eventos.length === 0 ? (
            <p className="campo-ajuda">
              Trabalho <Link href={`/trabalho/${trabalhoId}`}>{trabalhoId}</Link> — nada gravado.
            </p>
          ) : (
            <>
              <p className="campo-ajuda">
                Trabalho <Link href={`/trabalho/${trabalhoId}`}>{trabalhoId}</Link> —{" "}
                {eventos.length >= LIMITE_DO_LOG
                  ? `as ${LIMITE_DO_LOG} últimas linhas de um log maior (o começo não está aqui nem em /trabalho)`
                  : `o log inteiro, ${eventos.length} linhas`}
                ; o relatório dos agentes acima não depende deste corte.
              </p>
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
