import type { Job } from "../../api/types";
import { Button, ProgressBar } from "../../components/ui";
import { useT } from "../../i18n";
import { jobTitle } from "../jobs/jobTitle";

/** The storyboard was planned for another animation style than the project's current one. */
export interface AnimationMismatch {
  planned: string; // display name
  current: string;
  onReplan: () => void;
  busy: boolean;
  disabled: boolean;
}

interface Props {
  writing: Job | undefined;
  stale: boolean;
  onLoadServer: () => void;
  mismatch?: AnimationMismatch | null;
}

/** "Director is writing — editing locked", "newer version on the server" and "planned for another style" notices. */
export function StoryboardBanners({ writing, stale, onLoadServer, mismatch }: Props) {
  const t = useT();
  return (
    <>
      {mismatch && (
        <div role="status" className="mb-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-lg border border-warn/40 bg-warn/[0.06] px-4 py-2.5 text-sm">
          <span className="min-w-0 flex-1">{t("sb.animMismatch", { planned: mismatch.planned, current: mismatch.current })}</span>
          <Button size="sm" variant="secondary" busy={mismatch.busy} disabled={mismatch.disabled} onClick={mismatch.onReplan}>
            {t("sb.animReplan")}
          </Button>
        </div>
      )}
      {writing && (
        <div className="mb-4 rounded-xl border border-safe/40 bg-safe/[0.05] px-5 py-3">
          <div className="flex items-center justify-between gap-4 text-sm">
            <span>{t("sb.writingBanner", { title: jobTitle(writing, t) })}</span>
            <span className="truncate font-mono text-[0.75rem] text-ink-400">{writing.message}</span>
          </div>
          {writing.progress && <ProgressBar className="mt-2" value={writing.progress.done} total={writing.progress.total} />}
        </div>
      )}
      {stale && (
        <div className="mb-4 flex items-center justify-between gap-4 rounded-lg border border-warn/40 bg-warn/[0.06] px-4 py-2 text-sm">
          <span>{t("sb.stale")}</span>
          <Button size="sm" variant="ghost" onClick={onLoadServer}>{t("sb.loadServer")}</Button>
        </div>
      )}
    </>
  );
}
