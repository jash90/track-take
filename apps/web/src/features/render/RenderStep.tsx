import { useState } from "react";
import { api } from "../../api/client";
import { useEstimate, useStartJob, useVast } from "../../api/hooks";
import type { KeySet } from "../../api/types";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { useToast } from "../../components/Toaster";
import { Button, Hint, InlineError, StepHeader } from "../../components/ui";
import { cx } from "../../lib/cx";
import { formatMinutes, formatUsd } from "../../lib/format";
import { useDebounced } from "../../lib/useDebounced";
import { activeJob, useWorkspace } from "../workspace/context";
import { FormatBadge, formatRatio, orientationInfo, projectFormat, projectOrientation } from "../../lib/orientation";
import { EstimatePanel } from "./EstimatePanel";
import { RenderJobPanel } from "./RenderJobPanel";
import { VastPanel } from "./VastPanel";
import { Trans, useT, type Key } from "../../i18n";

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
  const [gpu, setGpu] = useState(project.settings.gpu);
  const [maxDph, setMaxDph] = useState(project.settings.max_dph);
  const [confirm, setConfirm] = useState(false);
  const w = useDebounced(workers, 350);
  const est = useEstimate(project.id, set, w, project.stage.shots > 0);

  const running = activeJob(jobs, "render");
  const lastRender = running ?? jobs.find((j) => j.kind === "render");
  const e = est.data && est.data.set === set ? est.data : undefined;
  const blockedByKeys = set === "codex" && (e?.missing_keys ?? 0) > 0;
  const configured = !!vast.data?.configured;
  const balance = vast.data?.balance;
  const lowBalance = !!e && typeof balance === "number" && balance < e.usd;

  const render = useStartJob(
    project.id,
    () =>
      api.render(project.id, {
        set,
        workers,
        gpu: gpu.trim() || undefined,
        max_dph: Number.isFinite(maxDph) && maxDph > 0 ? maxDph : undefined,
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
          : undefined;

  return (
    <div>
      <StepHeader
        index="04"
        title={t("step.video")}
        actions={
          <>
          <FormatBadge orientation={orientation} />
          <Button variant="primary" disabled={!!disabledReason} title={disabledReason} busy={render.isPending} onClick={() => setConfirm(true)}>
            {e ? t("render.buttonCost", { usd: formatUsd(e.usd) }) : t("render.button")}
          </Button>
          </>
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
          {t("render.lowBalance", { balance: formatUsd(balance), usd: formatUsd(e?.usd) })}
        </div>
      )}
      {lastRender && <div className="mb-6"><RenderJobPanel job={lastRender} projectId={project.id} /></div>}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <section className="panel flex flex-col gap-6 p-5">
          <div className="grid gap-5 md:grid-cols-2">
            <div>
              <div className="label" id="set-label">{t("render.setLabel")}</div>
              <div role="radiogroup" aria-labelledby="set-label" className="grid grid-cols-2 gap-2">
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
            <div>
              <label className="label" htmlFor="workers">
                <Trans k="render.workers" values={{ n: <span className="font-mono text-ink-100">{workers}</span> }} />
              </label>
              <input id="workers" type="range" min={1} max={8} step={1} value={workers} onChange={(ev) => setWorkers(Number(ev.target.value))} className="slider mt-3 w-full" />
              <div className="mt-1 flex justify-between font-mono text-[0.62rem] text-ink-500">
                {Array.from({ length: 8 }, (_, i) => <span key={i}>{i + 1}</span>)}
              </div>
            </div>
          </div>
          <div className="grid gap-5 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="gpu">GPU</label>
              <input id="gpu" className="field font-mono" value={gpu} onChange={(ev) => setGpu(ev.target.value)} />
            </div>
            <div>
              <label className="label" htmlFor="dph">{t("render.maxDph")}</label>
              <input id="dph" type="number" min={0.05} step={0.05} className="field font-mono" value={maxDph} onChange={(ev) => setMaxDph(Number(ev.target.value))} />
            </div>
          </div>
          <EstimatePanel estimate={e} loading={est.isFetching} error={est.error} ready={project.stage.shots > 0} />
          <Hint>
            {t("render.hint", { gb: e?.models_gb ?? 40 })}
          </Hint>
        </section>
        <VastPanel />
      </div>

      <ConfirmDialog
        open={confirm}
        title={t("render.confirmTitle")}
        confirmLabel={e ? t("render.confirmCost", { usd: formatUsd(e.usd) }) : t("render.confirm")}
        busy={render.isPending}
        onConfirm={() => render.mutate(undefined)}
        onClose={() => setConfirm(false)}
      >
        {e && (
          <div className="flex flex-col gap-3">
            <p>
              <Trans k="render.estCost" values={{ usd: <b className="font-display text-3xl text-safe-hi">{formatUsd(e.usd)}</b> }} />
            </p>
            <ul className="font-mono text-[0.78rem] text-ink-300">
              <li>{t("render.lineFormat", { ratio, set: set === "codex" ? "Codex" : "ComfyUI", count: e.clips })}</li>
              <li>{t("render.lineCards", { workers, gpu, dph: formatUsd(maxDph) })}</li>
              <li>{t("render.lineTime", { time: formatMinutes(e.minutes), gb: e.models_gb })}</li>
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
