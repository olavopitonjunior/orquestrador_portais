import { listarRodadas, type RodadaResumo } from "@/lib/registro";
import { dataHora, PilulaEstado } from "./estado";

// Lê o Registro a cada request (nada estático): o console reflete o estado vivo.
export const dynamic = "force-dynamic";

export default async function Page() {
  let rodadas: RodadaResumo[] = [];
  let erro: string | null = null;
  try {
    rodadas = await listarRodadas();
  } catch (e) {
    // Detalhe (que pode conter host/porta do driver) fica no log do servidor;
    // a UI mostra só uma mensagem genérica acionável (evita vazar interno).
    console.error("[console] falha ao ler o Registro:", e);
    erro =
      "Não foi possível ler o Registro. Verifique se o Postgres está no ar e a " +
      "POSTGRES_URL correta; o detalhe está no log do servidor.";
  }

  return (
    <>
      <h1>Rodadas</h1>
      <p className="subtitulo">
        Histórico das rodadas registradas — decisão (sexta) e acompanhamento (segunda).
      </p>

      {erro ? (
        <div className="banner" role="alert">
          {erro}
        </div>
      ) : rodadas.length === 0 ? (
        <div className="tabela-wrap">
          <p className="vazio">Nenhuma rodada registrada ainda.</p>
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
    </>
  );
}
