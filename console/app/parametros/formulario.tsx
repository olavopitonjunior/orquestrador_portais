"use client";

import { useMemo, useState } from "react";

import { CAMPOS, GRUPOS, REGRAS, campoAtivo, type Campo, type Fonte, type Funcao, type Grupo } from "@/lib/contrato";
import { PARAMETROS } from "@/lib/parametros";
import { validar } from "@/lib/toml";

import { salvarParametros, type Resposta } from "./acoes";

// O que cada função e cada fonte significam para quem lê a seção. Rótulos de
// exibição — a taxonomia em si vem do contrato gerado (`GRUPOS`), não daqui.
const FUNCAO: Record<Funcao, string> = {
  excludente: "excludente · decide quem entra",
  classificatorio: "classificatório · decide a ordem",
  decisorio: "decisório · decide quantos e onde",
};
const FONTE: Record<Fonte, string> = {
  contrato: "contrato",
  banco_imovel: "banco · imóvel",
  banco_corretor: "banco · corretor",
  raspagem: "raspagem",
  registro: "registro",
};

/** O rótulo do campo: a última parte do caminho, legível. */
function rotulo(campo: Campo): string {
  return campo.caminho.split(".").pop()!.replace(/_/g, " ");
}

/** O trecho do meio do caminho, quando há três níveis. Exemplo HISTÓRICO (contrato
 *  anterior à D-034): nos oito pesos por nível era "super destaque · semelhanca
 *  perfil". Os 16 caminhos de hoje têm dois níveis, então devolve null — fica para o
 *  dia em que um caminho de três níveis voltar. */
function prefixo(campo: Campo): string | null {
  const partes = campo.caminho.split(".");
  return partes.length > 2 ? partes.slice(1, -1).join(" ").replace(/_/g, " ") : null;
}

function faixaEmTexto(campo: Campo): string {
  if (campo.escolhas) return campo.escolhas.join(" · ");
  const partes: string[] = [];
  if (campo.minimo !== null) {
    partes.push(campo.minimo_aberto ? `maior que ${campo.minimo}` : `de ${campo.minimo}`);
  }
  if (campo.maximo !== null) partes.push(`até ${campo.maximo}`);
  if (campo.tipo === "inteiro") partes.push("inteiro");
  return partes.join(", ");
}

function tituloDoPendente(n: number): string {
  return PARAMETROS.find((p) => p.numero === n)?.titulo ?? `parâmetro nº ${n}`;
}

function CabecalhoDoGrupo({ g, n }: { g: Grupo; n: number }) {
  return (
    <div className="grupo-cabecalho">
      <div className="grupo-titulo">
        <span className="grupo-ordem">{g.ordem}</span>
        <h2>{g.titulo}</h2>
        <span className="pill pill-acc">{FUNCAO[g.funcao]}</span>
        {g.fontes.map((f) => (
          <span key={f} className="pill pill-muted">
            {FONTE[f]}
          </span>
        ))}
        {n > 0 ? <span className="nota">{n} {n === 1 ? "campo" : "campos"}</span> : null}
      </div>
      <p className="grupo-explicacao">{g.explicacao}</p>
      {g.fixos_no_codigo.length ? (
        <ul className="grupo-fixos">
          {g.fixos_no_codigo.map((f) => (
            <li key={f}>
              <span className="pill pill-muted">fixo</span> {f}
            </li>
          ))}
        </ul>
      ) : null}
      {g.pendentes_sem_campo.length ? (
        <div className="chips">
          {g.pendentes_sem_campo.map((p) => (
            <span key={p} className="chip" title="parâmetro pendente, sem campo no TOML: permanece nulo">
              <b>#{p}</b> {tituloDoPendente(p)} · sem campo, nulo
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function Formulario({ inicial }: { inicial: Record<string, string> }) {
  const [valores, setValores] = useState<Record<string, string>>(inicial);
  const [por, setPor] = useState("");
  const [resposta, setResposta] = useState<Resposta | null>(null);
  const [enviando, setEnviando] = useState(false);

  const mapa = useMemo(() => new Map(Object.entries(valores)), [valores]);
  const problemas = useMemo(() => validar(mapa), [mapa]);
  // O PRIMEIRO problema de cada campo, não o último.
  //
  // `validar` lista os problemas do próprio campo antes dos de regra cruzada, e um
  // `Map` construído do array inteiro fica com o ÚLTIMO — então "40.5 precisa ser
  // inteiro" era engolido por "os quatro pesos somam 100.5". O dono via a soma errada
  // e não via a causa dela. O erro mais específico é o mais acionável.
  const porCaminho = useMemo(() => {
    const m = new Map<string, string>();
    for (const p of problemas) if (!m.has(p.caminho)) m.set(p.caminho, p.mensagem);
    return m;
  }, [problemas]);

  const ativos = CAMPOS.filter((c) => campoAtivo(c, mapa));

  // Só campos TOCADOS mostram erro: um formulário que nasce vermelho ensina a ignorar
  // o vermelho, e aí o erro que importa passa despercebido.
  const [tocados, setTocados] = useState<Record<string, boolean>>({});

  function somaDe(caminhos: string[]): number {
    return caminhos.reduce((a, c) => a + (Number(valores[c]) || 0), 0);
  }

  async function enviar() {
    setEnviando(true);
    setResposta(await salvarParametros(valores, por));
    setEnviando(false);
  }

  return (
    <>
      {GRUPOS.map((g) => {
        const doGrupo = ativos.filter((c) => c.grupo === g.id);
        const caminhos = new Set(doGrupo.map((c) => c.caminho));
        // Toda regra de soma cujos campos estão TODOS neste grupo (os dois níveis dos
        // pesos moram no mesmo grupo, então são duas linhas de soma, uma por nível).
        const somas = REGRAS.filter((r) => r.tipo === "soma_igual" && r.campos.every((c) => caminhos.has(c)));
        return (
          <section className="caixa grupo" key={g.id} id={g.id}>
            <CabecalhoDoGrupo g={g} n={doGrupo.length} />
            {somas.map((r) => (
              <p key={r.descricao} className={somaDe(r.campos) === r.valor ? "soma-ok" : "soma-erro"}>
                {r.descricao} Somam <strong>{somaDe(r.campos)}</strong> de {r.valor}.
              </p>
            ))}
            {doGrupo.length ? (
              <div className="campos">
                {doGrupo.map((campo) => {
                  const erro = tocados[campo.caminho] ? porCaminho.get(campo.caminho) : undefined;
                  const pre = prefixo(campo);
                  return (
                    <label className="campo" key={campo.caminho}>
                      <span className="campo-nome">
                        <span>
                          {pre ? <span className="campo-prefixo">{pre} · </span> : null}
                          {rotulo(campo)}
                          {campo.unidade ? <span className="campo-unidade"> · {campo.unidade}</span> : null}
                        </span>
                        {campo.pendencia ? (
                          <em className="pendencia">{campo.pendencia}</em>
                        ) : campo.adotado !== null ? (
                          <em className="adotado" title="valor adotado por decisão registrada (D-034); mude para declarar um PROVISÓRIO só nesta rodada">
                            adotado: {String(campo.adotado)}
                          </em>
                        ) : null}
                      </span>
                      {campo.escolhas ? (
                        <select
                          value={valores[campo.caminho] ?? ""}
                          onChange={(e) => setValores({ ...valores, [campo.caminho]: e.target.value })}
                          onBlur={() => setTocados({ ...tocados, [campo.caminho]: true })}
                        >
                          <option value="">— escolha —</option>
                          {campo.escolhas.map((o) => (
                            <option key={o} value={o}>
                              {o}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <input
                          inputMode="decimal"
                          // NUNCA um número, nem sequer de exemplo: é assim que um valor
                          // que ninguém escolheu entra numa planilha aprovada.
                          placeholder={campo.adotado !== null ? `adotado: ${String(campo.adotado)}` : "a definir"}
                          value={valores[campo.caminho] ?? ""}
                          onChange={(e) => setValores({ ...valores, [campo.caminho]: e.target.value })}
                          onBlur={() => setTocados({ ...tocados, [campo.caminho]: true })}
                        />
                      )}
                      <span className="campo-faixa">{faixaEmTexto(campo)}</span>
                      <span className="campo-ajuda">{campo.ajuda}</span>
                      {campo.se_aumentar ? (
                        <span className="campo-ajuda">
                          <b>Se aumentar:</b> {campo.se_aumentar}
                        </span>
                      ) : null}
                      {erro ? <span className="campo-erro">{erro}</span> : null}
                    </label>
                  );
                })}
              </div>
            ) : null}
          </section>
        );
      })}

      <section className="caixa grupo">
        <div className="grupo-cabecalho">
          <div className="grupo-titulo">
            <h2>Enviar</h2>
          </div>
        </div>
        <label className="campo">
          <span className="campo-nome">quem está declarando</span>
          <input value={por} onChange={(e) => setPor(e.target.value)} placeholder="seu nome" />
          <span className="campo-ajuda">
            Vai para o Registro junto dos valores. Não é autenticação: é o que você declara de si.
          </span>
        </label>
        <p>
          <button className="botao" disabled={problemas.length > 0 || enviando} onClick={() => void enviar()}>
            {enviando ? "guardando…" : "Guardar os parâmetros"}
          </button>
          {problemas.length > 0 ? (
            <span className="pendente-contagem">
              {problemas.length} {problemas.length === 1 ? "pendência" : "pendências"} antes de enviar
            </span>
          ) : null}
        </p>
        {resposta?.ok === true ? (
          <div className="banner banner-ok" role="status">
            Guardado (declaração nº {resposta.id}). Os valores seguem <strong>PROVISÓRIOS</strong>:
            valem para a rodada, são rotulados na planilha, e não viram parâmetro adotado.
          </div>
        ) : null}
        {resposta?.ok === false ? (
          <div className="banner" role="alert">
            {"erro" in resposta ? resposta.erro : "há campos inválidos — corrija acima."}
          </div>
        ) : null}
      </section>
    </>
  );
}
