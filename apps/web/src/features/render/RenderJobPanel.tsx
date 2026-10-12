import { useEffect, useRef } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, qk } from "../../api/client";
import { isActive } from "../../api/hooks";
import type { Job } from "../../api/types";
import { Button, Chip, InlineError, ProgressBar } from "../../components/ui";
import { cx } from "../../lib/cx";
import { elapsed, formatClock } from "../../lib/format";

const TONE = { queued: "warn", running: "live", done: "ok", failed: "err", cancelled: "neutral" } as const;
const LABEL = { queued: "w kolejce", running: "renderuje", done: "gotowe", failed: "błąd", cancelled: "anulowany" } as const;

/** Big, always-expanded view of the current (or last) render job. */
export function RenderJobPanel({ job, projectId }: { job: Job; projectId: string }) {
  const qc = useQueryClient();
  const log = useRef<HTMLPreElement>(null);
  const active = isActive(job);
  const cancel = useMutation({
    mutationFn: () => api.cancelJob(job.id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: qk.jobs(projectId) }),
  });

  useEffect(() => {
    const el = log.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [job.log_tail]);

  const pct = job.progress && job.progress.total > 0 ? Math.round((job.progress.done / job.progress.total) * 100) : null;

  return (
    <section className={cx("overflow-hidden rounded-xl border", active ? "border-safe/50 bg-safe/[0.04]" : "border-ink-700 bg-ink-850")}>
      <div className="flex flex-wrap items-center gap-4 px-5 py-4">
        <Chip tone={TONE[job.status]}>{LABEL[job.status]}</Chip>
        <div className="min-w-0 flex-1">
          <div className="truncate text-[0.95rem]">{job.title}</div>
          <div className="truncate font-mono text-[0.75rem] text-ink-400">{job.message || "—"}</div>
        </div>
        {pct !== null && <div className="font-display text-5xl leading-none tabular text-ink-100">{pct}%</div>}
        <div className="text-right font-mono text-[0.7rem] text-ink-500 tabular">
          <div>start {formatClock(job.started)}</div>
          <div>{elapsed(job.started, job.finished)}</div>
        </div>
        {active && (
          <Button variant="danger" size="sm" busy={cancel.isPending} onClick={() => cancel.mutate()}>
            Przerwij render
          </Button>
        )}
      </div>
      {job.progress && (
        <div className="flex items-center gap-3 px-5 pb-4">
          <ProgressBar value={job.progress.done} total={job.progress.total} className="h-2" />
          <span className="shrink-0 font-mono text-[0.72rem] text-ink-400 tabular">
            {job.progress.done}/{job.progress.total}
          </span>
        </div>
      )}
      <InlineError error={cancel.error} />
      {job.log_tail.length > 0 && (
        <pre
          ref={log}
          className={cx(
            "overflow-auto border-t border-ink-800 bg-ink-950/80 px-5 py-3 font-mono text-[0.7rem] leading-relaxed text-ink-300",
            active ? "max-h-72" : "max-h-40",
          )}
        >
          {job.log_tail.join("\n")}
        </pre>
      )}
    </section>
  );
}
