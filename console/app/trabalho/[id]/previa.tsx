import Link from "next/link";

import {
  ESPERA_DA_PREVIA,
  ROTULO_DO_DEGRAU,
  formatar,
  fraseDaPrevia,
  grupoDoCaminho,
  linkDoGrupo,
  valoresEmOrdem,
  type Previa,
} from "@/lib/previa";

const n = formatar;

const TITULO_DO_GRUPO: Record<string, string> = {
  quem_entra_imovel: "o imóvel",
  quem_entra_perfil: "o perfil de conversão",
  quem_entra_corretor: "o corretor",
};

/** A prévia ainda correndo: o mesmo aviso de espera do botão, sem inventar progresso. */
export function PreviaEmCurso() {
  return (
    <section className="secao">
      <h2>A prévia está sendo calculada</h2>
      <p className="campo-ajuda">
        {ESPERA_DA_PREVIA} Esta página se atualiza sozinha.
      </p>
    </section>
  );
}

export function PreviaDoFunil({ previa }: { previa: Previa }) {
  const base = previa.candidatos;
  const declarados = new Set(
    previa.parametros.declarados_diferentes_do_adotado,
  );
  const efetivo = previa.parametros.efetivo;
  return (
    <>
      <section className="secao">
        <h2>Quem entra, com estes valores</h2>
        <p className="previa-frase">{fraseDaPrevia(previa)}</p>
        <p className="campo-ajuda">
          Contagem pelas mesmas regras da rodada, sobre o estoque lido{" "}
          {previa.hoje
            ? `em ${new Date(previa.hoje + "T12:00:00").toLocaleDateString("pt-BR")}`
            : "hoje"}
          {previa.duracao_s !== undefined
            ? ` (${n(previa.duracao_s)} s de leitura)`
            : ""}
          . A projeção de posições é aritmética — quem está acima de R$ 700.000
          disputa o super destaque, o resto vai ao destaque —, não a alocação
          por nota, que só a rodada faz.
        </p>

        <div className="tabela-wrap">
          <table className="funil">
            <thead>
              <tr>
                <th scope="col">regra</th>
                <th scope="col">de</th>
                <th scope="col" className="num">
                  cortou
                </th>
                <th scope="col" className="num">
                  sobram
                </th>
                <th scope="col"></th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>candidatos lidos</td>
                <td></td>
                <td className="num"></td>
                <td className="num">
                  <b>{n(base)}</b>
                </td>
                <td>
                  <span className="funil-barra" aria-hidden="true" style={{ width: "100%" }} />
                </td>
              </tr>
              {previa.funil.map((ln) => (
                <tr
                  key={ln.regra}
                  className={ln.cortou > 0 ? "funil-corta" : undefined}
                >
                  <td>
                    <Link
                      href={linkDoGrupo(ln.grupo)}
                      title="ver o parâmetro que governa esta regra"
                    >
                      {ln.rotulo}
                    </Link>
                  </td>
                  <td className="discreto">
                    {TITULO_DO_GRUPO[ln.grupo] ?? ln.grupo}
                  </td>
                  <td className="num">
                    {ln.cortou > 0 ? `−${n(ln.cortou)}` : ""}
                  </td>
                  <td className="num">
                    <b>{n(ln.sobram)}</b>
                  </td>
                  <td>
                    <span
                      className="funil-barra"
                      aria-hidden="true"
                      style={{
                        width: `${base > 0 ? Math.max(1, Math.round((100 * ln.sobram) / base)) : 0}%`,
                      }}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!previa.perfil.filtro_incide ? (
          <div className="banner banner-warn" role="status">
            <strong>O filtro de perfil não incidiu.</strong> Nenhum perfil
            robusto
            {previa.perfil.exigencia
              ? ` contendo ${previa.perfil.exigencia.replace(/_/g, " ")}`
              : ""}{" "}
            saiu das {previa.vendas ? n(previa.vendas.assinadas) : ""} vendas da
            janela — ninguém foi cortado por perfil, e a rodada real sairia
            degradada por isso.{" "}
            <Link href={linkDoGrupo("quem_entra_perfil")}>
              Ver a janela do que vende
            </Link>
            .
          </div>
        ) : null}
      </section>

      <section className="secao">
        <h2>Quantos</h2>
        <div className="kpis">
          <div className="kpi">
            <div className="kpi-valor">
              {n(previa.projecao.super_destaque_preenchido)}
              <small> / {n(previa.posicoes.super_destaque)}</small>
            </div>
            <div className="kpi-sub">
              super destaque · {n(previa.candidatos_super_destaque)} candidatos
              acima do piso
            </div>
          </div>
          <div className="kpi">
            <div className="kpi-valor">
              {n(previa.projecao.destaque_preenchido)}
              <small> / {n(previa.posicoes.destaque)}</small>
            </div>
            <div className="kpi-sub">
              destaque · pelo funil, antes da cedência
            </div>
          </div>
          <div
            className={
              previa.projecao.vazias_total > 0 ? "kpi kpi-warn" : "kpi"
            }
          >
            <div className="kpi-valor">{n(previa.projecao.vazias_total)}</div>
            <div className="kpi-sub">posições ficariam vazias</div>
          </div>
        </div>
        {previa.projecao.vazias_destaque > 0 ? (
          <>
            <p className="campo-ajuda">
              No destaque a rodada cede regras, nesta ordem, até encher — o
              super destaque nunca cede. Quantos a cedência recuperaria,
              acumulado:
            </p>
            <ul className="linhas-kv">
              {previa.relaxamento.por_degrau.map((d) => (
                <li className="linha-kv" key={d.regra}>
                  <span>{ROTULO_DO_DEGRAU[d.regra] ?? d.regra}</span>
                  <b>{n(d.recuperaveis_ate_aqui)}</b>
                </li>
              ))}
              {previa.relaxamento.travados_pelo_login > 0 ? (
                <li className="linha-kv">
                  <span>
                    irrecuperáveis: gestor sem login em{" "}
                    {String(efetivo["corretor.login_janela_dias"] ?? "")} dias (
                    <Link href={linkDoGrupo("quem_entra_corretor")}>
                      o parâmetro
                    </Link>
                    )
                  </span>
                  <b>{n(previa.relaxamento.travados_pelo_login)}</b>
                </li>
              ) : null}
            </ul>
          </>
        ) : null}
      </section>

      <section className="secao">
        <h2>Os valores que produziram esta prévia</h2>
        <p className="campo-ajuda">
          {declarados.size === 0
            ? "Todos adotados (D-034): nada foi declarado diferente."
            : `${declarados.size} ${declarados.size === 1 ? "valor declarado" : "valores declarados"} diferente do adotado, em negrito.`}
        </p>
        <ul className="linhas-kv">
          {valoresEmOrdem(efetivo).map(([caminho, valor]) => (
            <li className="linha-kv" key={caminho}>
              <span>
                <Link href={linkDoGrupo(grupoDoCaminho(caminho))}>
                  {caminho.replace(/_/g, " ")}
                </Link>
              </span>
              {declarados.has(caminho) ? (
                <b>{String(valor)}</b>
              ) : (
                <span>{String(valor)}</span>
              )}
            </li>
          ))}
        </ul>
        {previa.degradacoes.length > 0 ? (
          <ol className="limitacoes">
            {previa.degradacoes.map((d) => (
              <li key={d}>{d}</li>
            ))}
          </ol>
        ) : null}
      </section>
    </>
  );
}
