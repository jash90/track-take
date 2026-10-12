import type { FormatName, Orientation, Project } from "../api/types";
import { cx } from "./cx";
import { useT, type Key } from "../i18n";

export const ORIENTATIONS: { value: Orientation; format: FormatName; label: Key; ratio: string; hint: Key }[] = [
  { value: "landscape", format: "16x9", label: "orient.landscape", ratio: "16:9", hint: "orient.landscapeHint" },
  { value: "portrait", format: "9x16", label: "orient.portrait", ratio: "9:16", hint: "orient.portraitHint" },
];

/** Tolerates projects created before orientation existed (treated as landscape). */
export function projectOrientation(p: Pick<Project, "orientation">): Orientation {
  return p.orientation === "portrait" ? "portrait" : "landscape";
}

export function projectFormat(p: Pick<Project, "orientation">): FormatName {
  return projectOrientation(p) === "portrait" ? "9x16" : "16x9";
}

export function orientationInfo(o: Orientation) {
  return ORIENTATIONS.find((x) => x.value === o) ?? ORIENTATIONS[0]!;
}

export const formatRatio = (f: FormatName) => (f === "9x16" ? "9:16" : "16:9");

/** Tiny frame-shape glyph: a wide or a tall rectangle. */
export function FrameGlyph({ orientation, size = 14, className }: { orientation: Orientation; size?: number; className?: string }) {
  const w = orientation === "landscape" ? size : Math.round((size * 9) / 16);
  const h = orientation === "landscape" ? Math.round((size * 9) / 16) : size;
  return (
    <span
      aria-hidden
      className={cx("inline-block shrink-0 rounded-[2px] border-[1.5px] border-current", className)}
      style={{ width: w, height: h }}
    />
  );
}

/** "▭ Horizontal · 16:9" chip used on cards, headers and steps. */
export function FormatBadge({ orientation, className }: { orientation: Orientation; className?: string }) {
  const info = orientationInfo(orientation);
  const t = useT();
  return (
    <span
      title={`${t(info.label)} ${info.ratio} — ${t(info.hint)}`}
      className={cx(
        "inline-flex h-6 items-center gap-1.5 whitespace-nowrap rounded-full border border-ink-600 bg-ink-900/80 px-2.5 font-mono text-[0.68rem] text-ink-200",
        className,
      )}
    >
      <FrameGlyph orientation={orientation} size={12} className="text-safe" />
      {t(info.label)} · {info.ratio}
    </span>
  );
}

/** Sets (codex/comfy) with a video in the project format; leftovers in the other format don't count. */
export function renderedSets(p: Pick<Project, "orientation" | "stage">): number {
  const f = projectFormat(p);
  return (["codex", "comfy"] as const).filter((s) => p.stage.videos[s]?.includes(f)).length;
}
