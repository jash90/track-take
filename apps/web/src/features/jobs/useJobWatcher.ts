import { useEffect, useRef } from "react";
import { useQueryClient, type QueryKey } from "@tanstack/react-query";
import { qk } from "../../api/client";
import { isActive } from "../../api/hooks";
import type { Job, JobKind } from "../../api/types";
import { useToast } from "../../components/Toaster";
import { useT } from "../../i18n";
import { jobTitle } from "./jobTitle";

function keysFor(kind: JobKind, id: string): QueryKey[] {
  const common: QueryKey[] = [qk.project(id), qk.projects];
  switch (kind) {
    case "analyze":
      return [...common, qk.analysis(id), qk.peaks(id), qk.lyrics(id)];
    case "storyboard":
      return [...common, qk.storyboard(id)];
    case "character":
    case "keys_codex":
      return [...common, qk.keys(id)];
    case "render":
      return [...common, qk.videos(id), qk.keys(id), qk.vast, ["project", id, "estimate"]];
  }
}

/** Watches job transitions: invalidates related queries when a job finishes (and while keyframes trickle in). */
export function useJobWatcher(projectId: string, jobs: Job[]) {
  const qc = useQueryClient();
  const toast = useToast();
  const t = useT();
  const seen = useRef(new Map<string, { status: Job["status"]; done: number }>());

  useEffect(() => {
    const map = seen.current;
    for (const job of jobs) {
      const prev = map.get(job.id);
      const done = job.progress?.done ?? 0;
      if (prev) {
        const finished = !isActive(job) && (prev.status === "queued" || prev.status === "running");
        if (finished) {
          for (const key of keysFor(job.kind, projectId)) void qc.invalidateQueries({ queryKey: key });
          const title = jobTitle(job, t);
          if (job.status === "done") toast(t("job.toast.done", { title }), "ok");
          else if (job.status === "failed") toast(t("job.toast.failed", { title }), "err");
          else if (job.status === "cancelled") toast(t("job.toast.cancelled", { title }), "info");
        } else if (isActive(job) && done !== prev.done && (job.kind === "keys_codex" || job.kind === "character")) {
          // stream new thumbnails into the grid while the batch is running
          void qc.invalidateQueries({ queryKey: qk.keys(projectId) });
        }
      }
      map.set(job.id, { status: job.status, done });
    }
  }, [jobs, projectId, qc, toast, t]);
}
