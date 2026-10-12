import { NavLink } from "react-router";
import type { Job, JobKind, Project } from "../../api/types";
import { cx } from "../../lib/cx";
import { formatRatio, projectFormat, renderedSets } from "../../lib/orientation";

interface Step {
  to: string;
  n: string;
  label: string;
  status: (p: Project) => { text: string; done: boolean };
  kinds: JobKind[];
}

export const STEPS: Step[] = [
  {
    to: "wejscie",
    n: "01",
    label: "Wejście",
    kinds: ["analyze"],
    status: (p) => {
      const have = [p.inputs.song, p.inputs.cover, p.inputs.lyrics].filter(Boolean).length;
      if (p.stage.analysis) return { text: "przeanalizowany", done: true };
      return { text: `${have}/3 plików`, done: false };
    },
  },
  {
    to: "storyboard",
    n: "02",
    label: "Storyboard",
    kinds: ["storyboard"],
    status: (p) =>
      p.stage.storyboard
        ? { text: `${p.stage.storyboard_written}/${p.stage.shots} opisanych`, done: p.stage.shots > 0 && p.stage.storyboard_written >= p.stage.shots }
        : { text: "brak ujęć", done: false },
  },
  {
    to: "klatki",
    n: "03",
    label: "Klatki",
    kinds: ["character", "keys_codex"],
    status: (p) => {
      const total = p.stage.shots;
      const c = p.stage.keys.codex ?? 0;
      return total ? { text: `Codex ${c}/${total} · ${formatRatio(projectFormat(p))}`, done: c >= total } : { text: "—", done: false };
    },
  },
  {
    to: "wideo",
    n: "04",
    label: "Wideo",
    kinds: ["render"],
    status: (p) => {
      const n = renderedSets(p);
      return { text: n ? "wyrenderowane" : `render ${formatRatio(projectFormat(p))} na Vast`, done: n > 0 };
    },
  },
  {
    to: "wynik",
    n: "05",
    label: "Wynik",
    kinds: [],
    status: (p) => {
      const n = renderedSets(p);
      return { text: n ? `${n} ${n === 1 ? "zestaw" : "zestawy"} · ${formatRatio(projectFormat(p))}` : "jeszcze nic", done: n > 0 };
    },
  },
];

export function Stepper({ project, jobs }: { project: Project; jobs: Job[] }) {
  return (
    <nav aria-label="Etapy projektu" className="flex gap-1 overflow-x-auto lg:flex-col lg:gap-0.5">
      {STEPS.map((s) => {
        const st = s.status(project);
        const busy = jobs.some((j) => s.kinds.includes(j.kind) && (j.status === "running" || j.status === "queued"));
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
                    {s.label}
                  </span>
                  <span className="flex items-center gap-1.5 text-[0.72rem] text-ink-500">
                    {busy ? (
                      <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-safe" />
                    ) : (
                      <span className={cx("h-1.5 w-1.5 rounded-full", st.done ? "bg-ok" : "bg-ink-600")} />
                    )}
                    <span className="truncate">{busy ? "w toku…" : st.text}</span>
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
