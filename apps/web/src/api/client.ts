import type {
  Analysis,
  Estimate,
  Job,
  KeySet,
  Keys,
  Orientation,
  Project,
  ProjectSettings,
  Storyboard,
  VastStatus,
  Videos,
} from "./types";

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

export function isNotFound(err: unknown): boolean {
  return err instanceof ApiError && err.status === 404;
}

async function readError(res: Response): Promise<string> {
  const text = await res.text().catch(() => "");
  if (!text) return `${res.status} ${res.statusText}`;
  try {
    const body: unknown = JSON.parse(text);
    if (body && typeof body === "object" && "detail" in body) {
      const detail = (body as { detail: unknown }).detail;
      if (typeof detail === "string") return detail;
      return JSON.stringify(detail);
    }
  } catch {
    /* not JSON */
  }
  return text.slice(0, 400);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) throw new ApiError(res.status, await readError(res));
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: body === undefined ? undefined : JSON.stringify(body),
});

const p = (id: string) => `/api/projects/${encodeURIComponent(id)}`;

export interface InputsPayload {
  song?: File;
  cover?: File;
  lyrics?: string;
}

export interface WritePayload {
  shots?: string[];
  instructions?: string;
}

/** Backend draws only the project orientation. */
export interface CodexKeysPayload {
  shots?: string[];
  force?: boolean;
  workers?: number;
}

export interface RenderPayload {
  set: KeySet;
  workers: number;
  gpu?: string;
  max_dph?: number;
  masters?: boolean;
  confirm: true;
}

export const api = {
  projects: () => request<Project[]>("/api/projects"),
  project: (id: string) => request<Project>(p(id)),
  createProject: (payload: { name: string; orientation: Orientation; style?: string; language?: string }) =>
    request<Project>("/api/projects", json("POST", payload)),
  patchProject: (
    id: string,
    patch: Partial<{ name: string; style: string; language: string; settings: ProjectSettings; orientation: Orientation }>,
  ) => request<Project>(p(id), json("PATCH", patch)),
  deleteProject: (id: string) => request<{ ok: true }>(p(id), { method: "DELETE" }),
  uploadInputs: (id: string, payload: InputsPayload) => {
    const form = new FormData();
    if (payload.song) form.append("song", payload.song);
    if (payload.cover) form.append("cover", payload.cover);
    if (payload.lyrics !== undefined) form.append("lyrics", payload.lyrics);
    return request<Project>(`${p(id)}/inputs`, { method: "POST", body: form });
  },
  lyrics: (id: string) => request<{ text: string }>(`${p(id)}/lyrics`),

  analyze: (id: string) => request<Job>(`${p(id)}/analyze`, { method: "POST" }),
  analysis: (id: string) => request<Analysis>(`${p(id)}/analysis`),
  peaks: (id: string, n = 1500) =>
    request<{ duration: number; peaks: number[] }>(`${p(id)}/peaks?n=${n}`),

  storyboard: (id: string) => request<Storyboard>(`${p(id)}/storyboard`),
  saveStoryboard: (id: string, doc: Storyboard) =>
    request<Storyboard>(`${p(id)}/storyboard`, json("PUT", doc)),
  planStoryboard: (id: string) =>
    request<Storyboard>(`${p(id)}/storyboard/plan`, { method: "POST" }),
  writeStoryboard: (id: string, payload: WritePayload) =>
    request<Job>(`${p(id)}/storyboard/write`, json("POST", payload)),

  keys: (id: string) => request<Keys>(`${p(id)}/keys`),
  character: (id: string, force: boolean) =>
    request<Job>(`${p(id)}/character`, json("POST", { force })),
  codexKeys: (id: string, payload: CodexKeysPayload) =>
    request<Job>(`${p(id)}/keys/codex`, json("POST", payload)),

  videos: (id: string) => request<Videos>(`${p(id)}/videos`),
  estimate: (id: string, set: KeySet, workers: number) =>
    request<Estimate>(`${p(id)}/estimate?set=${set}&workers=${workers}`),
  render: (id: string, payload: RenderPayload) =>
    request<Job>(`${p(id)}/render`, json("POST", payload)),

  vast: () => request<VastStatus>("/api/vast"),
  vastKey: (key: string) => request<VastStatus>("/api/vast/key", json("POST", { key })),
  vastDown: () => request<{ freed: number; usd: number }>("/api/vast/down", { method: "POST" }),

  jobs: (project?: string) =>
    request<Job[]>(project ? `/api/jobs?project=${encodeURIComponent(project)}` : "/api/jobs"),
  job: (jobId: string) => request<Job>(`/api/jobs/${encodeURIComponent(jobId)}`),
  cancelJob: (jobId: string) =>
    request<Job>(`/api/jobs/${encodeURIComponent(jobId)}/cancel`, { method: "POST" }),
};

/** Query keys, centralised so invalidation stays consistent. */
export const qk = {
  projects: ["projects"] as const,
  project: (id: string) => ["project", id] as const,
  lyrics: (id: string) => ["project", id, "lyrics"] as const,
  analysis: (id: string) => ["project", id, "analysis"] as const,
  peaks: (id: string) => ["project", id, "peaks"] as const,
  storyboard: (id: string) => ["project", id, "storyboard"] as const,
  keys: (id: string) => ["project", id, "keys"] as const,
  videos: (id: string) => ["project", id, "videos"] as const,
  estimate: (id: string, set: KeySet, workers: number) =>
    ["project", id, "estimate", set, workers] as const,
  jobs: (id: string) => ["jobs", id] as const,
  vast: ["vast"] as const,
};
