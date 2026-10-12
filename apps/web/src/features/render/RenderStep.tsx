import { useState } from "react";
import { api } from "../../api/client";
import { useEstimate, useRenderPresets, useStartJob, useVast } from "../../api/hooks";
import type { KeySet, PresetChoice } from "../../api/types";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { useToast } from "../../components/Toaster";
import { Button, InlineError, StepHeader } from "../../components/ui";
import { cx } from "../../lib/cx";
import { formatMinutes, formatUsd } from "../../lib/format";
import { useDebounced } from "../../lib/useDebounced";
import { activeJob, useWorkspace } from "../workspace/context";
import { FormatBadge, formatRatio, orientationInfo, projectFormat, projectOrientation } from "../../lib/orientation";
import { RenderJobPanel } from "./RenderJobPanel";
import { VastPanel } from "./VastPanel";
import { Trans, useT, type Key } from "../../i18n";
import { RenderOptions, flagOn } from "./RenderOptions";
import { CustomRender } from "./CustomRender";
import { useSaveSettings } from "./useSaveSettings";
import { PresetCards } from "../autopilot/PresetCards";

const SETS: { v: KeySet; label: string; note: Key }[] = [
  { v: "codex", label: "Codex", note: "render.set.codexNote" },
  { v: "comfy", label: "ComfyUI", note: "render.set.comfyNote" },
];

export function RenderStep() {
  const { project, jobs, openJobs } = useWorkspace();
  const toast = useToast();
  const t = useT();
  const vast = useVast();
  const orientation = projectOrientation(project);
  const ratio = formatRatio(projectFormat(project));
  const [set, setSet] = useState<KeySet>("codex");
  const [workers, setWorkers] = useState(Math.min(8, Math.max(1, project.settings.workers || 4)));
  const { gpu, gpus = 1, max_dph: maxDph } = project.settings;
  const [confirm, setConfirm] = useState(false);
  const presets = useRenderPresets(project.id);
  const saveSettings = useSaveSettings(project, "gpu.saveError");
  // match incl. max $/h (±15 %: preset caps follow live Vast prices) → the simple view shows the card's numbers; otherwise "custom settings" + /estimate
  const preset =
    presets.data?.presets.find(
      (pr) => pr.gpu === gpu && pr.gpus === gpus && pr.workers === workers && Math.abs(pr.max_dph - maxDph) <= pr.max_dph * 0.15,
    ) ?? null;
  // "Custom" = the saved settings as they are; auto-selected when they don't match a preset exactly
  const [forceCustom, setForceCustom] = useState(false);
  const choice: PresetChoice = forceCustom || !preset ? "custom" : preset.id;
  const w = useDebounced(workers, 350);
  const est = useEstimate(project.id, set, w, project.stage.shots > 0, { gpu, gpus, max_dph: maxDph });

  const running = activeJob(jobs, "render");
  const lastRender = running ?? jobs.find((j) => j.kind === "render");
  const e = est.data && est.data.set === set ? est.data : undefined;
  const blockedByKeys = set === "codex" && (e?.missing_keys ?? 0) > 0;
  const configured = !!vast.data?.configured;
  const balance = vast.data?.balance;
  // a preset card shows its own price — the button and the confirm must say the same; "Custom" uses /estimate
  const shownUsd = choice !== "custom" && preset ? preset.usd : e && !e.no_offers ? e.usd : undefined;
  const shownMinutes = choice !== "custom" && preset ? preset.minutes : e?.minutes;
  const lowBalance = shownUsd !== undefined && typeof balance === "number" && balance < shownUsd;

  const render = useStartJob(
    project.id,
    () =>
      api.render(project.id, {
        set,
        // a preset renders with its current cap, so the price shown on the card is the price paid
        ...(choice !== "custom" && preset
          ? { workers: preset.workers, gpu: preset.gpu, gpus: preset.gpus, max_dph: preset.max_dph }
          : { workers, gpu, gpus, max_dph: maxDph }),
        masters: true,
        confirm: true,
      }),
    () => {
      setConfirm(false);
      toast(t("render.startedToast"), "info");
      openJobs();
    },
  );

  const disabledReason = !configured
    ? t("render.needKey")
    : running
      ? t("render.alreadyRunning")
      : blockedByKeys
        ? t("render.missingKeys")
        : !e || w !== workers || e.workers !== workers
          ? t("render.waitingEstimate")
          : e.no_offers
            ? t("render.noOffers")
            : undefined;

  return (
    <div>
      <StepHeader
        index="04"
        title={t("step.video")}
        actions={
          <FormatBadge orientation={orientation} />
        }
      >
        <Trans
          k="render.lead"
          values={{ format: <>{t(orientationInfo(orientation).label).toLowerCase()} <b className="text-ink-200">{ratio}</b></> }}
        />
      </StepHeader>
      <InlineError error={render.error} />

      {configured && lowBalance && (
        <div role="alert" className="mb-6 rounded-lg border border-warn/40 bg-warn/[0.07] px-4 py-2.5 text-[0.85rem] text-warn">
          {t("render.lowBalance", { balance: formatUsd(balance), usd: formatUsd(shownUsd) })}
        </div>
      )}
      {lastRender && <div className="mb-6"><RenderJobPanel job={lastRender} projectId={project.id} /></div>}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <section className="panel flex flex-col gap-6 p-5">
          <div className="flex flex-col gap-2">
            <div className="label">{t("preset.title")}</div>
            <PresetCards
              data={presets.data}
              loading={presets.isPending}
              error={presets.error}
              selected={choice}
              onSelect={(pr) => {
                setForceCustom(false);
                setWorkers(pr.workers);
                saveSettings.mutate({ gpu: pr.gpu, gpus: pr.gpus, max_dph: pr.max_dph, workers: pr.workers });
              }}
              onCustom={() => setForceCustom(true)}
              customHint={t("preset.customNow", { n: workers, gpu: `${gpus > 1 ? `${gpus}× ` : ""}${gpu.replace(/_/g, " ")}` })}
              customPrice={choice === "custom" && e && !e.no_offers ? formatUsd(e.usd) : undefined}
            />
          </div>
          {choice === "custom" && (
            <CustomRender
              project={project}
              workers={workers}
              onWorkers={setWorkers}
              onWorkersCommit={(n) => saveSettings.mutate({ workers: n })}
              estimate={e}
              estimating={est.isFetching}
              estimateError={est.error}
            />
          )}
          <RenderOptions project={project} />
          {blockedByKeys && e && (
            <p role="alert" className="rounded-lg border border-warn/40 bg-warn/[0.07] px-4 py-2.5 text-[0.85rem] text-warn">
              {t("est.missing", { count: e.missing_keys })}
            </p>
          )}
          {choice === "custom" && e?.no_offers && (
            <p role="alert" className="rounded-lg border border-warn/40 bg-warn/[0.07] px-4 py-2.5 text-[0.85rem] text-warn">
              {t("render.noOffers")}
            </p>
          )}
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="primary" disabled={!!disabledReason} title={disabledReason} busy={render.isPending} onClick={() => setConfirm(true)}>
              {shownUsd !== undefined ? t("render.buttonCost", { usd: formatUsd(shownUsd) }) : t("render.button")}
            </Button>
            {disabledReason && <span className="text-[0.75rem] text-ink-500">{disabledReason}</span>}
          </div>

          <details className="group rounded-lg border border-ink-700 bg-ink-900/40">
            <summary className="flex cursor-pointer list-none items-center gap-3 px-4 py-3 [&::-webkit-details-marker]:hidden">
              <span aria-hidden className="text-ink-400 transition-transform group-open:rotate-90">▸</span>
              <span className="text-sm text-ink-100">{t("render.advanced")}</span>
              <span className="truncate text-[0.72rem] text-ink-500">{t("render.advancedHint")}</span>
            </summary>
            <div className="border-t border-ink-700 px-4 py-5">
              <div className="label" id="set-label">{t("render.setLabel")}</div>
              <div role="radiogroup" aria-labelledby="set-label" className="grid max-w-md grid-cols-2 gap-2">
                {SETS.map((s) => (
                  <button
                    key={s.v}
                    type="button"
                    role="radio"
                    aria-checked={set === s.v}
                    onClick={() => setSet(s.v)}
                    className={cx(
                      "rounded-lg border px-3 py-2.5 text-left transition-colors",
                      set === s.v ? "border-safe bg-safe/[0.07]" : "border-ink-600 hover:border-ink-400",
                    )}
                  >
                    <div className="font-display text-xl">{s.label}</div>
                    <div className="text-[0.72rem] text-ink-400">{t(s.note)}</div>
                  </button>
                ))}
              </div>
            </div>
          </details>
        </section>
        <VastPanel />
      </div>

      <ConfirmDialog
        open={confirm}
        title={t("render.confirmTitle")}
        confirmLabel={shownUsd !== undefined ? t("render.confirmCost", { usd: formatUsd(shownUsd) }) : t("render.confirm")}
        busy={render.isPending}
        onConfirm={() => render.mutate(undefined)}
        onClose={() => setConfirm(false)}
      >
        {e && (
          <div className="flex flex-col gap-3">
            <p>
              <Trans k="render.estCost" values={{ usd: <b className="font-display text-3xl text-safe-hi">{formatUsd(shownUsd)}</b> }} />
            </p>
            <ul className="font-mono text-[0.78rem] text-ink-300">
              <li>{t("render.lineFormat", { ratio, set: set === "codex" ? "Codex" : "ComfyUI", count: e.clips })}</li>
              <li>{t("render.lineCards", { workers, gpus, gpu: gpu.replace(/_/g, " "), dph: formatUsd(maxDph) })}</li>
              <li>
                {t("render.lineOptions", {
                  captions: t(flagOn(project.settings, "captions") ? "renderOpts.on" : "renderOpts.off"),
                  beat: t(flagOn(project.settings, "beat_motion") ? "renderOpts.on" : "renderOpts.off"),
                })}
              </li>
              <li>{t("render.lineTime", { time: formatMinutes(shownMinutes ?? e.minutes), gb: e.models_gb })}</li>
              <li className={lowBalance ? "text-warn" : undefined}>
                {t("render.lineBalance", { balance: formatUsd(balance) })}
                {lowBalance ? t("render.lineBalanceLow") : ""}
              </li>
            </ul>
            <p className="text-ink-400">
              {t("render.billing", { release: t("vastPanel.releaseAll") })}
            </p>
          </div>
        )}
        <InlineError error={render.error} />
      </ConfirmDialog>
    </div>
  );
}
