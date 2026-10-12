import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cx } from "../lib/cx";
import { errorMessage } from "../lib/format";
import { useT } from "../i18n";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-safe text-ink-950 font-semibold hover:bg-safe-hi shadow-[0_0_0_1px_rgb(255_90_60/0.6),0_8px_24px_-8px_rgb(255_90_60/0.55)]",
  secondary: "bg-ink-750 text-ink-100 border border-ink-600 hover:border-ink-400 hover:bg-ink-700",
  ghost: "text-ink-200 hover:text-ink-100 hover:bg-ink-750",
  danger: "bg-transparent text-err border border-err/50 hover:bg-err/10 hover:border-err",
};

const SIZES: Record<Size, string> = {
  sm: "h-8 px-3 text-[0.8rem] gap-1.5",
  md: "h-10 px-4 text-[0.88rem] gap-2",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  busy?: boolean;
  icon?: ReactNode;
}

export function Button({
  variant = "secondary",
  size = "md",
  busy = false,
  icon,
  className,
  children,
  disabled,
  type = "button",
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      className={cx(
        "inline-flex select-none items-center justify-center whitespace-nowrap rounded-md transition-[background,border-color,color,box-shadow] duration-150 disabled:cursor-not-allowed disabled:opacity-45",
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...rest}
    >
      {busy ? <Spinner small /> : icon}
      {children}
    </button>
  );
}

export function Spinner({ small = false, className }: { small?: boolean; className?: string }) {
  const t = useT();
  return (
    <span
      role="status"
      aria-label={t("common.loadingAria")}
      className={cx(
        "inline-block animate-spin rounded-full border-2 border-current border-r-transparent opacity-80",
        small ? "h-3.5 w-3.5" : "h-5 w-5",
        className,
      )}
    />
  );
}

export function Loading({ label }: { label?: string }) {
  const t = useT();
  return (
    <div className="flex items-center gap-3 px-1 py-8 text-ink-400">
      <Spinner />
      <span className="text-sm">{label ?? t("common.loading")}</span>
    </div>
  );
}

export function ErrorBox({ error, title, onRetry }: { error: unknown; title?: string; onRetry?: () => void }) {
  const t = useT();
  return (
    <div role="alert" className="rounded-lg border border-err/40 bg-err/[0.07] px-4 py-3 text-sm">
      <div className="font-semibold text-err">{title ?? t("common.error")}</div>
      <div className="mt-1 break-words font-mono text-[0.78rem] text-ink-200">{errorMessage(error)}</div>
      {onRetry && (
        <Button size="sm" variant="ghost" className="mt-2 -ml-2" onClick={onRetry}>
          {t("common.retry")}
        </Button>
      )}
    </div>
  );
}

export function InlineError({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <p role="alert" className="text-[0.8rem] text-err">
      {errorMessage(error)}
    </p>
  );
}

export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-3 rounded-xl border border-dashed border-ink-600 px-6 py-10">
      <div className="font-display text-2xl italic text-ink-200">{title}</div>
      {children && <div className="max-w-xl text-sm leading-relaxed text-ink-400">{children}</div>}
      {action}
    </div>
  );
}

type Tone = "neutral" | "ok" | "warn" | "err" | "safe" | "live";
const TONES: Record<Tone, string> = {
  neutral: "border-ink-600 text-ink-300 bg-ink-800",
  ok: "border-ok/40 text-ok bg-ok/[0.08]",
  warn: "border-warn/40 text-warn bg-warn/[0.08]",
  err: "border-err/40 text-err bg-err/[0.08]",
  safe: "border-safe/50 text-safe-hi bg-safe/[0.1]",
  live: "border-safe/60 text-safe-hi bg-safe/[0.12]",
};

export function Chip({ tone = "neutral", children, className, title }: { tone?: Tone; children: ReactNode; className?: string; title?: string }) {
  return (
    <span
      title={title}
      className={cx(
        "inline-flex h-6 items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 font-mono text-[0.68rem] tracking-wide",
        TONES[tone],
        className,
      )}
    >
      {tone === "live" && <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-safe" />}
      {children}
    </span>
  );
}

export function ProgressBar({ value, total, className }: { value: number; total: number; className?: string }) {
  const pct = total > 0 ? Math.min(100, Math.max(0, (value / total) * 100)) : 0;
  return (
    <div
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={total}
      aria-valuenow={value}
      className={cx("h-1.5 w-full overflow-hidden rounded-full bg-ink-700", className)}
    >
      <div className="h-full rounded-full bg-safe transition-[width] duration-500" style={{ width: `${pct}%` }} />
    </div>
  );
}

export function StepHeader({ index, title, children, actions }: { index: string; title: string; children?: ReactNode; actions?: ReactNode }) {
  const t = useT();
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4 border-b border-ink-700 pb-5">
      <div className="min-w-0">
        <div className="eyebrow">{t("common.step", { n: index })}</div>
        <h1 className="mt-1 font-display text-[2.6rem] leading-none text-ink-100">{title}</h1>
        {children && <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-400">{children}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

export function Hint({ children }: { children: ReactNode }) {
  return (
    <div className="flex gap-3 rounded-lg border border-ink-700 bg-ink-900/60 px-4 py-3 text-[0.82rem] leading-relaxed text-ink-300">
      <span aria-hidden className="mt-0.5 font-mono text-safe">※</span>
      <div>{children}</div>
    </div>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="rounded border border-ink-600 bg-ink-800 px-1.5 py-px font-mono text-[0.68rem] text-ink-300">{children}</kbd>
  );
}
