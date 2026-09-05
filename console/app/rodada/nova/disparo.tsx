"use client";

import { useState } from "react";

import { dispararSexta, type ModoDisparo, type RespostaDisparo } from "./acoes";

export function Disparo({
  declaracaoVista,
  coletaOk,
  chromeNoAr,
}: {
  declaracaoVista: number | null;
  coletaOk: boolean; // há um `out/` com status ok — a rodada pode ler a nota do portal de lá
  chromeNoAr: boolean; // a rodada completa começa raspando: precisa do Chrome logado
}) {
  const [por, setPor] = useState("");
  const [modo, setModo] = useState<ModoDisparo>("seco");
  const [usarColeta, setUsarColeta] = useState(coletaOk);
  const [passos, setPassos] = useState("1,10,100");
  const [enviando, setEnviando] = useState(false);
  const [resposta, setResposta] = useState<RespostaDisparo | null>(null);

  async function disparar() {
    setEnviando(true);
    // Em sucesso a ação REDIRECIONA e esta linha não retorna — por isso o estado de
    // "enviando" só é desfeito no caminho de erro.
    const r = await dispararSexta(por, modo, declaracaoVista, usarColeta, passos);
    setResposta(r);
    setEnviando(false);
  }

  const rotulo =
    modo === "seco" ? "Rodar em modo seco" : modo === "real" ? "Rodar e gravar" : "Rodada completa";
  const bloqueado = enviando || (modo === "completa" && !chromeNoAr);

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
          <select value={modo} onChange={(e) => setModo(e.target.value as ModoDisparo)}>
            <option value="seco">seco — não grava nem escreve nada</option>
            <option value="real">real — grava no Registro e escreve a planilha</option>
            <option value="completa">
              rodada completa — raspa (canário) e, se der certo, decide sobre o raspado
            </option>
          </select>
          <span className="campo-ajuda">
            {modo === "completa"
              ? "Um clique, dois trabalhos encadeados: o canário raspa; terminando com 0, o " +
                "trabalhador enfileira a decisão apontando para o out/, recortada pela raspagem. " +
                "É uma rodada AMOSTRAL: declarada, nunca COMPLETA, nunca aprovável — existe para " +
                "ver a corrente inteira funcionar com a nota do portal entrando de verdade. " +
                "GRAVA no Registro e escreve a planilha em saida/sexta, como o modo real."
              : "O modo seco percorre a rodada inteira contra o banco de verdade e descarta o " +
                "resultado. É o jeito de ver os números antes de gravar uma decisão."}
          </span>
        </label>
        {modo === "completa" ? (
          <label className="campo">
            <span className="campo-nome">passos do canário</span>
            <input value={passos} onChange={(e) => setPassos(e.target.value)} />
            <span className="campo-ajuda">
              Quantos anúncios raspar, em degraus (CANARY_STEPS). O maior degrau é o tamanho da
              amostra. Algumas centenas dão uma rodada legível; 55 mil é a coleta completa, que
              leva horas e tem tela própria.
            </span>
          </label>
        ) : (
          <label className="campo">
            <span className="campo-nome">a raspagem do portal</span>
            <span>
              <input
                type="checkbox"
                checked={usarColeta}
                disabled={!coletaOk}
                onChange={(e) => setUsarColeta(e.target.checked)}
              />{" "}
              usar a coleta que está em <code>coletor-externo/out</code>
            </span>
            <span className="campo-ajuda">
              {coletaOk
                ? "Há uma coleta 'ok' no disco. Marcado, a rodada lê o CSV e a nota do anúncio " +
                  "ordena a lista (se a raspagem cobrir o mínimo e for recente). Desmarcado, a " +
                  "ordem cai para o desempate de banco e a rodada sai DEGRADADA, com a limitação " +
                  "declarada."
                : "Não há coleta 'ok' no disco: sem raspagem, a ordem cai para o desempate de banco " +
                  "e a rodada sai DEGRADADA, com a limitação declarada. Rode um canário em Coleta."}
            </span>
          </label>
        )}
      </div>
      {modo === "completa" && !chromeNoAr ? (
        <div className="banner" role="alert">
          A rodada completa começa raspando, e o Chrome de depuração não está no ar. Logue no
          Canal Pro primeiro — veja a tela <a href="/coleta">Coleta</a>.
        </div>
      ) : null}
      <p>
        <button className="botao" disabled={bloqueado} onClick={() => void disparar()}>
          {enviando ? "enfileirando…" : rotulo}
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
