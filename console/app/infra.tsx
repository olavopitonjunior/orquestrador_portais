import { saudeChrome } from "@/lib/chrome";
import { saudeColeta } from "@/lib/coletor";
import { db } from "@/lib/db";
import { trabalhadorVivo } from "@/lib/operacao";

// A infraestrutura que a rodada precisa, num canto fixo da barra lateral: o operador
// vê de qualquer tela se o que executa está no ar. Quatro leituras independentes —
// cada uma degrada sozinha para "?" sem derrubar a casca.
async function registroResponde(): Promise<boolean> {
  try {
    await db().query("SELECT 1");
    return true;
  } catch {
    return false;
  }
}

function Pilula({ v, sim, nao }: { v: boolean | null; sim: string; nao: string }) {
  if (v === null) return <span className="pill pill-muted">?</span>;
  return <span className={v ? "pill pill-ok" : "pill pill-bad"}>{v ? sim : nao}</span>;
}

export async function Infra() {
  const [reg, viv, chr, col] = await Promise.allSettled([
    registroResponde(),
    trabalhadorVivo(),
    saudeChrome(),
    saudeColeta(),
  ]);
  const registro = reg.status === "fulfilled" ? reg.value : false;
  const vivo = viv.status === "fulfilled" ? viv.value : null;
  const chrome = chr.status === "fulfilled" ? chr.value : null;
  const coleta = col.status === "fulfilled" ? col.value : null;
  // "sessão" aqui é o que dá para saber sem raspar: aba do painel aberta e sem a flag
  // de re-login. Só o canário prova autenticação (chrome.ts).
  const sessao =
    chrome === null || coleta === null || !chrome.noAr || chrome.abaDoPainel === null
      ? null
      : chrome.abaDoPainel && !coleta.needsWarm;

  return (
    <div className="infra">
      <div className="lbl">Infraestrutura</div>
      <div className="infra-linha">
        <span>Registro (Postgres)</span>
        <Pilula v={registro} sim="ok" nao="fora" />
      </div>
      <div className="infra-linha">
        <span>Trabalhador</span>
        <Pilula v={vivo} sim="vivo" nao="parado" />
      </div>
      <div className="infra-linha">
        <span>Chrome (depuração)</span>
        <Pilula v={chrome ? chrome.noAr : null} sim="no ar" nao="fora" />
      </div>
      <div className="infra-linha">
        <span>Sessão Canal Pro</span>
        <Pilula v={sessao} sim="aberta" nao="re-login" />
      </div>
    </div>
  );
}
