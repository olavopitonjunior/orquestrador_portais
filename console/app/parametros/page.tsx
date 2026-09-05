import Link from "next/link";

import { CAMPOS } from "@/lib/contrato";
import { listarTrabalhos } from "@/lib/operacao";
import { previaEmVoo } from "@/lib/previa";

import { Formulario } from "./formulario";

// Lê o contrato a cada request; nada estático.
export const dynamic = "force-dynamic";

export default async function Page() {
  // NENHUM valor inicial. O que o dono não declarar usa o ADOTADO (D-034), que o
  // campo mostra ao lado; um default de formulário seria uma segunda cópia do adotado,
  // e as duas divergiriam.
  const inicial: Record<string, string> = {};
  const trabalhos = await listarTrabalhos(50).catch(() => []);
  const emVoo = previaEmVoo(trabalhos);
  const ultima =
    trabalhos.find((t) => t.tipo === "previa" && t.estado === "ok") ?? null;

  return (
    <>
      <h1>Como a lista de sexta é montada</h1>
      <p className="subtitulo">
        São {CAMPOS.filter((c) => c.obrigatorio).length} valores, todos com um{" "}
        <strong>adotado</strong> por decisão registrada. Declare só o que quiser
        mudar: o que você declarar diferente vale para a próxima rodada, sai
        rotulado na planilha, e não vira adotado — adotar exige decisão
        registrada e entrada no CHANGELOG.
      </p>
      {emVoo !== null ? (
        <div className="banner banner-info" role="status">
          Há uma prévia sendo calculada agora:{" "}
          <Link href={`/trabalho/${emVoo}`}>acompanhe a nº {emVoo}</Link>.
        </div>
      ) : ultima ? (
        <div className="banner banner-info" role="note">
          Última prévia:{" "}
          <Link href={`/trabalho/${ultima.id}`}>nº {ultima.id}</Link>, pedida em{" "}
          {new Date(ultima.pedido_em).toLocaleString("pt-BR")}
          {ultima.pedido_por ? ` por ${ultima.pedido_por}` : ""}. Mudou algum
          valor desde então? Peça outra no fim da página.
        </div>
      ) : null}
      <Formulario inicial={inicial} />
    </>
  );
}
