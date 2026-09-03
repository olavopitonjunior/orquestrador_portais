"use client";

import { useMemo, useState } from "react";

import { CAMPOS, REGRAS, campoAtivo, secaoDe, type Campo } from "@/lib/contrato";
import { validar } from "@/lib/toml";

import { salvarParametros, type Resposta } from "./acoes";

const TITULO_DA_SECAO: Record<string, string> = {
  semelhanca: "Semelhança com o perfil de conversão",
  intensidades: "Intensidade das três penalidades",
  decaimento_janela: "Decaimento da penalidade por janela",
  "pesos.super_destaque": "Pesos do ranking — SUPER DESTAQUE",
  "pesos.destaque": "Pesos do ranking — DESTAQUE",
  externo: "Coleta externa (Canal Pro)",
  "externo.desempenho": "Como o desempenho de portal é composto",
  resultado_esperado: "Resultado esperado por nível (opcional)",
};

/** O rótulo do campo: a última parte do caminho, legível. */
function rotulo(campo: Campo): string {
  return campo.caminho.split(".").pop()!.replace(/_/g, " ");
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
  const secoes = [...new Set(ativos.map(secaoDe))];

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
      {secoes.map((secao) => {
        const daSecao = ativos.filter((c) => secaoDe(c) === secao);
        const regraDeSoma = REGRAS.find(
          (r) => r.tipo === "soma_igual" && r.campos.every((c) => secaoDe(c) === secao),
        );
        return (
          <section className="secao" key={secao}>
            <h2>{TITULO_DA_SECAO[secao] ?? secao}</h2>
            {regraDeSoma ? (
              <p className={somaDe(regraDeSoma.campos) === regraDeSoma.valor ? "soma-ok" : "soma-erro"}>
                Somam <strong>{somaDe(regraDeSoma.campos)}</strong> de {regraDeSoma.valor}.
              </p>
            ) : null}
            <div className="campos">
              {daSecao.map((campo) => {
                const erro = tocados[campo.caminho] ? porCaminho.get(campo.caminho) : undefined;
                return (
                  <label className="campo" key={campo.caminho}>
                    <span className="campo-nome">
                      {rotulo(campo)}
                      {campo.pendencia ? <em className="pendencia">{campo.pendencia}</em> : null}
                    </span>
                    {campo.escolhas ? (
                      <select
                        value={valores[campo.caminho] ?? ""}
                        onChange={(e) =>
                          setValores({ ...valores, [campo.caminho]: e.target.value })
                        }
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
                        // que ninguém escolheu entra numa planilha aprovada. E não
                        // repete a etiqueta da pendência, que já está no rótulo acima e
                        // aqui dentro truncava no meio da frase.
                        placeholder="a definir"
                        value={valores[campo.caminho] ?? ""}
                        onChange={(e) =>
                          setValores({ ...valores, [campo.caminho]: e.target.value })
                        }
                        onBlur={() => setTocados({ ...tocados, [campo.caminho]: true })}
                      />
                    )}
                    <span className="campo-faixa">{faixaEmTexto(campo)}</span>
                    <span className="campo-ajuda">{campo.ajuda}</span>
                    {erro ? <span className="campo-erro">{erro}</span> : null}
                  </label>
                );
              })}
            </div>
          </section>
        );
      })}

      <section className="secao">
        <h2>Enviar</h2>
        <label className="campo">
          <span className="campo-nome">quem está declarando</span>
          <input value={por} onChange={(e) => setPor(e.target.value)} placeholder="seu nome" />
          <span className="campo-ajuda">
            Vai para o Registro junto dos valores. Não é autenticação: é o que você declara de si.
          </span>
        </label>
        <p>
          <button
            className="botao"
            disabled={problemas.length > 0 || enviando}
            onClick={() => void enviar()}
          >
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
