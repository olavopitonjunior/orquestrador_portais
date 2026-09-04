import type { Estado } from "@/lib/registro";

// Pílula de estado da rodada (Spec §7.2). Cor = leitura de risco à distância:
// completa verde, degradada âmbar, abortada vermelha.
const CLASSE: Record<Estado, string> = {
  completa: "pill pill-ok",
  degradada: "pill pill-warn",
  abortada: "pill pill-bad",
};

export function PilulaEstado({ estado }: { estado: Estado | null }) {
  if (!estado) return <span className="pill pill-muted">em andamento</span>;
  return <span className={CLASSE[estado]}>{estado}</span>;
}

const FMT = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

export function dataHora(iso: string | null): string {
  return iso ? FMT.format(new Date(iso)) : "—";
}

/** Duração entre início e fim, curta: "43 s" até um minuto e meio, "2 min" depois;
 *  "—" enquanto não terminou. */
export function duracao(inicio: string, fim: string | null): string {
  if (!fim) return "—";
  const s = Math.round((new Date(fim).getTime() - new Date(inicio).getTime()) / 1000);
  return s < 90 ? `${s} s` : `${Math.round(s / 60)} min`;
}
