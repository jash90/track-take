import { useMemo, useState } from "react";
import { Link, Navigate, Outlet, useParams } from "react-router";
import { isNotFound } from "../../api/client";
import { useProject, useProjectJobs } from "../../api/hooks";
import { ErrorBox, Loading } from "../../components/ui";
import { JobsDrawer } from "../jobs/JobsDrawer";
import { useJobWatcher } from "../jobs/useJobWatcher";
import { WorkspaceCtx, useWorkspace, type WorkspaceValue } from "./context";
import { Stepper } from "./Stepper";
import { FormatBadge, projectOrientation, renderedSets } from "../../lib/orientation";
import { useT } from "../../i18n";

export function WorkspacePage() {
  const { id = "" } = useParams();
  const project = useProject(id);
  const jobsQ = useProjectJobs(id);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const t = useT();
  const jobs = useMemo(() => jobsQ.data ?? [], [jobsQ.data]);
  useJobWatcher(id, jobs);

  const value = useMemo<WorkspaceValue | null>(
    () => (project.data ? { project: project.data, jobs, openJobs: () => setDrawerOpen(true) } : null),
    [project.data, jobs],
  );

  if (project.isPending) return <div className="px-10"><Loading label={t("workspace.opening")} /></div>;
  if (project.isError || !value) {
    return (
      <div className="mx-auto max-w-xl px-6 py-16">
        <ErrorBox
          title={isNotFound(project.error) ? t("workspace.notFound", { id }) : t("workspace.loadError")}
          error={project.error}
          onRetry={() => void project.refetch()}
        />
        <Link to="/" className="mt-4 inline-block text-sm text-safe hover:underline">{t("workspace.back")}</Link>
      </div>
    );
  }

  return (
    <WorkspaceCtx.Provider value={value}>
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <aside className="shrink-0 border-b border-ink-800 px-3 py-3 lg:sticky lg:top-[52px] lg:h-[calc(100vh-52px)] lg:w-[220px] lg:border-b-0 lg:border-r lg:py-6">
          <div className="mb-4 hidden px-3 lg:block">
            <div className="eyebrow">{t("workspace.project")}</div>
            <div className="mt-1 truncate font-display text-2xl italic">{value.project.name}</div>
            <FormatBadge orientation={projectOrientation(value.project)} className="mt-2" />
          </div>
          <div className="mb-2 px-3 lg:hidden">
            <FormatBadge orientation={projectOrientation(value.project)} />
          </div>
          <Stepper project={value.project} jobs={jobs} />
        </aside>
        <section className="min-w-0 flex-1 px-6 pb-28 pt-8 lg:px-10">
          <Outlet />
        </section>
      </div>
      <JobsDrawer projectId={id} jobs={jobs} open={drawerOpen} onOpenChange={setDrawerOpen} error={jobsQ.error} />
    </WorkspaceCtx.Provider>
  );
}

/** /p/:id → jump to the first step that still needs work. */
export function WorkspaceIndex() {
  const { project: p } = useWorkspace();
  const s = p.stage;
  let to = "wejscie";
  if (s.analysis && p.inputs.song) to = "storyboard";
  if (s.storyboard && s.shots > 0 && s.storyboard_written >= s.shots) to = "klatki";
  if (s.shots > 0 && (s.keys.codex ?? 0) >= s.shots) to = "wideo";
  if (renderedSets(p) > 0) to = "wynik";
  return <Navigate to={to} replace />;
}
