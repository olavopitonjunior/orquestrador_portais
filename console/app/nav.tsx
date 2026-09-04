"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

// O único pedaço de cliente da casca: marcar o item ativo pela rota. Tudo o mais na
// barra lateral é servidor (a infraestrutura lê banco e Chrome).
export function NavLink({
  href,
  children,
  exato = false,
}: {
  href: string;
  children: ReactNode;
  exato?: boolean;
}) {
  const atual = usePathname();
  const ativo = exato ? atual === href : atual === href || atual.startsWith(`${href}/`);
  return (
    <Link href={href} className="navi" aria-current={ativo ? "page" : undefined}>
      {children}
    </Link>
  );
}
