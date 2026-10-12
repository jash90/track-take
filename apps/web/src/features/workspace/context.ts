import { createContext, useContext } from "react";
import type { Job, Project } from "../../api/types";
import type { MakeVideoInitial } from "../autopilot/MakeVideoDialog";

export interface WorkspaceValue {
  project: Project;
  jobs: Job[];
  openJobs: () => void;
  /** Opens the "Make the video" dialog (autopilot). */
  openMakeVideo: (initial?: MakeVideoInitial) => void;
}

export const WorkspaceCtx = createContext<WorkspaceValue | null>(null);

export function useWorkspace(): WorkspaceValue {
  const v = useContext(WorkspaceCtx);
  if (!v) throw new Error("useWorkspace outside WorkspacePage");
  return v;
}

/** The newest queued/running job of one of the given kinds. */
export function activeJob(jobs: Job[], ...kinds: Job["kind"][]): Job | undefined {
  return jobs.find((j) => kinds.includes(j.kind) && (j.status === "queued" || j.status === "running"));
}
