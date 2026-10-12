import { getLocale } from "../i18n/core";
import type { TFn } from "../i18n";

/** 83.4 -> "1:23.4" (tenths optional). */
export function formatTime(seconds: number, tenths = false): string {
  if (!Number.isFinite(seconds) || seconds < 0) seconds = 0;
  const m = Math.floor(seconds / 60);
  const s = seconds - m * 60;
  if (tenths) {
    const whole = Math.floor(s);
    const t = Math.floor((s - whole) * 10);
    return `${m}:${String(whole).padStart(2, "0")}.${t}`;
  }
  return `${m}:${String(Math.floor(s)).padStart(2, "0")}`;
}

export function formatDuration(seconds: number): string {
  return `${seconds.toFixed(1)} s`;
}

export function formatUsd(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  return `$${v.toFixed(digits)}`;
}

export function formatMinutes(min: number): string {
  if (!Number.isFinite(min)) return "—";
  if (min < 60) return `${Math.round(min)} min`;
  const h = Math.floor(min / 60);
  return `${h} h ${Math.round(min - h * 60)} min`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(getLocale(), { day: "numeric", month: "short", year: "numeric" });
}

export function formatClock(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString(getLocale(), { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function elapsed(from: string | null, to: string | null): string {
  if (!from) return "";
  const a = new Date(from).getTime();
  const b = to ? new Date(to).getTime() : Date.now();
  if (Number.isNaN(a) || Number.isNaN(b)) return "";
  const s = Math.max(0, Math.round((b - a) / 1000));
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min ${s % 60} s`;
  return `${Math.floor(m / 60)} h ${m % 60} min`;
}

export function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

/** Compact time range for cards and chips: "32–42 min" (or a single value when there is no upper bound). */
export function timeRange(min: number, max?: number): string {
  if (!Number.isFinite(min)) return "—";
  if (max === undefined || !Number.isFinite(max) || Math.round(max) <= Math.round(min)) return formatMinutes(min);
  // plain minutes read best up to ~1.5 h ("54–64 min"); longer renders switch to hours
  if (max < 100) return `${Math.round(min)}–${Math.round(max)} min`;
  return `${formatMinutes(min)}–${formatMinutes(max)}`;
}

/** Parts for the roomy form "~32 min (up to ~42 …)": max without the unit when both are under an hour. */
export function timeRangeParts(min: number, max?: number): { min: string; max: string | null } {
  const hasMax = max !== undefined && Number.isFinite(max) && Math.round(max) > Math.round(min);
  return {
    min: (max ?? min) < 100 ? `${Math.round(min)} min` : formatMinutes(min),
    max: hasMax ? ((max as number) < 100 ? String(Math.round(max as number)) : formatMinutes(max as number)) : null,
  };
}

/** Roomy form: "~32 min (do ~42, jeśli host nie wystartuje)". */
export function timeRoomy(t: TFn, min: number, max?: number): string {
  const p = timeRangeParts(min, max);
  return p.max ? t("time.roomy", { min: p.min, max: p.max }) : t("time.single", { min: p.min });
}

/** "1 maszyna · 2× RTX PRO 6000 S" — machines and GPUs per machine, always explicit. */
export function machineSummary(t: TFn, workers: number, gpus: number, gpu: string): string {
  return t("summary.machines", { machines: t("est.cards", { count: workers }), gpus, gpu: gpu.replace(/_/g, " ") });
}
