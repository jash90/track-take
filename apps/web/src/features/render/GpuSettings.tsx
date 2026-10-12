import { useEffect, useState } from "react";
import { useVastGpus } from "../../api/hooks";
import type { Project, VastGpu } from "../../api/types";
import { useT } from "../../i18n";
import { formatUsd } from "../../lib/format";
import { useDebounced } from "../../lib/useDebounced";
import { GpuPicker } from "./GpuPicker";
import { useSaveSettings } from "./useSaveSettings";
import { useQueryClient } from "@tanstack/react-query";
import { qk } from "../../api/client";
import { REGIONS, regionValue } from "./region";

/** GPU model (live Vast offers), GPUs per machine and max $/h per GPU — all saved to project settings. */
export function GpuSettings({ project, onWorkersReset }: { project: Project; onWorkersReset?: (n: number) => void }) {
  const t = useT();
  const region = regionValue(project.settings.region);
  const gpusQ = useVastGpus(region);
  const save = useSaveSettings(project, "gpu.saveError");
  const qc = useQueryClient();
  const saveRegion = (value: string) =>
    save.mutate(
      { region: value },
      {
        // presets and estimates are priced server-side for the project's region
        onSuccess: () => {
          void qc.invalidateQueries({ queryKey: qk.renderPresets(project.id) });
          void qc.invalidateQueries({ queryKey: ["project", project.id, "estimate"] });
        },
      },
    );
  const { gpu, gpus = 1, max_dph } = project.settings;
  const card = gpusQ.data?.gpus.find((g) => g.gpu === gpu) ?? null;

  // max $/h: local text, saved debounced once it is a valid positive number
  const [dph, setDph] = useState(String(max_dph));
  const dphDebounced = useDebounced(dph, 600);
  useEffect(() => {
    const v = Number(dphDebounced.replace(",", "."));
    if (Number.isFinite(v) && v > 0 && v !== project.settings.max_dph) save.mutate({ max_dph: v });
  }, [dphDebounced]);

  const pickCard = (value: string, _picked: VastGpu | null) => {
    if (value === gpu) return;
    // a new card starts as 1 GPU on 1 machine — never inherit a multi-GPU host from the previous choice
    onWorkersReset?.(1);
    save.mutate({ gpu: value, gpus: 1, workers: 1 });
  };

  const hosts = card?.hosts ?? [];
  const hostSizes = hosts.some((h) => h.gpus === gpus) ? hosts : [...hosts, { gpus, offers: 0, min_dph: 0 }].sort((a, b) => a.gpus - b.gpus);

  return (
    <div className="flex flex-col gap-5">
    <div>
      <label className="label" htmlFor="region">{t("region.label")}</label>
      <select id="region" className="field max-w-md" value={region} onChange={(e) => saveRegion(e.target.value)}>
        {REGIONS.map((r) => (
          <option key={r.value} value={r.value}>{t(r.label)}</option>
        ))}
        {!REGIONS.some((r) => r.value === region) && <option value={region}>{t("region.other", { list: region })}</option>}
      </select>
      <p className="mt-1 text-[0.7rem] text-ink-500">{t("region.hint")}</p>
    </div>
    <div className="grid gap-5 md:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)_minmax(0,0.8fr)]">
      <div>
        <label className="label" htmlFor="gpu">{t("gpu.label")}</label>
        <GpuPicker value={gpu} data={gpusQ.data} loading={gpusQ.isFetching} failed={gpusQ.isError} onPick={pickCard} />
      </div>
      <div>
        <label className="label" htmlFor="gpus">{t("gpu.perMachine")}</label>
        <select
          id="gpus"
          className="field font-mono"
          value={gpus}
          onChange={(e) => save.mutate({ gpus: Number(e.target.value) })}
        >
          {hostSizes.map((h) => (
            <option key={h.gpus} value={h.gpus}>
              {h.offers > 0 ? t("gpu.hostOption", { n: h.gpus, usd: formatUsd(h.min_dph, 2) }) : t("gpu.hostNoOffers", { n: h.gpus })}
            </option>
          ))}
        </select>
        <p className="mt-1 text-[0.7rem] leading-snug text-ink-500">{t("gpu.perMachineHint")}</p>
      </div>
      <div>
        <label className="label" htmlFor="dph">{t("render.maxDph")}</label>
        <input
          id="dph"
          type="number"
          inputMode="decimal"
          min={0.05}
          step={0.05}
          className="field font-mono"
          value={dph}
          onChange={(e) => setDph(e.target.value)}
        />
      </div>
    </div>
    </div>
  );
}
