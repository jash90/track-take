import { useEffect } from "react";
import { Dialog } from "./Dialog";
import { useT } from "../i18n";

export interface LightboxItem {
  src: string;
  caption: string;
}

interface LightboxProps {
  items: LightboxItem[];
  index: number | null;
  onIndex: (i: number | null) => void;
}

export function Lightbox({ items, index, onIndex }: LightboxProps) {
  const open = index !== null && items.length > 0;
  const i = index ?? 0;
  const item = items[Math.min(i, items.length - 1)];
  const t = useT();

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") onIndex((i + 1) % items.length);
      if (e.key === "ArrowLeft") onIndex((i - 1 + items.length) % items.length);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, i, items.length, onIndex]);

  return (
    <Dialog open={open} onClose={() => onIndex(null)} bare>
      {item && (
        <figure className="relative flex flex-col items-center gap-3 p-2">
          <img
            src={item.src}
            alt={item.caption}
            className="max-h-[80vh] max-w-[90vw] rounded-md object-contain shadow-[0_30px_100px_-20px_rgb(0_0_0/0.9)]"
          />
          <figcaption className="flex items-center gap-4 font-mono text-[0.75rem] text-ink-300">
            <button
              type="button"
              onClick={() => onIndex((i - 1 + items.length) % items.length)}
              className="rounded-md border border-ink-600 px-3 py-1 hover:border-ink-300"
              aria-label={t("common.prev")}
            >
              ←
            </button>
            <span className="tabular">
              {item.caption} · {i + 1}/{items.length}
            </span>
            <button
              type="button"
              onClick={() => onIndex((i + 1) % items.length)}
              className="rounded-md border border-ink-600 px-3 py-1 hover:border-ink-300"
              aria-label={t("common.next")}
            >
              →
            </button>
            <a href={item.src} target="_blank" rel="noreferrer" className="text-ink-400 underline-offset-2 hover:text-ink-100 hover:underline">
              {t("common.open")}
            </a>
            <button
              type="button"
              onClick={() => onIndex(null)}
              className="rounded-md border border-ink-600 px-3 py-1 hover:border-ink-300"
              aria-label={t("common.close")}
            >
              Esc
            </button>
          </figcaption>
        </figure>
      )}
    </Dialog>
  );
}
