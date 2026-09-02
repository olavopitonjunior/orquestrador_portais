import { montarAcoes, type Acao } from "@/lib/acoes";
import { outDirPublico, saudeColeta, type SaudeColeta } from "@/lib/coletor";
import { PARAMETROS, PARAMETROS_PENDENTES } from "@/lib/parametros";
import {
  listarRodadas,
  rodadasAguardandoAprovacao,
  type RodadaResumo,
} from "@/lib/registro";
import { dataHora, PilulaEstado } from "./estado";

// Lê o Registro e os arquivos do coletor a cada request (nada estático).
export const dynamic = "force-dynamic";

const CLASSE_SEVERIDADE: Record<Acao["severidade"], string> = {
  acao: "card card-acao",
  aviso: "card card-aviso",
  info: "card card-info",
};

const ESTADO_COLETA_PILL: Record<SaudeColeta["estado"], string> = {
  ok: "pill pill-ok",
  blocked: "pill pill-bad",
  error: "pill pill-bad",
  corrompido: "pill pill-bad",
  ausente: "pill pill-muted",
};

export default async function Page() {
  // Fontes independentes: o banco pode estar fora e os arquivos legíveis, ou o
  // contrário — cada uma degrada sozinha, sem derrubar o painel.
  const [resRodadas, resAguardando, resSaude] = await Promise.allSettled([
    listarRodadas(),
    rodadasAguardandoAprovacao(),
    saudeColeta(),
  ]);

  const rodadas = resRodadas.status === "fulfilled" ? resRodadas.value : [];
  const aguardando = resAguardando.status === "fulfilled" ? resAguardando.value : [];
  const saude = resSaude.status === "fulfilled" ? resSaude.value : null;
  // Detalhe (que pode conter host/porta) só no log do servidor; a UI mostra genérico.
  // Uma linha por fonte, inclusive a de arquivos: `saudeColeta` promete não lançar,
  // mas se a promessa for quebrada no futuro o diagnóstico não pode sumir.
  if (resRodadas.status === "rejected")
    console.error("[console] falha ao ler rodadas:", resRodadas.reason);
  if (resAguardando.status === "rejected")
    console.error("[console] falha ao ler aprovações pendentes:", resAguardando.reason);
  if (resSaude.status === "rejected")
    console.error("[console] falha ao ler a saúde da coleta:", resSaude.reason);

  const acoes = saude ? montarAcoes(saude, aguardando, PARAMETROS_PENDENTES.length) : [];

  return (
    <>
      <h1>Painel do operador</h1>
      <p className="subtitulo">O que precisa da sua atenção, a saúde das fontes e as rodadas.</p>

      {resRodadas.status === "rejected" ? (
        <div className="banner" role="alert">
          Não foi possível ler o Registro. Verifique se o Postgres está no ar e a POSTGRES_URL
          correta; o detalhe está no log do servidor.
        </div>
      ) : (
        resAguardando.status === "rejected" && (
          // Falha parcial: a tabela abaixo tem dado real, então a mensagem não pode
          // dizer "o Postgres está fora" — só o que de fato faltou.
          <div className="banner" role="alert">
            Não foi possível checar as aprovações pendentes; o resto do painel está atualizado.
            O detalhe está no log do servidor.
          </div>
        )
      )}

      <section className="secao">
        <h2>Caixa de ações</h2>
        {acoes.length === 0 ? (
          <p className="vazio-inline">Nada pendente. ✓</p>
        ) : (
          <div className="cards">
            {acoes.map((a) => (
              <div key={a.id} className={CLASSE_SEVERIDADE[a.severidade]}>
                <div className="card-titulo">{a.titulo}</div>
                <div className="card-desc">{a.descricao}</div>
                {a.detalhe && <div className="card-detalhe">{a.detalhe}</div>}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="secao">
        <h2>Saúde das fontes</h2>
        <div className="cards">
          {/* title com o caminho consultado: se o out/ estiver mal configurado, o
              operador descobre sem abrir o servidor (fica no atributo, não no corpo). */}
          <div className="card" title={outDirPublico()}>
            <div className="card-titulo">
              Coleta externa (Canal Pro){" "}
              {saude ? (
                <span className={ESTADO_COLETA_PILL[saude.estado]}>{saude.estado}</span>
              ) : (
                <span className="pill pill-muted">desconhecida</span>
              )}
            </div>
            <div className="card-desc">
              {!saude
                ? "Não foi possível ler os arquivos do coletor."
                : saude.estado === "ausente"
                  ? "Nenhuma coleta encontrada em out/ — o raspador ainda não rodou."
                  : saude.estado === "corrompido"
                    ? "O status da última coleta está ilegível — o raspador rodou e não fechou o arquivo."
                    : `${
                        saude.coletadoEm ? `Coletado ${dataHora(saude.coletadoEm)}` : "Sem data de coleta"
                      }${saude.idadeDias !== null ? ` · ${saude.idadeDias} dia(s) atrás` : ""}${
                        saude.linhas !== null
                          ? ` · ${saude.linhas.toLocaleString("pt-BR")} anúncios`
                          : ""
                      }`}
            </div>
          </div>
        </div>
      </section>

      <section className="secao">
        <h2>Parâmetros pendentes</h2>
        <p className="vazio-inline">
          {PARAMETROS_PENDENTES.length} de {PARAMETROS.length} aguardam sua decisão — permanecem nulos até você
          definir (nada é inventado).
        </p>
        <div className="chips">
          {PARAMETROS_PENDENTES.map((p) => (
            <span key={p.numero} className="chip" title={p.titulo}>
              <b>#{p.numero}</b> {p.titulo}
            </span>
          ))}
        </div>
      </section>

      <section className="secao">
        <h2>Rodadas</h2>
        {rodadas.length === 0 ? (
          <div className="tabela-wrap">
            <p className="vazio">
              {resRodadas.status === "rejected" ? "—" : "Nenhuma rodada registrada ainda."}
            </p>
          </div>
        ) : (
          <div className="tabela-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">#</th>
                  <th scope="col">Tipo</th>
                  <th scope="col">Estado</th>
                  <th scope="col">Início</th>
                  <th scope="col" className="num">Super</th>
                  <th scope="col" className="num">Destaque</th>
                  <th scope="col" className="num">Vazias</th>
                  <th scope="col">Aprovação</th>
                </tr>
              </thead>
              <tbody>
                {rodadas.map((r) => (
                  <tr key={r.id}>
                    <td className="id">{r.id}</td>
                    <td>{r.tipo === "decisao" ? "decisão" : "acompanhamento"}</td>
                    <td>
                      <PilulaEstado estado={r.estado} />
                    </td>
                    <td>{dataHora(r.inicio)}</td>
                    <td className="num">{r.superDestaque.toLocaleString("pt-BR")}</td>
                    <td className="num">{r.destaque.toLocaleString("pt-BR")}</td>
                    <td className="num">{r.posicoesVaziasDestaque.toLocaleString("pt-BR")}</td>
                    <td>
                      {r.aprovadaEm ? (
                        <span className="aprov">
                          {dataHora(r.aprovadaEm)}
                          {r.aprovadaPor ? ` · ${r.aprovadaPor}` : ""}
                        </span>
                      ) : r.tipo === "decisao" ? (
                        <span className="pill pill-muted">pendente</span>
                      ) : (
                        <span className="aprov">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
