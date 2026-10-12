import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, qk } from "../../api/client";
import { isActive } from "../../api/hooks";
import type { Job } from "../../api/types";
import { Button, Chip, InlineError, ProgressBar } from "../../components/ui";
import { elapsed, formatClock } from "../../lib/format";

const STATUS: Record<Job["status"], { label: string; tone: "live" | "ok" | "err" | "neutral" | "warn" }> = {
  queued: { label: "w kolejce", tone: "warn" },
  running: { label: "trwa", tone: "live" },
  done: { label: "gotowe", tone: "ok" },
  failed: { label: "błąd", tone: "err" },
  cancelled: { label: "anulowane", tone: "neutral" },
};

const KIND: Record<Job["kind"], string> = {
  analyze: "analiza",
  storyboard: "storyboard",
  character: "postać",
  keys_codex: "klatki codex",
  render: "render vast",
};

export function JobItem({ job, projectId, defaultOpen = false }: { job: Job; projectId: string; defaultOpen?: boolean }) {
  const qc = useQueryClient();
  const cancel = useMutation({
    mutationFn: () => api.cancelJob(job.id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: qk.jobs(projectId) }),
  });
  const st = STATUS[job.status];
  const active = isActive(job);

  return (
    <li className="border-b border-ink-800 px-5 py-3 last:border-b-0">
      <div className="flex items-center gap-3">
        <Chip tone={st.tone}>{st.label}</Chip>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <span className="truncate text-sm text-ink-100">{job.title}</span>
            <span className="shrink-0 font-mono text-[0.65rem] uppercase tracking-wider text-ink-500">{KIND[job.kind]}</span>
          </div>
          {job.message && <div className="truncate font-mono text-[0.72rem] text-ink-400">{job.message}</div>}
        </div>
        <div className="shrink-0 text-right font-mono text-[0.68rem] text-ink-500 tabular">
          <div>{formatClock(job.started)}</div>
          <div>{elapsed(job.started, job.finished)}</div>
        </div>
        {active && (
          <Button size="sm" variant="danger" busy={cancel.isPending} onClick={() => cancel.mutate()}>
            Anuluj
          </Button>
        )}
      </div>
      {job.progress && (
        <div className="mt-2 flex items-center gap-3">
          <ProgressBar value={job.progress.done} total={job.progress.total} />
          <span className="shrink-0 font-mono text-[0.68rem] text-ink-400 tabular">
            {job.progress.done}/{job.progress.total}
          </span>
        </div>
      )}
      <InlineError error={cancel.error} />
      {job.log_tail.length > 0 && (
        <details className="group mt-2" open={defaultOpen}>
          <summary className="w-fit list-none select-none text-[0.72rem] text-ink-500 hover:text-ink-200 [&::-webkit-details-marker]:hidden">
            <span className="inline-block transition-transform group-open:rotate-90">▸</span> log ({job.log_tail.length} linii)
          </summary>
          <pre className="mt-2 max-h-64 overflow-auto rounded-md border border-ink-800 bg-ink-950 p-3 font-mono text-[0.7rem] leading-relaxed text-ink-300">
            {job.log_tail.join("\n")}
          </pre>
        </details>
      )}
    </li>
  );
}
