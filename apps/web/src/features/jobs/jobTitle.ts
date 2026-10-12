import type { Job } from "../../api/types";
import type { TFn } from "../../i18n";

const num = (v: unknown): number | null => {
  const n = typeof v === "string" ? Number(v) : v;
  return typeof n === "number" && Number.isFinite(n) ? n : null;
};
const setName = (v: unknown) => (v === "comfy" ? "ComfyUI" : v === "codex" ? "Codex" : typeof v === "string" ? v : null);

/** Localised job title from kind + params; the backend `title` is only an English fallback. */
const STAGES = ["analyze", "plan", "write", "character", "keys", "render"] as const;
export type Stage = (typeof STAGES)[number];
export const isStage = (v: unknown): v is Stage => typeof v === "string" && (STAGES as readonly string[]).includes(v);

/** "keyframes 12/45" — autopilot stage label with progress when known. */
export function stageLabel(stage: Stage, t: TFn, progress?: Job["progress"]): string {
  const label = t(`ap.stage.${stage}`);
  return progress && progress.total > 0 ? `${label} ${progress.done}/${progress.total}` : label;
}

export function jobTitle(job: Pick<Job, "kind" | "params"> & { progress?: Job["progress"] }, t: TFn): string {
  const p = job.params ?? {};
  switch (job.kind) {
    case "analyze":
      return t("job.analyze");
    case "storyboard": {
      const n = num(p.shots);
      return n !== null ? t("job.storyboard.n", { count: n }) : t("job.storyboard");
    }
    case "character":
      return t("job.character");
    case "keys_codex": {
      const missing = num(p.missing);
      if (missing !== null) return t("job.keys.missing", { count: missing });
      const shots = num(p.shots);
      return shots !== null ? t("job.keys.shots", { count: shots }) : t("job.keys");
    }
    case "render": {
      const set = setName(p.set);
      const workers = num(p.workers);
      if (set && workers !== null) return t("job.render.full", { set, count: workers });
      if (set) return t("job.render.set", { set });
      return t("job.render");
    }
    case "continuity":
      return t("job.continuity");
    case "autopilot": {
      const stage = p.stage;
      return isStage(stage) ? t("job.autopilot.stage", { stage: stageLabel(stage, t, job.progress) }) : t("job.autopilot");
    }
  }
}
