import type { Project, ProjectSettings } from "../../api/types";
import { useT, type Key } from "../../i18n";
import { cx } from "../../lib/cx";
import { isIllustrated, projectAnimation } from "../../lib/animation";
import { useSaveSettings } from "./useSaveSettings";

type Flag = "captions" | "beat_motion";
const OPTIONS: { flag: Flag; label: Key; hint: Key }[] = [
  { flag: "captions", label: "renderOpts.captions", hint: "renderOpts.captionsHint" },
  { flag: "beat_motion", label: "renderOpts.beat", hint: "renderOpts.beatHint" },
];

/** Missing in older backends = on (the defaults). */
export const flagOn = (s: Partial<ProjectSettings>, f: Flag) => s[f] !== false;

/** Whether the flag actually takes effect: the living-illustration montage never pumps/shakes to the beat. */
export const flagApplies = (p: Pick<Project, "settings">, f: Flag) => f !== "beat_motion" || !isIllustrated(projectAnimation(p));

/** Captions / beat-motion switches; saved immediately (optimistic PATCH of project settings). */
export function RenderOptions({ project }: { project: Project }) {
  const t = useT();
  const save = useSaveSettings(project, "renderOpts.saveError");

  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="label">{t("renderOpts.title")}</legend>
      <div className="grid gap-2 sm:grid-cols-2">
        {OPTIONS.map((o) => {
          const applies = flagApplies(project, o.flag);
          const on = applies && flagOn(project.settings, o.flag);
          return (
            <button
              key={o.flag}
              type="button"
              role="switch"
              aria-checked={on}
              disabled={!applies}
              onClick={() => save.mutate({ [o.flag]: !on })}
              className={cx(
                "flex items-start gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-55",
                on ? "border-safe/60 bg-safe/[0.06]" : "border-ink-600 enabled:hover:border-ink-400",
              )}
            >
              <span
                aria-hidden
                className={cx(
                  "relative mt-0.5 h-5 w-9 shrink-0 rounded-full transition-colors",
                  on ? "bg-safe" : "bg-ink-600",
                )}
              >
                <span
                  className={cx(
                    "absolute top-0.5 h-4 w-4 rounded-full bg-ink-100 shadow transition-[left]",
                    on ? "left-[18px]" : "left-0.5",
                  )}
                />
              </span>
              <span className="flex min-w-0 flex-col">
                <span className="text-[0.9rem] text-ink-100">{t(o.label)}</span>
                <span className="text-[0.72rem] leading-snug text-ink-400">{applies ? t(o.hint) : t("renderOpts.beatTableau")}</span>
              </span>
            </button>
          );
        })}
      </div>
      <p className="text-[0.72rem] text-ink-500">{t("renderOpts.note")}</p>
    </fieldset>
  );
}
