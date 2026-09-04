// Ícones em SVG de traço, 24 de grade, um estilo só. Sem emoji: escala e recolore.
type P = { className?: string };

export function IconePainel({ className = "icone" }: P) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M3 10h18M8 4v4" />
    </svg>
  );
}
export function IconeRodar({ className = "icone" }: P) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </svg>
  );
}
export function IconeColeta({ className = "icone" }: P) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path d="M4 4h16v6H4zM4 14h16v6H4z" />
      <path d="M8 7h.01M8 17h.01" />
    </svg>
  );
}
export function IconeRodadas({ className = "icone" }: P) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path d="M4 19V5M4 19h16M8 15v-4M12 15V8M16 15v-6" />
    </svg>
  );
}
export function IconeParametros({ className = "icone" }: P) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path d="M4 7h16M4 12h16M4 17h16" />
      <circle cx="9" cy="7" r="2" fill="var(--surface)" />
      <circle cx="15" cy="12" r="2" fill="var(--surface)" />
      <circle cx="11" cy="17" r="2" fill="var(--surface)" />
    </svg>
  );
}
export function IconePlay({ className = "icone" }: P) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path d="M6 4l14 8-14 8z" />
    </svg>
  );
}
export function IconeCerto({ className = "icone" }: P) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path d="M5 12l5 5 9-10" />
    </svg>
  );
}
export function IconeAtencao({ className = "icone" }: P) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path d="M12 7v6M12 17h.01" />
    </svg>
  );
}
export function IconeAlerta({ className = "icone" }: P) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path d="M12 3l10 18H2z" />
      <path d="M12 10v4M12 17.5h.01" />
    </svg>
  );
}
export function IconeMarca() {
  return (
    <svg viewBox="0 0 24 24" className="icone" style={{ width: 16, height: 16, strokeWidth: 2 }} aria-hidden="true">
      <path d="M4 6h16M4 12h10M4 18h7" />
    </svg>
  );
}
