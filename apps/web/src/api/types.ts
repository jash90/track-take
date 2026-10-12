// API contract between the web UI and the sunomv backend (FastAPI, `uv run sunomv serve`, default :8770).
// All JSON. File URLs are relative to the backend origin (e.g. "/files/silence/full/codex/keys/s01_landscape.png").

export type KeySet = "codex" | "comfy";
export type Orientation = "landscape" | "portrait";
export type FormatName = "16x9" | "9x16";

export interface ProjectSettings {
  workers: number; // Vast cards for the render
  gpu: string; // e.g. "RTX_4090"
  max_dph: number; // USD per hour cap per card
}

export interface Project {
  id: string;
  name: string;
  orientation: Orientation; // chosen at creation: landscape = 16:9 video, portrait = 9:16 video (one per project)
  format: FormatName; // derived from orientation: "16x9" | "9x16"
  created: string; // ISO date
  style: string; // free text style of the video, e.g. "paper cut-out stop-motion, rainy night"
  language: string; // lyrics language, "en" | "pl" | ...
  inputs: { song: string | null; cover: string | null; lyrics: boolean }; // song/cover = file URLs
  stage: {
    analysis: boolean;
    storyboard: boolean; // storyboard exists
    storyboard_written: number; // shots that have a scene text
    shots: number; // total shots in the storyboard
    character_sheet: string | null; // URL
    keys: Record<KeySet, number>; // keyframes present per set in the project orientation (out of shots)
    videos: Record<KeySet, FormatName[]>; // formats rendered per set
  };
  settings: ProjectSettings;
}

// GET /api/projects -> Project[]
// POST /api/projects {name: string, orientation: Orientation, style?: string, language?: string} -> Project
// GET /api/projects/{id} -> Project
// PATCH /api/projects/{id} Partial<{name, style, language, settings, orientation}> -> Project
//   (changing orientation later is allowed; keyframes/videos of the other orientation are kept but not shown)
// DELETE /api/projects/{id} -> {ok: true}
// POST /api/projects/{id}/inputs  multipart/form-data: song?: File, cover?: File, lyrics?: string -> Project
// GET /api/projects/{id}/lyrics -> {text: string}

export interface Section {
  label: string; // "Verse 1", "Chorus"
  kind: string; // intro|verse|pre_chorus|chorus|build|break|bridge|breakdown|outro|other
  start: number; // seconds
  end: number;
}
export interface LyricLine {
  text: string;
  start: number;
  end: number;
}
export interface Analysis {
  duration: number;
  bpm: number;
  beats: number[];
  downbeats: number[];
  sections: Section[];
  lines: LyricLine[];
}
// POST /api/projects/{id}/analyze -> Job
// GET /api/projects/{id}/analysis -> Analysis (404 until analysed)
// GET /api/projects/{id}/peaks?n=1500 -> {duration: number, peaks: number[]}  (0..1, mono mix)

export interface Shot {
  id: string; // "s01"
  start: number;
  end: number;
  section: string;
  kind: string;
  lines: string[]; // lyric lines sung in this shot
  scene: string; // what the keyframe shows (whole scene, character included)
  motion: string; // what moves in the clip
  hints?: string[]; // non-structural Suno tags of the section, e.g. "Rain" (kept as is)
  cut?: boolean; // true = shot starts with a hard cut (may change place); false = continues the previous shot (same take: its keyframe is drawn from the previous keyframe and the previous clip is animated to land exactly on it). Missing = cut (old storyboards). s01 is always a cut.
}
export interface Storyboard {
  style: string;
  heroine: string; // character description used in every prompt
  shots: Shot[];
}
// GET /api/projects/{id}/storyboard -> Storyboard (404 if none)
// PUT /api/projects/{id}/storyboard Storyboard -> Storyboard
// POST /api/projects/{id}/storyboard/plan -> Storyboard  (cut on downbeats, 2 bars/shot; keeps texts of unchanged shots)
// POST /api/projects/{id}/storyboard/write {shots?: string[], instructions?: string} -> Job  (director writes scene+motion)

export interface ShotKeys {
  landscape: string | null; // URL of the full-size PNG
  portrait: string | null;
  landscape_thumb: string | null; // small JPEG for grids
  portrait_thumb: string | null;
}
export interface Keys {
  character_sheet: string | null;
  sets: Record<KeySet, Record<string, ShotKeys>>; // shot id -> keys
}
// GET /api/projects/{id}/keys -> Keys
// POST /api/projects/{id}/character {force?: boolean} -> Job  (Codex character sheet from cover + heroine text)
// POST /api/projects/{id}/keys/codex {shots?: string[], force?: boolean, workers?: number} -> Job  (project orientation only)

export interface VideoFiles {
  preview: string | null; // small HEVC (<50 MB) URL
  master: string | null; // full quality URL
  size_mb: { preview?: number; master?: number };
}
export type Videos = Record<KeySet, Partial<Record<FormatName, VideoFiles>>>;
// GET /api/projects/{id}/videos -> Videos

export interface Offer {
  id: number;
  gpu: string;
  dph: number;
  download_usd: number;
  inet_down: number;
  location: string;
}
export interface Estimate {
  set: KeySet;
  workers: number;
  clips: number; // = shots (one orientation)
  minutes: number;
  usd: number;
  models_gb: number;
  offers: Offer[]; // cheapest matching offers right now
  missing_keys: number; // keyframes still missing for set=codex (render refuses while > 0)
  alternatives: { workers: number; minutes: number; usd: number }[]; // same job with 1/2/4 cards: fewer = cheaper, slower
}
// GET /api/projects/{id}/estimate?set=codex&workers=4 -> Estimate
// POST /api/projects/{id}/render {set: KeySet, workers: number, gpu?: string, max_dph?: number, masters?: boolean, confirm: true} -> Job

export interface VastStatus {
  configured: boolean; // API key present
  balance: number | null; // USD
  instances: { id: number; name: string; gpu: string; status: string; dph: number }[];
  error?: string;
}
// GET /api/vast -> VastStatus
// POST /api/vast/key {key: string} -> VastStatus   (stores it like `vastai set api-key`, never echoed back)
// POST /api/vast/down -> {freed: number, usd: number}

export type JobKind = "analyze" | "storyboard" | "character" | "keys_codex" | "render";
export type JobStatus = "queued" | "running" | "done" | "failed" | "cancelled";
export interface Job {
  id: string;
  kind: JobKind;
  project: string;
  status: JobStatus;
  title: string; // human readable, Polish
  progress: { done: number; total: number } | null;
  message: string; // last meaningful line
  started: string | null;
  finished: string | null;
  log_tail: string[]; // last ~40 log lines
}
// GET /api/jobs?project={id} -> Job[]   (newest first)
// GET /api/jobs/{job_id} -> Job
// POST /api/jobs/{job_id}/cancel -> Job
