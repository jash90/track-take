import { useEffect, useMemo, useRef, useState } from "react";
import type { Keys, LyricLine, Orientation, Shot } from "../../api/types";
import { useT } from "../../i18n";
import { isCut } from "../../lib/continuity";
import { cx } from "../../lib/cx";
import { kindColor } from "../../lib/kinds";
import type { Transport } from "./useAudioTransport";
import { KeyBadges, checkKinds } from "../keys/stale";
import { useCurrentIndex } from "./useCurrentIndex";

interface Props {
  shots: Shot[];
  lines: LyricLine[];
  keys: Keys | undefined;
  orientation: Orientation;
  transport: Transport;
  /** the editor below is not following because of unsaved edits */
  editorHeld: boolean;
}

function imageFor(keys: Keys | undefined, id: string, o: Orientation, full: boolean): string | null {
  const k = keys?.sets.codex?.[id] ?? keys?.sets.comfy?.[id];
  if (!k) return null;
  const thumb = o === "landscape" ? k.landscape_thumb : k.portrait_thumb;
  const big = o === "landscape" ? k.landscape : k.portrait;
  return full ? (big ?? thumb) : (thumb ?? big);
}

/** "Monitor": the keyframe under the playhead — cuts switch instantly, continuous shots crossfade. */
export function Monitor({ shots, lines, keys, orientation, transport, editorHeld }: Props) {
  const t = useT();
  const idx = useCurrentIndex(transport, shots);
  const lineIdx = useCurrentIndex(transport, lines);
  const shownIdx = idx >= 0 ? idx : 0;
  const shot = shots[shownIdx];
  const playing = transport.playing;
  const src = shot ? imageFor(keys, shot.id, orientation, !playing) : null;
  // imageFor prefers Codex, so a stale / flagged / mirrored Codex keyframe is the one on screen
  const codexKey = shot ? keys?.sets.codex?.[shot.id] : undefined;
  const kinds = useMemo(() => checkKinds(keys), [keys]);
  const issueKind = shot ? kinds[shot.id] : undefined;

  // previous frame stays underneath while a continuous shot fades in
  const [under, setUnder] = useState<string | null>(null);
  const last = useRef<{ id: string | null; src: string | null }>({ id: null, src: null });
  const continuous = !!shot && shownIdx > 0 && !isCut(shot, shownIdx);
  useEffect(() => {
    if (!shot) return;
    if (last.current.id !== shot.id) setUnder(continuous ? last.current.src : null);
    last.current = { id: shot.id, src };
  }, [shot, src, continuous]);

  // preload the next shots (thumbnails while playing, full images when paused)
  useEffect(() => {
    for (let i = shownIdx + 1; i <= shownIdx + 3 && i < shots.length; i++) {
      const s = shots[i];
      const u = s && imageFor(keys, s.id, orientation, !playing);
      if (u) new Image().src = u;
    }
  }, [shownIdx, shots, keys, orientation, playing]);

  if (!shot) return null;
  const line = lineIdx >= 0 ? lines[lineIdx] : null;
  const portrait = orientation === "portrait";

  return (
    <section className="panel mb-6 overflow-hidden p-4" aria-label={t("monitor.aria")}>
      <div className={cx("flex gap-4", portrait ? "flex-row items-end" : "flex-col")}>
        <button
          type="button"
          onClick={transport.toggle}
          title={playing ? t("tl.pause") : t("tl.play")}
          className={cx(
            "group relative shrink-0 overflow-hidden rounded-lg bg-black",
            portrait ? "aspect-[9/16] h-[440px]" : "aspect-video w-full",
          )}
        >
          {under && <img src={under} alt="" className="absolute inset-0 h-full w-full object-cover" />}
          {src ? (
            <img
              key={shot.id}
              src={src}
              alt={shot.id}
              className={cx("absolute inset-0 h-full w-full object-cover", continuous && under && "animate-[fade-in_150ms_ease-out_both]")}
            />
          ) : (
            <div key={shot.id} className="absolute inset-0 grid place-items-center bg-ink-900 p-6">
              <p className="max-w-prose text-center font-display text-lg italic leading-snug text-ink-300">{shot.scene || t("monitor.noScene")}</p>
            </div>
          )}
          <span className="absolute left-3 top-3 flex items-center gap-2 rounded-md bg-black/60 px-2 py-1 font-mono text-[0.72rem] text-ink-100 backdrop-blur">
            <span className="h-2 w-2 rounded-sm" style={{ background: kindColor(shot.kind) }} />
            {shot.id} · {shot.section}
          </span>
          <span
            className={cx(
              "absolute right-3 top-3 rounded-md px-2 py-1 font-mono text-[0.68rem] backdrop-blur",
              isCut(shot, shownIdx) ? "bg-safe/80 text-ink-950" : "bg-black/60 text-ink-200",
            )}
          >
            {isCut(shot, shownIdx) ? `✂ ${t("tl.cut")}` : `∞ ${t("monitor.continuous")}`}
          </span>
          <KeyBadges k={codexKey} orientation={orientation} kind={issueKind} className="bottom-3 left-3" pillClassName="px-2 py-0.5 text-[0.68rem]" />
          {!playing && (
            <span className="absolute inset-0 grid place-items-center bg-black/25 opacity-0 transition-opacity group-hover:opacity-100">
              <span className="grid h-14 w-14 place-items-center rounded-full bg-ink-100/90 text-xl text-ink-950">▶</span>
            </span>
          )}
        </button>
        <div className={cx("flex min-w-0 flex-col gap-1", portrait && "pb-1")}>
          <p className={cx("font-display text-[1.6rem] italic leading-snug", line ? "text-ink-100" : "text-ink-600")}>
            {line ? line.text : "♪"}
          </p>
          {editorHeld && <p className="text-[0.75rem] text-warn">{t("monitor.held")}</p>}
        </div>
      </div>
    </section>
  );
}
