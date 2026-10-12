import type { Project, ProjectSettings } from "../../api/types";
import { useT, type Key } from "../../i18n";
import { cx } from "../../lib/cx";
import { useSaveSettings } from "./useSaveSettings";

type Flag = "captions" | "beat_motion";
const OPTIONS: { flag: Flag; label: Key; hint: Key }[] = [
  { flag: "captions", label: "renderOpts.captions", hint: "renderOpts.captionsHint" },
  { flag: "beat_motion", label: "renderOpts.beat", hint: "renderOpts.beatHint" },
];

/** Missing in older backends = on (the defaults). */
export const flagOn = (s: Partial<ProjectSettings>, f: Flag) => s[f] !== false;

/** Captions / beat-motion switches; saved immediately (optimistic PATCH of project settings). */
export function RenderOptions({ project }: { project: Project }) {
  const t = useT();
  const save = useSaveSettings(project, "renderOpts.saveError");

  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="label">{t("renderOpts.title")}</legend>
      <div className="grid gap-2 sm:grid-cols-2">
        {OPTIONS.map((o) => {
          const on = flagOn(project.settings, o.flag);
          return (
            <button
              key={o.flag}
              type="button"
              role="switch"
              aria-checked={on}
              onClick={() => save.mutate({ [o.flag]: !on })}
              className={cx(
                "flex items-start gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors",
                on ? "border-safe/60 bg-safe/[0.06]" : "border-ink-600 hover:border-ink-400",
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
                <span className="text-[0.72rem] leading-snug text-ink-400">{t(o.hint)}</span>
              </span>
            </button>
          );
        })}
      </div>
      <p className="text-[0.72rem] text-ink-500">{t("renderOpts.note")}</p>
    </fieldset>
  );
}
