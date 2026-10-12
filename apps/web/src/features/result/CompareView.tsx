import { useEffect, useRef, useState } from "react";
import type { FormatName, VideoFiles } from "../../api/types";
import { cx } from "../../lib/cx";
import { formatTime } from "../../lib/format";
import { SmartVideo } from "./SmartVideo";
import { useT } from "../../i18n";

/** Codex vs ComfyUI side by side, one transport driving both players. */
export function CompareView({ format: fmt, a: filesA, b: filesB }: { format: FormatName; a: VideoFiles; b: VideoFiles }) {
  const a = useRef<HTMLVideoElement>(null);
  const b = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);
  const [pos, setPos] = useState(0);
  const t = useT();
  const [dur, setDur] = useState(0);

  const srcA = [filesA.preview, filesA.master];
  const srcB = [filesB.preview, filesB.master];

  useEffect(() => {
    const va = a.current;
    const vb = b.current;
    if (!va || !vb) return;
    const onTime = () => {
      setPos(va.currentTime);
      if (Math.abs(vb.currentTime - va.currentTime) > 0.15) vb.currentTime = va.currentTime;
    };
    const onMeta = () => setDur(va.duration || 0);
    const onPause = () => {
      vb.pause();
      setPlaying(false);
    };
    va.addEventListener("timeupdate", onTime);
    va.addEventListener("loadedmetadata", onMeta);
    va.addEventListener("pause", onPause);
    va.addEventListener("ended", onPause);
    return () => {
      va.removeEventListener("timeupdate", onTime);
      va.removeEventListener("loadedmetadata", onMeta);
      va.removeEventListener("pause", onPause);
      va.removeEventListener("ended", onPause);
    };
  }, [fmt]);

  useEffect(() => {
    setPlaying(false);
    setPos(0);
  }, [fmt]);

  const toggle = () => {
    const va = a.current;
    const vb = b.current;
    if (!va || !vb) return;
    if (va.paused) {
      vb.currentTime = va.currentTime;
      void Promise.all([va.play(), vb.play()]).then(() => setPlaying(true)).catch(() => setPlaying(false));
    } else {
      va.pause();
    }
  };
  const seek = (v: number) => {
    if (a.current) a.current.currentTime = v;
    if (b.current) b.current.currentTime = v;
    setPos(v);
  };

  const portrait = fmt === "9x16";
  return (
    <section className="panel p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="eyebrow">{t("compare.eyebrow")}</div>
          <h2 className="font-display text-3xl">Codex <span className="text-ink-500">vs</span> ComfyUI</h2>
        </div>
        <span className="eyebrow">{t("compare.sub", { ratio: fmt === "16x9" ? "16:9" : "9:16" })}</span>
      </div>
      <div className={cx("grid gap-4", portrait ? "mx-auto max-w-[520px] grid-cols-2" : "grid-cols-2")}>
        {[{ ref: a, src: srcA, label: "Codex", muted: false }, { ref: b, src: srcB, label: "ComfyUI", muted: true }].map((v) => (
          <figure key={v.label} className="flex flex-col gap-1.5">
            <SmartVideo ref={v.ref} sources={v.src} muted={v.muted} preload="metadata" playsInline onClick={toggle}
              className={cx("w-full cursor-pointer rounded-lg bg-black", portrait ? "aspect-[9/16]" : "aspect-video")} />
            <figcaption className="font-mono text-[0.68rem] uppercase tracking-[0.16em] text-ink-500">{v.label}{v.muted ? t("compare.muted") : ""}</figcaption>
          </figure>
        ))}
      </div>
      <div className="mt-4 flex items-center gap-4">
        <button type="button" onClick={toggle} aria-label={playing ? t("tl.pause") : t("compare.playBoth")}
          className={cx("grid h-10 w-10 shrink-0 place-items-center rounded-full", playing ? "bg-safe text-ink-950" : "bg-ink-100 text-ink-950")}>
          {playing ? "❚❚" : "▶"}
        </button>
        <input type="range" className="slider flex-1" min={0} max={dur || 0} step={0.05} value={pos} aria-label={t("compare.position")}
          onChange={(e) => seek(Number(e.target.value))} />
        <span className="font-mono text-[0.8rem] text-ink-300 tabular">{formatTime(pos)} / {formatTime(dur)}</span>
      </div>
    </section>
  );
}
