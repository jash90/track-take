import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, isNotFound, qk, type EstimateChoice } from "./client";
import type { Job, KeySet } from "./types";

const ACTIVE: ReadonlySet<Job["status"]> = new Set(["queued", "running"]);
export const isActive = (j: Job) => ACTIVE.has(j.status);

/** Retry transient errors but never 404s (which mean "not created yet"). */
const retryUnless404 = (count: number, err: unknown) => !isNotFound(err) && count < 2;

export function useProjects() {
  return useQuery({ queryKey: qk.projects, queryFn: api.projects });
}

export function useProject(id: string) {
  return useQuery({ queryKey: qk.project(id), queryFn: () => api.project(id), retry: retryUnless404 });
}

export function useLyrics(id: string, enabled: boolean) {
  return useQuery({
    queryKey: qk.lyrics(id),
    queryFn: () => api.lyrics(id),
    enabled,
    retry: retryUnless404,
  });
}

/** `enabled` should follow Project.stage so we don't fire requests that are known to 404. */
export function useAnalysis(id: string, enabled = true) {
  return useQuery({ queryKey: qk.analysis(id), queryFn: () => api.analysis(id), retry: retryUnless404, enabled });
}

export function usePeaks(id: string, enabled: boolean) {
  return useQuery({
    queryKey: qk.peaks(id),
    queryFn: () => api.peaks(id, 1500),
    enabled,
    retry: retryUnless404,
    staleTime: 5 * 60_000,
  });
}

export function useStoryboard(id: string, enabled = true) {
  return useQuery({ queryKey: qk.storyboard(id), queryFn: () => api.storyboard(id), retry: retryUnless404, enabled });
}

export function useKeys(id: string) {
  return useQuery({ queryKey: qk.keys(id), queryFn: () => api.keys(id), retry: retryUnless404 });
}

export function useVideos(id: string) {
  return useQuery({ queryKey: qk.videos(id), queryFn: () => api.videos(id), retry: retryUnless404 });
}

export function useEstimate(id: string, set: KeySet, workers: number, enabled: boolean, choice: EstimateChoice = {}) {
  return useQuery({
    queryKey: qk.estimate(id, set, workers, choice),
    queryFn: () => api.estimate(id, set, workers, choice),
    enabled,
    staleTime: 60_000,
    placeholderData: (prev) => prev,
  });
}

export function useRenderPresets(id: string, enabled = true) {
  return useQuery({ queryKey: qk.renderPresets(id), queryFn: () => api.renderPresets(id), enabled, staleTime: 60_000, retry: 1 });
}

export function useSetup(enabled = true) {
  return useQuery({ queryKey: qk.setup, queryFn: api.setup, enabled, staleTime: 30_000, retry: 1 });
}

/** The animation styles the backend knows (static: cached for the session). */
export function useAnimations() {
  return useQuery({ queryKey: qk.animations, queryFn: api.animations, staleTime: Infinity, retry: 1 });
}

export function useVastGpus(region?: string) {
  return useQuery({ queryKey: qk.vastGpus(region), queryFn: () => api.vastGpus(region), staleTime: 5 * 60_000, retry: 1 });
}

export function useVast(poll = false) {
  return useQuery({
    queryKey: qk.vast,
    queryFn: api.vast,
    refetchInterval: poll ? 30_000 : false,
    retry: 1,
  });
}

/** Jobs of one project. Polls fast while anything is queued/running. */
export function useProjectJobs(id: string) {
  return useQuery({
    queryKey: qk.jobs(id),
    queryFn: () => api.jobs(id),
    refetchInterval: (query) => (query.state.data?.some(isActive) ? 2000 : 10_000),
    refetchIntervalInBackground: false,
  });
}

/** Wraps a mutation that starts a backend Job: refreshes the jobs list right away. */
export function useStartJob<TVars>(projectId: string, fn: (vars: TVars) => Promise<Job>, onStarted?: (job: Job) => void) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (job) => {
      qc.setQueryData<Job[]>(qk.jobs(projectId), (prev) =>
        prev ? [job, ...prev.filter((j) => j.id !== job.id)] : [job],
      );
      void qc.invalidateQueries({ queryKey: qk.jobs(projectId) });
      onStarted?.(job);
    },
  });
}

/** POST keys/check: the vision model's keyframe continuity check (flips mirrored frames, redraws wrong ones). */
export function useCheckKeys(projectId: string, onStarted?: (job: Job) => void) {
  return useStartJob(projectId, (redraw: boolean = true) => api.checkKeys(projectId, redraw), onStarted);
}
