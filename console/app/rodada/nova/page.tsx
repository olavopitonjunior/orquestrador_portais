import Link from "next/link";

import { saudeChrome } from "@/lib/chrome";
import { saudeColeta } from "@/lib/coletor";
import { trabalhadorVivo, ultimosParametros } from "@/lib/operacao";

import { Disparo } from "./disparo";

export const dynamic = "force-dynamic";

export default async function Page() {
  const [declaracao, vivo, saude, chrome] = await Promise.all([
    ultimosParametros().catch(() => null),
    trabalhadorVivo().catch(() => false),
    saudeColeta().catch(() => null),
    saudeChrome().catch(() => null),
  ]);

  return (
    <>
      <h1>Rodar a sexta</h1>
      <p className="subtitulo">
        A rodada lê o Newcore, cruza com os perfis, ordena, aloca nas cotas e escreve a
        planilha. Leva minutos.
      </p>

      {declaracao === null ? (
        <div className="banner" role="alert">
          Não há parâmetros declarados. <Link href="/parametros">Preencha o formulário</Link> antes
          — a rodada <strong>recusa rodar</strong> sem eles, e isso é proteção: peso inventado numa
          planilha aprovada é invisível.
        </div>
      ) : (
        <div className="banner banner-info">
          Vai rodar com a declaração <strong>nº {declaracao.id}</strong>
          {declaracao.por ? ` (por ${declaracao.por})` : ""}, de{" "}
          {new Date(declaracao.criado_em).toLocaleString("pt-BR")}. Os valores são{" "}
          <strong>PROVISÓRIOS</strong> e viajam rotulados para a planilha e para o Registro.
        </div>
      )}

      {!vivo ? (
        <div className="banner" role="alert">
          <strong>O trabalhador não está no ar.</strong> O console apenas enfileira; quem executa é
          um processo separado. Sem ele, o pedido fica esperando e nada acontece. Suba com{" "}
          <code>uv run rodada-trabalhador</code> na raiz do repositório.
        </div>
      ) : null}

      <Disparo
        podeDisparar={declaracao !== null}
        declaracaoVista={declaracao?.id ?? null}
        coletaOk={saude?.estado === "ok"}
        chromeNoAr={chrome?.noAr === true}
      />
    </>
  );
}
