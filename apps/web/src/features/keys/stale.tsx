import type { KeyCheckKind, Keys, Orientation, ShotKeys } from "../../api/types";
import { useT, type TFn } from "../../i18n";
import { cx } from "../../lib/cx";

/** A Codex keyframe drawn before its scene / the world bible / the keyframe it follows changed — it will be redrawn. */
export function isStale(k: ShotKeys | undefined, o: Orientation): boolean {
  return !!k?.[o] && !!(o === "landscape" ? k.landscape_stale : k.portrait_stale);
}

/** Correction note left by the keyframe check that is still pending (the keyframe is stale and will be redrawn with it). */
export function keyIssue(k: ShotKeys | undefined, o: Orientation): string | null {
  if (!k?.[o]) return null;
  return (o === "landscape" ? k.landscape_issue : k.portrait_issue) || null;
}

/** The keyframe check mirrored this keyframe left-right (the original is kept). */
export function isFlipped(k: ShotKeys | undefined, o: Orientation): boolean {
  return !!k?.[o] && !!(o === "landscape" ? k.landscape_flipped : k.portrait_flipped);
}

/** shot id -> error kind from the last keyframe check (first issue per shot). */
export function checkKinds(keys: Keys | undefined): Record<string, KeyCheckKind> {
  const out: Record<string, KeyCheckKind> = {};
  for (const i of keys?.check?.issues ?? []) out[i.shot] ??= i.kind;
  return out;
}

/** "3 missing, 11 outdated" — zero parts are left out. */
export function keysCountSummary(t: TFn, missing: number, stale: number): string {
  const parts: string[] = [];
  if (missing > 0) parts.push(t("keys.count.missing", { count: missing }));
  if (stale > 0) parts.push(t("keys.count.stale", { count: stale }));
  return parts.join(", ");
}

const PILL = "w-fit rounded-full border bg-ink-950/80 px-1.5 py-px font-mono text-[0.6rem] leading-normal backdrop-blur";

/** Thumbnail border colour: red for a pending check error, amber for outdated. */
export function keyBorder(k: ShotKeys | undefined, o: Orientation): string | null {
  if (keyIssue(k, o)) return "border-err/60";
  if (isStale(k, o)) return "border-warn/50";
  return null;
}

/**
 * Status pills laid over a Codex keyframe thumbnail (the parent must be `relative`): a pending check error
 * ("error: object", the correction as tooltip) takes precedence over the plain "outdated"; "mirrored" when flipped.
 */
export function KeyBadges({
  k,
  orientation,
  kind,
  className,
  pillClassName,
}: {
  k: ShotKeys | undefined;
  orientation: Orientation;
  /** error kind from the last check report, when known */
  kind?: KeyCheckKind;
  className?: string;
  pillClassName?: string;
}) {
  const t = useT();
  const issue = keyIssue(k, orientation);
  const stale = isStale(k, orientation);
  const flipped = isFlipped(k, orientation);
  if (!issue && !stale && !flipped) return null;
  return (
    <span className={cx("absolute z-[1] flex flex-col items-start gap-1", className ?? "left-1.5 top-1.5")}>
      {issue ? (
        <span title={t("keys.issueTip", { note: issue })} className={cx(PILL, "border-err/70 text-err", pillClassName)}>
          {kind ? t("keys.issueBadge", { kind: t(`keys.kind.${kind}`) }) : t("keys.issueBadgeShort")}
        </span>
      ) : (
        stale && (
          <span title={t("keys.staleTip")} className={cx(PILL, "border-warn/60 text-warn", pillClassName)}>
            {t("keys.staleBadge")}
          </span>
        )
      )}
      {flipped && (
        <span title={t("keys.flippedTip")} className={cx(PILL, "border-ink-500/70 text-ink-300", pillClassName)}>
          ⇋ {t("keys.flippedBadge")}
        </span>
      )}
    </span>
  );
}
