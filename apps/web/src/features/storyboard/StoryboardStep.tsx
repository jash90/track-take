import { useCallback, useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router";
import { api, isNotFound, qk } from "../../api/client";
import { useAnalysis, useKeys, usePeaks, useStartJob, useStoryboard } from "../../api/hooks";
import type { KeySet, Storyboard } from "../../api/types";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { Lightbox, type LightboxItem } from "../../components/Lightbox";
import { useToast } from "../../components/Toaster";
import { Button, Empty, NextStepLink, ErrorBox, InlineError, Loading, StepHeader } from "../../components/ui";
import { errorMessage } from "../../lib/format";
import { projectOrientation } from "../../lib/orientation";
import { continuitySummary } from "../../lib/continuity";
import { activeJob, useWorkspace } from "../workspace/context";
import { StoryboardSide } from "./StoryboardSide";
import { ShotEditor } from "./ShotEditor";
import { Timeline } from "./Timeline";
import { useAudioTransport } from "./useAudioTransport";
import { useStoryboardDraft } from "./useStoryboardDraft";
import { Trans, useT } from "../../i18n";
import { shotLightbox } from "./shotLightbox";
import { Monitor } from "./Monitor";
import { useFollowPlayhead } from "./useFollowPlayhead";
import { StoryboardBanners } from "./StoryboardBanners";
import { checkKinds, isStale } from "../keys/stale";
import { projectAnimation, storyboardAnimation, useAnimationName } from "../../lib/animation";

const isTyping = (t: EventTarget | null) =>
  t instanceof HTMLElement && (t.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName));

export function StoryboardStep() {
  const { project, jobs, openJobs } = useWorkspace();
  const id = project.id;
  const orientation = projectOrientation(project);
  const qc = useQueryClient();
  const toast = useToast();
  const t = useT();
  const analysis = useAnalysis(id, project.stage.analysis);
  const peaks = usePeaks(id, !!analysis.data);
  const sbQ = useStoryboard(id, project.stage.storyboard);
  const keysQ = useKeys(id);
  const transport = useAudioTransport();
  const { draft, dirty, stale, adopt, update, updateShot, discard } = useStoryboardDraft(sbQ.data);

  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
  const [primary, setPrimary] = useState<string | null>(null);
  const [instructions, setInstructions] = useState("");
  const [confirmPlan, setConfirmPlan] = useState(false);
  const [lightbox, setLightbox] = useState<{ items: LightboxItem[]; index: number | null }>({ items: [], index: null });

  const shots = useMemo(() => draft?.shots ?? [], [draft]);
  const primaryIdx = shots.findIndex((s) => s.id === primary);
  const shot = shots[primaryIdx];
  const writing = activeJob(jobs, "storyboard");
  const written = shots.filter((s) => s.scene.trim()).length;

  useEffect(() => {
    if (!primary && shots[0]) setPrimary(shots[0].id);
  }, [primary, shots]);

  // while playing with "follow" on, the editor follows the playhead — unless it holds unsaved edits
  const [follow, setFollow] = useState(true);
  useFollowPlayhead(transport, shots, follow, dirty, (sid) => {
    setPrimary(sid);
    setSelected(new Set([sid]));
  });
  const locationNames = useMemo(() => Object.fromEntries((draft?.locations ?? []).map((l) => [l.id, l.name])), [draft?.locations]);
  const thumbs = useMemo(() => {
    const out: Record<string, string | null> = {};
    const sets = keysQ.data?.sets;
    const thumbKey = orientation === "landscape" ? "landscape_thumb" : "portrait_thumb";
    for (const s of shots) out[s.id] = sets?.codex?.[s.id]?.[thumbKey] ?? sets?.comfy?.[s.id]?.[thumbKey] ?? null;
    return out;
  }, [keysQ.data, shots, orientation]);
  const staleIds = useMemo(
    () => new Set(shots.filter((s) => isStale(keysQ.data?.sets.codex?.[s.id], orientation)).map((s) => s.id)),
    [keysQ.data, shots, orientation],
  );
  const issueKinds = useMemo(() => checkKinds(keysQ.data), [keysQ.data]);
  const animName = useAnimationName();
  const wanted = projectAnimation(project);
  const planned = sbQ.data ? storyboardAnimation(sbQ.data) : null;
  // planned for another style: the shot rhythm doesn't fit until re-planned (never automatic)
  const animMismatch = planned !== null && planned !== wanted;
  const shown = planned ?? wanted;

  const pick = useCallback((sid: string, additive: boolean) => {
    setPrimary(sid);
    setSelected((prev) => {
      if (!additive) return new Set([sid]);
      const next = new Set(prev);
      if (next.has(sid)) next.delete(sid);
      else next.add(sid);
      return next;
    });
  }, []);

  const pickAndSeek = useCallback(
    (sid: string, additive: boolean) => {
      pick(sid, additive);
      const s = shots.find((x) => x.id === sid);
      if (s && !additive) transport.seek(s.start);
    },
    [pick, shots, transport],
  );

  const step = useCallback(
    (delta: number) => {
      const next = shots[Math.max(0, Math.min(shots.length - 1, primaryIdx + delta))];
      if (next) pickAndSeek(next.id, false);
    },
    [shots, primaryIdx, pickAndSeek],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isTyping(e.target) || e.metaKey || e.ctrlKey || e.altKey || document.querySelector("dialog[open]")) return;
      if (e.code === "Space") {
        e.preventDefault();
        transport.toggle();
      } else if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        e.preventDefault();
        step(e.key === "ArrowRight" ? 1 : -1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [transport, step]);

  // an edited scene / world look marks drawn keyframes stale — refresh their badges and the render estimate
  const refreshKeys = () => {
    void qc.invalidateQueries({ queryKey: qk.keys(id) });
    void qc.invalidateQueries({ queryKey: ["project", id, "estimate"] });
  };

  const persist = async (doc: Storyboard | null) => {
    if (!doc || !dirty) return;
    const saved = await api.saveStoryboard(id, doc);
    adopt(saved);
    qc.setQueryData(qk.storyboard(id), saved);
    refreshKeys();
  };

  const save = useMutation({
    mutationFn: () => persist(draft),
    onSuccess: () => {
      toast(t("sb.savedToast"), "ok");
      void qc.invalidateQueries({ queryKey: qk.project(id) });
    },
  });

  const plan = useMutation({
    mutationFn: async () => {
      await persist(draft);
      return api.planStoryboard(id);
    },
    onSuccess: (doc) => {
      adopt(doc);
      qc.setQueryData(qk.storyboard(id), doc);
      void qc.invalidateQueries({ queryKey: qk.project(id) });
      refreshKeys();
      setConfirmPlan(false);
      toast(t("sb.plannedToast", { count: doc.shots.length }), "ok");
    },
  });

  const write = useStartJob(
    id,
    async (shotsToWrite: string[] | undefined) => {
      await persist(draft);
      const instr = instructions.trim() || undefined;
      return api.writeStoryboard(id, { shots: shotsToWrite, instructions: instr });
    },
    () => {
      toast(t("sb.writingToast"), "info");
      openJobs();
    },
  );

  const openImage = (set: KeySet) => shot && setLightbox(shotLightbox(keysQ.data, shot.id, orientation, set));

  const noAnalysis = !analysis.data && (!project.stage.analysis || isNotFound(analysis.error));
  if (!noAnalysis && analysis.isPending) return <Loading label={t("analysis.loading")} />;
  if (noAnalysis || !analysis.data) {
    if (noAnalysis)
      return (
        <Empty title={t("sb.noAnalysis")} action={<Link to="../wejscie" className="text-sm text-safe hover:underline">{t("sb.backToInputs")}</Link>}>
          {t("sb.noAnalysisBody")}
        </Empty>
      );
    return <ErrorBox error={analysis.error} onRetry={() => void analysis.refetch()} />;
  }

  const noStoryboard = !sbQ.data && (!project.stage.storyboard || isNotFound(sbQ.error));
  const busyAny = save.isPending || plan.isPending || write.isPending;

  return (
    <div>
      <audio ref={transport.audioRef} src={project.inputs.song ?? undefined} preload="auto" />
      <StepHeader
        index="02"
        title={t("step.storyboard")}
        actions={
          <>
            {dirty && <Button variant="ghost" size="sm" onClick={discard} disabled={busyAny}>{t("sb.discard")}</Button>}
            <Button variant="secondary" disabled={!dirty || !!writing} busy={save.isPending} onClick={() => save.mutate()}>
              {dirty ? t("common.save") : t("common.saved")}
            </Button>
            <Button variant="secondary" busy={plan.isPending} disabled={busyAny || !!writing} onClick={() => (noStoryboard ? plan.mutate() : setConfirmPlan(true))}>
              {noStoryboard ? t("sb.planFirst") : t("sb.plan")}
            </Button>
            <Button variant="primary" busy={write.isPending || !!writing} disabled={noStoryboard || busyAny} onClick={() => write.mutate(undefined)}>
              {t("sb.write")}
            </Button>
          </>
        }
      >
        {t(shown === "journey" ? "sb.leadJourney" : shown === "tableau" ? "sb.leadTableau" : "sb.lead")}
        {draft && (
          <>
            <Trans k="sb.writtenCount" values={{ written: <b className="text-ink-200">{written}/{shots.length}</b> }} />
            <span className="mt-2 flex items-center gap-2 font-mono text-[0.78rem] text-ink-300">
              <span aria-hidden className="grid h-4 w-4 place-items-center rounded-full bg-safe text-[0.6rem] text-ink-950">✂</span>
              {continuitySummary(shots, t)}
            </span>
          </>
        )}
      </StepHeader>
      <InlineError error={save.error ?? plan.error ?? write.error ?? (noStoryboard ? null : sbQ.error)} />

      <StoryboardBanners
        writing={writing}
        stale={stale}
        onLoadServer={discard}
        mismatch={
          animMismatch && planned
            ? {
                planned: animName(planned),
                current: animName(wanted),
                onReplan: () => setConfirmPlan(true),
                busy: plan.isPending,
                disabled: busyAny || !!writing,
              }
            : null
        }
      />
      <Timeline
        duration={analysis.data.duration}
        peaks={peaks.data?.peaks}
        analysis={analysis.data}
        shots={shots}
        selected={selected}
        primary={primary}
        onPick={pickAndSeek}
        thumbs={thumbs}
        staleIds={staleIds}
        locationNames={locationNames}
        follow={follow}
        onFollow={setFollow}
        transport={transport}
      />
      {peaks.isError && <p className="mt-2 text-[0.75rem] text-err">{t("sb.peaksError", { error: errorMessage(peaks.error) })}</p>}

      <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div>
          {sbQ.isPending && !noStoryboard && <Loading label={t("sb.loading")} />}
          {noStoryboard && (
            <Empty title={t("sb.empty")} action={<Button variant="primary" busy={plan.isPending} onClick={() => plan.mutate()}>{t("sb.planFirst")}</Button>}>
              {t(wanted === "journey" ? "sb.emptyBodyJourney" : wanted === "tableau" ? "sb.emptyBodyTableau" : "sb.emptyBody")}
            </Empty>
          )}
          {draft && shots.length > 0 && (
            <Monitor
              shots={shots}
              lines={analysis.data.lines}
              keys={keysQ.data}
              orientation={orientation}
              transport={transport}
              editorHeld={follow && transport.playing && dirty}
            />
          )}
          {shot && (
            <ShotEditor
              shot={shot}
              index={primaryIdx}
              total={shots.length}
              keys={{ codex: keysQ.data?.sets.codex?.[shot.id], comfy: keysQ.data?.sets.comfy?.[shot.id] }}
              issueKind={issueKinds[shot.id]}
              orientation={orientation}
              world={{ locations: draft?.locations ?? [], props: draft?.props ?? [] }}
              disabled={!!writing}
              onChange={(patch) => updateShot(shot.id, patch)}
              onStep={step}
              onOpenImage={openImage}
              onPlay={() => {
                transport.seek(shot.start);
                if (!transport.playing) transport.toggle();
              }}
            />
          )}
        </div>
        {draft && (
          <StoryboardSide
            projectId={id}
            draft={draft}
            dirty={dirty}
            writing={!!writing}
            checking={activeJob(jobs, "continuity")}
            instructions={instructions}
            onInstructions={setInstructions}
            onChange={update}
            selectedCount={selected.size}
            rewriteBusy={write.isPending}
            onRewrite={() => write.mutate([...selected])}
            onJump={(sid) => pickAndSeek(sid, false)}
            onJobStarted={openJobs}
          />
        )}
      </div>

      {draft && <NextStepLink to="../klatki" />}
      <ConfirmDialog
        open={confirmPlan}
        title={animMismatch ? t("sb.animReplanTitle", { current: animName(wanted) }) : t("sb.planTitle")}
        confirmLabel={animMismatch ? t("sb.animReplan") : t("sb.planConfirm")}
        busy={plan.isPending}
        onConfirm={() => plan.mutate()}
        onClose={() => setConfirmPlan(false)}
      >
        {animMismatch && planned
          ? t("sb.animReplanBody", { planned: animName(planned), current: animName(wanted), write: t("sb.write") })
          : t(wanted === "journey" ? "sb.planBodyJourney" : wanted === "tableau" ? "sb.planBodyTableau" : "sb.planBody")}
        {dirty && t("sb.planDirty")}
        <InlineError error={plan.error} />
      </ConfirmDialog>
      <Lightbox items={lightbox.items} index={lightbox.index} onIndex={(i) => setLightbox((l) => ({ ...l, index: i }))} />
    </div>
  );
}
