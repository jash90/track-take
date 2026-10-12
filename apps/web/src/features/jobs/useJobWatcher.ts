import { useEffect, useRef } from "react";
import { useQueryClient, type QueryKey } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { api, qk } from "../../api/client";
import { isActive } from "../../api/hooks";
import type { Job, JobKind } from "../../api/types";
import { useToast } from "../../components/Toaster";
import { useT } from "../../i18n";
import { jobTitle } from "./jobTitle";

function keysFor(kind: JobKind, id: string): QueryKey[] {
  const common: QueryKey[] = [qk.project(id), qk.projects];
  const estimate: QueryKey = ["project", id, "estimate"];
  switch (kind) {
    case "analyze":
      return [...common, qk.analysis(id), qk.peaks(id), qk.lyrics(id), qk.renderPresets(id)];
    // new scene texts can make drawn keyframes stale
    case "storyboard":
      return [...common, qk.storyboard(id), qk.renderPresets(id), qk.keys(id), estimate];
    case "continuity":
      return [...common, qk.storyboard(id), qk.keys(id), estimate];
    case "character":
      return [...common, qk.keys(id)];
    case "keys_codex":
    // flips mirrored keyframes, leaves correction notes (stale) and redraws them
    case "keys_check":
      return [...common, qk.keys(id), estimate];
    case "render":
      return [...common, qk.videos(id), qk.keys(id), qk.vast, estimate];
    case "autopilot":
      return [
        ...common,
        qk.analysis(id),
        qk.peaks(id),
        qk.lyrics(id),
        qk.storyboard(id),
        qk.keys(id),
        qk.videos(id),
        qk.vast,
        qk.renderPresets(id),
        estimate,
      ];
  }
}

interface Seen {
  status: Job["status"];
  done: number;
  stage: unknown;
}

/**
 * Watches job transitions: refreshes related data when a job finishes or the autopilot moves to the next stage,
 * streams keyframes in while they are drawn, and jumps to the Result step when a video is finished.
 */
export function useJobWatcher(projectId: string, jobs: Job[]) {
  const qc = useQueryClient();
  const toast = useToast();
  const t = useT();
  const navigate = useNavigate();
  const seen = useRef(new Map<string, Seen>());

  useEffect(() => {
    const map = seen.current;
    const refresh = (kind: JobKind) => {
      for (const key of keysFor(kind, projectId)) void qc.invalidateQueries({ queryKey: key });
    };
    for (const job of jobs) {
      const prev = map.get(job.id);
      const done = job.progress?.done ?? 0;
      const stage = job.params?.stage;
      if (prev) {
        const finished = !isActive(job) && (prev.status === "queued" || prev.status === "running");
        if (finished) {
          refresh(job.kind);
          const title = jobTitle(job, t);
          if (job.kind === "autopilot") {
            if (job.status === "done") {
              // the autopilot also "finishes" when it stops for a review or a budget decision — check the project
              void qc.fetchQuery({ queryKey: qk.project(projectId), queryFn: () => api.project(projectId), staleTime: 0 }).then((p) => {
                if (p.autopilot && "state" in p.autopilot && p.autopilot.state === "done") {
                  toast(t("ap.doneToast"), "ok");
                  navigate(`/p/${encodeURIComponent(projectId)}/wynik`);
                }
              });
            } else if (job.status === "failed") toast(t("job.toast.failed", { title }), "err");
            else if (job.status === "cancelled") toast(t("ap.stoppedToast"), "info");
          } else if (job.status === "done") {
            if (job.kind === "render") {
              toast(t("render.doneToast"), "ok");
              navigate(`/p/${encodeURIComponent(projectId)}/wynik`);
            } else toast(t("job.toast.done", { title }), "ok");
          } else if (job.status === "failed") toast(t("job.toast.failed", { title }), "err");
          else if (job.status === "cancelled") toast(t("job.toast.cancelled", { title }), "info");
        } else if (isActive(job)) {
          if (job.kind === "autopilot" && stage !== prev.stage) refresh("autopilot");
          const drawing =
            job.kind === "keys_codex" ||
            job.kind === "keys_check" ||
            job.kind === "character" ||
            (job.kind === "autopilot" && (stage === "keys" || stage === "character" || stage === "check"));
          if (drawing && done !== prev.done) void qc.invalidateQueries({ queryKey: qk.keys(projectId) });
        }
      }
      map.set(job.id, { status: job.status, done, stage });
    }
  }, [jobs, projectId, qc, toast, t, navigate]);
}
