import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Console do Operador — Vitrine",
  description: "Operação e observabilidade da curadoria da vitrine de destaques.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>
        <header className="topo">
          <div className="marca">Vitrine · Console do Operador</div>
          <nav className="nav">
            <a href="/">Painel</a>
        <a href="/parametros">Parâmetros</a>
        <a href="/rodada/nova">Rodar</a>
          </nav>
        </header>
        <main className="conteudo">{children}</main>
      </body>
    </html>
  );
}
