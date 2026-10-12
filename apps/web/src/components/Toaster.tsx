import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { cx } from "../lib/cx";

type ToastTone = "ok" | "err" | "info";
interface Toast {
  id: number;
  text: string;
  tone: ToastTone;
}

const ToastCtx = createContext<(text: string, tone?: ToastTone) => void>(() => {});

export function useToast() {
  return useContext(ToastCtx);
}

let seq = 0;

export function Toaster({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((text: string, tone: ToastTone = "info") => {
    const id = ++seq;
    setToasts((t) => [...t.slice(-3), { id, text, tone }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), tone === "err" ? 7000 : 3500);
  }, []);
  const value = useMemo(() => push, [push]);
  return (
    <ToastCtx.Provider value={value}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed right-5 top-16 z-[90] flex w-[min(380px,90vw)] flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={cx(
              "pointer-events-auto animate-rise rounded-lg border px-4 py-3 text-sm shadow-[0_16px_40px_-12px_rgb(0_0_0/0.8)] backdrop-blur",
              t.tone === "ok" && "border-ok/40 bg-ink-850/95 text-ink-100",
              t.tone === "err" && "border-err/50 bg-ink-850/95 text-ink-100",
              t.tone === "info" && "border-ink-600 bg-ink-850/95 text-ink-100",
            )}
          >
            <span className={cx("mr-2 font-mono", t.tone === "ok" ? "text-ok" : t.tone === "err" ? "text-err" : "text-safe")}>
              {t.tone === "ok" ? "✓" : t.tone === "err" ? "!" : "•"}
            </span>
            {t.text}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}
