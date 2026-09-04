import Link from "next/link";

import { montarAcoes, type Acao } from "@/lib/acoes";
import { saudeChrome } from "@/lib/chrome";
import { outDirPublico, saudeColeta } from "@/lib/coletor";
import { cotasDoRegistro } from "@/lib/cotas";
import { trabalhadorVivo } from "@/lib/operacao";
import { PARAMETROS, PARAMETROS_PENDENTES } from "@/lib/parametros";
import { condicoes, veredito } from "@/lib/prontidao";
import {
  limitacoesDe,
  listarRodadas,
  rodadasAguardandoAprovacao,
  type RodadaResumo,
} from "@/lib/registro";
import { cadencia, diaCurto, diaLongo, quando } from "@/lib/semana";
import { dataHora, duracao, PilulaEstado } from "./estado";
import { IconeAtencao, IconeCerto, IconeColeta, IconePlay } from "./icones";

// Lê o Registro e os arquivos do coletor a cada request (nada estático).
export const dynamic = "force-dynamic";

const PILULA_DA_ACAO: Record<Acao["severidade"], { classe: string; texto: string }> = {
  acao: { classe: "pill pill-warn", texto: "ação" },
  aviso: { classe: "pill pill-bad", texto: "aviso" },
  info: { classe: "pill pill-muted", texto: "informação" },
};

export default async function Page() {
  // Fontes independentes: cada uma degrada sozinha, sem derrubar o painel.
  const [resRodadas, resAguardando, resSaude, resChrome, resVivo, resCotas] = await Promise.allSettled([
    listarRodadas(),
    rodadasAguardandoAprovacao(),
    saudeColeta(),
    saudeChrome(),
    trabalhadorVivo(),
    cotasDoRegistro(),
  ]);

  const rodadas = resRodadas.status === "fulfilled" ? resRodadas.value : [];
  const aguardando = resAguardando.status === "fulfilled" ? resAguardando.value : [];
  const saude = resSaude.status === "fulfilled" ? resSaude.value : null;
  const chrome = resChrome.status === "fulfilled" ? resChrome.value : null;
  const vivo = resVivo.status === "fulfilled" ? resVivo.value : null;
  const cotas = resCotas.status === "fulfilled" ? resCotas.value : null;
  // Detalhe (que pode conter host/porta) só no log do servidor; a UI mostra genérico.
  for (const [nome, r] of [
    ["rodadas", resRodadas],
    ["aprovações pendentes", resAguardando],
    ["saúde da coleta", resSaude],
    ["Chrome", resChrome],
    ["trabalhador", resVivo],
    ["cotas", resCotas],
  ] as const)
    if (r.status === "rejected") console.error(`[console] falha ao ler ${nome}:`, r.reason);

  const acoes = saude ? montarAcoes(saude, aguardando, PARAMETROS_PENDENTES.length) : [];
  const cs = condicoes(saude, chrome, vivo, PARAMETROS_PENDENTES.length, PARAMETROS.length, dataHora);
  const v = veredito(cs);
  const hoje = new Date();
  const c = cadencia(hoje);
  const ultimaAprovada = rodadas.find((r) => r.aprovadaEm !== null) ?? null;

  return (
    <>
      <header className="cabecalho">
        <div>
          <h1>Painel</h1>
          <p className="subtitulo">
            {diaLongo(hoje)} · a próxima decisão é {quando(c.diasAteDecisao)}, {diaLongo(c.decisao).toLowerCase()}.
          </p>
        </div>
        <div className="cabecalho-acoes">
          <Link href="/coleta" className="botao-secundario">
            <IconeColeta />
            Coletar do portal
          </Link>
          <Link href="/rodada/nova" className="botao">
            <IconePlay />
            Rodar a decisão
          </Link>
        </div>
      </header>

      {resRodadas.status === "rejected" ? (
        <div className="banner" role="alert">
          Não foi possível ler o Registro. Verifique se o Postgres está no ar e a POSTGRES_URL
          correta; o detalhe está no log do servidor.
        </div>
      ) : (
        resAguardando.status === "rejected" && (
          <div className="banner" role="alert">
            Não foi possível checar as aprovações pendentes; o resto do painel está atualizado.
            O detalhe está no log do servidor.
          </div>
        )
      )}

      <section className="caixa">
        <div className="caixa-cabecalho">
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <h2>Prontidão para a rodada de {diaLongo(c.decisao).toLowerCase()}</h2>
            <span className={v.classe}>{v.texto}</span>
          </div>
          <span className="nota">{v.explicacao}</span>
        </div>
        <div className="caixa-corpo">
          <div className="grade-4">
            {cs.map((cnd) => (
              <div key={cnd.titulo} className={`condicao condicao-${cnd.nivel}`} title={cnd.titulo === "Coleta do portal" ? outDirPublico() : undefined}>
                <div className="condicao-marca">{cnd.nivel === "ok" ? <IconeCerto /> : <IconeAtencao />}</div>
                <div style={{ minWidth: 0 }}>
                  <div className="condicao-titulo">{cnd.titulo}</div>
                  <div className="condicao-texto">
                    {cnd.texto}
                    {cnd.href ? (
                      <>
                        {" "}
                        <Link href={cnd.href}>{cnd.rotulo}</Link>
                      </>
                    ) : null}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="grade-2">
        <section className="caixa">
          <div className="caixa-cabecalho">
            <h2>Precisa de você</h2>
            <span className="pill pill-muted">{acoes.length === 0 ? "nada pendente" : `${acoes.length} ${acoes.length === 1 ? "item" : "itens"}`}</span>
          </div>
          {!saude ? (
            <p className="vazio-inline">Sem leitura da coleta, a caixa de ações não pode ser montada.</p>
          ) : acoes.length === 0 ? (
            <p className="vazio-inline">Nada pendente.</p>
          ) : (
            <div>
              {acoes.map((a) => (
                <div key={a.id} className="acao-item">
                  <span className={PILULA_DA_ACAO[a.severidade].classe}>{PILULA_DA_ACAO[a.severidade].texto}</span>
                  <div className="acao-corpo">
                    <div className="acao-titulo">{a.titulo}</div>
                    <div className="acao-desc">{a.descricao}</div>
                    {a.detalhe && <div className="acao-detalhe">{a.detalhe}</div>}
                  </div>
                  {a.href ? (
                    <Link href={a.href} className="botao-secundario botao-pequeno">
                      {a.rotulo ?? "Abrir"}
                    </Link>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </section>

        <div className="coluna">
          <section className="caixa">
            <div className="caixa-cabecalho">
              <h2>Contrato vigente</h2>
              <span className="nota">Grupo OLX · plano Exclusivo</span>
            </div>
            <div className="caixa-corpo">
              {cotas === null ? (
                <p className="nota" style={{ margin: 0 }}>
                  Sem cota lida do Registro: a restrição <code>posicao_dentro_da_cota</code> não respondeu. O
                  console não redeclara cotas.
                </p>
              ) : (
                <div className="kpis">
                  <div className="kpi">
                    <div className="lbl">Super destaque</div>
                    <div className="kpi-valor">{cotas.superDestaque.toLocaleString("pt-BR")}</div>
                    <div className="kpi-sub">posições · nunca relaxa</div>
                  </div>
                  <div className="kpi">
                    <div className="lbl">Destaque</div>
                    <div className="kpi-valor">{cotas.destaque.toLocaleString("pt-BR")}</div>
                    <div className="kpi-sub">posições · relaxamento permitido</div>
                  </div>
                </div>
              )}
              <div className="linhas-kv">
                <div className="linha-kv">
                  <span>Última carga aprovada</span>
                  <b>
                    {ultimaAprovada ? (
                      <Link href={`/rodada/${ultimaAprovada.id}`}>
                        rodada {ultimaAprovada.id} · {dataHora(ultimaAprovada.aprovadaEm)}
                      </Link>
                    ) : (
                      "nenhuma"
                    )}
                  </b>
                </div>
                <div className="linha-kv">
                  <span>Aguardando aprovação</span>
                  <b>{aguardando.length === 0 ? "nenhuma" : aguardando.map((r) => r.id).join(", ")}</b>
                </div>
              </div>
            </div>
          </section>

          <section className="caixa">
            <div className="caixa-cabecalho">
              <h2>Semana</h2>
              <span className="nota">horário: parâmetro nº 8, nulo</span>
            </div>
            <div className="caixa-corpo" style={{ gap: 0, paddingTop: 8, paddingBottom: 8 }}>
              <div className="semana-linha">
                <span className="semana-dia">{diaCurto(c.decisao)}</span>
                <span className="semana-o-que">Rodada de decisão</span>
                <span className="pill pill-acc">{quando(c.diasAteDecisao)}</span>
              </div>
              <div className="semana-linha">
                <span className="semana-dia">{diaCurto(c.decisao)}</span>
                <span className="semana-o-que">Aprovação e carga manual</span>
                <span className="pill pill-muted">depois da decisão</span>
              </div>
              <div className="semana-linha">
                <span className="semana-dia">{diaCurto(c.acompanhamento)}</span>
                <span className="semana-o-que">Acompanhamento</span>
                <span className="pill pill-muted">só lê o banco</span>
              </div>
            </div>
          </section>
        </div>
      </div>

      <section className="caixa">
        <div className="caixa-cabecalho">
          <h2>Parâmetros que aguardam sua decisão</h2>
          <span className="nota">
            {PARAMETROS_PENDENTES.length} de {PARAMETROS.length} · permanecem nulos até você definir; nada é inventado
          </span>
        </div>
        {PARAMETROS_PENDENTES.length === 0 ? (
          <p className="vazio-inline">Todos definidos.</p>
        ) : (
          <div className="caixa-corpo">
            <div className="chips">
              {PARAMETROS_PENDENTES.map((p) => (
                <span key={p.numero} className="chip" title={p.titulo}>
                  <b>#{p.numero}</b> {p.titulo}
                </span>
              ))}
            </div>
          </div>
        )}
      </section>

      <section className="caixa ancora" id="rodadas">
        <div className="caixa-cabecalho">
          <h2>Rodadas</h2>
          <span className="nota">{rodadas.length === 0 ? "" : `${rodadas.length} mais recentes`}</span>
        </div>
        {rodadas.length === 0 ? (
          <p className="vazio">{resRodadas.status === "rejected" ? "—" : "Nenhuma rodada registrada ainda."}</p>
        ) : (
          <div className="tabela-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Rodada</th>
                  <th scope="col">Tipo</th>
                  <th scope="col">Estado</th>
                  <th scope="col">Início</th>
                  <th scope="col">Duração</th>
                  <th scope="col" className="num">Super</th>
                  <th scope="col" className="num">Destaque</th>
                  <th scope="col" className="num">Vazias</th>
                  <th scope="col">Declarou</th>
                  <th scope="col">Aprovação</th>
                </tr>
              </thead>
              <tbody>
                {rodadas.map((r) => {
                  const n = limitacoesDe(r.motivoDegradacao).length;
                  return (
                    <tr key={r.id}>
                      <td className="id">
                        <Link href={`/rodada/${r.id}`}>{r.id}</Link>
                      </td>
                      <td>{r.tipo === "decisao" ? "decisão" : "acompanhamento"}</td>
                      <td>
                        <PilulaEstado estado={r.estado} />
                        {r.amostral ? (
                          <>
                            {" "}
                            <span className="pill pill-bad">amostral</span>
                          </>
                        ) : null}
                      </td>
                      <td>{dataHora(r.inicio)}</td>
                      <td className="discreto">{duracao(r.inicio, r.fim)}</td>
                      <td className="num">{r.superDestaque.toLocaleString("pt-BR")}</td>
                      <td className="num">{r.destaque.toLocaleString("pt-BR")}</td>
                      <td className="num">{r.posicoesVaziasDestaque.toLocaleString("pt-BR")}</td>
                      <td title={r.motivoDegradacao ?? undefined}>
                        {n === 0 ? <span className="discreto">—</span> : <span className="pill pill-muted">{n} {n === 1 ? "limitação" : "limitações"}</span>}
                      </td>
                      <td>
                        {r.aprovadaEm ? (
                          <span className="aprov">
                            {dataHora(r.aprovadaEm)}
                            {r.aprovadaPor ? ` · ${r.aprovadaPor}` : ""}
                          </span>
                        ) : r.amostral ? (
                          <span className="discreto">recusada · amostral</span>
                        ) : r.tipo === "decisao" ? (
                          <span className="pill pill-muted">pendente</span>
                        ) : (
                          <span className="aprov">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
