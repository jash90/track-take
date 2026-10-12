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

const SETS: { v: KeySet; label: string; note: string }[] = [
  { v: "codex", label: "Codex", note: "gotowe klatki z kroku 03" },
  { v: "comfy", label: "ComfyUI", note: "klatki rysowane na Vast" },
];

export function RenderStep() {
  const { project, jobs, openJobs } = useWorkspace();
  const toast = useToast();
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
      toast("Render ruszył — wynajmuję karty na Vast", "info");
      openJobs();
    },
  );

  const disabledReason = !configured
    ? "Najpierw dodaj klucz Vast"
    : running
      ? "Render już trwa"
      : blockedByKeys
        ? "Brakuje klatek Codex"
        : !e || w !== workers || e.workers !== workers
          ? "Czekam na wycenę"
          : undefined;

  return (
    <div>
      <StepHeader
        index="04"
        title="Wideo"
        actions={
          <>
          <FormatBadge orientation={orientation} />
          <Button variant="primary" disabled={!!disabledReason} title={disabledReason} busy={render.isPending} onClick={() => setConfirm(true)}>
            Renderuj na Vast{e ? ` · ~${formatUsd(e.usd)}` : ""}
          </Button>
          </>
        }
      >
        Renderujemy jeden format — {orientationInfo(orientation).label.toLowerCase()} <b className="text-ink-200">{ratio}</b>. Klipy i cały
        teledysk (podgląd + master) powstają na wynajętych kartach Vast.ai — Mac pobiera tylko gotowe pliki, a karty zwalniają się same.
      </StepHeader>
      <InlineError error={render.error} />

      {configured && lowBalance && (
        <div role="alert" className="mb-6 rounded-lg border border-warn/40 bg-warn/[0.07] px-4 py-2.5 text-[0.85rem] text-warn">
          Saldo Vast ({formatUsd(balance)}) jest niższe niż szacowany koszt renderu ({formatUsd(e?.usd)}). Doładuj konto na console.vast.ai,
          inaczej karty mogą zostać zatrzymane w trakcie.
        </div>
      )}
      {lastRender && <div className="mb-6"><RenderJobPanel job={lastRender} projectId={project.id} /></div>}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <section className="panel flex flex-col gap-6 p-5">
          <div className="grid gap-5 md:grid-cols-2">
            <div>
              <div className="label" id="set-label">Zestaw klatek</div>
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
                    <div className="text-[0.72rem] text-ink-400">{s.note}</div>
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="label" htmlFor="workers">
                Karty równolegle: <span className="font-mono text-ink-100">{workers}</span>
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
              <label className="label" htmlFor="dph">Maks. $/h za kartę</label>
              <input id="dph" type="number" min={0.05} step={0.05} className="field font-mono" value={maxDph} onChange={(ev) => setMaxDph(Number(ev.target.value))} />
            </div>
          </div>
          <EstimatePanel estimate={e} loading={est.isFetching} error={est.error} ready={project.stage.shots > 0} />
          <Hint>
            Więcej kart = krócej, ale każda pobiera ~{e?.models_gb ?? "40"} GB modeli, więc koszt rośnie wolniej niż czas spada. Wycena dotyczy
            GPU i ustawień z tego formularza; pokazane oferty to aktualne ceny Vast.
          </Hint>
        </section>
        <VastPanel />
      </div>

      <ConfirmDialog
        open={confirm}
        title="Wynająć karty na Vast?"
        confirmLabel={e ? `Renderuj za ~${formatUsd(e.usd)}` : "Renderuj"}
        busy={render.isPending}
        onConfirm={() => render.mutate(undefined)}
        onClose={() => setConfirm(false)}
      >
        {e && (
          <div className="flex flex-col gap-3">
            <p>
              Szacowany koszt: <b className="font-display text-3xl text-safe-hi">{formatUsd(e.usd)}</b>
            </p>
            <ul className="font-mono text-[0.78rem] text-ink-300">
              <li>format: {ratio} · zestaw: {set === "codex" ? "Codex" : "ComfyUI"} · {e.clips} klipów</li>
              <li>karty: {workers} × {gpu} (maks. {formatUsd(maxDph)}/h)</li>
              <li>czas: ~{formatMinutes(e.minutes)} · modele {e.models_gb} GB na kartę</li>
              <li className={lowBalance ? "text-warn" : undefined}>
                saldo Vast: {formatUsd(balance)}
                {lowBalance ? " — mniej niż szacowany koszt!" : ""}
              </li>
            </ul>
            <p className="text-ink-400">
              Karty są płatne od chwili wynajęcia do zwolnienia. Po zakończeniu backend sam je zwalnia; w razie problemów użyj „Zwolnij wszystkie
              karty”.
            </p>
          </div>
        )}
        <InlineError error={render.error} />
      </ConfirmDialog>
    </div>
  );
}
