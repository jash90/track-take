import { NavLink } from "react-router";
import { isStage, stageLabel, type Stage } from "../jobs/jobTitle";
import type { Job, JobKind, Project } from "../../api/types";
import { cx } from "../../lib/cx";
import { formatRatio, projectFormat, renderedSets } from "../../lib/orientation";
import { useT, type Key, type TFn } from "../../i18n";

interface Step {
  to: string;
  n: string;
  label: Key;
  status: (p: Project, t: TFn) => { text: string; done: boolean };
  kinds: JobKind[];
  /** autopilot stages that belong to this step */
  stages: Stage[];
}

export const STEPS: Step[] = [
  {
    to: "wejscie",
    n: "01",
    label: "step.inputs",
    kinds: ["analyze"],
    stages: ["analyze"],
    status: (p, t) => {
      const have = [p.inputs.song, p.inputs.cover, p.inputs.lyrics].filter(Boolean).length;
      if (p.stage.analysis) return { text: t("step.inputs.analysed"), done: true };
      return { text: t("step.inputs.files", { have }), done: false };
    },
  },
  {
    to: "storyboard",
    n: "02",
    label: "step.storyboard",
    kinds: ["storyboard"],
    stages: ["plan", "write", "review"],
    status: (p, t) =>
      p.stage.storyboard
        ? { text: t("step.storyboard.written", { written: p.stage.storyboard_written, shots: p.stage.shots }), done: p.stage.shots > 0 && p.stage.storyboard_written >= p.stage.shots }
        : { text: t("step.storyboard.none"), done: false },
  },
  {
    to: "klatki",
    n: "03",
    label: "step.keys",
    kinds: ["character", "keys_codex", "keys_check"],
    stages: ["character", "keys", "check"],
    status: (p) => {
      const total = p.stage.shots;
      const c = p.stage.keys.codex ?? 0;
      return total ? { text: `Codex ${c}/${total} · ${formatRatio(projectFormat(p))}`, done: c >= total } : { text: "—", done: false };
    },
  },
  {
    to: "wideo",
    n: "04",
    label: "step.video",
    kinds: ["render"],
    stages: ["render"],
    status: (p, t) => {
      const n = renderedSets(p);
      return { text: n ? t("step.video.rendered") : t("step.video.todo", { ratio: formatRatio(projectFormat(p)) }), done: n > 0 };
    },
  },
  {
    to: "wynik",
    n: "05",
    label: "step.result",
    kinds: [],
    stages: [],
    status: (p, t) => {
      const n = renderedSets(p);
      return { text: n ? t("step.result.sets", { count: n, ratio: formatRatio(projectFormat(p)) }) : t("step.result.none"), done: n > 0 };
    },
  },
];

export function Stepper({ project, jobs }: { project: Project; jobs: Job[] }) {
  const t = useT();
  const pilot = jobs.find((j) => j.kind === "autopilot" && (j.status === "running" || j.status === "queued"));
  return (
    <nav aria-label={t("step.navAria")} className="flex gap-1 overflow-x-auto lg:flex-col lg:gap-0.5">
      {STEPS.map((s) => {
        const st = s.status(project, t);
        const pilotHere = pilot && isStage(pilot.params?.stage) && s.stages.includes(pilot.params.stage) ? pilot : null;
        const busy = !!pilotHere || jobs.some((j) => s.kinds.includes(j.kind) && (j.status === "running" || j.status === "queued"));
        const busyText =
          pilotHere && isStage(pilotHere.params?.stage)
            ? `${t("ap.eyebrow")}: ${stageLabel(pilotHere.params.stage, t, pilotHere.progress)}`
            : t("step.busy");
        return (
          <NavLink
            key={s.to}
            to={s.to}
            className={({ isActive }) =>
              cx(
                "group relative flex min-w-[150px] items-start gap-3 rounded-lg px-3 py-2.5 transition-colors lg:min-w-0",
                isActive ? "bg-ink-800" : "hover:bg-ink-850",
              )
            }
          >
            {({ isActive }) => (
              <>
                <span
                  aria-hidden
                  className={cx(
                    "absolute bottom-2 left-0 top-2 w-[2px] rounded-full transition-colors max-lg:hidden",
                    isActive ? "bg-safe" : "bg-transparent",
                  )}
                />
                <span className={cx("mt-1 font-mono text-[0.7rem] tabular", isActive ? "text-safe" : "text-ink-500")}>{s.n}</span>
                <span className="flex min-w-0 flex-col">
                  <span className={cx("font-display text-[1.35rem] leading-tight", isActive ? "text-ink-100" : "text-ink-300 group-hover:text-ink-100")}>
                    {t(s.label)}
                  </span>
                  <span className="flex items-center gap-1.5 text-[0.72rem] text-ink-500">
                    {busy ? (
                      <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-safe" />
                    ) : (
                      <span className={cx("h-1.5 w-1.5 rounded-full", st.done ? "bg-ok" : "bg-ink-600")} />
                    )}
                    <span className="truncate">{busy ? busyText : st.text}</span>
                  </span>
                </span>
              </>
            )}
          </NavLink>
        );
      })}
    </nav>
  );
}
