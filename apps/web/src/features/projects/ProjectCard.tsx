import { Link } from "react-router";
import type { Project } from "../../api/types";
import { cx } from "../../lib/cx";
import { formatDate } from "../../lib/format";
import { FormatBadge, projectFormat, projectOrientation } from "../../lib/orientation";
import { AnimationBadge, projectAnimation } from "../../lib/animation";
import { keysSummary, projectStages } from "./stages";
import { useT } from "../../i18n";

function vidsTitle(p: Project, none: string): string {
  const f = projectFormat(p);
  return (["codex", "comfy"] as const).filter((s) => p.stage.videos[s]?.includes(f)).join(", ") || none;
}

export function ProjectCard({ project, index }: { project: Project; index: number }) {
  const t = useT();
  const stages = projectStages(project, t);
  const cover = project.inputs.cover;
  return (
    <Link
      to={`/p/${encodeURIComponent(project.id)}`}
      style={{ animationDelay: `${Math.min(index, 12) * 45}ms` }}
      className="group relative flex animate-rise flex-col overflow-hidden rounded-xl border border-ink-700 bg-ink-850 transition-[border-color,transform] duration-200 hover:-translate-y-0.5 hover:border-ink-500 focus-visible:-translate-y-0.5"
    >
      <div className="relative aspect-square overflow-hidden bg-ink-900">
        {cover ? (
          <img
            src={cover}
            alt=""
            loading="lazy"
            className="h-full w-full object-cover opacity-85 saturate-[0.9] transition-[opacity,transform] duration-500 group-hover:scale-[1.03] group-hover:opacity-100"
          />
        ) : (
          <div className="grid h-full place-items-center">
            <span className="font-display text-7xl italic text-ink-700">{project.name.slice(0, 1).toUpperCase() || "?"}</span>
          </div>
        )}
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-ink-950 via-ink-950/20 to-transparent" />
        <div className="absolute right-3 top-3 flex flex-col items-end gap-1.5">
          <FormatBadge orientation={projectOrientation(project)} className="backdrop-blur" />
          <AnimationBadge animation={projectAnimation(project)} className="backdrop-blur" />
        </div>
        <div className="absolute inset-x-0 bottom-0 p-4">
          <div className="font-mono text-[0.65rem] uppercase tracking-[0.16em] text-ink-400">
            {formatDate(project.created)} · {project.language || "—"}
          </div>
          <h2 className="mt-1 truncate font-display text-[1.75rem] leading-tight text-ink-100">{project.name}</h2>
          {project.style && <p className="mt-0.5 line-clamp-1 text-[0.8rem] text-ink-300">{project.style}</p>}
        </div>
      </div>
      <ol className="grid grid-cols-5 border-t border-ink-700" aria-label={t("stage.aria")}>
        {stages.map((s) => (
          <li
            key={s.key}
            title={s.key === "keys" ? keysSummary(project, t) : s.key === "videos" ? t("stage.renderedSets", { sets: vidsTitle(project, t("stage.none")) }) : `${s.label}: ${s.value}`}
            className="flex flex-col items-center gap-1 border-r border-ink-750 px-1 py-2.5 last:border-r-0"
          >
            <span
              className={cx(
                "h-1 w-6 rounded-full",
                s.tone === "ok" && "bg-ok",
                s.tone === "warn" && "bg-warn",
                s.tone === "neutral" && "bg-ink-600",
              )}
            />
            <span className="text-[0.66rem] text-ink-400">{s.label}</span>
            <span className={cx("font-mono text-[0.68rem] tabular", s.tone === "neutral" ? "text-ink-500" : "text-ink-200")}>{s.value}</span>
          </li>
        ))}
      </ol>
    </Link>
  );
}
