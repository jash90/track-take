// API contract between the web UI and the tracktake backend (FastAPI, `uv run tracktake serve`, default :8770).
// All JSON. File URLs are relative to the backend origin (e.g. "/files/silence/full/codex/keys/s01_landscape.png").

export type KeySet = "codex" | "comfy";
export type Orientation = "landscape" | "portrait";
export type FormatName = "16x9" | "9x16";

export interface ProjectSettings {
  workers: number; // Vast cards for the render
  gpu: string; // e.g. "RTX_4090"
  gpus: number; // GPUs per machine (host); >1 = one machine with N GPUs, one model download
  max_dph: number; // USD per hour cap per GPU (a host with N GPUs may cost up to N × max_dph)
  captions: boolean; // karaoke lyrics burned into the video (default true)
  region?: string; // "US" (default) | "US,CA" | "any" | comma list of country codes; falls back to anywhere when no offer
  beat_motion: boolean; // camera pump on downbeats + shake on snares (default true)
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
  storyboard_approved?: boolean; // reset to false when the storyboard is (re)planned or (re)written
  autopilot?: Autopilot | Record<string, never>; // {} when never started
}

export type RenderPresetId = "cheapest" | "recommended" | "fastest";
/** what the user picked: one of the presets, or "custom" = the project's saved gpu/gpus/max_dph/workers */
export type PresetChoice = RenderPresetId | "custom";
// "review" = waiting for the storyboard approval; "check" = visual keyframe continuity check (keys_check)
export type AutopilotStage = "analyze" | "plan" | "write" | "review" | "character" | "keys" | "check" | "render";
export type AutopilotState = "running" | "awaiting_storyboard" | "awaiting_budget" | "done" | "failed" | "cancelled";
export interface Autopilot {
  state: AutopilotState;
  stage: AutopilotStage | null;
  job: string | null;
  budget_usd: number;
  preset: PresetChoice;
  review: boolean;
  estimate_usd?: number;
  estimate_minutes?: number;
  error?: string;
  updated: string;
}
export interface AutopilotPayload {
  budget_usd: number;
  preset: PresetChoice;
  review: boolean;
  approve?: boolean;
}
// POST /api/projects/{id}/autopilot AutopilotPayload -> Job (kind "autopilot"); runs only the missing steps

export interface RenderPreset {
  id: RenderPresetId;
  gpu: string;
  label: string;
  gpus: number;
  workers: number;
  minutes: number;
  minutes_max?: number; // upper bound if a host fails to start
  usd: number;
  speed: number;
  speed_measured: boolean;
  max_dph: number;
}
export interface RenderPresets {
  clips: number;
  estimated_clips: boolean; // guessed from song length before the storyboard exists
  presets: RenderPreset[]; // cheapest / recommended / fastest, [] when no offers
}
// GET /api/projects/{id}/render-presets -> RenderPresets

export type SetupCheck = "claude" | "codex" | "codex_login" | "ffmpeg" | "vast_key" | "ssh_key" | "ssh_key_on_vast";
export interface Setup {
  checks: Record<SetupCheck, boolean | null>;
  ready: boolean;
}
// GET /api/setup -> Setup ; POST /api/setup/ssh-key -> Setup

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
  location?: string; // location id from Storyboard.locations
  props?: string[]; // prop ids from Storyboard.props
  cut?: boolean; // true = shot starts with a hard cut (may change place); false = continues the previous shot (same take: its keyframe is drawn from the previous keyframe and the previous clip is animated to land exactly on it). Missing = cut (old storyboards). s01 is always a cut.
}
/** World bible entry: a recurring place or object with a fixed look, kept verbatim in every prompt. */
export interface WorldItem {
  id: string;
  name: string;
  look: string;
}
export interface ContinuityIssue {
  shot: string;
  problem: string;
  before: string; // scene text before the fix
}
export interface Storyboard {
  style: string;
  heroine: string; // character description used in every prompt
  shots: Shot[];
  locations?: WorldItem[];
  props?: WorldItem[];
  continuity?: { checked: string; issues: ContinuityIssue[] };
}
// POST /api/projects/{id}/storyboard/check -> Job (kind "continuity")
// GET /api/projects/{id}/storyboard -> Storyboard (404 if none)
// PUT /api/projects/{id}/storyboard Storyboard -> Storyboard
// POST /api/projects/{id}/storyboard/plan -> Storyboard  (cut on downbeats, 2 bars/shot; keeps texts of unchanged shots)
// POST /api/projects/{id}/storyboard/write {shots?: string[], instructions?: string} -> Job  (director writes scene+motion)

export interface ShotKeys {
  landscape: string | null; // URL of the full-size PNG
  portrait: string | null;
  landscape_thumb: string | null; // small JPEG for grids
  portrait_thumb: string | null;
  // set=codex only: drawn before its scene / the world bible / the keyframe it is drawn after changed → no longer matches
  landscape_stale?: boolean;
  portrait_stale?: boolean;
  // set=codex only: correction note left by the keyframe check, still pending — the keyframe is stale and will be redrawn
  landscape_issue?: string | null;
  portrait_issue?: string | null;
  // set=codex only: mirrored automatically by the keyframe check (the original is kept as *.orig.png)
  landscape_flipped?: boolean;
  portrait_flipped?: boolean;
}
export type KeyCheckKind = "mirrored" | "object" | "count" | "character" | "place" | "other";
export interface KeyCheckIssue {
  shot: string;
  kind: KeyCheckKind;
  problem: string;
  fix: string; // correction for the image model that redraws it
}
/** Last visual keyframe continuity check (a vision model compares the pictures of each location / continuous take). */
export interface KeyCheck {
  checked: string; // ISO date
  orientation: Orientation;
  issues: KeyCheckIssue[];
}
export interface Keys {
  character_sheet: string | null;
  sets: Record<KeySet, Record<string, ShotKeys>>; // shot id -> keys
  check?: KeyCheck | null; // null until the first check
}
// GET /api/projects/{id}/keys -> Keys
// POST /api/projects/{id}/keys/check {redraw?: boolean = true} -> Job (kind "keys_check", params {redraw}); 409 while running.
//   Mirrored frames are flipped; others get a correction note (stale) and, with redraw, are redrawn and re-checked (≤3 rounds).
// POST /api/projects/{id}/character {force?: boolean} -> Job  (Codex character sheet from cover + heroine text)
// POST /api/projects/{id}/keys/codex {shots?: string[], force?: boolean, workers?: number} -> Job  (project orientation only;
//   without shots: draws the missing AND redraws the stale ones — job params {missing, stale})

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
  stale_keys: number; // set=codex keyframes drawn before their scene/world changed (render still runs, with the old images)
  alternatives: { workers: number; minutes: number; minutes_max?: number; usd: number }[]; // same job with 1/2/4 cards: fewer = cheaper, slower
  minutes_max?: number; // upper bound if a host fails to start and a spare takes over
  gpu: string;
  gpus: number;
  speed: number; // clip speed vs an RTX 4090
  speed_measured: boolean; // false = estimated from Vast DLPerf
  no_offers: boolean; // nothing matches under max_dph
  max_dph: number;
}
// GET /api/projects/{id}/estimate?set=codex&workers=4[&gpu=RTX_5090&gpus=2&max_dph=0.6] -> Estimate

export interface VastHost {
  gpus: number; // GPUs in the machine
  offers: number;
  min_dph: number; // USD/h for the whole host
}
export interface VastGpu {
  gpu: string; // value to save, e.g. "RTX_5090"
  label: string; // "RTX 5090"
  vram_gb: number;
  suitable: boolean; // >= min VRAM and Ampere or newer
  offers: number; // all rentable
  matching: number; // pass host filters (reliability, network, download price, CUDA)
  min_dph_per_gpu: number;
  median_dph_per_gpu: number;
  hosts: VastHost[];
  speed: number; // vs RTX 4090
  speed_measured: boolean;
  usd_per_4090_hour: number | null; // lower = cheaper video
  in_region?: boolean; // false = no matching offer in the region; numbers come from the "anywhere" fallback
}
export interface VastGpus {
  min_vram_gb: number;
  regions?: string[];
  filters: { min_reliability: number; max_download_usd_per_gb: number; min_inet_down_mbps: number };
  gpus: VastGpu[];
}
// GET /api/vast/gpus -> VastGpus (cached ~5 min server-side)
// GET /api/projects/{id}/estimate?set=codex&workers=4 -> Estimate
// POST /api/projects/{id}/render {set: KeySet, workers: number, gpu?: string, max_dph?: number, masters?: boolean, confirm: true} -> Job

export interface VastStatus {
  configured: boolean; // API key present
  balance: number | null; // USD
  instances: VastInstance[];
  error?: string;
}
// GET /api/vast -> VastStatus

export interface VastInstance {
  id: number;
  name: string;
  gpu: string;
  status: string;
  dph: number;
  gpus?: number; // GPUs in this machine
  location?: string; // e.g. "New York, US"
  known?: boolean; // started by this app; false = rented elsewhere or orphaned
  in_use?: boolean; // used by a running render
  job?: string | null; // id of the running render job using it
  project?: string | null;
}
// POST /api/vast/instances/{id}/down?force=false -> {freed: id, usd}; 409 {detail} when in use (unless force=true)
// POST /api/vast/key {key: string} -> VastStatus   (stores it like `vastai set api-key`, never echoed back)
// POST /api/vast/down -> {freed: number, usd: number}

export type JobKind = "analyze" | "storyboard" | "character" | "keys_codex" | "keys_check" | "render" | "autopilot" | "continuity";
export type JobStatus = "queued" | "running" | "done" | "failed" | "cancelled";
export interface Job {
  id: string;
  kind: JobKind;
  project: string;
  status: JobStatus;
  title: string; // English fallback; the UI builds a localised title from kind + params
  params: Record<string, number | string>; // e.g. {shots: 45} | {missing: 12} | {set: "codex", workers: 2}; may be {} for old jobs
  progress: { done: number; total: number } | null;
  message: string; // last meaningful line
  started: string | null;
  finished: string | null;
  log_tail: string[]; // last ~40 log lines
}
// GET /api/jobs?project={id} -> Job[]   (newest first)
// GET /api/jobs/{job_id} -> Job
// POST /api/jobs/{job_id}/cancel -> Job
