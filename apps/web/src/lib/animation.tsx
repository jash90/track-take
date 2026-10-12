import { useAnimations } from "../api/hooks";
import type { AnimationId, Project, Storyboard } from "../api/types";
import { cx } from "./cx";
import { useI18n, type Key } from "../i18n";

export const DEFAULT_ANIMATION: AnimationId = "stopmotion";

/** Known styles; names fall back to these keys when GET /api/animations is unavailable, descriptions always come from i18n. */
export const ANIMATIONS: { value: AnimationId; label: Key; hint: Key }[] = [
  { value: "stopmotion", label: "anim.stopmotion", hint: "anim.stopmotionHint" },
  { value: "tableau", label: "anim.tableau", hint: "anim.tableauHint" },
  { value: "journey", label: "anim.journey", hint: "anim.journeyHint" },
];

/** Living-picture styles: smooth playback, no beat pump. */
export const isIllustrated = (a: AnimationId) => a === "tableau" || a === "journey";

const known = (v: unknown): v is AnimationId => ANIMATIONS.some((a) => a.value === v);

/** Missing (older backends / projects) = stop-motion, the original look. */
export function projectAnimation(p: Pick<Project, "settings">): AnimationId {
  const a = p.settings.animation;
  return known(a) ? a : DEFAULT_ANIMATION;
}

/** The animation a storyboard was planned with; storyboards from before the setting were planned as stop-motion. */
export function storyboardAnimation(sb: Pick<Storyboard, "animation">): AnimationId {
  return known(sb.animation) ? sb.animation : DEFAULT_ANIMATION;
}

/** Display name: the backend's (in the UI language) when loaded, else the built-in translation. */
export function useAnimationName() {
  const { lang, t } = useI18n();
  const list = useAnimations();
  return (id: AnimationId): string => {
    const fromApi = list.data?.find((a) => a.id === id)?.name[lang];
    if (fromApi) return fromApi;
    const info = ANIMATIONS.find((a) => a.value === id);
    return info ? t(info.label) : id;
  };
}

/** Tiny glyph: three frames (stop-motion), a framed landscape (living illustration) or a road (illustrated journey). */
export function AnimationGlyph({ animation, className }: { animation: AnimationId; className?: string }) {
  return (
    <svg aria-hidden viewBox="0 0 14 10" width={14} height={10} className={cx("shrink-0", className)} fill="none" stroke="currentColor" strokeWidth={1.4}>
      {animation === "journey" ? (
        <>
          <rect x={0.7} y={0.7} width={12.6} height={8.6} rx={1} />
          <path d="M2 8.5 C 5 6, 9 6, 12 2" strokeLinecap="round" />
          <path d="M9.6 2 L12 2 L12 4.4" strokeLinecap="round" strokeLinejoin="round" />
        </>
      ) : animation === "tableau" ? (
        <>
          <rect x={0.7} y={0.7} width={12.6} height={8.6} rx={1} />
          <path d="M1.5 8 L5 4.5 L7.5 6.8 L9.5 5 L12.5 8" strokeLinejoin="round" />
        </>
      ) : (
        <>
          <rect x={0.7} y={1.7} width={3.2} height={6.6} rx={0.6} />
          <rect x={5.4} y={1.7} width={3.2} height={6.6} rx={0.6} />
          <rect x={10.1} y={1.7} width={3.2} height={6.6} rx={0.6} />
        </>
      )}
    </svg>
  );
}

/** "▥ Stop-motion" chip used on project cards and the workspace header. */
export function AnimationBadge({ animation, className }: { animation: AnimationId; className?: string }) {
  const { t } = useI18n();
  const name = useAnimationName();
  const info = ANIMATIONS.find((a) => a.value === animation);
  return (
    <span
      title={`${t("anim.label")}: ${name(animation)}${info ? ` — ${t(info.hint)}` : ""}`}
      className={cx(
        "inline-flex h-6 items-center gap-1.5 whitespace-nowrap rounded-full border border-ink-600 bg-ink-900/80 px-2.5 font-mono text-[0.68rem] text-ink-200",
        className,
      )}
    >
      <AnimationGlyph animation={animation} className="text-safe" />
      {name(animation)}
    </span>
  );
}
