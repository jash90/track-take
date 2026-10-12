import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, qk } from "../../api/client";
import { useEstimate, useRenderPresets, useSetup, useStartJob } from "../../api/hooks";
import { useDebounced } from "../../lib/useDebounced";
import { CustomRender } from "../render/CustomRender";
import { useSaveSettings } from "../render/useSaveSettings";
import type { PresetChoice, Project } from "../../api/types";
import { Dialog } from "../../components/Dialog";
import { useToast } from "../../components/Toaster";
import { Button, InlineError } from "../../components/ui";
import { useT } from "../../i18n";
import { PresetCards, suggestedBudget } from "./PresetCards";
import { SetupChecklist } from "./SetupChecklist";
import { formatUsd, machineSummary } from "../../lib/format";

export interface MakeVideoInitial {
  preset?: PresetChoice;
  budget?: number;
  review?: boolean;
}

interface Props {
  open: boolean;
  onClose: () => void;
  project: Project;
  initial?: MakeVideoInitial;
}

/** One dialog to go from a song to a video: pick an option, a budget, start the autopilot. */
export function MakeVideoDialog({ open, onClose, project, initial }: Props) {
  const t = useT();
  const qc = useQueryClient();
  const toast = useToast();
  const setup = useSetup(open);
  const presets = useRenderPresets(project.id, open);
  const [skipSetup, setSkipSetup] = useState(false);
  const [preset, setPreset] = useState<PresetChoice>(initial?.preset ?? "recommended");
  const [workers, setWorkers] = useState(Math.min(8, Math.max(1, project.settings.workers || 1)));
  const saveSettings = useSaveSettings(project, "gpu.saveError");
  const custom = preset === "custom";
  const w = useDebounced(workers, 350);
  const { gpu, gpus = 1, max_dph } = project.settings;
  const est = useEstimate(project.id, "codex", w, open && custom && project.stage.shots > 0, { gpu, gpus, max_dph });
  const [budget, setBudget] = useState<string>(initial?.budget ? String(initial.budget) : "");
  const [budgetTouched, setBudgetTouched] = useState(!!initial?.budget);
  const [review, setReview] = useState(initial?.review ?? true);

  // reset when reopened with other initial values
  useEffect(() => {
    if (!open) return;
    setPreset(initial?.preset ?? "recommended");
    setWorkers(Math.min(8, Math.max(1, project.settings.workers || 1)));
    setBudget(initial?.budget ? String(initial.budget) : "");
    setBudgetTouched(!!initial?.budget);
    setReview(initial?.review ?? true);
  }, [open]);

  // prefill the budget from the chosen option until the user edits it
  const recommended = presets.data?.presets.find((p) => p.id === "recommended");
  const chosen = custom ? null : (presets.data?.presets.find((p) => p.id === preset) ?? recommended);
  const basisUsd = custom ? (est.data && !est.data.no_offers ? est.data.usd : recommended?.usd) : chosen?.usd;
  useEffect(() => {
    if (!budgetTouched && basisUsd !== undefined) setBudget(suggestedBudget(basisUsd).toFixed(2));
  }, [basisUsd, budgetTouched]);

  const start = useStartJob(
    project.id,
    (vars: { budget: number; preset: PresetChoice; review: boolean }) =>
      api.autopilot(project.id, { budget_usd: vars.budget, preset: vars.preset, review: vars.review }),
    () => {
      void qc.invalidateQueries({ queryKey: qk.project(project.id) });
      toast(t("ap.startedToast"), "info");
      onClose();
    },
  );

  const needSetup = !!setup.data && !setup.data.ready && !skipSetup;
  const budgetNum = Number(budget.replace(",", "."));
  const canStart = !!project.inputs.song && Number.isFinite(budgetNum) && budgetNum > 0 && !start.isPending;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={needSetup ? t("mv.setupFirst") : t("mv.title")}
      wide
      footer={
        needSetup ? (
          <>
            <Button variant="ghost" onClick={() => setSkipSetup(true)}>{t("mv.setupSkip")}</Button>
            <Button variant="primary" disabled={!setup.data?.ready} onClick={() => setSkipSetup(true)}>{t("mv.setupContinue")}</Button>
          </>
        ) : (
          <>
            <Button variant="ghost" onClick={onClose}>{t("common.cancel")}</Button>
            <Button
              variant="primary"
              busy={start.isPending}
              disabled={!canStart}
              title={!project.inputs.song ? t("mv.needSong") : undefined}
              onClick={() => start.mutate({ budget: budgetNum, preset: custom ? "custom" : (chosen?.id ?? preset), review })}
            >
              {t("mv.start")}
            </Button>
          </>
        )
      }
    >
      {needSetup ? (
        <SetupChecklist />
      ) : (
        <div className="flex flex-col gap-5">
          <p className="text-sm leading-relaxed text-ink-400">{t("mv.lead")}</p>
          <PresetCards
            data={presets.data}
            loading={presets.isPending}
            error={presets.error}
            selected={custom ? "custom" : (chosen?.id ?? null)}
            onSelect={(p) => {
              setPreset(p.id);
              setBudgetTouched(false);
            }}
            onCustom={() => {
              setPreset("custom");
              setBudgetTouched(false);
            }}
            customHint={t("preset.customNow", { summary: machineSummary(t, workers, gpus, gpu) })}
            region={project.settings.region}
            customPrice={custom && est.data && !est.data.no_offers ? formatUsd(est.data.usd) : undefined}
          />
          {custom && (
            <CustomRender
              compact
              project={project}
              workers={workers}
              onWorkers={setWorkers}
              onWorkersCommit={(n) => saveSettings.mutate({ workers: n })}
              estimate={est.data}
              estimating={est.isFetching}
              estimateError={est.error}
            />
          )}
          <div className="grid gap-4 sm:grid-cols-[180px_minmax(0,1fr)] sm:items-start">
            <div>
              <label className="label" htmlFor="ap-budget">{t("mv.budget")}</label>
              <div className="relative">
                <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 font-mono text-ink-400">$</span>
                <input
                  id="ap-budget"
                  type="number"
                  inputMode="decimal"
                  min={0.5}
                  step={0.5}
                  className="field pl-7 font-mono"
                  value={budget}
                  onChange={(e) => {
                    setBudget(e.target.value);
                    setBudgetTouched(true);
                  }}
                />
              </div>
            </div>
            <p className="text-[0.78rem] leading-relaxed text-ink-400 sm:pt-7">{t("mv.budgetHint")}</p>
          </div>
          <label className="flex items-center gap-2.5 text-sm text-ink-200">
            <input type="checkbox" checked={review} onChange={(e) => setReview(e.target.checked)} className="h-4 w-4 accent-[#ff5a3c]" />
            {t("mv.review")}
          </label>
          <InlineError error={start.error} />
        </div>
      )}
    </Dialog>
  );
}
