import { useCallback, useEffect, useRef } from "react";
import type { Transport } from "./useAudioTransport";

export const RULER_H = 22;
export const WAVE_H = 92;

interface Props {
  scroller: React.RefObject<HTMLDivElement | null>;
  viewport: number;
  pps: number;
  duration: number;
  peaks: number[] | undefined;
  downbeats: number[];
  transport: Transport;
}

const C = {
  bg: "#0d0b0a",
  ruler: "#121010",
  rulerText: "#82796f",
  tick: "#3b3631",
  bar: "rgba(237,231,221,0.07)",
  bar4: "rgba(237,231,221,0.16)",
  barLabel: "#5a534c",
  wave: "#5f574f",
  played: "#ff5a3c",
  center: "rgba(237,231,221,0.08)",
};

/** Seconds between labelled ruler ticks for a given zoom. */
function tickStep(pps: number): number {
  const steps = [0.5, 1, 2, 5, 10, 15, 30, 60];
  return steps.find((s) => s * pps >= 70) ?? 120;
}

function label(t: number): string {
  const m = Math.floor(t / 60);
  const s = t - m * 60;
  return `${m}:${(s < 10 ? "0" : "") + (Number.isInteger(s) ? s.toFixed(0) : s.toFixed(1))}`;
}

/** Ruler + waveform + downbeat grid, drawn only for the visible window (sticky canvas). */
export function TimelineCanvas({ scroller, viewport, pps, duration, peaks, downbeats, transport }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);

  const draw = useCallback(() => {
    const el = canvas.current;
    const sc = scroller.current;
    if (!el || !sc || viewport <= 0) return;
    const dpr = window.devicePixelRatio || 1;
    const w = viewport;
    const h = RULER_H + WAVE_H;
    if (el.width !== Math.round(w * dpr) || el.height !== Math.round(h * dpr)) {
      el.width = Math.round(w * dpr);
      el.height = Math.round(h * dpr);
    }
    const ctx = el.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const sl = sc.scrollLeft;
    const t0 = sl / pps;
    const t1 = (sl + w) / pps;
    const now = transport.time();

    ctx.fillStyle = C.bg;
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = C.ruler;
    ctx.fillRect(0, 0, w, RULER_H);

    // downbeat grid (+ bar numbers when there is room)
    const barPx = downbeats.length > 1 ? ((downbeats[1] ?? 0) - (downbeats[0] ?? 0)) * pps : 0;
    ctx.font = "10px 'JetBrains Mono Variable', monospace";
    for (let i = 0; i < downbeats.length; i++) {
      const t = downbeats[i] ?? 0;
      if (t < t0 - 1 || t > t1 + 1) continue;
      const x = Math.round(t * pps - sl) + 0.5;
      const strong = i % 4 === 0;
      ctx.fillStyle = strong ? C.bar4 : C.bar;
      ctx.fillRect(x, RULER_H, 1, WAVE_H);
      if (barPx > 26 || (strong && barPx > 9)) {
        ctx.fillStyle = C.barLabel;
        ctx.fillText(String(i + 1), x + 3, RULER_H + 11);
      }
    }

    // time ruler
    const step = tickStep(pps);
    ctx.fillStyle = C.tick;
    ctx.fillRect(0, RULER_H - 1, w, 1);
    const minor = step / 5;
    for (let t = Math.floor(t0 / minor) * minor; t <= t1; t += minor) {
      const x = Math.round(t * pps - sl) + 0.5;
      const major = Math.abs(t / step - Math.round(t / step)) < 1e-6;
      ctx.fillStyle = major ? C.rulerText : C.tick;
      ctx.fillRect(x, major ? RULER_H - 9 : RULER_H - 4, 1, major ? 9 : 4);
      if (major && t >= 0) {
        ctx.fillStyle = C.rulerText;
        ctx.fillText(label(Math.round(t * 10) / 10), x + 4, 12);
      }
    }

    // waveform (mirrored), played part in safelight red
    const mid = RULER_H + WAVE_H / 2;
    ctx.fillStyle = C.center;
    ctx.fillRect(0, mid, w, 1);
    if (peaks && peaks.length > 0 && duration > 0) {
      const n = peaks.length;
      const perSec = n / duration;
      const amp = WAVE_H / 2 - 4;
      const playedX = now * pps - sl;
      for (let x = 0; x < w; x++) {
        const ta = (sl + x) / pps;
        if (ta > duration) break;
        const tb = (sl + x + 1) / pps;
        const ia = ta * perSec;
        const ib = tb * perSec;
        let v: number;
        if (ib - ia >= 1) {
          v = 0;
          for (let i = Math.floor(ia); i < Math.min(n, Math.ceil(ib)); i++) v = Math.max(v, peaks[i] ?? 0);
        } else {
          const i = Math.min(n - 1, Math.floor(ia));
          const f = ia - i;
          v = (peaks[i] ?? 0) * (1 - f) + (peaks[Math.min(n - 1, i + 1)] ?? 0) * f;
        }
        const bh = Math.max(1, Math.min(1, v * 0.95) * amp);
        ctx.fillStyle = x < playedX ? C.played : C.wave;
        ctx.fillRect(x, mid - bh, 1, bh * 2);
      }
    }
  }, [scroller, viewport, pps, duration, peaks, downbeats, transport]);

  useEffect(() => {
    draw();
    const sc = scroller.current;
    sc?.addEventListener("scroll", draw, { passive: true });
    const unsub = transport.subscribe(draw);
    return () => {
      sc?.removeEventListener("scroll", draw);
      unsub();
    };
  }, [draw, scroller, transport]);

  // fonts load late — redraw once they are in
  useEffect(() => {
    void document.fonts?.ready.then(draw);
  }, [draw]);

  return (
    <canvas
      ref={canvas}
      aria-hidden
      className="sticky left-0 block"
      style={{ width: viewport, height: RULER_H + WAVE_H }}
    />
  );
}
