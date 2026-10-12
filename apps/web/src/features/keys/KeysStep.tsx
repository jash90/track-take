import { useCallback, useMemo, useState } from "react";
import { api, isNotFound } from "../../api/client";
import { useCheckKeys, useKeys, useStartJob, useStoryboard } from "../../api/hooks";
import type { KeySet, Shot } from "../../api/types";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { Lightbox, type LightboxItem } from "../../components/Lightbox";
import { useToast } from "../../components/Toaster";
import { Button, Chip, Empty, NextStepLink, ErrorBox, Hint, InlineError, Loading, ProgressBar, StepHeader } from "../../components/ui";
import { cx } from "../../lib/cx";
import { activeJob, useWorkspace } from "../workspace/context";
import { formatRatio, projectFormat, projectOrientation } from "../../lib/orientation";
import { CharacterSheet } from "./CharacterSheet";
import { KeyCheckReport } from "./KeyCheckReport";
import { KeyRow, SET_LABEL, keyRowId } from "./KeyRow";
import { checkKinds, isStale, keysCountSummary } from "./stale";
import { dependentShots, isCut } from "../../lib/continuity";
import { Trans, useT } from "../../i18n";
import { jobTitle } from "../jobs/jobTitle";

type View = "codex" | "comfy" | "both";
const VIEWS: { v: View; label: string | null }[] = [
  { v: "codex", label: "Codex" },
  { v: "comfy", label: "ComfyUI" },
  { v: "both", label: null },
];
type ShotLike = Pick<Shot, "id" | "start" | "end" | "section" | "kind" | "lines" | "cut">;
type Pending = { kind: "missing" } | { kind: "shot"; id: string } | { kind: "character" } | { kind: "check" } | null;

export function KeysStep() {
  const { project, jobs, openJobs } = useWorkspace();
  const id = project.id;
  const orientation = projectOrientation(project);
  const ratio = formatRatio(projectFormat(project));
  const toast = useToast();
  const t = useT();
  const keysQ = useKeys(id);
  const sbQ = useStoryboard(id, project.stage.storyboard);
  const [view, setView] = useState<View>("both");
  const [lbIndex, setLbIndex] = useState<number | null>(null);
  const [pending, setPending] = useState<Pending>(null);
  const [regenShot, setRegenShot] = useState<string | null>(null);

  const keysJob = activeJob(jobs, "keys_codex");
  const charJob = activeJob(jobs, "character");
  const checkJob = activeJob(jobs, "keys_check");
  const sets: KeySet[] = view === "both" ? ["codex", "comfy"] : [view];

  const shots: ShotLike[] = useMemo(() => {
    if (sbQ.data) return sbQ.data.shots;
    const ids = Object.keys({ ...keysQ.data?.sets.codex, ...keysQ.data?.sets.comfy }).sort();
    return ids.map((sid) => ({ id: sid, start: 0, end: 0, section: "", kind: "other", lines: [] }));
  }, [sbQ.data, keysQ.data]);

  const counts = useMemo(() => {
    const c: Record<KeySet, number> = { codex: 0, comfy: 0 };
    for (const set of ["codex", "comfy"] as KeySet[]) {
      for (const s of shots) if (keysQ.data?.sets[set]?.[s.id]?.[orientation]) c[set] += 1;
    }
    return c;
  }, [keysQ.data, shots, orientation]);
  const staleCodex = useMemo(
    () => shots.filter((s) => isStale(keysQ.data?.sets.codex?.[s.id], orientation)).length,
    [keysQ.data, shots, orientation],
  );
  const total = shots.length;
  const issueKinds = useMemo(() => checkKinds(keysQ.data), [keysQ.data]);

  const { items, index } = useMemo(() => {
    const items: LightboxItem[] = [];
    const index = new Map<string, number>();
    const cs = keysQ.data?.character_sheet;
    if (cs) {
      index.set("character", items.length);
      items.push({ src: cs, caption: t("keys.sheet") });
    }
    for (const s of shots) {
      for (const set of sets) {
        const src = keysQ.data?.sets[set]?.[s.id]?.[orientation];
        if (!src) continue;
        index.set(`${s.id}:${set}`, items.length);
        items.push({ src, caption: `${s.id} · ${SET_LABEL[set]} · ${ratio}` });
      }
    }
    return { items, index };
  }, [shots, keysQ.data, view, orientation, ratio]);

  const openKey = useCallback((sid: string, set: KeySet) => {
    const i = index.get(`${sid}:${set}`);
    if (i !== undefined) setLbIndex(i);
  }, [index]);
  const deps = useMemo(() => {
    const out: Record<string, string[]> = {};
    shots.forEach((s, i) => {
      out[s.id] = dependentShots(shots, i).map((d) => d.id);
    });
    return out;
  }, [shots]);
  const askRegen = useCallback((sid: string) => setPending({ kind: "shot", id: sid }), []);
  const jumpTo = useCallback((sid: string) => {
    document.getElementById(keyRowId(sid))?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  const started = () => {
    openJobs();
    setPending(null);
  };
  const genKeys = useStartJob(id, (shotsToGen: string[] | undefined) =>
    api.codexKeys(id, shotsToGen ? { shots: shotsToGen, force: true } : {}), () => {
      toast(t("keys.drawingToast"), "info");
      started();
    });
  const checkKeys = useCheckKeys(id, () => {
    toast(t("keys.checkToast"), "info");
    started();
  });
  const genChar = useStartJob(id, (force: boolean) => api.character(id, force), () => {
    toast(t("keys.sheetToast"), "info");
    started();
  });

  const confirm = () => {
    if (!pending) return;
    if (pending.kind === "missing") genKeys.mutate(undefined);
    if (pending.kind === "shot") {
      setRegenShot(pending.id);
      genKeys.mutate([pending.id]);
    }
    if (pending.kind === "character") genChar.mutate(!!keysQ.data?.character_sheet);
    if (pending.kind === "check") checkKeys.mutate(true);
  };

  if (keysQ.isPending) return <Loading label={t("keys.loading")} />;
  if (keysQ.isError) return <ErrorBox error={keysQ.error} onRetry={() => void keysQ.refetch()} />;

  const missingCodex = Math.max(0, total - counts.codex);
  // "generate" without shots draws the missing ones and redraws the stale ones
  const toDraw = missingCodex + staleCodex;

  return (
    <div>
      <StepHeader
        index="03"
        title={t("step.keys")}
        actions={
          <>
            <div role="radiogroup" aria-label={t("keys.setAria")} className="flex rounded-md border border-ink-600 p-0.5">
              {VIEWS.map(({ v, label }) => (
                <button
                  key={v}
                  type="button"
                  role="radio"
                  aria-checked={view === v}
                  onClick={() => setView(v)}
                  className={cx("rounded px-3 py-1.5 text-[0.8rem] transition-colors", view === v ? "bg-ink-100 text-ink-950" : "text-ink-300 hover:text-ink-100")}
                >
                  {label ?? t("keys.both")}
                </button>
              ))}
            </div>
            <Button
              busy={!!checkJob || checkKeys.isPending}
              disabled={counts.codex === 0 || !!keysJob}
              title={counts.codex === 0 ? t("keys.checkNoKeys") : undefined}
              onClick={() => setPending({ kind: "check" })}
            >
              {t("keys.check")}
            </Button>
            <Button variant="primary" busy={!!keysJob || genKeys.isPending} disabled={!sbQ.data || toDraw === 0 || !!checkJob} onClick={() => setPending({ kind: "missing" })}
              title={toDraw === 0 ? t("keys.allDone") : undefined}>
              {staleCodex > 0
                ? t("keys.genMissingStaleN", { count: toDraw })
                : missingCodex > 0
                  ? t("keys.genMissingN", { count: missingCodex })
                  : t("keys.genMissing")}
            </Button>
          </>
        }
      >
        <Trans k="keys.lead" values={{ ratio: <b className="text-ink-200">{ratio}</b> }} />{" "}
        <Chip tone={total && counts.codex >= total ? "ok" : "neutral"}>Codex {counts.codex}/{total}</Chip>{" "}
        <Chip tone={total && counts.comfy >= total ? "ok" : "neutral"}>ComfyUI {counts.comfy}/{total}</Chip>
        {staleCodex > 0 && (
          <>
            {" "}
            <Chip tone="warn" title={t("keys.staleTip")}>{keysCountSummary(t, missingCodex, staleCodex)}</Chip>
          </>
        )}
      </StepHeader>
      <InlineError error={genKeys.error ?? genChar.error ?? checkKeys.error} />

      <div className="flex flex-col gap-5">
        {keysQ.data.check && <KeyCheckReport check={keysQ.data.check} codex={keysQ.data.sets.codex} onJump={jumpTo} />}
        <CharacterSheet
          src={keysQ.data.character_sheet}
          busy={genChar.isPending}
          running={!!charJob}
          onGenerate={() => setPending({ kind: "character" })}
          onOpen={() => setLbIndex(index.get("character") ?? null)}
        />
        <Hint>
          <Trans k="keys.hint" values={{ comfy: <b>ComfyUI</b>, codex: <b>Codex</b> }} />
        </Hint>
        {[keysJob, checkJob].map(
          (job) =>
            job && (
              <div key={job.id} className="rounded-xl border border-safe/40 bg-safe/[0.05] px-5 py-3">
                <div className="flex items-center justify-between gap-4 text-sm">
                  <span>{jobTitle(job, t)}</span>
                  <span className="truncate font-mono text-[0.75rem] text-ink-400">{job.message}</span>
                </div>
                {job.progress && <ProgressBar className="mt-2" value={job.progress.done} total={job.progress.total} />}
              </div>
            ),
        )}
        {!sbQ.data && (!project.stage.storyboard || isNotFound(sbQ.error)) && <Empty title={t("sb.empty")}>{t("keys.noStoryboardBody")}</Empty>}
        {shots.length > 0 && (
          <ul className="panel px-5">
            {shots.map((s, i) => (
              <KeyRow
                key={s.id}
                shot={s}
                cut={isCut(s, i)}
                dependents={deps[s.id] ?? []}
                sets={sets}
                orientation={orientation}
                keys={{ codex: keysQ.data.sets.codex?.[s.id], comfy: keysQ.data.sets.comfy?.[s.id] }}
                issueKind={issueKinds[s.id]}
                onOpen={openKey}
                onRegenerate={askRegen}
                regenerating={!!keysJob && regenShot === s.id}
              />
            ))}
          </ul>
        )}
      </div>

      {shots.length > 0 && <NextStepLink to="../wideo" />}

      <ConfirmDialog
        open={pending !== null}
        title={pending?.kind === "character" ? t("keys.sheet") : pending?.kind === "check" ? t("keys.checkTitle") : t("keys.genTitle")}
        confirmLabel={pending?.kind === "check" ? t("keys.checkConfirm") : t("keys.genConfirm")}
        busy={genKeys.isPending || genChar.isPending || checkKeys.isPending}
        onConfirm={confirm}
        onClose={() => setPending(null)}
      >
        {pending?.kind === "missing" &&
          (staleCodex > 0
            ? t("keys.genMissingStaleBody", { detail: keysCountSummary(t, missingCodex, staleCodex), ratio })
            : t("keys.genMissingBody", { count: missingCodex, ratio }))}
        {pending?.kind === "shot" && (
          <>
            <Trans k="keys.regenBody" values={{ id: <b>{pending.id}</b>, ratio }} />
            {(deps[pending.id]?.length ?? 0) > 0 && (
              <span className="mt-3 block rounded-lg border border-warn/40 bg-warn/[0.07] px-3 py-2 text-warn">
                {t("keys.regenWarn", { ids: deps[pending.id]?.join(", ") ?? "" })}
              </span>
            )}
          </>
        )}
        {pending?.kind === "check" && (
          <>
            {t("keys.checkBody")}
            <span className="mt-3 block">{t("keys.checkBodyFix")}</span>
          </>
        )}
        {pending?.kind === "character" && (keysQ.data.character_sheet
          ? t("keys.sheetReplace")
          : t("keys.sheetNew"))}
      </ConfirmDialog>
      <Lightbox items={items} index={lbIndex} onIndex={setLbIndex} />
    </div>
  );
}
