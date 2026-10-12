import { useEffect, useState } from "react";
import { useVastGpus } from "../../api/hooks";
import type { Project, VastGpu } from "../../api/types";
import { useT } from "../../i18n";
import { formatUsd } from "../../lib/format";
import { useDebounced } from "../../lib/useDebounced";
import { GpuPicker } from "./GpuPicker";
import { useSaveSettings } from "./useSaveSettings";

/** GPU model (live Vast offers), GPUs per machine and max $/h per GPU — all saved to project settings. */
export function GpuSettings({ project }: { project: Project }) {
  const t = useT();
  const gpusQ = useVastGpus();
  const save = useSaveSettings(project, "gpu.saveError");
  const { gpu, gpus = 1, max_dph } = project.settings;
  const card = gpusQ.data?.gpus.find((g) => g.gpu === gpu) ?? null;

  // max $/h: local text, saved debounced once it is a valid positive number
  const [dph, setDph] = useState(String(max_dph));
  const dphDebounced = useDebounced(dph, 600);
  useEffect(() => {
    const v = Number(dphDebounced.replace(",", "."));
    if (Number.isFinite(v) && v > 0 && v !== project.settings.max_dph) save.mutate({ max_dph: v });
  }, [dphDebounced]);

  const pickCard = (value: string, picked: VastGpu | null) => {
    if (value === gpu) return;
    const sizes = picked?.hosts.map((h) => h.gpus) ?? [];
    const nextGpus = sizes.length === 0 || sizes.includes(gpus) ? gpus : sizes.includes(1) ? 1 : (sizes[0] ?? 1);
    save.mutate(nextGpus === gpus ? { gpu: value } : { gpu: value, gpus: nextGpus });
  };

  const hosts = card?.hosts ?? [];
  const hostSizes = hosts.some((h) => h.gpus === gpus) ? hosts : [...hosts, { gpus, offers: 0, min_dph: 0 }].sort((a, b) => a.gpus - b.gpus);

  return (
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
  );
}
