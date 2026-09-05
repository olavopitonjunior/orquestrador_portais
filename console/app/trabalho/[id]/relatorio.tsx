// Seção "O que cada agente fez" — usada por /trabalho/[id] (rodada em curso) e por
// /rodada/[id] (a rodada inteira num lugar só). Um cartão por etapa da lista de
// apresentação, com o resumo gravado em `operacao.trabalho_evento.resumo` (jsonb):
// chave/valor, sem conhecer o esquema de cada agente (varia por nó, e é isso que o
// jsonb comporta). `porNo` vem de `resumosDoTrabalho` — consulta própria, não do log
// cortado em 300.

// O que cada agente é, para quem lê o relatório sem a Spec ao lado.
const SOBRE_O_AGENTE: Record<string, string> = {
  coletor_interno: "Lê o Newcore: candidatos, penalizáveis e dimensões. Sem estoque não há decisão.",
  analista_perfil: "Vendas assinadas em 180 dias → combinações de características que vendem, com quantas vendas sustentam cada uma.",
  coletor_externo: "Lê a raspagem do portal e decide se a nota do anúncio entra na ordem: estado, cobertura (amarração), idade.",
  decisor: "Quem entra (nove regras, o perfil incluído), em que ordem (nota do portal menos descontos), quantos (cotas e cedência) — cálculo, sem modelo.",
  crivo: "Auditoria antes de gravar: cota, piso do super, relaxamento só em destaque. Viola → aborta.",
  redator: "Serializa a planilha; nesta geração não redige prosa.",
  finalizar: "Declara o estado da rodada a partir do que cada etapa reportou.",
};

const NOME_DO_AGENTE: Record<string, string> = {
  coletor_interno: "Coletor Interno",
  analista_perfil: "Analista de Perfil",
  coletor_externo: "Coletor Externo",
  decisor: "Decisor",
  crivo: "Crivo",
  redator: "Redator",
  finalizar: "Monitor",
};

function Valor({ v }: { v: unknown }) {
  if (v === null || v === undefined) return <span className="discreto">—</span>;
  if (typeof v === "boolean") return <span className={v ? "pill pill-ok" : "pill pill-bad"}>{v ? "sim" : "não"}</span>;
  if (typeof v === "number") return <b>{Number.isInteger(v) ? v.toLocaleString("pt-BR") : v.toFixed(3)}</b>;
  if (Array.isArray(v)) {
    if (v.length === 0) return <span className="discreto">nenhuma</span>;
    return (
      <ul>
        {v.map((x, i) => (
          <li key={i}>
            <Valor v={x} />
          </li>
        ))}
      </ul>
    );
  }
  if (typeof v === "object") {
    const entradas = Object.entries(v as Record<string, unknown>);
    if (entradas.length === 0) return <span className="discreto">—</span>;
    return (
      <ul>
        {entradas.map(([k, x]) => (
          <li key={k}>
            {k.replace(/_/g, " ")}: <Valor v={x} />
          </li>
        ))}
      </ul>
    );
  }
  return <>{String(v)}</>;
}

export function RelatorioDosAgentes({
  etapas,
  porNo,
}: {
  etapas: readonly string[];
  porNo: Map<string, Record<string, unknown>>;
}) {
  return (
    <section className="secao ancora" id="agentes">
      <div className="secao-cabecalho">
        <h2>O que cada agente fez</h2>
        <span className="nota">Contagens tiradas do estado da rodada a cada etapa. Nada aqui é redigido por modelo, e nenhum id de imóvel sai daqui.</span>
      </div>
      {porNo.size === 0 ? (
        <p className="nota" style={{ margin: 0 }}>
          Nenhum agente reportou ainda. Cada etapa concluída traz aqui o que o agente leu, o que
          produziu e o que não conseguiu.
        </p>
      ) : (
        <div className="agentes-grid">
          {etapas.map((etapa) => {
            const r = porNo.get(etapa);
            if (!r) return null;
            const { degradacoes, indisponivel, ...resto } = r as {
              degradacoes?: unknown;
              indisponivel?: unknown;
            } & Record<string, unknown>;
            const degs = Array.isArray(degradacoes) ? degradacoes : [];
            return (
              <article key={etapa} className="agente">
                <div className="agente-cabecalho">
                  <span>{NOME_DO_AGENTE[etapa] ?? etapa.replace(/_/g, " ")}</span>
                  {indisponivel ? (
                    <span className="pill pill-warn">relatório indisponível</span>
                  ) : degs.length ? (
                    <span className="pill pill-warn">{degs.length} {degs.length === 1 ? "limitação" : "limitações"}</span>
                  ) : (
                    <span className="pill pill-ok">pronto</span>
                  )}
                </div>
                <div className="agente-sobre">{SOBRE_O_AGENTE[etapa] ?? ""}</div>
                {indisponivel ? (
                  <div className="agente-sobre">
                    O resumo deste agente não pôde ser montado ({String(indisponivel)}); a etapa em si concluiu.
                  </div>
                ) : null}
                {Object.keys(resto).length ? (
                  <table>
                    <tbody>
                      {Object.entries(resto).map(([k, v]) => (
                        <tr key={k}>
                          <td>{k.replace(/_/g, " ")}</td>
                          <td>
                            <Valor v={v} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : null}
                {degs.length ? (
                  <ul>
                    {degs.map((d, i) => (
                      <li key={i} className="linha-erro">
                        {String(d)}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
