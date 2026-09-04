// Seção "Relatório dos agentes" — usada por /trabalho/[id] (rodada em curso) e por
// /rodada/[id] (a rodada inteira num lugar só).
// Requer: `Evento.resumo: Record<string, unknown> | null` e `eventosDoTrabalho` lendo a
// coluna `resumo`. A seção mostra, por etapa da lista de apresentação, o resumo do
// evento com `no_grafo = etapa` e `resumo` não nulo — chave/valor, sem conhecer o
// esquema de cada agente (varia por nó, e é isso que o jsonb comporta).

// O que cada agente é, para quem lê o relatório sem a Spec ao lado.
const SOBRE_O_AGENTE: Record<string, string> = {
  coletor_interno: "Lê o Newcore: candidatos, penalizáveis e dimensões. Sem estoque não há decisão.",
  analista_perfil: "Vendas assinadas em 180 dias → combinações de características que vendem, com quantas vendas sustentam cada uma.",
  coletor_externo: "Lê a raspagem do portal e decide se o desempenho do anúncio (F3) entra: estado, amarração, idade.",
  decisor: "Elegibilidade (8 regras), ranking (4 fatores), penalidades, alocação nas cotas e relaxamento — cálculo, sem modelo.",
  crivo: "Auditoria antes de gravar: cota, piso do super, relaxamento só em destaque. Viola → aborta.",
  redator: "Serializa a planilha; nesta geração não redige prosa.",
  finalizar: "Declara o estado da rodada a partir do que cada etapa reportou.",
};

function Valor({ v }: { v: unknown }) {
  if (v === null || v === undefined) return <span className="vazio-inline">—</span>;
  if (typeof v === "boolean") return <span className={v ? "pill pill-ok" : "pill pill-bad"}>{v ? "sim" : "não"}</span>;
  if (typeof v === "number") return <span className="id">{Number.isInteger(v) ? v : v.toFixed(3)}</span>;
  if (Array.isArray(v)) {
    if (v.length === 0) return <span className="vazio-inline">nenhuma</span>;
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
    if (entradas.length === 0) return <span className="vazio-inline">—</span>;
    return (
      <ul>
        {entradas.map(([k, x]) => (
          <li key={k}>
            {k}: <Valor v={x} />
          </li>
        ))}
      </ul>
    );
  }
  return <>{String(v)}</>;
}

// `porNo` vem de `resumosDoTrabalho` — consulta própria, não do log cortado em 300.
export function RelatorioDosAgentes({
  etapas,
  porNo,
}: {
  etapas: readonly string[];
  porNo: Map<string, Record<string, unknown>>;
}) {
  if (porNo.size === 0) {
    return (
      <section className="secao">
        <h2>Relatório dos agentes</h2>
        <p className="campo-ajuda">
          Nenhum agente reportou ainda. Cada etapa concluída traz aqui o que o agente leu, o que
          produziu e o que não conseguiu — contado a partir do estado da rodada, sem modelo e sem
          cifra inventada.
        </p>
      </section>
    );
  }
  return (
    <section className="secao">
      <h2>Relatório dos agentes</h2>
      <p className="campo-ajuda">
        O que cada agente leu, produziu e não conseguiu — derivado do estado da rodada a cada
        etapa. Só contagens e limitações: nenhum id de imóvel sai daqui.
      </p>
      {etapas.map((etapa) => {
        const r = porNo.get(etapa);
        if (!r) return null;
        const { degradacoes, indisponivel, ...resto } = r as {
          degradacoes?: unknown;
          indisponivel?: unknown;
        } & Record<string, unknown>;
        const degs = Array.isArray(degradacoes) ? degradacoes : [];
        return (
          <details key={etapa} open>
            <summary>
              <strong>{etapa.replace(/_/g, " ")}</strong>
              {degs.length ? <span className="pill pill-warn"> {degs.length} limitação(ões)</span> : null}
            </summary>
            <p className="campo-ajuda">{SOBRE_O_AGENTE[etapa] ?? ""}</p>
            {indisponivel ? (
              <p>
                <span className="pill pill-warn">relatório indisponível</span> o resumo deste agente
                não pôde ser montado ({String(indisponivel)}); a etapa em si concluiu.
              </p>
            ) : null}
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
            {degs.length ? (
              <ul>
                {degs.map((d, i) => (
                  <li key={i} className="linha-erro">
                    {String(d)}
                  </li>
                ))}
              </ul>
            ) : null}
          </details>
        );
      })}
    </section>
  );
}
