import { isNotFound } from "../../api/client";
import { useAnalysis } from "../../api/hooks";
import { ErrorBox, Loading } from "../../components/ui";
import { formatTime } from "../../lib/format";
import { kindColor, kindLabel } from "../../lib/kinds";
import { useT } from "../../i18n";

export function AnalysisSummary({ projectId }: { projectId: string }) {
  const { data, isPending, error, refetch } = useAnalysis(projectId);
  const t = useT();
  if (isPending) return <Loading label={t("analysis.loading")} />;
  if (error || !data) {
    if (isNotFound(error)) return null;
    return <ErrorBox error={error} onRetry={() => void refetch()} />;
  }
  const d = data.duration || 1;
  return (
    <section className="panel animate-rise p-6">
      <div className="flex flex-wrap items-end gap-x-10 gap-y-4">
        <div>
          <div className="eyebrow">{t("analysis.tempo")}</div>
          <div className="font-display text-5xl leading-none tabular">
            {data.bpm.toFixed(1)} <span className="font-sans text-base text-ink-400">BPM</span>
          </div>
        </div>
        <div>
          <div className="eyebrow">{t("analysis.duration")}</div>
          <div className="font-display text-5xl leading-none tabular">{formatTime(data.duration)}</div>
        </div>
        <div className="flex gap-8 pb-1 font-mono text-[0.78rem] text-ink-300">
          <span>
            <span className="text-ink-100">{data.downbeats.length}</span> {t("analysis.bars", { count: data.downbeats.length })}
          </span>
          <span>
            <span className="text-ink-100">{data.beats.length}</span> {t("analysis.beats", { count: data.beats.length })}
          </span>
          <span>
            <span className="text-ink-100">{data.lines.length}</span> {t("analysis.lines", { count: data.lines.length })}
          </span>
        </div>
      </div>

      <div className="mt-6 flex h-3 overflow-hidden rounded-full" aria-hidden>
        {data.sections.map((s, i) => (
          <div
            key={i}
            title={`${s.label} ${formatTime(s.start)}–${formatTime(s.end)}`}
            style={{ width: `${((s.end - s.start) / d) * 100}%`, background: kindColor(s.kind) }}
            className="border-r border-ink-950 last:border-r-0"
          />
        ))}
      </div>

      <ol className="mt-4 grid grid-cols-[repeat(auto-fill,minmax(250px,1fr))] gap-x-6 gap-y-1.5">
        {data.sections.map((s, i) => (
          <li key={i} className="flex items-center gap-2.5 text-sm">
            <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: kindColor(s.kind) }} />
            <span className="truncate text-ink-100" title={`${s.label} · ${kindLabel(s.kind, t)}`}>{s.label}</span>
            <span className="ml-auto whitespace-nowrap font-mono text-[0.72rem] text-ink-400 tabular">
              {formatTime(s.start)}–{formatTime(s.end)}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
