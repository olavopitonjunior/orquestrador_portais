import Link from "next/link";

import { blocosPreenchidos, type BlocosDaRodada } from "@/lib/blocos-da-rodada";
import { formatar, linkDoGrupo } from "@/lib/previa";

const n = (v: number | null) => (v === null ? "—" : formatar(v));

const ESCOLHA: Record<string, string> = {
  fim_da_fila: "fim da fila",
  mediana: "nota mediana",
  leads_180d: "leads em 180 dias",
  produtividade_gestor: "produtividade do gestor",
  cadastro_mais_novo: "cadastro mais novo",
};

function Degradacoes({ itens }: { itens: string[] }) {
  if (itens.length === 0) return null;
  return (
    <ol className="limitacoes">
      {itens.map((d) => (
        <li key={d}>{d}</li>
      ))}
    </ol>
  );
}

/** Os três blocos de uma rodada — os mesmos nomes e a mesma ordem de /parametros e
 *  /rodada/nova — com o REALIZADO. Em curso, cada bloco enche quando o nó dele conclui;
 *  o que ainda não chegou fica "—", nunca zero. Cada número aponta para o grupo de
 *  /parametros que o governa. */
export function BlocosRealizados({ b, emCurso }: { b: BlocosDaRodada; emCurso: boolean }) {
  const q = b.quemEntrou;
  const o = b.emQueOrdem;
  const t = b.quantos;
  const grupo = (id: string) => linkDoGrupo(id);
  const preenchidos = blocosPreenchidos(b);
  return (
    <div className="blocos-realizados">
      {emCurso ? (
        <p className="campo-ajuda blocos-progresso">
          {preenchidos} de 3 blocos preenchidos — cada um enche quando o agente dele conclui.
        </p>
      ) : null}
      <section className="caixa bloco-realizado" id="quem-entrou">
        <div className="caixa-cabecalho">
          <h2>
            <span className="bloco-numero">1</span> Quem entrou
          </h2>
          <span className="nota">{q.elegiveis === null ? (emCurso ? "esperando o decisor…" : "sem dado") : `${n(q.elegiveis)} elegíveis de ${n(q.candidatos)} candidatos`}</span>
        </div>
        <div className="caixa-corpo">
          <div className="kpis">
            <div className="kpi">
              <div className="kpi-valor">{n(q.candidatos)}</div>
              <div className="kpi-sub">
                candidatos lidos{q.recorteAmostral !== null ? ` · recorte amostral de ${formatar(q.recorteAmostral)}` : ""}
              </div>
            </div>
            <div className="kpi">
              <div className="kpi-valor">{n(q.perfis)}</div>
              <div className="kpi-sub">
                perfis do que vendeu{q.perfisFrageis !== null ? ` · ${formatar(q.perfisFrageis)} frágeis não contam` : ""} ·{" "}
                <Link href={grupo("quem_entra_perfil")}>a janela</Link>
              </div>
            </div>
            <div className="kpi">
              <div className="kpi-valor">{n(q.elegiveis)}</div>
              <div className="kpi-sub">elegíveis{q.reprovados !== null ? ` · ${formatar(q.reprovados)} reprovados` : ""}</div>
            </div>
          </div>
          {q.porRegra.length > 0 ? (
            <ul className="linhas-kv">
              {q.porRegra.map((r) => (
                <li className="linha-kv" key={r.regra}>
                  <span>
                    reprovados em <Link href={grupo(r.grupo)}>{r.rotulo}</Link>
                  </span>
                  <b>{formatar(r.n)}</b>
                </li>
              ))}
            </ul>
          ) : null}
          <p className="campo-ajuda">
            Um imóvel pode reprovar em mais de uma regra, então as linhas somam mais que os reprovados. Reprovar em uma basta.
          </p>
          <Degradacoes itens={q.degradacoes} />
        </div>
      </section>

      <section className="caixa bloco-realizado" id="em-que-ordem">
        <div className="caixa-cabecalho">
          <h2>
            <span className="bloco-numero">2</span> Em que ordem
          </h2>
          <span className="nota">
            {o.portalEntrou === null
              ? emCurso
                ? "esperando a coleta do portal…"
                : "sem dado"
              : o.portalEntrou
                ? "a nota do anúncio ordenou"
                : `a raspagem não entrou: ordem por ${o.ordemSemPortal ? (ESCOLHA[o.ordemSemPortal] ?? o.ordemSemPortal) : "desempate de banco"}`}
          </span>
        </div>
        <div className="caixa-corpo">
          <ul className="linhas-kv">
            <li className="linha-kv">
              <span>
                cobertura da raspagem (mínimo{" "}
                <Link href={grupo("em_que_ordem_portal")}>{o.coberturaMinima === null ? "—" : `${formatar(o.coberturaMinima)} %`}</Link>)
              </span>
              <b>{o.coberturaAtingida === null ? "—" : `${formatar(o.coberturaAtingida)} %`}</b>
            </li>
            <li className="linha-kv">
              <span>
                idade da raspagem (máximo <Link href={grupo("em_que_ordem_portal")}>{o.idadeMaxima === null ? "—" : `${formatar(o.idadeMaxima)} dias`}</Link>)
              </span>
              <b>{o.idadeDias === null ? "—" : `${formatar(o.idadeDias)} dias`}</b>
            </li>
            <li className="linha-kv">
              <span>imóveis com anúncio raspado</span>
              <b>{n(o.imoveisComAnuncio)}</b>
            </li>
            <li className="linha-kv">
              <span>
                pesos da nota: anúncio · cliques · visualizações (<Link href={grupo("em_que_ordem_portal")}>pontos de 100</Link>)
              </span>
              <b>
                {n(o.pesos.nota)} · {n(o.pesos.cliques)} · {n(o.pesos.visualizacoes)}
              </b>
            </li>
            <li className="linha-kv">
              <span>imóvel sem anúncio raspado</span>
              <b>{o.semAnuncio ? (ESCOLHA[o.semAnuncio] ?? o.semAnuncio) : "—"}</b>
            </li>
          </ul>
          <Degradacoes itens={o.degradacoes} />
        </div>
      </section>

      <section className="caixa bloco-realizado" id="quantos">
        <div className="caixa-cabecalho">
          <h2>
            <span className="bloco-numero">3</span> Quantos
          </h2>
          <span className="nota">
            {t.crivoPassou === null ? (emCurso ? "esperando a alocação…" : "sem dado") : t.crivoPassou ? "o crivo aprovou: cotas, piso e cedência dentro das regras" : "o crivo VETOU"}
          </span>
        </div>
        <div className="caixa-corpo">
          <div className="kpis">
            <div className="kpi">
              <div className="kpi-valor">{n(t.superDestaque)}</div>
              <div className="kpi-sub">super destaque · nunca cede</div>
            </div>
            <div className="kpi">
              <div className="kpi-valor">{n(t.destaque)}</div>
              <div className="kpi-sub">destaque{t.recuperados !== null ? ` · ${formatar(t.recuperados)} por cedência` : ""}</div>
            </div>
            <div className={t.vaziasDestaque !== null && t.vaziasDestaque > 0 ? "kpi kpi-warn" : "kpi"}>
              <div className="kpi-valor">{n(t.vaziasDestaque)}</div>
              <div className="kpi-sub">destaques vazios</div>
            </div>
          </div>
          {t.cedencia.length > 0 ? (
            <>
              <p className="campo-ajuda">
                Degraus cedidos, na ordem, e quantas posições cada um encheu (<Link href={grupo("quantos")}>a ordem é fixa</Link>):
              </p>
              <ul className="linhas-kv">
                {t.cedencia.map((c) => (
                  <li className="linha-kv" key={c.regra}>
                    <span>cedendo {c.rotulo}</span>
                    <b>{formatar(c.n)}</b>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          {t.violacoes.length > 0 ? (
            <div className="banner" role="alert">
              O crivo apontou: {t.violacoes.join("; ")}
            </div>
          ) : null}
          <Degradacoes itens={t.degradacoes} />
        </div>
      </section>
    </div>
  );
}
