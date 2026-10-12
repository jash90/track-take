import type { Shot } from "../api/types";
import type { TFn } from "../i18n";

/** Missing flag = cut (old storyboards); the first shot is always a cut. */
export function isCut(shot: Pick<Shot, "cut">, index: number): boolean {
  return index === 0 || shot.cut !== false;
}

export function continuitySummary(shots: Pick<Shot, "cut">[], t: TFn): string {
  const cuts = shots.filter((s, i) => isCut(s, i)).length;
  const flows = shots.length - cuts;
  return `${t("cont.cuts", { count: cuts })} · ${t("cont.flows", { count: flows })}`;
}

/** Continuous shots right after `index` — their keyframes were drawn from this one. */
export function dependentShots<T extends Pick<Shot, "id" | "cut">>(shots: T[], index: number): T[] {
  const out: T[] = [];
  for (let i = index + 1; i < shots.length; i++) {
    const s = shots[i];
    if (!s || isCut(s, i)) break;
    out.push(s);
  }
  return out;
}
