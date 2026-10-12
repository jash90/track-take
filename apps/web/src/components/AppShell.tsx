import { createContext, useContext, useState } from "react";
import { Link, Outlet, useMatch } from "react-router";
import { useProject, useVast } from "../api/hooks";
import { formatUsd } from "../lib/format";
import { SettingsDialog } from "./SettingsDialog";
import { useT } from "../i18n";
import { LangSwitch } from "./LangSwitch";

const ShellCtx = createContext<{ openSettings: () => void }>({ openSettings: () => {} });
export const useShell = () => useContext(ShellCtx);

function ProjectCrumb({ id }: { id: string }) {
  const { data } = useProject(id);
  return (
    <>
      <span aria-hidden className="text-ink-600">/</span>
      <span className="max-w-[28ch] truncate text-ink-200">{data?.name ?? id}</span>
    </>
  );
}

function VastChip({ onClick }: { onClick: () => void }) {
  const { data } = useVast();
  const t = useT();
  if (!data) return null;
  const running = data.instances.length;
  return (
    <button
      type="button"
      onClick={onClick}
      title={t("shell.vastStatus")}
      className="hidden items-center gap-2 rounded-full border border-ink-700 px-3 py-1 font-mono text-[0.7rem] text-ink-300 hover:border-ink-500 sm:inline-flex"
    >
      <span className={`h-1.5 w-1.5 rounded-full ${data.configured ? (running ? "animate-pulse-dot bg-safe" : "bg-ok") : "bg-ink-500"}`} />
      vast {data.configured ? formatUsd(data.balance) : "—"}
      {running > 0 && <span className="text-safe-hi">· {running} GPU</span>}
    </button>
  );
}

export function AppShell() {
  const [settings, setSettings] = useState(false);
  const match = useMatch("/p/:id/*");
  const projectId = match?.params.id;
  const t = useT();

  return (
    <ShellCtx.Provider value={{ openSettings: () => setSettings(true) }}>
      <div className="flex min-h-screen flex-col">
        <header className="sticky top-0 z-40 flex h-[52px] shrink-0 items-center gap-4 border-b border-ink-800 bg-ink-950/85 px-5 backdrop-blur-md">
          <Link to="/" className="group flex items-baseline gap-2" aria-label={t("shell.homeAria")}>
            <span aria-hidden className="relative top-[3px] inline-grid h-4 w-4 place-items-center rounded-full border-[2.5px] border-safe">
              <span className="h-1 w-1 rounded-full bg-safe" />
            </span>
            <span className="font-display text-[1.45rem] italic leading-none tracking-tight">tracktake</span>
            <span className="hidden font-mono text-[0.62rem] uppercase tracking-[0.18em] text-ink-500 group-hover:text-ink-300 md:inline">
              {t("shell.tagline")}
            </span>
          </Link>
          <nav className="flex min-w-0 items-center gap-2 text-sm" aria-label={t("shell.breadcrumbs")}>
            <Link to="/" className="text-ink-400 hover:text-ink-100">
              {t("shell.projects")}
            </Link>
            {projectId && <ProjectCrumb id={projectId} />}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <VastChip onClick={() => setSettings(true)} />
            <LangSwitch />
            <button
              type="button"
              onClick={() => setSettings(true)}
              className="rounded-md px-3 py-1.5 text-sm text-ink-300 hover:bg-ink-800 hover:text-ink-100"
            >
              {t("shell.settings")}
            </button>
          </div>
        </header>
        <main className="flex min-h-0 flex-1 flex-col">
          <Outlet />
        </main>
      </div>
      <SettingsDialog open={settings} onClose={() => setSettings(false)} />
    </ShellCtx.Provider>
  );
}
