import type { Project } from "../../api/types";
import { formatRatio, projectFormat, renderedSets } from "../../lib/orientation";

export type StageTone = "ok" | "warn" | "neutral";
export interface StageInfo {
  key: string;
  label: string;
  value: string;
  tone: StageTone;
}

/** The five production stages, derived from Project.stage. */
export function projectStages(p: Project): StageInfo[] {
  const s = p.stage;
  const totalKeys = s.shots; // one keyframe per shot, in the project orientation
  const codex = s.keys.codex ?? 0;
  const comfy = s.keys.comfy ?? 0;
  const bestKeys = Math.max(codex, comfy);
  const vids = renderedSets(p);
  return [
    { key: "analysis", label: "Analiza", value: s.analysis ? "✓" : "—", tone: s.analysis ? "ok" : "neutral" },
    {
      key: "storyboard",
      label: "Ujęcia",
      value: s.storyboard ? `${s.storyboard_written}/${s.shots}` : "—",
      tone: !s.storyboard ? "neutral" : s.shots > 0 && s.storyboard_written >= s.shots ? "ok" : "warn",
    },
    { key: "character", label: "Postać", value: s.character_sheet ? "✓" : "—", tone: s.character_sheet ? "ok" : "neutral" },
    {
      key: "keys",
      label: "Klatki",
      value: totalKeys > 0 && bestKeys > 0 ? `${bestKeys}/${totalKeys}` : "—",
      tone: bestKeys === 0 ? "neutral" : bestKeys >= totalKeys ? "ok" : "warn",
    },
    { key: "videos", label: "Wideo", value: vids > 0 ? formatRatio(projectFormat(p)) : "—", tone: vids > 0 ? "ok" : "neutral" },
  ];
}

/** Codex/ComfyUI keyframe counts for tooltips. */
export function keysSummary(p: Project): string {
  const total = p.stage.shots;
  return `Klatki ${formatRatio(projectFormat(p))} · Codex ${p.stage.keys.codex ?? 0}/${total} · ComfyUI ${p.stage.keys.comfy ?? 0}/${total}`;
}
