import { memo } from "react";
import type { KeySet, Orientation, Shot, ShotKeys } from "../../api/types";
import { Button } from "../../components/ui";
import { cx } from "../../lib/cx";
import { formatTime } from "../../lib/format";
import { kindColor } from "../../lib/kinds";

export const SET_LABEL: Record<KeySet, string> = { codex: "Codex", comfy: "ComfyUI" };

interface Props {
  shot: Pick<Shot, "id" | "start" | "end" | "section" | "kind" | "lines">;
  /** false = continues the previous shot (keyframe drawn from the previous one). */
  cut: boolean;
  /** ids of the following continuous shots drawn from this keyframe */
  dependents: string[];
  sets: KeySet[];
  orientation: Orientation;
  keys: Partial<Record<KeySet, ShotKeys | undefined>>;
  onOpen: (shotId: string, set: KeySet) => void;
  onRegenerate: (shotId: string) => void;
  regenerating: boolean;
}

export const KeyRow = memo(function KeyRow({ shot, cut, dependents, sets, orientation, keys, onOpen, onRegenerate, regenerating }: Props) {
  return (
    <li className="grid grid-cols-[180px_minmax(0,1fr)] gap-5 border-b border-ink-800 py-4 [content-visibility:auto] [contain-intrinsic-size:auto_190px] last:border-b-0">
      <div className="flex min-w-0 flex-col gap-1">
        <div className="flex items-baseline gap-2">
          <span className="font-display text-3xl leading-none">{shot.id}</span>
          <span className="font-mono text-[0.7rem] text-ink-400 tabular">{formatTime(shot.start)}–{formatTime(shot.end)}</span>
        </div>
        {!cut && (
          <span
            title="Ciągłe: klatka powstaje z klatki poprzedniego ujęcia, a poprzedni klip kończy się dokładnie na niej"
            className="w-fit rounded-full border border-ink-600 bg-ink-900 px-2 py-px font-mono text-[0.62rem] text-ink-300"
          >
            ↳ ciągłe
          </span>
        )}
        <span className="flex items-center gap-1.5 text-[0.72rem] text-ink-400">
          <span className="h-2 w-2 shrink-0 rounded-sm" style={{ background: kindColor(shot.kind) }} />
          <span className="truncate">{shot.section}</span>
        </span>
        {shot.lines.length > 0 && (
          <p className="line-clamp-3 font-display text-[0.95rem] italic leading-snug text-ink-300">{shot.lines.join(" / ")}</p>
        )}
        <Button
          size="sm"
          variant="ghost"
          className="-ml-3 mt-auto w-fit"
          busy={regenerating}
          onClick={() => onRegenerate(shot.id)}
          title={dependents.length ? `Uwaga: ${dependents.join(", ")} powstały z tej klatki (ujęcia ciągłe) i mogą przestać pasować` : undefined}
        >
          ↻ {keys.codex?.[orientation] ? "Wygeneruj ponownie (Codex)" : "Wygeneruj (Codex)"}
          {dependents.length > 0 && <span className="text-warn" aria-hidden> ⚠</span>}
        </Button>
      </div>
      <div className="flex flex-wrap gap-6">
        {sets.map((set) => {
          const k = keys[set];
          return (
            <div key={set} className="flex flex-col gap-1.5">
              <span className="font-mono text-[0.6rem] uppercase tracking-[0.16em] text-ink-500">{SET_LABEL[set]}</span>
              <Thumb
                src={orientation === "landscape" ? k?.landscape_thumb : k?.portrait_thumb}
                full={k?.[orientation]}
                className={orientation === "landscape" ? "h-[146px] w-[260px]" : "h-[214px] w-[120px]"}
                label={`${shot.id} ${SET_LABEL[set]} ${orientation === "landscape" ? "16:9" : "9:16"}`}
                onOpen={() => onOpen(shot.id, set)}
              />
            </div>
          );
        })}
      </div>
    </li>
  );
});

function Thumb({ src, full, className, label, onOpen }: { src?: string | null; full?: string | null; className: string; label: string; onOpen: () => void }) {
  const img = src ?? full;
  if (!img) {
    return (
      <div className={cx(className, "grid place-items-center rounded-md border border-dashed border-ink-700 bg-ink-900/60 text-[0.65rem] text-ink-600")}>
        brak
      </div>
    );
  }
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label={`Powiększ ${label}`}
      className={cx(className, "group overflow-hidden rounded-md border border-ink-700 bg-ink-900 transition-colors hover:border-safe")}
    >
      <img src={img} alt={label} loading="lazy" decoding="async" className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.04]" />
    </button>
  );
}
