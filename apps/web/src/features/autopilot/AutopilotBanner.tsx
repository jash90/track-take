import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router";
import { api, qk } from "../../api/client";
import { isActive, useStartJob } from "../../api/hooks";
import type { Autopilot, AutopilotPayload, Job, Project } from "../../api/types";
import { useToast } from "../../components/Toaster";
import { Button, InlineError, ProgressBar } from "../../components/ui";
import { useT } from "../../i18n";
import { cx } from "../../lib/cx";
import { errorMessage, formatUsd } from "../../lib/format";
import { isStage, stageLabel } from "../jobs/jobTitle";
import type { MakeVideoInitial } from "./MakeVideoDialog";

export function autopilotOf(p: Project): Autopilot | null {
  return p.autopilot && "state" in p.autopilot ? (p.autopilot as Autopilot) : null;
}

const roundUp = (usd: number, step: number) => Math.round(Math.ceil(usd / step - 1e-9) * step * 100) / 100;

interface Props {
  project: Project;
  jobs: Job[];
  onChangePreset: (initial: MakeVideoInitial) => void;
}

/** Top-of-workspace status of the "make the video" autopilot, with the one action that moves it forward. */
export function AutopilotBanner({ project, jobs, onChangePreset }: Props) {
  const t = useT();
  const qc = useQueryClient();
  const toast = useToast();
  const ap = autopilotOf(project);
  const job = jobs.find((j) => j.kind === "autopilot" && isActive(j));

  const post = useStartJob(
    project.id,
    (payload: AutopilotPayload) => api.autopilot(project.id, payload),
    () => void qc.invalidateQueries({ queryKey: qk.project(project.id) }),
  );
  const stop = useMutation({
    mutationFn: (id: string) => api.cancelJob(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: qk.jobs(project.id) });
      void qc.invalidateQueries({ queryKey: qk.project(project.id) });
    },
    onError: (err) => toast(errorMessage(err), "err"),
  });

  const state = job ? "running" : ap?.state;
  if (!state || state === "done" || state === "cancelled") return null;
  const base: AutopilotPayload = { budget_usd: ap?.budget_usd ?? 1, preset: ap?.preset ?? "recommended", review: ap?.review ?? true };

  const stageRaw = job?.params?.stage ?? ap?.stage;
  const stage = isStage(stageRaw) ? stageLabel(stageRaw, t, job?.progress) : null;
  const tone = state === "failed" ? "err" : state === "running" ? "live" : "ask";

  let title: string;
  let sub: string | null = null;
  let actions: React.ReactNode = null;
  if (state === "running") {
    title = stage ? t("ap.running", { stage }) : t("ap.starting");
    actions = job && (
      <Button size="sm" variant="danger" busy={stop.isPending} onClick={() => stop.mutate(job.id)}>
        {t("ap.stop")}
      </Button>
    );
  } else if (state === "awaiting_storyboard") {
    title = t("ap.awaitingStoryboard");
    sub = t("ap.awaitingStoryboardSub");
    actions = (
      <>
        <Link to={`/p/${encodeURIComponent(project.id)}/storyboard`} className="text-sm text-ink-200 underline-offset-4 hover:underline">
          {t("ap.toStoryboard")}
        </Link>
        <Button variant="primary" busy={post.isPending} onClick={() => post.mutate({ ...base, approve: true })}>
          {t("ap.approve")}
        </Button>
      </>
    );
  } else if (state === "awaiting_budget") {
    const est = ap?.estimate_usd ?? 0;
    const needed = roundUp(est, 0.05);
    title = t("ap.awaitingBudget", { usd: formatUsd(est), budget: formatUsd(ap?.budget_usd) });
    sub = t("ap.awaitingBudgetSub");
    actions = (
      <>
        <Button variant="ghost" onClick={() => onChangePreset({ preset: base.preset, review: base.review })}>
          {t("ap.changePreset")}
        </Button>
        <Button variant="primary" busy={post.isPending} onClick={() => post.mutate({ ...base, budget_usd: needed })}>
          {t("ap.renderFor", { usd: formatUsd(est) })}
        </Button>
      </>
    );
  } else {
    title = t("ap.failed");
    sub = ap?.error ?? null;
    actions = (
      <Button variant="primary" busy={post.isPending} onClick={() => post.mutate(base)}>
        {t("ap.retry")}
      </Button>
    );
  }

  return (
    <section
      aria-live="polite"
      className={cx(
        "mb-6 rounded-xl border px-5 py-4",
        tone === "live" && "border-safe/50 bg-safe/[0.06]",
        tone === "ask" && "border-ok/50 bg-ok/[0.06]",
        tone === "err" && "border-err/50 bg-err/[0.06]",
      )}
    >
      <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
        <div className="min-w-0 flex-1">
          <div className="eyebrow flex items-center gap-2">
            {tone === "live" && <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-safe" />}
            {t("ap.eyebrow")}
          </div>
          <div className="mt-0.5 font-display text-[1.6rem] leading-tight">{title}</div>
          {sub && <p className="mt-0.5 text-[0.82rem] text-ink-400">{sub}</p>}
          {state === "running" && job?.message && <p className="mt-0.5 truncate font-mono text-[0.72rem] text-ink-500">{job.message}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-3">{actions}</div>
      </div>
      {state === "running" && job?.progress && <ProgressBar className="mt-3" value={job.progress.done} total={job.progress.total} />}
      <InlineError error={post.error} />
    </section>
  );
}
