import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export interface Transport {
  /** Callback ref for the <audio> element. */
  audioRef: (el: HTMLAudioElement | null) => void;
  playing: boolean;
  ready: boolean;
  /** Current time read straight from the element (no re-render). */
  time: () => number;
  toggle: () => void;
  seek: (t: number) => void;
  /** Subscribe to per-frame time updates (while playing) and seeks. */
  subscribe: (fn: (t: number) => void) => () => void;
}

/** Thin wrapper around an <audio> element with a rAF-driven clock for the timeline. */
export function useAudioTransport(): Transport {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [el, setEl] = useState<HTMLAudioElement | null>(null);
  const attach = useCallback((node: HTMLAudioElement | null) => {
    audioRef.current = node;
    setEl(node);
  }, []);
  const [playing, setPlaying] = useState(false);
  const [ready, setReady] = useState(false);
  const listeners = useRef(new Set<(t: number) => void>());

  const emit = useCallback(() => {
    const t = audioRef.current?.currentTime ?? 0;
    for (const fn of listeners.current) fn(t);
  }, []);

  useEffect(() => {
    if (!el) {
      setReady(false);
      return;
    }
    const onPlay = () => setPlaying(true);
    const onPause = () => setPlaying(false);
    const onReady = () => setReady(true);
    el.addEventListener("play", onPlay);
    el.addEventListener("pause", onPause);
    el.addEventListener("ended", onPause);
    el.addEventListener("loadedmetadata", onReady);
    el.addEventListener("seeked", emit);
    el.addEventListener("timeupdate", emit);
    if (el.readyState >= 1) setReady(true);
    return () => {
      el.removeEventListener("play", onPlay);
      el.removeEventListener("pause", onPause);
      el.removeEventListener("ended", onPause);
      el.removeEventListener("loadedmetadata", onReady);
      el.removeEventListener("seeked", emit);
      el.removeEventListener("timeupdate", emit);
    };
  }, [el, emit]);

  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    const loop = () => {
      emit();
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [playing, emit]);

  const toggle = useCallback(() => {
    const el = audioRef.current;
    if (!el) return;
    if (el.paused) void el.play().catch(() => setPlaying(false));
    else el.pause();
  }, []);

  const seek = useCallback(
    (t: number) => {
      const el = audioRef.current;
      if (!el) return;
      const max = Number.isFinite(el.duration) ? el.duration : t;
      el.currentTime = Math.max(0, Math.min(max, t));
      emit();
    },
    [emit],
  );

  const time = useCallback(() => audioRef.current?.currentTime ?? 0, []);
  const subscribe = useCallback((fn: (t: number) => void) => {
    listeners.current.add(fn);
    return () => {
      listeners.current.delete(fn);
    };
  }, []);

  return useMemo(
    () => ({ audioRef: attach, playing, ready, time, toggle, seek, subscribe }),
    [attach, playing, ready, time, toggle, seek, subscribe],
  );
}
