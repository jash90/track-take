import type { Estimate, Project } from "../../api/types";
import { Hint, Spinner } from "../../components/ui";
import { useT } from "../../i18n";
import { formatMinutes, formatUsd } from "../../lib/format";
import { EstimatePanel } from "./EstimatePanel";
import { GpuSettings } from "./GpuSettings";
import { MachinesSlider } from "./MachinesSlider";

interface Props {
  project: Project;
  workers: number;
  onWorkers: (n: number) => void;
  onWorkersCommit: (n: number) => void;
  estimate: Estimate | undefined;
  estimating: boolean;
  estimateError: unknown;
  /** compact = dialog version: no alternatives/offers table, one estimate line */
  compact?: boolean;
}

/** "Custom" render option: the full GPU picker, GPUs per machine, max $/h, machines and the live estimate. */
export function CustomRender({ project, workers, onWorkers, onWorkersCommit, estimate, estimating, estimateError, compact }: Props) {
  const t = useT();
  const hasShots = project.stage.shots > 0;
  return (
    <div className="flex flex-col gap-5 rounded-xl border border-ink-700 bg-ink-900/40 p-4">
      <GpuSettings project={project} />
      <MachinesSlider value={workers} onChange={onWorkers} onCommit={onWorkersCommit} />
      {compact ? (
        !hasShots ? (
          <p className="text-[0.78rem] text-ink-400">{t("preset.customNoStoryboard")}</p>
        ) : estimate && !estimate.no_offers ? (
          <p className="font-mono text-[0.82rem] text-ink-200">
            {t("preset.customEstimate", { usd: formatUsd(estimate.usd), time: formatMinutes(estimate.minutes) })}
            {estimating && <Spinner small className="ml-2" />}
          </p>
        ) : estimate?.no_offers ? (
          <p className="text-[0.82rem] text-warn">{t("render.noOffers")}</p>
        ) : (
          <p className="flex items-center gap-2 text-[0.78rem] text-ink-400"><Spinner small /> {t("est.loading")}</p>
        )
      ) : (
        <>
          <EstimatePanel estimate={estimate} loading={estimating} error={estimateError} ready={hasShots} />
          <Hint>{t("render.hint", { gb: estimate?.models_gb ?? 40 })}</Hint>
        </>
      )}
    </div>
  );
}
