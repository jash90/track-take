import { memo } from "react";
import type { LyricLine, Section, Shot } from "../../api/types";
import { cx } from "../../lib/cx";
import { formatTime } from "../../lib/format";
import { kindColor, kindLabel } from "../../lib/kinds";
import { isCut } from "../../lib/continuity";
import { useT } from "../../i18n";

export const SECTIONS_H = 26;
export const SHOTS_H = 58;
export const LYRICS_H = 46;

const UNWRITTEN_BG =
  "repeating-linear-gradient(135deg, rgba(237,231,221,0.05) 0 6px, transparent 6px 12px)";

export const SectionsLane = memo(function SectionsLane({ sections, pps }: { sections: Section[]; pps: number }) {
  const t = useT();
  return (
    <div className="relative" style={{ height: SECTIONS_H }}>
      {sections.map((s, i) => {
        const w = (s.end - s.start) * pps;
        return (
          <div
            key={i}
            title={`${s.label} · ${kindLabel(s.kind, t)} · ${formatTime(s.start)}–${formatTime(s.end)}`}
            className="absolute top-[3px] flex items-center overflow-hidden rounded-[3px] px-2 text-[0.7rem] font-medium text-ink-100/90"
            style={{
              left: s.start * pps + 1,
              width: Math.max(0, w - 2),
              height: SECTIONS_H - 6,
              background: `linear-gradient(180deg, ${kindColor(s.kind)}, ${kindColor(s.kind)}cc)`,
            }}
          >
            {w > 40 && <span className="truncate">{s.label}</span>}
          </div>
        );
      })}
    </div>
  );
});

interface ShotsLaneProps {
  shots: Shot[];
  pps: number;
  selected: ReadonlySet<string>;
  primary: string | null;
  current: number;
  thumbs: Record<string, string | null>;
  onPick: (id: string, additive: boolean) => void;
}

export const ShotsLane = memo(function ShotsLane({ shots, pps, selected, primary, current, thumbs, onPick }: ShotsLaneProps) {
  const t = useT();
  return (
    <div className="relative" style={{ height: SHOTS_H }} role="listbox" aria-label={t("tl.shotsAria")} aria-multiselectable>
      {shots.map((s, i) => {
        const w = (s.end - s.start) * pps;
        const written = s.scene.trim().length > 0;
        const isSel = selected.has(s.id);
        const thumb = thumbs[s.id];
        const showThumb = thumb && w >= 70;
        const cut = isCut(s, i);
        const next = shots[i + 1];
        const joinsNext = !!next && !isCut(next, i + 1);
        // continuous shots touch their neighbour (no gap, square corners) — one take
        const left = s.start * pps + (cut ? 1 : 0);
        const width = Math.max(2, w - (cut ? 1 : 0) - (joinsNext ? 0 : 1));
        return (
          <div
            key={s.id}
            role="option"
            aria-selected={isSel}
            tabIndex={s.id === primary ? 0 : -1}
            data-shot={s.id}
            title={`${s.id} · ${formatTime(s.start, true)}–${formatTime(s.end, true)} · ${cut ? t("tl.cut") : t("tl.continuous")}${written ? "" : ` · ${t("tl.unwritten")}`}`}
            onClick={(e) => {
              e.stopPropagation();
              onPick(s.id, e.metaKey || e.ctrlKey || e.shiftKey);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") onPick(s.id, e.metaKey || e.ctrlKey || e.shiftKey);
            }}
            className={cx(
              "absolute top-[3px] overflow-hidden rounded-[4px] border transition-[border-color,background-color] duration-100",
              isSel ? "border-safe bg-ink-700" : "border-ink-600 bg-ink-800 hover:border-ink-400",
              s.id === primary && "ring-1 ring-safe ring-offset-1 ring-offset-ink-950",
              !cut && "rounded-l-none",
              joinsNext && "rounded-r-none",
            )}
            style={{
              left,
              width,
              height: SHOTS_H - 6,
              backgroundImage: showThumb ? undefined : written ? undefined : UNWRITTEN_BG,
            }}
          >
            {showThumb && (
              <img
                src={thumb}
                alt=""
                loading="lazy"
                draggable={false}
                className={cx("absolute inset-0 h-full w-full object-cover", isSel ? "opacity-70" : "opacity-40")}
              />
            )}
            {i === current && <span className="absolute inset-x-0 top-0 h-[3px] bg-safe" />}
            {w >= 26 && (
              <span className="relative flex items-center gap-1 px-1.5 pt-1 font-mono text-[0.66rem] text-ink-100 [text-shadow:0_1px_2px_#000]">
                <span className={cx("h-1.5 w-1.5 shrink-0 rounded-full", written ? "bg-ok" : "border border-ink-400")} />
                {s.id}
              </span>
            )}
          </div>
        );
      })}
      {shots.map((s, i) =>
        i === 0 ? null : (
          <ContinuityMarker key={`m-${s.id}`} x={s.start * pps} cut={isCut(s, i)} />
        ),
      )}
    </div>
  );
});

/** Boundary marker: hard cut = red bar + scissors, continuous = small chain link over the joint. */
function ContinuityMarker({ x, cut }: { x: number; cut: boolean }) {
  if (cut) {
    return (
      <div aria-hidden className="pointer-events-none absolute top-0 z-[1]" style={{ left: x - 1, height: SHOTS_H }}>
        <span className="absolute left-0 top-0 h-full w-[2px] bg-safe shadow-[0_0_6px_rgb(255_90_60/0.7)]" />
        <span className="absolute -left-[7px] bottom-[2px] grid h-4 w-4 place-items-center rounded-full bg-safe text-[0.6rem] leading-none text-ink-950">
          ✂
        </span>
      </div>
    );
  }
  return (
    <span
      aria-hidden
      className="pointer-events-none absolute bottom-[4px] z-[1] grid h-[14px] w-[18px] place-items-center rounded-full border border-ink-500 bg-ink-900 text-ink-300"
      style={{ left: x - 9 }}
    >
      <svg width="12" height="8" viewBox="0 0 12 8" fill="none" stroke="currentColor" strokeWidth="1.4">
        <rect x="0.7" y="1.2" width="6" height="5.6" rx="2.8" />
        <rect x="5.3" y="1.2" width="6" height="5.6" rx="2.8" />
      </svg>
    </span>
  );
}

interface LyricsLaneProps {
  lines: LyricLine[];
  pps: number;
  current: number;
  onSeek: (t: number) => void;
}

export const LyricsLane = memo(function LyricsLane({ lines, pps, current, onSeek }: LyricsLaneProps) {
  return (
    <div className="relative" style={{ height: LYRICS_H }}>
      {lines.map((l, i) => {
        const row = i % 2;
        // let the label run until the next line on the same row; the underline marks the sung part
        const nextSameRow = lines[i + 2]?.start ?? l.end + 12;
        const span = Math.max(l.end, Math.min(nextSameRow, l.start + 12)) - l.start;
        const w = Math.max(4, span * pps - 3);
        const sung = Math.max(2, (l.end - l.start) * pps);
        return (
          <button
            key={i}
            type="button"
            tabIndex={-1}
            title={`${formatTime(l.start, true)} ${l.text}`}
            onClick={(e) => {
              e.stopPropagation();
              onSeek(l.start);
            }}
            className={cx(
              "absolute overflow-hidden truncate rounded-[3px] border-l-2 px-1.5 text-left text-[0.72rem] leading-[18px] transition-colors",
              i === current ? "border-safe bg-safe/15 text-ink-100" : "border-ink-500 text-ink-300 hover:bg-ink-800 hover:text-ink-100",
            )}
            style={{ left: l.start * pps, width: w, top: 3 + row * 21, height: 19 }}
          >
            {w >= 24 ? l.text : ""}
            <span
              aria-hidden
              className={cx("absolute bottom-0 left-0 h-[2px]", i === current ? "bg-safe" : "bg-ink-500/70")}
              style={{ width: Math.min(sung, w) }}
            />
          </button>
        );
      })}
    </div>
  );
});
