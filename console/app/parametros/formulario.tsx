"use client";

import Link from "next/link";
import { useMemo, useState, type ReactNode } from "react";

import {
  CAMPOS,
  GRUPOS,
  POR_CAMINHO,
  REGRAS,
  campoAtivo,
  type Campo,
  type Fonte,
  type Funcao,
  type Grupo,
} from "@/lib/contrato";
import { PARAMETROS } from "@/lib/parametros";
import { ESPERA_DA_PREVIA } from "@/lib/previa";
import { BLOCOS } from "@/lib/blocos";
import { validar } from "@/lib/toml";

import { salvarEIrRodar, salvarParametros, verPrevia, type Resposta } from "./acoes";

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

/** O nome que o dono lê: vem do contrato (`rotulo`). O caminho do TOML é reserva. */
function rotulo(campo: Campo): string {
  return campo.rotulo || campo.caminho.split(".").pop()!.replace(/_/g, " ");
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

export function Formulario({ inicial, funil }: { inicial: Record<string, string>; funil?: ReactNode }) {
  const [valores, setValores] = useState<Record<string, string>>(inicial);
  const [por, setPor] = useState("");
  const [resposta, setResposta] = useState<Resposta | null>(null);
  const [ocupado, setOcupado] = useState<"" | "guardar" | "previa" | "rodar">("");

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
  const declarados = ativos.filter((c) => (valores[c.caminho] ?? "").trim() !== "").length;

  // Só campos TOCADOS mostram erro: um formulário que nasce vermelho ensina a ignorar
  // o vermelho, e aí o erro que importa passa despercebido.
  const [tocados, setTocados] = useState<Record<string, boolean>>({});

  // A soma EFETIVA: o declarado ou, vazio, o adotado — como a rodada resolve (D-034).
  function somaDe(caminhos: string[]): number {
    return caminhos.reduce((a, c) => {
      const bruto = valores[c];
      const efetivo = bruto === undefined || bruto.trim() === "" ? POR_CAMINHO.get(c)?.adotado : bruto;
      return a + (Number(efetivo) || 0);
    }, 0);
  }

  async function agir(qual: "guardar" | "previa" | "rodar") {
    setOcupado(qual);
    // Com sucesso, `verPrevia` e `salvarEIrRodar` REDIRECIONAM e a linha seguinte não
    // volta; só a recusa volta para a tela.
    const acao = qual === "guardar" ? salvarParametros : qual === "previa" ? verPrevia : salvarEIrRodar;
    setResposta(await acao(valores, por));
    setOcupado("");
  }

  const bloqueado = problemas.length > 0 || ocupado !== "";

  // Função de renderização, NÃO um componente aninhado: um componente definido aqui
  // dentro é uma função nova a cada render, e o React remontaria a subárvore inteira
  // a cada tecla — o campo perderia o foco enquanto o dono digita.
  function grupos(ids: string[]) {
    return (
      <>
        {GRUPOS.filter((g) => ids.includes(g.id)).map((g) => {
          const doGrupo = ativos.filter((c) => c.grupo === g.id);
          const caminhos = new Set(doGrupo.map((c) => c.caminho));
          // Toda regra de soma cujos campos estão TODOS neste grupo.
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
                            <em className="adotado" title="valor adotado por decisão registrada (D-034); mude para declarar um valor só para a próxima rodada">
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
                            <option value="">— o adotado —</option>
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
      </>
    );
  }

  return (
    <>
      <nav className="abas" aria-label="os três blocos">
        {BLOCOS.map((b) => (
          <a key={b.id} className="aba" href={`#${b.id}`}>
            {b.titulo}
          </a>
        ))}
      </nav>

      {BLOCOS.map((b, i) => (
        <section key={b.id} id={b.id} className="bloco">
          <div className="bloco-cabecalho">
            <span className="bloco-numero">{i + 1}</span>
            <h2 className="bloco-titulo">{b.titulo}</h2>
          </div>
          <p className="bloco-tese">{b.tese}</p>
          {i === 0 ? funil : null}
          {grupos(b.grupos)}
        </section>
      ))}

      <div className="rodape-acoes" role="region" aria-label="guardar, ver a prévia ou ir rodar">
        <div className="rodape-linha">
          <label className="rodape-por">
            <span className="campo-nome">quem está declarando</span>
            <input value={por} onChange={(e) => setPor(e.target.value)} placeholder="seu nome" />
          </label>
          <span className="rodape-estado">
            {problemas.length > 0
              ? `${problemas.length} ${problemas.length === 1 ? "pendência" : "pendências"} antes de enviar`
              : declarados === 0
                ? "nada declarado: vale tudo adotado"
                : `${declarados} ${declarados === 1 ? "valor declarado" : "valores declarados"} diferente do adotado`}
          </span>
        </div>
        <div className="rodape-linha">
          <button className="botao botao-secundario" disabled={bloqueado} onClick={() => void agir("guardar")}>
            {ocupado === "guardar" ? "guardando…" : "Guardar"}
          </button>
          <button className="botao botao-secundario" disabled={bloqueado} onClick={() => void agir("previa")} title={ESPERA_DA_PREVIA}>
            {ocupado === "previa" ? "pedindo a prévia…" : "Ver a prévia"}
          </button>
          <button className="botao" disabled={bloqueado} onClick={() => void agir("rodar")}>
            {ocupado === "rodar" ? "guardando e indo…" : "Guardar e ir rodar"}
          </button>
        </div>
        <p className="campo-ajuda">
          <b>Guardar</b> registra a declaração. <b>Ver a prévia</b> guarda e conta quantos imóveis sobram
          para as posições, regra a regra, sem rodar a semana: lê o estoque inteiro do Newcore e leva um
          ou dois minutos. <b>Guardar e ir rodar</b> guarda e leva à tela de disparo.
        </p>
        {resposta?.ok === true ? (
          <div className="banner banner-ok" role="status">
            Guardado (declaração nº {resposta.id}). O que difere do adotado vale para a próxima rodada e sai
            na planilha como <strong>PROVISÓRIO (declarado)</strong>; nada vira adotado por aqui.{" "}
            <Link href="/rodada/nova">Ir rodar</Link>.
          </div>
        ) : null}
        {resposta?.ok === false ? (
          <div className="banner" role="alert">
            {"erro" in resposta ? resposta.erro : "há campos inválidos — corrija acima."}
            {"emVoo" in resposta && resposta.emVoo ? (
              <>
                {" "}
                <Link href={`/trabalho/${resposta.emVoo}`}>Abrir a prévia nº {resposta.emVoo}</Link>.
              </>
            ) : null}
          </div>
        ) : null}
      </div>
    </>
  );
}
