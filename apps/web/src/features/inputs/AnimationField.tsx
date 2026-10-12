import { Link } from "react-router";
import { useAnimations, useStoryboard } from "../../api/hooks";
import type { AnimationId, Project } from "../../api/types";
import { useT } from "../../i18n";
import { ANIMATIONS, AnimationGlyph, projectAnimation, storyboardAnimation, useAnimationName } from "../../lib/animation";
import { cx } from "../../lib/cx";
import { useSaveSettings } from "../render/useSaveSettings";

interface Props {
  project: Project;
  /** locked while the autopilot runs (it plans with the setting) */
  disabled?: boolean;
  /** called when the user follows the "re-plan in the storyboard" link (e.g. to close a dialog) */
  onGoStoryboard?: () => void;
}

/** "Animation style": how the video moves. Saved immediately; a planned storyboard is never re-planned from here. */
export function AnimationField({ project, disabled, onGoStoryboard }: Props) {
  const t = useT();
  const name = useAnimationName();
  const list = useAnimations();
  const save = useSaveSettings(project, "anim.saveError");
  const sb = useStoryboard(project.id, project.stage.storyboard);
  const current = projectAnimation(project);
  // the backend decides which styles exist; unknown ids (newer backend) still get a card, without a description
  const options: { value: AnimationId; hint?: (typeof ANIMATIONS)[number]["hint"] }[] = list.data?.length
    ? list.data.map((a) => ({ value: a.id, hint: ANIMATIONS.find((x) => x.value === a.id)?.hint }))
    : ANIMATIONS;
  const planned = sb.data ? storyboardAnimation(sb.data) : null;
  const mismatch = planned !== null && planned !== current;

  return (
    <div>
      <div className="label" id="anim-label">{t("anim.label")}</div>
      <div role="radiogroup" aria-labelledby="anim-label" className="grid gap-2 sm:grid-cols-2">
        {options.map((o) => {
          const on = current === o.value;
          return (
            <button
              key={o.value}
              type="button"
              role="radio"
              aria-checked={on}
              disabled={disabled}
              title={disabled ? t("anim.busy") : undefined}
              onClick={() => !on && save.mutate({ animation: o.value })}
              className={cx(
                "flex items-start gap-3 rounded-md border px-3 py-2 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-60",
                on ? "border-safe bg-safe/[0.07] text-ink-100" : "border-ink-600 text-ink-400 enabled:hover:border-ink-400 enabled:hover:text-ink-200",
              )}
            >
              <AnimationGlyph animation={o.value} className={cx("mt-1", on ? "text-safe" : undefined)} />
              <span className="flex min-w-0 flex-col leading-tight">
                <span className="text-[0.88rem]">{name(o.value)}</span>
                {o.hint && <span className="mt-0.5 text-[0.68rem] leading-snug text-ink-500">{t(o.hint)}</span>}
              </span>
            </button>
          );
        })}
      </div>
      {mismatch ? (
        <p className="mt-1.5 text-[0.72rem] leading-relaxed text-warn" role="status">
          {t("anim.mismatch", { planned: name(planned), current: name(current) })}{" "}
          <Link
            to={`/p/${encodeURIComponent(project.id)}/storyboard`}
            onClick={onGoStoryboard}
            className="whitespace-nowrap text-safe hover:underline"
          >
            {t("anim.goReplan")}
          </Link>
        </p>
      ) : (
        <p className="mt-1.5 text-[0.72rem] leading-relaxed text-ink-500">
          {project.stage.storyboard ? t("anim.noteReplan") : t("anim.note")}
        </p>
      )}
    </div>
  );
}
