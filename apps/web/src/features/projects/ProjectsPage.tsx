import { useProjects } from "../../api/hooks";
import { ErrorBox } from "../../components/ui";
import { plural } from "../../lib/format";
import { NewProjectTile } from "./NewProjectTile";
import { ProjectCard } from "./ProjectCard";

export function ProjectsPage() {
  const { data, isPending, isError, error, refetch } = useProjects();
  const projects = data ? [...data].sort((a, b) => b.created.localeCompare(a.created)) : [];

  return (
    <div className="mx-auto w-full max-w-[1400px] px-6 pb-20 pt-10 lg:px-10">
      <header className="mb-10 flex flex-wrap items-end justify-between gap-6">
        <div>
          <div className="eyebrow">Ciemnia · {data ? `${data.length} ${plural(data.length, "projekt", "projekty", "projektów")}` : "…"}</div>
          <h1 className="mt-2 font-display text-[clamp(3rem,6vw,5.2rem)] leading-[0.9] tracking-tight">
            Każdy takt <em className="text-safe">to klatka.</em>
          </h1>
          <p className="mt-3 max-w-xl text-[0.95rem] leading-relaxed text-ink-400">
            Wrzuć utwór z Suno, tekst, okładkę i kilka słów o stylu — sunomv rozpisze storyboard na bitach, narysuje klatki
            i złoży teledysk poklatkowy — poziomy 16:9 albo pionowy 9:16.
          </p>
        </div>
      </header>

      {isError && <ErrorBox title="Nie mogę pobrać projektów — czy backend działa na :8770?" error={error} onRetry={() => void refetch()} />}

      <div className="grid grid-cols-[repeat(auto-fill,minmax(270px,1fr))] gap-5">
        <NewProjectTile />
        {isPending &&
          Array.from({ length: 3 }, (_, i) => (
            <div key={i} className="aspect-[1/1.18] animate-pulse rounded-xl border border-ink-800 bg-ink-850" />
          ))}
        {projects.map((p, i) => (
          <ProjectCard key={p.id} project={p} index={i} />
        ))}
      </div>
    </div>
  );
}
