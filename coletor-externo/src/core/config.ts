// Configuração genérica do coletor — agnóstica de portal.
// Nada de credenciais nem endpoints aqui: o que é específico de um portal
// vive no adapter (ver src/portal.ts). Segredos e URLs do portal chegam ao
// adapter por process.env, nunca são embutidos no código.

import { config as loadEnv } from 'dotenv';
import { resolve } from 'path';

loadEnv();

function str(key: string, fallback = ''): string {
  return String(process.env[key] ?? fallback).trim();
}

function num(key: string, fallback: number): number {
  const raw = process.env[key];
  if (raw == null || String(raw).trim() === '') return fallback;
  const parsed = Number(raw);
  // aceita 0 (ex.: SLEEP_MS=0); rejeita negativos e NaN.
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback;
}

export const config = {
  // Transporte: porta do --remote-debugging-port do Chrome real.
  cdpPort: num('CDP_PORT', 9222),

  // Ritmo e volume.
  concurrency: num('CONCURRENCY', 6),
  pageLimit: num('PAGE_LIMIT', 200),
  sleepMs: num('SLEEP_MS', 400),

  // Saída e retomada.
  outDir: resolve(str('OUT_DIR', './out')),
  checkpointEvery: num('CHECKPOINT_EVERY', 2000),

  // Escada do canário (portão do full).
  canarySteps: str('CANARY_STEPS', '1,10,100,1000')
    .split(',')
    .map((s) => Number(s.trim()))
    .filter((n) => Number.isFinite(n) && n > 0),

  // Sharding: teto por shard (as dimensões são do adapter do portal).
  shardMax: num('SHARD_MAX', 9500),

  // Override de sessão para depuração (opcional).
  sessionIdOverride: str('SESSION_ID_OVERRIDE'),
};

/** Arquivo de sinalização: quando existe, o operador precisa re-logar no portal. */
export const NEEDS_WARM_FLAG = 'NEEDS_WARM.flag';
