import { CAMPOS } from "@/lib/contrato";

import { Formulario } from "./formulario";

// Lê o contrato a cada request; nada estático.
export const dynamic = "force-dynamic";

export default function Page() {
  // NENHUM valor inicial. Catorze dos quinze parâmetros da decisão são nulos, e o
  // CLAUDE.md proíbe preenchê-los com valor inventado — um default de formulário é
  // exatamente como um número que ninguém escolheu entra numa planilha aprovada.
  const inicial: Record<string, string> = {};

  return (
    <>
      <h1>Parâmetros da rodada</h1>
      <p className="subtitulo">
        São {CAMPOS.filter((c) => c.obrigatorio).length} valores obrigatórios, e nenhum tem
        default. A rodada <strong>recusa rodar</strong> sem eles — o que é proteção, não
        obstáculo: peso inventado numa planilha aprovada é invisível.
      </p>
      <div className="banner banner-info" role="note">
        Tudo que você declarar aqui é <strong>PROVISÓRIO</strong>. Vale para a rodada, viaja
        rotulado para a planilha e para o Registro, e <strong>não</strong> vira parâmetro
        adotado — adotar exige decisão registrada e entrada no CHANGELOG.
      </div>
      <Formulario inicial={inicial} />
    </>
  );
}
