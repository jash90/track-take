import type { KeySet, Keys, Orientation } from "../../api/types";
import type { LightboxItem } from "../../components/Lightbox";

/** Lightbox items for one shot's keyframes (Codex, ComfyUI) in the project orientation, starting at `set`. */
export function shotLightbox(keys: Keys | undefined, shotId: string, orientation: Orientation, set: KeySet) {
  const items: LightboxItem[] = [];
  let index = 0;
  for (const s of ["codex", "comfy"] as KeySet[]) {
    const src = keys?.sets[s]?.[shotId]?.[orientation];
    if (!src) continue;
    if (s === set) index = items.length;
    items.push({ src, caption: `${shotId} · ${s === "codex" ? "Codex" : "ComfyUI"} · ${orientation === "landscape" ? "16:9" : "9:16"}` });
  }
  return { items, index };
}
