import Link from "next/link";

import { desfechoDe } from "@/lib/desfecho";
import {
  ETAPAS,
  etapasConcluidas,
  eventosDoTrabalho,
  lerTrabalho,
  resumosDoTrabalho,
  trabalhadorVivo,
} from "@/lib/operacao";

import { RelatorioDosAgentes } from "./relatorio";

export const dynamic = "force-dynamic";

const EM_CURSO = new Set(["pendente", "executando"]);

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const id = Number((await params).id);
  if (!Number.isInteger(id)) return <h1>Trabalho inválido</h1>;

  const [trabalho, eventos, anunciadas, vivo, resumos] = await Promise.all([
    lerTrabalho(id).catch(() => null),
    eventosDoTrabalho(id).catch(() => []),
    etapasConcluidas(id).catch(() => [] as string[]),
    trabalhadorVivo().catch(() => false),
    resumosDoTrabalho(id).catch(() => new Map<string, Record<string, unknown>>()),
  ]);

  if (trabalho === null) {
    return (
      <>
        <h1>Trabalho {id}</h1>
        <div className="banner" role="alert">
          Não encontrado. Ou o id está errado, ou o Registro de operação está fora.
        </div>
      </>
    );
  }

  const emCurso = EM_CURSO.has(trabalho.estado);
  const desfecho = desfechoDe(trabalho.tipo, trabalho.codigo_saida);
  // Quais etapas já se anunciaram. O nó vem do NDJSON que a rodada emite ao vivo; a
  // ordem de apresentação é a de ETAPAS, não a de chegada — dois nós do mesmo passo do
  // grafo terminam juntos, e listá-los na ordem de chegada sugeriria uma sequência que
  // não houve.
  //
  // Só os nós que a lista de apresentação conhece entram na CONTAGEM. A rodada também
  // emite `registrar`, que é sink e não etapa da decisão — contá-lo produzia "8 de 7
  // anunciadas", que não quer dizer nada. Aparecia na tela e em nenhum teste.
  const anunciados = new Set(anunciadas);
  const concluidas = new Set(ETAPAS.filter((etapa) => anunciados.has(etapa)));

  return (
    <>
      {/* Auto-refresh sem JavaScript enquanto o trabalho corre. Um poller cliente seria
          mais suave, e é o que entra se isto incomodar — mas começar pelo que não tem
          código é o que garante que a tela funcione antes de haver o que otimizar. */}
      {emCurso ? <meta httpEquiv="refresh" content="5" /> : null}

      <h1>
        Trabalho {trabalho.id} · {trabalho.tipo}
      </h1>
      <p className="subtitulo">
        pedido {new Date(trabalho.pedido_em).toLocaleString("pt-BR")}
        {trabalho.pedido_por ? ` por ${trabalho.pedido_por}` : ""} ·{" "}
        <strong>{trabalho.estado}</strong>
        {emCurso ? " · esta página se atualiza sozinha" : ""}
      </p>

      {/* O MESMO aviso de `/rodada/nova`, e ele precisa estar aqui: é para cá que o
          disparo redireciona, então quem enfileirou já saiu da tela que o tinha. Sem
          isto, com o processo parado, o trabalho fica `pendente`, a página se recarrega
          a cada cinco segundos para sempre, e nada explica por que nada acontece. */}
      {emCurso && !vivo ? (
        <div className="banner" role="alert">
          <strong>O trabalhador não está no ar.</strong> Este pedido vai ficar esperando. Suba com{" "}
          <code>uv run rodada-trabalhador</code> na raiz do repositório — o console apenas
          enfileira; quem executa é um processo separado.
        </div>
      ) : null}

      {desfecho ? (
        <div className={desfecho.grave ? "banner" : "banner banner-info"} role="status">
          <strong>
            {desfecho.titulo} (código {trabalho.codigo_saida})
          </strong>
          <br />
          {desfecho.explicacao}
        </div>
      ) : null}

      {trabalho.rodada_id ? (
        <div className="banner banner-ok" role="status">
          Gravou a rodada <strong>nº {trabalho.rodada_id}</strong> no Registro. Ela fica
          pendente de aprovação — <Link href="/">veja no painel</Link>.
        </div>
      ) : null}

      <section className="secao">
        <h2>Etapas</h2>
        <ol className="etapas">
          {ETAPAS.map((etapa) => (
            <li key={etapa} className={concluidas.has(etapa) ? "etapa etapa-feita" : "etapa"}>
              {etapa.replace(/_/g, " ")}
            </li>
          ))}
        </ol>
        <p className="campo-ajuda">
          {concluidas.size} de {ETAPAS.length} anunciadas. Duas delas — perfil e coleta externa —
          correm em paralelo e terminam juntas: aparecem ao mesmo tempo, e o instante de ambas é o
          do mais lento.
        </p>
      </section>

      <RelatorioDosAgentes etapas={ETAPAS} porNo={resumos} />

      <section className="secao">
        <h2>Log</h2>
        {eventos.length === 0 ? (
          <p className="campo-ajuda">Nada ainda.</p>
        ) : (
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
        )}
      </section>
    </>
  );
}
