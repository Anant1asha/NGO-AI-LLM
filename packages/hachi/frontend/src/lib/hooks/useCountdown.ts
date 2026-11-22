// ============================================================
// Hachi Web App — useCountdown hook
// Ticks every 1s, formats "1m 19s" / "45s", clamps at 0.
// Expired approvals auto-decline via the store tickApprovals.
// ============================================================

import { useState, useEffect } from "react";
import { useStore } from "../store/store";

interface CountdownResult {
  ms: number;
  label: string;
}

function fmt(ms: number): string {
  const s = Math.max(0, Math.ceil(ms / 1000));
  const mm = Math.floor(s / 60);
  const ss = s % 60;
  if (mm > 0) {
    return mm + "m " + (ss < 10 ? "0" : "") + ss + "s";
  }
  return ss + "s";
}

/**
 * Countdown hook. Returns live `ms` remaining and a formatted `label`.
 * When `expiresAt` is in the past, clamps to 0 and label is "0s".
 *
 * A single shared interval (via the store's tickApprovals) drives
 * auto-decline; this hook only drives per-card display.
 */
export function useCountdown(expiresAt: number): CountdownResult {
  const [now, setNow] = useState<number>(() => Date.now());

  useEffect(() => {
    return subscribeNow(setNow);
  }, []);

  const ms = Math.max(0, expiresAt - now);

  return { ms, label: fmt(ms) };
}

type NowListener = (now: number) => void;

const nowListeners = new Set<NowListener>();
let nowTickInterval: ReturnType<typeof setInterval> | null = null;

function stopNowTickerIfIdle(): void {
  if (nowListeners.size === 0 && nowTickInterval) {
    clearInterval(nowTickInterval);
    nowTickInterval = null;
  }
}

function startNowTickerIfNeeded(): void {
  if (nowTickInterval) return;
  nowTickInterval = setInterval(() => {
    const next = Date.now();
    // One global auto-decline pass per second for all approval cards.
    useStore.getState().tickApprovals();
    nowListeners.forEach((listener) => listener(next));
  }, 1000);
}

function subscribeNow(listener: NowListener): () => void {
  nowListeners.add(listener);
  startNowTickerIfNeeded();
  listener(Date.now());
  return () => {
    nowListeners.delete(listener);
    stopNowTickerIfIdle();
  };
}
