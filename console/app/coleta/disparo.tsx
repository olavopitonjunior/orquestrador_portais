"use client";

import { useState } from "react";

import { dispararColeta, type RespostaColeta } from "./acoes";

export function DisparoColeta({
  podeCanario,
  podeFull,
  motivoSemFull,
}: {
  podeCanario: boolean;
  podeFull: boolean;
  motivoSemFull: string | null;
}) {
  const [por, setPor] = useState("");
  // Volume já validado contra o portal (canário de 31/08 foi até 100). Não é
  // parâmetro de decisão — é configuração do raspador — e por isso pode ter default.
  const [passos, setPassos] = useState("1,10,100");
  const [enviando, setEnviando] = useState<"canario" | "full" | null>(null);
  const [resposta, setResposta] = useState<RespostaColeta | null>(null);

  async function disparar(tipo: "canario" | "full") {
    setEnviando(tipo);
    // Em sucesso a ação REDIRECIONA e esta linha não retorna.
    const r = await dispararColeta(tipo, passos, por);
    setResposta(r);
    setEnviando(null);
  }

  return (
    <section className="secao">
      <h2>Disparar</h2>
      <div className="campos">
        <label className="campo">
          <span className="campo-nome">quem está disparando</span>
          <input value={por} onChange={(e) => setPor(e.target.value)} placeholder="seu nome" />
          <span className="campo-ajuda">Fica no registro de operação. Não é autenticação.</span>
        </label>
        <label className="campo">
          <span className="campo-nome">passos do canário</span>
          <input value={passos} onChange={(e) => setPassos(e.target.value)} />
          <span className="campo-ajuda">
            Quantos anúncios o canário traz, em degraus (CANARY_STEPS). O maior degrau é o teto.
            Para a sonda da amarração, <code>10</code> basta; para uma rodada amostral, algumas
            centenas.
          </span>
        </label>
      </div>
      <p>
        <button
          className="botao"
          disabled={!podeCanario || enviando !== null}
          onClick={() => void disparar("canario")}
        >
          {enviando === "canario" ? "enfileirando…" : "Canário"}
        </button>{" "}
        <button
          className="botao"
          disabled={!podeFull || enviando !== null}
          title={motivoSemFull ?? undefined}
          onClick={() => void disparar("full")}
        >
          {enviando === "full" ? "enfileirando…" : "Coleta completa (~55 mil anúncios, horas)"}
        </button>
      </p>
      {!podeFull && motivoSemFull ? <p className="campo-ajuda">{motivoSemFull}</p> : null}
      {resposta && !resposta.ok ? (
        <div className="banner" role="alert">
          {resposta.erro}
        </div>
      ) : null}
    </section>
  );
}
