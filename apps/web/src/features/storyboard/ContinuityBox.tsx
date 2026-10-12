import { api } from "../../api/client";
import { useStartJob } from "../../api/hooks";
import type { Job, Storyboard } from "../../api/types";
import { useToast } from "../../components/Toaster";
import { Button, InlineError } from "../../components/ui";
import { useT } from "../../i18n";
import { formatClock, formatDate } from "../../lib/format";

interface Props {
  projectId: string;
  continuity: Storyboard["continuity"];
  running: Job | undefined;
  /** unsaved edits — the check runs on the saved storyboard */
  dirty: boolean;
  onJump: (shotId: string) => void;
  onStarted: () => void;
}

/** Result of the automatic continuity pass (fixes between shots) + a button to re-run it. */
export function ContinuityBox({ projectId, continuity, running, dirty, onJump, onStarted }: Props) {
  const t = useT();
  const toast = useToast();
  const check = useStartJob(projectId, () => api.checkStoryboard(projectId), () => {
    toast(t("cont.box.started"), "info");
    onStarted();
  });
  const issues = continuity?.issues ?? [];

  return (
    <section className="panel flex flex-col gap-3 p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="eyebrow">{t("cont.box.eyebrow")}</div>
          <div className="mt-0.5 text-[0.85rem] text-ink-200">
            {continuity
              ? t("cont.box.checked", { time: `${formatDate(continuity.checked)} ${formatClock(continuity.checked)}`, count: issues.length })
              : t("cont.box.notChecked")}
          </div>
        </div>
        <Button
          size="sm"
          variant="secondary"
          busy={check.isPending || !!running}
          disabled={dirty}
          title={dirty ? t("cont.box.saveFirst") : undefined}
          onClick={() => check.mutate(undefined)}
        >
          {t("cont.box.check")}
        </Button>
      </div>
      {continuity && issues.length === 0 && <p className="text-[0.78rem] text-ok">{t("cont.box.noIssues")}</p>}
      {issues.length > 0 && (
        <ul className="flex max-h-72 flex-col gap-1.5 overflow-y-auto">
          {issues.map((it, i) => (
            <li key={`${it.shot}-${i}`} className="rounded-lg border border-ink-700 bg-ink-900 px-3 py-2 text-[0.78rem]">
              <button type="button" onClick={() => onJump(it.shot)} className="text-left hover:text-ink-100">
                <span className="mr-2 font-mono text-safe-hi">{it.shot}</span>
                <span className="text-ink-300">{it.problem}</span>
              </button>
              {it.before && (
                <details className="mt-1">
                  <summary className="w-fit cursor-pointer list-none text-[0.7rem] text-ink-500 hover:text-ink-200 [&::-webkit-details-marker]:hidden">
                    ▸ {t("cont.box.before")}
                  </summary>
                  <p className="mt-1 text-[0.75rem] italic leading-relaxed text-ink-400">{it.before}</p>
                </details>
              )}
            </li>
          ))}
        </ul>
      )}
      <InlineError error={check.error} />
    </section>
  );
}
