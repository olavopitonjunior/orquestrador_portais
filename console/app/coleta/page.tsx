import Link from "next/link";

import { portaCdp, saudeChrome, type SaudeChrome } from "@/lib/chrome";
import { amarracaoDoCsv, saudeColeta, type Amarracao, type SaudeColeta } from "@/lib/coletor";
import { listarTrabalhos, trabalhadorVivo, ultimoCanarioOk, type Trabalho } from "@/lib/operacao";
import { dataHora } from "../estado";

import { DisparoColeta } from "./disparo";

// Lê arquivos do raspador e a porta de depuração a cada request.
export const dynamic = "force-dynamic";

const PASSOS_LOGIN = [
  "Feche TODO o Chrome — a porta de depuração só abre na primeira instância do perfil.",
  `Reabra com --remote-debugging-port=${portaCdp()} (e as flags anti-throttling do README do coletor).`,
  "Faça login no Canal Pro nesse Chrome. O Cloudflare é resolvido por você, como humano.",
  "Volte aqui e dispare o canário. Ele prova que a sessão está viva com uma requisição.",
];

function Marcador({ ok, texto, detalhe }: { ok: boolean | null; texto: string; detalhe?: string }) {
  const classe = ok === null ? "pill pill-muted" : ok ? "pill pill-ok" : "pill pill-bad";
  const rotulo = ok === null ? "não deu para conferir" : ok ? "sim" : "não";
  return (
    <li>
      <span className={classe}>{rotulo}</span> {texto}
      {detalhe ? <span className="campo-ajuda"> — {detalhe}</span> : null}
    </li>
  );
}

function Checklist({ chrome, saude }: { chrome: SaudeChrome | null; saude: SaudeColeta | null }) {
  return (
    <section className="secao">
      <h2>Pré-condições — conferidas, não instruídas</h2>
      <ul>
        <Marcador
          ok={chrome ? chrome.noAr : null}
          texto={`Chrome com depuração remota no ar (porta ${portaCdp()})`}
          detalhe={chrome && !chrome.noAr ? "nada respondeu na porta" : undefined}
        />
        <Marcador
          ok={chrome ? chrome.abaDoPainel : null}
          texto="aba do painel do Canal Pro aberta nesse Chrome"
          detalhe="só o host é conferido; a URL nunca chega a esta tela"
        />
        <Marcador
          ok={saude ? !saude.needsWarm : null}
          texto="sessão sem pedido de re-login (NEEDS_WARM.flag ausente)"
          detalhe={saude?.needsWarm ? "a última coleta foi bloqueada; logue de novo" : undefined}
        />
      </ul>
      <p className="campo-ajuda">
        O que isto NÃO prova: que a sessão está autenticada. Só uma requisição ao portal prova, e
        é o canário quem a faz — por isso ele vem antes da coleta completa.
      </p>
      <h3>Se algo acima estiver vermelho</h3>
      <ol>
        {PASSOS_LOGIN.map((p) => (
          <li key={p}>{p}</li>
        ))}
      </ol>
    </section>
  );
}

function Amarracao({ a }: { a: Amarracao | null }) {
  if (a === null) {
    return (
      <section className="secao">
        <h2>Amarração anúncio ↔ imóvel</h2>
        <p className="vazio">
          Sem <code>canalpro.csv</code> em <code>out/</code>: nenhuma coleta escreveu CSV ainda
          nesta máquina. O canário é a primeira coisa a fazer — e a sonda decide tudo: se o{" "}
          <code>codigoImovel</code> não for o id numérico do Newcore, nenhuma linha amarra e o
          fator de portal não entra.
        </p>
      </section>
    );
  }
  const fracao = a.linhas ? a.noFormato / a.linhas : 0;
  const veredito =
    a.linhas === 0
      ? "CSV vazio"
      : fracao === 0
        ? "NENHUMA linha está no formato {Id}{letra} — a amarração NÃO funciona com este formato"
        : fracao < 0.5
          ? "menos da metade amarra: confira o formato antes de raspar em volume"
          : "a maioria amarra";
  return (
    <section className="secao">
      <h2>Amarração anúncio ↔ imóvel</h2>
      <p>
        <span className={fracao === 0 ? "pill pill-bad" : fracao < 0.5 ? "pill pill-warn" : "pill pill-ok"}>
          {veredito}
        </span>
      </p>
      <table>
        <tbody>
          <tr>
            <td>linhas no CSV</td>
            <td className="id">{a.linhas}</td>
          </tr>
          <tr>
            <td>
              com <code>codigoImovel</code> no formato <code>{"{Id}{letra}"}</code> (o que amarra)
            </td>
            <td className="id">
              {a.noFormato} ({(fracao * 100).toFixed(0)}%)
            </td>
          </tr>
          <tr>
            <td>vazios</td>
            <td className="id">{a.vazios}</td>
          </tr>
          <tr>
            <td>fora do formato</td>
            <td className="id">{a.foraDoFormato}</td>
          </tr>
          <tr>
            <td>exemplos do campo</td>
            <td>
              {a.exemplos.length ? a.exemplos.map((e) => <code key={e}>{e} </code>) : "—"}
            </td>
          </tr>
        </tbody>
      </table>
      <p className="campo-ajuda">
        O formato <code>{"{Id}{letra}"}</code> é o que o leitor da rodada exige para casar com{" "}
        <code>realties.Id</code> — a letra é a rotação de marketing do portal, não parte da chave. Casar de fato com um imóvel ATIVO só a rodada confere — o
        console não lê o Newcore.
      </p>
      <p className="campo-ajuda">
        <strong>Medido sobre o arquivo acumulado.</strong> Canários e coletas completas escrevem
        no mesmo <code>out/canalpro.csv</code>, sem limpeza: as linhas se somam, e um formato
        antigo pode mascarar um novo. Para uma sonda limpa, apague o arquivo antes de disparar o
        canário (cuidado: isso apaga também uma coleta completa anterior).
      </p>
    </section>
  );
}

const TIPOS_DE_COLETA = new Set(["canario", "full"]);

export default async function Page() {
  const [rChrome, rSaude, rAmarracao, rCanario, rVivo, rTrabalhos] = await Promise.allSettled([
    saudeChrome(),
    saudeColeta(),
    amarracaoDoCsv(),
    ultimoCanarioOk(),
    trabalhadorVivo(),
    listarTrabalhos(50),
  ]);
  const chrome = rChrome.status === "fulfilled" ? rChrome.value : null;
  const saude = rSaude.status === "fulfilled" ? rSaude.value : null;
  const amarracao = rAmarracao.status === "fulfilled" ? rAmarracao.value : null;
  const canarioOk = rCanario.status === "fulfilled" ? rCanario.value : null;
  const vivo = rVivo.status === "fulfilled" ? rVivo.value : false;
  const trabalhos: Trabalho[] =
    rTrabalhos.status === "fulfilled" ? rTrabalhos.value.filter((t) => TIPOS_DE_COLETA.has(t.tipo)) : [];
  for (const [nome, r] of [
    ["saúde do Chrome", rChrome],
    ["saúde da coleta", rSaude],
    ["amarração do CSV", rAmarracao],
    ["último canário", rCanario],
    ["batimento do trabalhador", rVivo],
    ["trabalhos", rTrabalhos],
  ] as const) {
    if (r.status === "rejected") console.error(`[console] falha ao ler ${nome}:`, r.reason);
  }

  // O portão da coleta completa: Chrome no ar, a saúde atual "ok" (o status.json é
  // reescrito por cada coleta, então "ok" é da ÚLTIMA — bloqueio posterior a um canário
  // bom o derruba), um canário concluído com 0 pelo console, e um CSV com ao menos um
  // código no formato {Id}{letra}. Sem isso, horas de raspagem e um login manual podem produzir um CSV
  // que não amarra — o canário custa segundos e decide isso antes.
  const podeCanario = chrome?.noAr === true;
  let motivoSemFull: string | null = null;
  if (!podeCanario) motivoSemFull = "o Chrome de depuração não está no ar.";
  else if (saude?.estado !== "ok") motivoSemFull = `a última coleta está '${saude?.estado ?? "?"}', não 'ok'.`;
  else if (canarioOk === null) motivoSemFull = "nenhum canário disparado pelo console terminou com sucesso ainda.";
  else if (amarracao === null) motivoSemFull = "não há CSV em out/ para medir a amarração.";
  else if (amarracao.noFormato === 0)
    motivoSemFull = "o CSV em out/ não tem nenhum codigoImovel no formato {Id}{letra}: raspar em volume não conserta isso.";
  const podeFull = motivoSemFull === null;

  return (
    <>
      <h1>Coleta externa (Canal Pro)</h1>
      <p className="subtitulo">
        A raspagem roda FORA da rodada e escreve <code>out/canalpro.csv</code>; a rodada lê o
        arquivo. O login é seu — o console confere a pré-condição e dispara.
      </p>

      {!vivo ? (
        <div className="banner" role="alert">
          <strong>O trabalhador não está no ar.</strong> O console apenas enfileira; sem ele o
          pedido fica esperando. Suba com <code>uv run rodada-trabalhador</code> na raiz.
        </div>
      ) : null}

      <Checklist chrome={chrome} saude={saude} />
      <Amarracao a={amarracao} />
      <DisparoColeta podeCanario={podeCanario} podeFull={podeFull} motivoSemFull={motivoSemFull} />

      <section className="secao">
        <h2>Coletas recentes</h2>
        {trabalhos.length === 0 ? (
          <p className="vazio">Nenhuma coleta enfileirada ainda.</p>
        ) : (
          <div className="tabela-wrap">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>tipo</th>
                  <th>estado</th>
                  <th>pedido em</th>
                  <th>por</th>
                  <th>saída</th>
                </tr>
              </thead>
              <tbody>
                {trabalhos.map((t) => (
                  <tr key={t.id}>
                    <td className="id">
                      <Link href={`/trabalho/${t.id}`}>{t.id}</Link>
                    </td>
                    <td>{t.tipo}</td>
                    <td>{t.estado}</td>
                    <td>{dataHora(t.pedido_em)}</td>
                    <td>{t.pedido_por ?? "—"}</td>
                    <td className="id">{t.codigo_saida ?? "—"}</td>
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
