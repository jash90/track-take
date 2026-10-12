import { useEffect, useRef, type ReactNode } from "react";
import { cx } from "../lib/cx";
import { useT } from "../i18n";

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
  /** Bare dialog without frame (lightbox). */
  bare?: boolean;
  wide?: boolean;
  labelledBy?: string;
}

/** Native <dialog> wrapper: focus trap, Esc and backdrop close come for free. */
export function Dialog({ open, onClose, title, children, footer, className, bare = false, wide = false }: DialogProps) {
  const t = useT();
  const ref = useRef<HTMLDialogElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    if (!open && el.open) el.close();
  }, [open]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const handle = () => onCloseRef.current();
    el.addEventListener("close", handle);
    return () => el.removeEventListener("close", handle);
  }, []);

  return (
    <dialog
      ref={ref}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
      className={cx(
        "m-auto max-h-[92vh] max-w-[94vw] bg-transparent p-0 text-ink-100 backdrop:bg-black/70",
        className,
      )}
    >
      {open &&
        (bare ? (
          children
        ) : (
          <div className={cx("panel shadow-[0_30px_80px_-20px_rgb(0_0_0/0.8)]", wide ? "w-[min(760px,94vw)]" : "w-[min(560px,94vw)]")}>
            {title && (
              <div className="flex items-center justify-between gap-4 border-b border-ink-700 px-6 py-4">
                <h2 className="font-display text-[1.7rem] leading-tight">{title}</h2>
                <button
                  type="button"
                  onClick={onClose}
                  aria-label={t("common.close")}
                  className="grid h-8 w-8 place-items-center rounded-md text-ink-400 hover:bg-ink-750 hover:text-ink-100"
                >
                  ✕
                </button>
              </div>
            )}
            <div className="max-h-[72vh] overflow-y-auto px-6 py-5">{children}</div>
            {footer && <div className="flex justify-end gap-2 border-t border-ink-700 px-6 py-4">{footer}</div>}
          </div>
        ))}
    </dialog>
  );
}
