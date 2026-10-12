import { useEffect } from "react";
import { isActive } from "../../api/hooks";
import type { Job } from "../../api/types";
import { ProgressBar } from "../../components/ui";
import { cx } from "../../lib/cx";
import { errorMessage } from "../../lib/format";
import { JobItem } from "./JobItem";
import { useT } from "../../i18n";
import { jobTitle } from "./jobTitle";

interface JobsDrawerProps {
  projectId: string;
  jobs: Job[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  error: unknown;
}

export function JobsDrawer({ projectId, jobs, open, onOpenChange, error }: JobsDrawerProps) {
  const active = jobs.filter(isActive);
  const lead = active[0];

  const t = useT();
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !document.querySelector("dialog[open]")) onOpenChange(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onOpenChange]);

  return (
    <div
      className={cx(
        "fixed inset-x-0 bottom-0 z-30 border-t bg-ink-900 shadow-[0_-20px_60px_-20px_rgb(0_0_0/0.8)] transition-colors lg:left-[220px]",
        active.length ? "border-safe/40" : "border-ink-700",
      )}
    >
      <button
        type="button"
        aria-expanded={open}
        aria-controls="jobs-list"
        onClick={() => onOpenChange(!open)}
        className="flex h-11 w-full items-center gap-4 px-5 text-left hover:bg-ink-850"
      >
        <span className="font-mono text-[0.7rem] uppercase tracking-[0.16em] text-ink-400">{t("jobs.title")}</span>
        {active.length > 0 ? (
          <span className="flex items-center gap-1.5 font-mono text-[0.7rem] text-safe-hi">
            <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-safe" />
            {t("jobs.active", { count: active.length })}
          </span>
        ) : (
          <span className="font-mono text-[0.7rem] text-ink-500">{jobs.length ? t("jobs.idle") : t("jobs.none")}</span>
        )}
        {lead && (
          <span className="flex min-w-0 flex-1 items-center gap-3">
            <span className="truncate text-[0.82rem] text-ink-200">{jobTitle(lead, t)}</span>
            {lead.progress && (
              <span className="flex w-40 shrink-0 items-center gap-2">
                <ProgressBar value={lead.progress.done} total={lead.progress.total} />
                <span className="font-mono text-[0.65rem] text-ink-400 tabular">
                  {lead.progress.done}/{lead.progress.total}
                </span>
              </span>
            )}
          </span>
        )}
        {!!error && <span className="ml-auto truncate text-[0.72rem] text-err">{errorMessage(error)}</span>}
        <span aria-hidden className={cx("ml-auto text-ink-400 transition-transform", open && "rotate-180")}>
          ▴
        </span>
      </button>
      {open && (
        <ul id="jobs-list" className="max-h-[45vh] overflow-y-auto border-t border-ink-800">
          {jobs.length === 0 && <li className="px-5 py-6 text-sm text-ink-500">{t("jobs.empty")}</li>}
          {jobs.map((j) => (
            <JobItem key={j.id} job={j} projectId={projectId} />
          ))}
        </ul>
      )}
    </div>
  );
}
