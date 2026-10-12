import type { KeySet, Orientation, Shot, ShotKeys, WorldItem } from "../../api/types";
import { ShotWorldFields } from "./ShotWorldFields";
import { Chip } from "../../components/ui";
import { cx } from "../../lib/cx";
import { formatTime } from "../../lib/format";
import { kindColor, kindLabel } from "../../lib/kinds";
import { isCut } from "../../lib/continuity";
import { useT } from "../../i18n";

interface Props {
  shot: Shot;
  index: number;
  total: number;
  keys: Partial<Record<KeySet, ShotKeys | undefined>>;
  orientation: Orientation;
  world: { locations: WorldItem[]; props: WorldItem[] };
  disabled: boolean;
  onChange: (patch: Partial<Shot>) => void;
  onStep: (delta: number) => void;
  onOpenImage: (set: KeySet) => void;
  onPlay: () => void;
}

const SETS: { set: KeySet; label: string }[] = [
  { set: "codex", label: "Codex" },
  { set: "comfy", label: "ComfyUI" },
];

export function ShotEditor({ shot, index, total, keys, orientation, world, disabled, onChange, onStep, onOpenImage, onPlay }: Props) {
  const written = shot.scene.trim().length > 0;
  const t = useT();
  return (
    <section className="panel animate-rise p-5" aria-label={t("shot.aria", { id: shot.id })} key={shot.id}>
      <div className="flex flex-wrap items-start gap-x-6 gap-y-3">
        <div>
          <div className="eyebrow">{t("shot.of", { n: index + 1, total })}</div>
          <div className="font-display text-[3.2rem] leading-[0.9]">{shot.id}</div>
        </div>
        <div className="flex flex-col gap-1.5 pt-1">
          <div className="font-mono text-[0.85rem] text-ink-200 tabular">
            {formatTime(shot.start, true)} → {formatTime(shot.end, true)}
            <span className="text-ink-500"> · {(shot.end - shot.start).toFixed(1)} s</span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 text-[0.78rem] text-ink-300">
              <span className="h-2.5 w-2.5 rounded-sm" style={{ background: kindColor(shot.kind) }} />
              {shot.section || "—"} <span className="text-ink-500">({kindLabel(shot.kind, t)})</span>
            </span>
            <Chip tone={written ? "ok" : "warn"}>{written ? t("shot.written") : t("shot.unwritten")}</Chip>
          </div>
        </div>
        <div className="ml-auto flex gap-1.5">
          <button type="button" onClick={onPlay} className="h-8 rounded-md border border-ink-600 px-3 text-[0.78rem] hover:border-ink-400">{t("shot.playFromStart")}</button>
          <button type="button" onClick={() => onStep(-1)} disabled={index === 0} aria-label={t("shot.prev")} className="h-8 w-8 rounded-md border border-ink-600 hover:border-ink-400 disabled:opacity-40">←</button>
          <button type="button" onClick={() => onStep(1)} disabled={index >= total - 1} aria-label={t("shot.next")} className="h-8 w-8 rounded-md border border-ink-600 hover:border-ink-400 disabled:opacity-40">→</button>
        </div>
      </div>

      <ContinuityToggle cut={isCut(shot, index)} first={index === 0} disabled={disabled} onChange={(cut) => onChange({ cut })} />
      <ShotWorldFields shot={shot} locations={world.locations} props={world.props} disabled={disabled} onChange={onChange} />

      {shot.lines.length > 0 ? (
        <blockquote className="mt-4 border-l-2 border-safe/60 pl-4 font-display text-[1.2rem] italic leading-snug text-ink-200">
          {shot.lines.map((l, i) => (
            <div key={i}>{l}</div>
          ))}
        </blockquote>
      ) : (
        <p className="mt-4 text-[0.8rem] italic text-ink-500">{t("shot.instrumental")}</p>
      )}

      <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,300px)]">
        <div className="flex flex-col gap-4">
          <div>
            <label className="label" htmlFor="shot-scene">{t("shot.scene")}</label>
            <textarea
              id="shot-scene"
              rows={6}
              disabled={disabled}
              className="field resize-y leading-relaxed disabled:opacity-60"
              placeholder={t("shot.scenePlaceholder")}
              value={shot.scene}
              onChange={(e) => onChange({ scene: e.target.value })}
            />
          </div>
          <div>
            <label className="label" htmlFor="shot-motion">{t("shot.motion")}</label>
            <textarea
              id="shot-motion"
              rows={3}
              disabled={disabled}
              className="field resize-y leading-relaxed disabled:opacity-60"
              placeholder={t("shot.motionPlaceholder")}
              value={shot.motion}
              onChange={(e) => onChange({ motion: e.target.value })}
            />
          </div>
        </div>

        <div className="flex flex-col gap-3">
          <div className="label">{t("shot.keyframes", { ratio: orientation === "landscape" ? "16:9" : "9:16" })}</div>
          <div className={orientation === "landscape" ? "flex flex-col gap-3" : "flex gap-3"}>
            {SETS.map(({ set, label }) => {
              const k = keys[set];
              const thumb = orientation === "landscape" ? (k?.landscape_thumb ?? k?.landscape) : (k?.portrait_thumb ?? k?.portrait);
              return (
                <div key={set} className="flex flex-col gap-1">
                  <span className="font-mono text-[0.62rem] uppercase tracking-wider text-ink-500">{label}</span>
                  <Thumb
                    src={thumb ?? null}
                    ratio={orientation === "landscape" ? "aspect-video w-full max-w-[300px]" : "aspect-[9/16] w-[118px]"}
                    label={`${shot.id} ${label} ${orientation === "landscape" ? "16:9" : "9:16"}`}
                    onOpen={() => onOpenImage(set)}
                  />
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}

function Thumb({ src, ratio, label, onOpen }: { src: string | null; ratio: string; label: string; onOpen: () => void }) {
  const t = useT();
  if (!src) {
    return (
      <div className={cx(ratio, "grid place-items-center rounded border border-dashed border-ink-700 text-[0.6rem] text-ink-600")}>{t("common.none")}</div>
    );
  }
  return (
    <button type="button" onClick={onOpen} aria-label={t("common.enlarge", { label })} className={cx(ratio, "overflow-hidden rounded border border-ink-600 hover:border-safe")}>
      <img src={src} alt={label} loading="lazy" className="h-full w-full object-cover" />
    </button>
  );
}

function ContinuityToggle({ cut, first, disabled, onChange }: { cut: boolean; first: boolean; disabled: boolean; onChange: (cut: boolean) => void }) {
  const t = useT();
  const opts = [
    { cut: true, label: t("cont.cut"), icon: "✂" },
    { cut: false, label: t("cont.continuous"), icon: "∞" },
  ];
  return (
    <div className="mt-4">
      <div className="flex flex-wrap items-center gap-3">
        <span className="label mb-0" id="cont-label">{t("cont.label")}</span>
        <div
          role="radiogroup"
          aria-labelledby="cont-label"
          className="flex rounded-md border border-ink-600 p-0.5"
          title={first ? t("cont.firstAlways") : undefined}
        >
          {opts.map((o) => {
            const on = cut === o.cut;
            return (
              <button
                key={o.label}
                type="button"
                role="radio"
                aria-checked={on}
                disabled={disabled || first}
                onClick={() => !on && onChange(o.cut)}
                className={cx(
                  "flex items-center gap-1.5 rounded px-3 py-1.5 text-[0.8rem] transition-colors disabled:cursor-not-allowed",
                  on ? (o.cut ? "bg-safe text-ink-950" : "bg-ink-100 text-ink-950") : "text-ink-300 hover:text-ink-100 disabled:opacity-40",
                )}
              >
                <span aria-hidden>{o.icon}</span>
                {o.label}
              </button>
            );
          })}
        </div>
      </div>
      <p className="mt-1.5 text-[0.72rem] leading-relaxed text-ink-500">
        {first
          ? t("cont.firstAlwaysDot")
          : t("cont.hint")}
      </p>
    </div>
  );
}
