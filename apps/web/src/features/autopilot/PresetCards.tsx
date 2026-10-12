import type { PresetChoice, RenderPreset, RenderPresetId, RenderPresets } from "../../api/types";
import { Spinner } from "../../components/ui";
import { useT, type Key } from "../../i18n";
import { cx } from "../../lib/cx";
import { formatUsd } from "../../lib/format";

const NAMES: Record<RenderPresetId, Key> = {
  cheapest: "preset.cheapest",
  recommended: "preset.recommended",
  fastest: "preset.fastest",
};

/** Budget rule from the brief: preset cost × 1.5, rounded up to $0.50. */
export function suggestedBudget(usd: number): number {
  return Math.max(0.5, Math.ceil((usd * 1.5) / 0.5) * 0.5);
}

export function presetLines(p: RenderPreset, t: ReturnType<typeof useT>): [string, string] {
  return [
    t("preset.time", { min: Math.round(p.minutes), usd: formatUsd(p.usd) }),
    t("preset.cards", { count: p.workers * p.gpus, gpu: p.label || p.gpu.replace(/_/g, " ") }),
  ];
}

interface Props {
  data: RenderPresets | undefined;
  loading: boolean;
  error: unknown;
  selected: PresetChoice | null;
  onSelect: (p: RenderPreset) => void;
  /** pick "Custom" (the saved GPU settings) */
  onCustom: () => void;
  /** short line under "Custom", e.g. the saved card */
  customHint?: string;
  /** live /estimate price for the saved settings, when known */
  customPrice?: string;
  disabled?: boolean;
}

const card = (on: boolean) =>
  cx(
    "flex min-w-0 flex-col gap-1 rounded-xl border px-4 py-3 text-left transition-colors disabled:opacity-50",
    on ? "border-safe bg-safe/[0.08]" : "border-ink-600 hover:border-ink-400",
  );

/** The plain-language render options (cheapest / recommended / fastest) plus "Custom". */
export function PresetCards({ data, loading, selected, onSelect, onCustom, customHint, customPrice, disabled }: Props) {
  const t = useT();
  const presets = data?.presets ?? [];
  const custom = (
    <button key="custom" type="button" role="radio" aria-checked={selected === "custom"} disabled={disabled} onClick={onCustom} className={card(selected === "custom")}>
      <span className="h-4" />
      <span className="font-display text-2xl leading-tight">{t("preset.custom")}</span>
      <span className={cx("font-display text-3xl leading-none tabular", customPrice ? "text-safe-hi" : "text-ink-500")}>{customPrice ? `~${customPrice}` : "…"}</span>
      <span className="font-mono text-[0.72rem] leading-snug text-ink-400">{t("preset.customSub")}</span>
      {customHint && <span className="truncate font-mono text-[0.72rem] leading-snug text-ink-500">{customHint}</span>}
    </button>
  );

  return (
    <div className="flex flex-col gap-2">
      {loading && !data && (
        <div className="flex items-center gap-2 py-2 text-sm text-ink-400">
          <Spinner small /> {t("preset.loading")}
        </div>
      )}
      {!loading && presets.length === 0 && <p className="text-sm text-warn">{t("preset.none")}</p>}
      <div role="radiogroup" aria-label={t("preset.title")} className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        {presets.map((p) => {
          const on = selected === p.id;
          return (
            <button key={p.id} type="button" role="radio" aria-checked={on} disabled={disabled} onClick={() => onSelect(p)} className={card(on)}>
              <span className="h-4">
                {p.id === "recommended" && (
                  <span className="rounded-full border border-ok/50 bg-ok/10 px-2 py-px font-mono text-[0.6rem] text-ok">{t("preset.badge")}</span>
                )}
              </span>
              <span className="font-display text-2xl leading-tight">{t(NAMES[p.id] ?? "preset.recommended")}</span>
              <span className="font-display text-3xl leading-none text-safe-hi tabular">~{formatUsd(p.usd)}</span>
              {presetLines(p, t).map((line) => (
                <span key={line} className="font-mono text-[0.72rem] leading-snug text-ink-400">{line}</span>
              ))}
            </button>
          );
        })}
        {custom}
      </div>
      {data?.estimated_clips && <p className="text-[0.72rem] text-ink-500">{t("preset.estimated")}</p>}
    </div>
  );
}
