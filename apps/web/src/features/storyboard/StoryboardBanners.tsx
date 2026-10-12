import type { Job } from "../../api/types";
import { Button, ProgressBar } from "../../components/ui";
import { useT } from "../../i18n";
import { jobTitle } from "../jobs/jobTitle";

/** "Director is writing — editing locked" and "newer version on the server" notices. */
export function StoryboardBanners({ writing, stale, onLoadServer }: { writing: Job | undefined; stale: boolean; onLoadServer: () => void }) {
  const t = useT();
  return (
    <>
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
