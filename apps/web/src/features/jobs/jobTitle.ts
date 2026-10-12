import type { Job } from "../../api/types";
import type { TFn } from "../../i18n";

const num = (v: unknown): number | null => {
  const n = typeof v === "string" ? Number(v) : v;
  return typeof n === "number" && Number.isFinite(n) ? n : null;
};
const setName = (v: unknown) => (v === "comfy" ? "ComfyUI" : v === "codex" ? "Codex" : typeof v === "string" ? v : null);

/** Localised job title from kind + params; the backend `title` is only an English fallback. */
export function jobTitle(job: Pick<Job, "kind" | "params">, t: TFn): string {
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
  }
}
