import Link from "next/link";

import { BLOCOS } from "@/lib/blocos";
import type { FraseDoBloco } from "@/lib/declaracao";
import { linkDoGrupo } from "@/lib/previa";

/** Os parâmetros guardados em PROSA, nos três blocos da jornada, cada número ligado
 *  ao parâmetro que o governa e marcado como declarado (negrito) ou adotado. */
export function ProsaDaRodada({ frases, declarados }: { frases: FraseDoBloco[]; declarados: number }) {
  const porBloco = new Map(frases.map((f) => [f.bloco, f]));
  return (
    <section className="secao">
      <div className="secao-cabecalho">
        <h2>O que esta rodada vai fazer</h2>
        <span className="nota">
          {declarados === 0
            ? "tudo com os valores adotados (D-034)"
            : `${declarados} ${declarados === 1 ? "valor declarado" : "valores declarados"} diferente do adotado, em negrito`}
        </span>
      </div>
      <div className="prosa-blocos">
        {BLOCOS.map((b, i) => {
          const f = porBloco.get(b.id as FraseDoBloco["bloco"]);
          return (
            <div className="prosa-bloco" key={b.id}>
              <div className="bloco-cabecalho">
                <span className="bloco-numero">{i + 1}</span>
                <h3 className="prosa-titulo">
                  <Link href={`/parametros#${b.id}`}>{b.titulo}</Link>
                </h3>
              </div>
              <p className="prosa-texto">
                {f?.trechos.map((t, j) =>
                  "t" in t ? (
                    <span key={j}>{t.t}</span>
                  ) : (
                    <Link
                      key={j}
                      href={linkDoGrupo(t.grupo)}
                      className={t.procedencia === "declarado" ? "prosa-valor prosa-declarado" : "prosa-valor"}
                      title={`${t.caminho} · ${t.procedencia === "declarado" ? "declarado para esta rodada" : "adotado (D-034)"}`}
                    >
                      {t.v}
                    </Link>
                  ),
                )}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
