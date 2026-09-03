"use client";

import { useState } from "react";

import { dispararSexta, type RespostaDisparo } from "./acoes";

export function Disparo({ podeDisparar }: { podeDisparar: boolean }) {
  const [por, setPor] = useState("");
  const [dryRun, setDryRun] = useState(true);
  const [enviando, setEnviando] = useState(false);
  const [resposta, setResposta] = useState<RespostaDisparo | null>(null);

  async function disparar() {
    setEnviando(true);
    // Em sucesso a ação REDIRECIONA e esta linha não retorna — por isso o estado de
    // "enviando" só é desfeito no caminho de erro.
    const r = await dispararSexta(por, dryRun);
    setResposta(r);
    setEnviando(false);
  }

  return (
    <section className="secao">
      <h2>Disparar</h2>
      <div className="campos">
        <label className="campo">
          <span className="campo-nome">quem está disparando</span>
          <input value={por} onChange={(e) => setPor(e.target.value)} placeholder="seu nome" />
          <span className="campo-ajuda">
            Fica no registro de operação. Não é autenticação: é o que você declara de si.
          </span>
        </label>
        <label className="campo">
          <span className="campo-nome">modo</span>
          <select value={dryRun ? "seco" : "real"} onChange={(e) => setDryRun(e.target.value === "seco")}>
            <option value="seco">seco — não grava nem escreve nada</option>
            <option value="real">real — grava no Registro e escreve a planilha</option>
          </select>
          <span className="campo-ajuda">
            O modo seco percorre a rodada inteira contra o banco de verdade e descarta o
            resultado. É o jeito de ver os números antes de gravar uma decisão.
          </span>
        </label>
      </div>
      <p>
        <button className="botao" disabled={!podeDisparar || enviando} onClick={() => void disparar()}>
          {enviando ? "enfileirando…" : dryRun ? "Rodar em modo seco" : "Rodar e gravar"}
        </button>
      </p>
      {resposta && !resposta.ok ? (
        <div className="banner" role="alert">
          {resposta.erro}
        </div>
      ) : null}
    </section>
  );
}
