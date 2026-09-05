import Link from "next/link";

import { saudeChrome } from "@/lib/chrome";
import { saudeColeta } from "@/lib/coletor";
import { cotasDoRegistro } from "@/lib/cotas";
import { efetivosDe, proseDaDeclaracao, valoresDoToml } from "@/lib/declaracao";
import { trabalhadorVivo, ultimosParametros } from "@/lib/operacao";

import { Disparo } from "./disparo";
import { ProsaDaRodada } from "./prosa";

export const dynamic = "force-dynamic";

export default async function Page() {
  const [declaracao, vivo, saude, chrome, cotas] = await Promise.all([
    ultimosParametros().catch(() => null),
    trabalhadorVivo().catch(() => false),
    saudeColeta().catch(() => null),
    saudeChrome().catch(() => null),
    cotasDoRegistro().catch(() => null),
  ]);
  // Sem declaração, a rodada usa os adotados (D-034): a prosa diz isso, e o disparo
  // cria uma declaração vazia na hora — a procedência precisa ficar registrada.
  const efetivos = efetivosDe(declaracao ? valoresDoToml(declaracao.toml) : new Map());
  const declarados = efetivos.filter((e) => e.procedencia === "declarado").length;
  const frases = proseDaDeclaracao(efetivos, cotas);

  return (
    <>
      <h1>Rodar a decisão de sexta</h1>
      <p className="subtitulo">
        Lê o Newcore, aplica quem entra, ordena pelo portal, preenche as cotas e escreve a planilha.
        Leva minutos, e a raspagem do portal — quando entra — é a única tentativa da semana.
      </p>

      {declaracao === null ? (
        <div className="banner banner-info" role="note">
          Não há declaração guardada: a rodada vai usar <strong>os valores adotados</strong> (D-034).
          Para mudar algum, <Link href="/parametros">declare em Parâmetros</Link> antes.
        </div>
      ) : (
        <div className="banner banner-info">
          Vai rodar com a declaração <strong>nº {declaracao.id}</strong>
          {declaracao.por ? ` (por ${declaracao.por})` : ""}, de{" "}
          {new Date(declaracao.criado_em).toLocaleString("pt-BR")}.{" "}
          {declarados === 0
            ? "Ela não muda nada do adotado."
            : "O que ela muda do adotado sai na planilha como PROVISÓRIO (declarado)."}{" "}
          <Link href="/parametros">Mudar</Link>.
        </div>
      )}

      <ProsaDaRodada frases={frases} declarados={declarados} />

      {!vivo ? (
        <div className="banner" role="alert">
          <strong>O trabalhador não está no ar.</strong> O console apenas enfileira; quem executa é
          um processo separado. Sem ele, o pedido fica esperando e nada acontece. Suba com{" "}
          <code>uv run rodada-trabalhador</code> na raiz do repositório.
        </div>
      ) : null}

      <Disparo
        declaracaoVista={declaracao?.id ?? null}
        coletaOk={saude?.estado === "ok"}
        chromeNoAr={chrome?.noAr === true}
      />
    </>
  );
}
