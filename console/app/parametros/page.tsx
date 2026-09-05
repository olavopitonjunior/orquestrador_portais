import Link from "next/link";

import { CAMPOS } from "@/lib/contrato";
import { listarTrabalhos, resumosDoTrabalho, ultimosParametros } from "@/lib/operacao";
import { lerPrevia, previaEmVoo } from "@/lib/previa";

import { Formulario } from "./formulario";
import { FunilDaUltimaPrevia } from "./funil";

// Lê o contrato a cada request; nada estático.
export const dynamic = "force-dynamic";

export default async function Page() {
  // NENHUM valor inicial. O que o dono não declarar usa o ADOTADO (D-034), que o
  // campo mostra ao lado; um default de formulário seria uma segunda cópia do adotado,
  // e as duas divergiriam.
  const inicial: Record<string, string> = {};
  const [trabalhos, declaracao] = await Promise.all([
    listarTrabalhos(50).catch(() => []),
    ultimosParametros().catch(() => null),
  ]);
  const emVoo = previaEmVoo(trabalhos);
  const ultima = trabalhos.find((t) => t.tipo === "previa" && t.estado === "ok") ?? null;
  const previa = ultima ? lerPrevia((await resumosDoTrabalho(ultima.id).catch(() => new Map())).get("previa")) : null;
  // "Desatualizada" = há declaração mais nova que a prévia. A prévia guarda a sua
  // própria declaração no instante do pedido, então basta comparar os instantes.
  const declaracaoMudou =
    ultima !== null && declaracao !== null && new Date(declaracao.criado_em) > new Date(ultima.pedido_em);

  return (
    <>
      <h1>Como a lista de sexta é montada</h1>
      <p className="subtitulo">
        São {CAMPOS.filter((c) => c.obrigatorio).length} valores, todos com um{" "}
        <strong>adotado</strong> por decisão registrada. Declare só o que quiser mudar: o que
        você declarar diferente vale para a próxima rodada, sai rotulado na planilha, e não
        vira adotado — adotar exige decisão registrada e entrada no CHANGELOG. Três blocos,
        na ordem em que a rodada decide: <b>quem entra</b>, <b>em que ordem</b>, <b>quantos</b>.
      </p>
      {emVoo !== null ? (
        <div className="banner banner-info" role="status">
          Há uma prévia sendo calculada agora: <Link href={`/trabalho/${emVoo}`}>acompanhe a nº {emVoo}</Link>.
        </div>
      ) : null}
      <Formulario
        inicial={inicial}
        funil={
          <FunilDaUltimaPrevia
            previa={previa}
            trabalhoId={ultima?.id ?? null}
            pedidoEm={ultima?.pedido_em ?? null}
            declaracaoMudou={declaracaoMudou}
          />
        }
      />
    </>
  );
}
