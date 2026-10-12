import { useCallback, useEffect, useLayoutEffect, useRef, useState, type PointerEvent as RPointerEvent } from "react";
import type { Analysis, Shot } from "../../api/types";
import { Kbd } from "../../components/ui";
import { cx } from "../../lib/cx";
import { formatTime } from "../../lib/format";
import { TimelineCanvas, RULER_H, WAVE_H } from "./TimelineCanvas";
import { LyricsLane, LYRICS_H, SectionsLane, SECTIONS_H, ShotsLane, SHOTS_H } from "./TimelineLanes";
import type { Transport } from "./useAudioTransport";

const MAX_PPS = 420;
const LANES = [
  { label: "czas", h: RULER_H },
  { label: "audio", h: WAVE_H },
  { label: "sekcje", h: SECTIONS_H },
  { label: "ujęcia", h: SHOTS_H },
  { label: "tekst", h: LYRICS_H },
];

interface TimelineProps {
  duration: number;
  peaks: number[] | undefined;
  analysis: Analysis | undefined;
  shots: Shot[];
  selected: ReadonlySet<string>;
  primary: string | null;
  onPick: (id: string, additive: boolean) => void;
  thumbs: Record<string, string | null>;
  transport: Transport;
}

const indexAt = <T extends { start: number; end: number }>(items: T[], t: number) =>
  items.findIndex((x) => t >= x.start && t < x.end);

export function Timeline({ duration, peaks, analysis, shots, selected, primary, onPick, thumbs, transport }: TimelineProps) {
  const scroller = useRef<HTMLDivElement>(null);
  const inner = useRef<HTMLDivElement>(null);
  const playhead = useRef<HTMLDivElement>(null);
  const clock = useRef<HTMLSpanElement>(null);
  const [viewport, setViewport] = useState(0);
  const [zoom, setZoom] = useState(2.5);
  const [follow, setFollow] = useState(true);
  const [curShot, setCurShot] = useState(-1);
  const [curLine, setCurLine] = useState(-1);
  const anchor = useRef<{ t: number; x: number } | null>(null);

  const fit = viewport > 0 && duration > 0 ? viewport / duration : 1;
  const maxZoom = Math.max(1, MAX_PPS / fit);
  const pps = fit * Math.min(zoom, maxZoom);
  const width = Math.max(viewport, duration * pps);
  const ppsRef = useRef(pps);
  ppsRef.current = pps;
  const zoomRef = useRef(zoom);
  zoomRef.current = zoom;

  // viewport size
  useEffect(() => {
    const el = scroller.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setViewport(el.clientWidth));
    ro.observe(el);
    setViewport(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  const zoomTo = useCallback(
    (next: number, anchorX?: number) => {
      const sc = scroller.current;
      if (!sc) return;
      const x = anchorX ?? sc.clientWidth / 2;
      anchor.current = { t: (sc.scrollLeft + x) / ppsRef.current, x };
      setZoom(Math.min(maxZoom, Math.max(1, next)));
    },
    [maxZoom],
  );

  // keep the anchored time under the cursor after zooming
  useLayoutEffect(() => {
    const sc = scroller.current;
    const a = anchor.current;
    if (sc && a) {
      sc.scrollLeft = a.t * pps - a.x;
      anchor.current = null;
    }
  }, [pps]);

  // ctrl/cmd + wheel zoom (needs a non-passive listener)
  useEffect(() => {
    const sc = scroller.current;
    if (!sc) return;
    const onWheel = (e: WheelEvent) => {
      if (!(e.ctrlKey || e.metaKey)) return;
      e.preventDefault();
      const rect = sc.getBoundingClientRect();
      zoomTo(zoomRef.current * Math.exp(-e.deltaY * 0.004), e.clientX - rect.left);
    };
    sc.addEventListener("wheel", onWheel, { passive: false });
    return () => sc.removeEventListener("wheel", onWheel);
  }, [zoomTo]);

  // playhead + clock + follow + current shot/line, all outside React renders
  const lines = analysis?.lines;
  useEffect(() => {
    const tick = (t: number) => {
      const p = ppsRef.current;
      const x = t * p;
      if (playhead.current) playhead.current.style.transform = `translateX(${x}px)`;
      if (clock.current) clock.current.textContent = formatTime(t, true);
      const sc = scroller.current;
      if (sc && follow && transport.playing && (x < sc.scrollLeft || x > sc.scrollLeft + sc.clientWidth - 30)) {
        sc.scrollLeft = x - sc.clientWidth * 0.12;
      }
      setCurShot(indexAt(shots, t));
      setCurLine(lines ? indexAt(lines, t) : -1);
    };
    tick(transport.time());
    return transport.subscribe(tick);
  }, [transport, shots, lines, follow, pps]);

  // bring the primary shot into view when it changes from outside the lane
  useEffect(() => {
    const sc = scroller.current;
    const s = shots.find((x) => x.id === primary);
    if (!sc || !s) return;
    const a = s.start * ppsRef.current;
    const b = s.end * ppsRef.current;
    if (a < sc.scrollLeft || b > sc.scrollLeft + sc.clientWidth) {
      sc.scrollTo({ left: Math.max(0, a - sc.clientWidth * 0.2), behavior: "smooth" });
    }
  }, [primary, shots]);

  const timeAt = (clientX: number) => {
    const rect = inner.current?.getBoundingClientRect();
    if (!rect) return 0;
    return Math.max(0, Math.min(duration, (clientX - rect.left) / ppsRef.current));
  };

  const scrub = (e: RPointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    const target = e.currentTarget;
    target.setPointerCapture(e.pointerId);
    transport.seek(timeAt(e.clientX));
    const move = (ev: PointerEvent) => transport.seek(timeAt(ev.clientX));
    const up = () => {
      target.removeEventListener("pointermove", move);
      target.removeEventListener("pointerup", up);
      target.removeEventListener("pointercancel", up);
    };
    target.addEventListener("pointermove", move);
    target.addEventListener("pointerup", up);
    target.addEventListener("pointercancel", up);
  };

  const section = analysis?.sections.find((s) => {
    const t = shots[curShot]?.start ?? -1;
    return t >= s.start && t < s.end;
  });
  const totalH = LANES.reduce((a, l) => a + l.h, 0);

  return (
    <div className="panel overflow-hidden">
      {/* transport bar */}
      <div className="flex flex-wrap items-center gap-3 border-b border-ink-700 px-3 py-2">
        <button
          type="button"
          onClick={transport.toggle}
          disabled={!transport.ready}
          aria-label={transport.playing ? "Pauza" : "Odtwórz"}
          className={cx(
            "grid h-9 w-9 place-items-center rounded-full transition-colors disabled:opacity-40",
            transport.playing ? "bg-safe text-ink-950" : "bg-ink-100 text-ink-950 hover:bg-white",
          )}
        >
          {transport.playing ? (
            <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden><rect x="1.5" y="1" width="3" height="10" fill="currentColor" /><rect x="7.5" y="1" width="3" height="10" fill="currentColor" /></svg>
          ) : (
            <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden><path d="M2.5 1 L11 6 L2.5 11 Z" fill="currentColor" /></svg>
          )}
        </button>
        <div className="font-mono text-[0.95rem] tabular">
          <span ref={clock} className="text-ink-100">0:00.0</span>
          <span className="text-ink-500"> / {formatTime(duration, true)}</span>
        </div>
        <div className="hidden min-w-0 items-center gap-2 text-[0.75rem] text-ink-400 md:flex">
          {shots[curShot] && <span className="font-mono text-safe-hi">{shots[curShot].id}</span>}
          {section && <span className="truncate">{section.label}</span>}
        </div>
        <div className="ml-auto flex items-center gap-1.5 text-[0.72rem] text-ink-400">
          {analysis && <span className="mr-2 font-mono">{analysis.bpm.toFixed(0)} BPM</span>}
          <span className="mr-2 hidden xl:inline">
            <Kbd>spacja</Kbd> odtwórz · <Kbd>←</Kbd><Kbd>→</Kbd> ujęcia · <Kbd>⌘</Kbd>+kółko zoom
          </span>
          <label className="mr-2 flex items-center gap-1.5">
            <input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} className="accent-[#ff5a3c]" />
            śledź
          </label>
          <button type="button" onClick={() => zoomTo(zoom / 1.6)} disabled={zoom <= 1} aria-label="Oddal" className="h-7 w-7 rounded border border-ink-600 hover:border-ink-400 disabled:opacity-40">−</button>
          <button type="button" onClick={() => zoomTo(1)} className="h-7 rounded border border-ink-600 px-2 font-mono hover:border-ink-400" title="Dopasuj do szerokości">
            {Math.round(Math.min(zoom, maxZoom) * 100)}%
          </button>
          <button type="button" onClick={() => zoomTo(zoom * 1.6)} disabled={zoom >= maxZoom} aria-label="Przybliż" className="h-7 w-7 rounded border border-ink-600 hover:border-ink-400 disabled:opacity-40">+</button>
        </div>
      </div>

      <div className="flex">
        {/* lane labels */}
        <div className="w-[58px] shrink-0 border-r border-ink-700 bg-ink-900" aria-hidden>
          {LANES.map((l) => (
            <div key={l.label} style={{ height: l.h }} className="flex items-center px-2 font-mono text-[0.6rem] uppercase tracking-wider text-ink-500">
              {l.label}
            </div>
          ))}
        </div>
        <div ref={scroller} className="relative min-w-0 flex-1 overflow-x-auto overflow-y-hidden bg-ink-950" style={{ height: totalH + 10 }}>
          <div ref={inner} className="relative" style={{ width }}>
            <div onPointerDown={scrub} className="cursor-text" style={{ height: RULER_H + WAVE_H }}>
              <TimelineCanvas
                scroller={scroller}
                viewport={viewport}
                pps={pps}
                duration={duration}
                peaks={peaks}
                downbeats={analysis?.downbeats ?? []}
                transport={transport}
              />
            </div>
            <div onPointerDown={scrub} className="border-t border-ink-800">
              <SectionsLane sections={analysis?.sections ?? []} pps={pps} />
            </div>
            <div className="border-t border-ink-800" onClick={(e) => transport.seek(timeAt(e.clientX))}>
              <ShotsLane shots={shots} pps={pps} selected={selected} primary={primary} current={curShot} thumbs={thumbs} onPick={onPick} />
            </div>
            <div className="border-t border-ink-800" onClick={(e) => transport.seek(timeAt(e.clientX))}>
              <LyricsLane lines={lines ?? []} pps={pps} current={curLine} onSeek={transport.seek} />
            </div>
            <div ref={playhead} aria-hidden className="pointer-events-none absolute left-0 top-0 z-10 w-px bg-safe shadow-[0_0_8px_rgb(255_90_60/0.9)]" style={{ height: totalH }}>
              <span className="absolute -left-[5px] -top-px h-0 w-0 border-x-[5px] border-t-[7px] border-x-transparent border-t-safe" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
