import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";

import "./globals.css";
import { IconeColeta, IconeMarca, IconePainel, IconeParametros, IconeRodadas, IconeRodar } from "./icones";
import { Infra } from "./infra";
import { NavLink } from "./nav";

export const metadata: Metadata = {
  title: "Console do Operador — Vitrine",
  description: "Operação e observabilidade da curadoria da vitrine de destaques.",
};

// A casca lê a infraestrutura a cada request (a barra lateral é viva), então nada
// desta árvore é estático.
export const dynamic = "force-dynamic";

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>
        <div className="shell">
          <aside className="lateral">
            <Link href="/" className="marca">
              <span className="marca-logo">
                <IconeMarca />
              </span>
              <span>
                <span className="marca-nome">Vitrine</span>
                <br />
                <span className="marca-sub">Console do operador</span>
              </span>
            </Link>

            <nav className="nav" aria-label="Principal">
              <div className="lbl nav-grupo">Operar</div>
              <NavLink href="/" exato>
                <IconePainel />
                Painel
              </NavLink>
              <NavLink href="/rodada/nova">
                <IconeRodar />
                Rodar a decisão
              </NavLink>
              <NavLink href="/coleta">
                <IconeColeta />
                Coleta do portal
              </NavLink>
              <div className="lbl nav-grupo">Ver</div>
              <NavLink href="/#rodadas">
                <IconeRodadas />
                Rodadas
              </NavLink>
              <NavLink href="/parametros">
                <IconeParametros />
                Parâmetros
              </NavLink>
            </nav>

            <Infra />
          </aside>
          <main className="conteudo">{children}</main>
        </div>
      </body>
    </html>
  );
}
