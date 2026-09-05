import Link from "next/link";

import { formatar, linkDoGrupo, type Previa } from "@/lib/previa";

/** O funil da última prévia, dentro do bloco "Quem entra": cada regra com quantos
 *  cortou, e o número que sobra. Diz de onde veio (a prévia nº X, de tal dia) — e
 *  que só vale para os valores daquela prévia. Componente de servidor; recebe a
 *  prévia já lida e validada. */
export function FunilDaUltimaPrevia({
  previa,
  trabalhoId,
  pedidoEm,
  declaracaoMudou,
}: {
  previa: Previa | null;
  trabalhoId: number | null;
  pedidoEm: string | null;
  declaracaoMudou: boolean;
}) {
  if (previa === null || trabalhoId === null) {
    return (
      <div className="funil-mini funil-mini-vazio">
        <p>
          <b>Ainda não há prévia.</b> Peça uma no rodapé para ver, regra a regra, quantos imóveis
          sobram para as 6.970 posições com os valores desta tela.
        </p>
      </div>
    );
  }
  const base = previa.candidatos;
  const quando = pedidoEm ? new Date(pedidoEm).toLocaleString("pt-BR") : "";
  return (
    <div className="funil-mini">
      <p className="funil-mini-frase">
        Sobram <b>{formatar(previa.elegiveis)}</b> de {formatar(base)} candidatos para as{" "}
        {formatar(previa.posicoes.total)} posições
        {previa.projecao.vazias_total > 0
          ? ` — ${formatar(previa.projecao.vazias_total)} ficariam vazias antes da cedência`
          : " — todas preenchidas"}
        . <span className="discreto">Pela prévia nº {trabalhoId}{quando ? `, de ${quando}` : ""}.</span>{" "}
        <Link href={`/trabalho/${trabalhoId}`}>Ver inteira</Link>.
      </p>
      {declaracaoMudou ? (
        <p className="campo-ajuda">
          <b>Desatualizada:</b> há uma declaração mais nova que esta prévia. Os números acima valem
          para os valores de então — peça outra prévia para os de agora.
        </p>
      ) : null}
      <ul className="funil-mini-linhas">
        {previa.funil.map((ln) => (
          <li key={ln.regra} className={ln.cortou > 0 ? "funil-mini-corta" : undefined}>
            <span className="funil-mini-rotulo">
              <Link href={linkDoGrupo(ln.grupo)}>{ln.rotulo}</Link>
            </span>
            <span className="funil-mini-cortou">{ln.cortou > 0 ? `−${formatar(ln.cortou)}` : ""}</span>
            <span className="funil-mini-sobram">{formatar(ln.sobram)}</span>
            <span className="funil-mini-barra-caixa" aria-hidden="true">
              <span
                className="funil-barra"
                style={{ width: `${base > 0 ? Math.max(1, Math.round((100 * ln.sobram) / base)) : 0}%` }}
              />
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
