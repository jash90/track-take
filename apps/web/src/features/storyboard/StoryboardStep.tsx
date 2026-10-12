import { useCallback, useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router";
import { api, isNotFound, qk } from "../../api/client";
import { useAnalysis, useKeys, usePeaks, useStartJob, useStoryboard } from "../../api/hooks";
import type { KeySet, Storyboard } from "../../api/types";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { Lightbox, type LightboxItem } from "../../components/Lightbox";
import { useToast } from "../../components/Toaster";
import { Button, Empty, ErrorBox, InlineError, Loading, ProgressBar, StepHeader } from "../../components/ui";
import { errorMessage } from "../../lib/format";
import { projectOrientation } from "../../lib/orientation";
import { continuitySummary } from "../../lib/continuity";
import { activeJob, useWorkspace } from "../workspace/context";
import { DirectorPanel } from "./DirectorPanel";
import { ShotEditor } from "./ShotEditor";
import { Timeline } from "./Timeline";
import { useAudioTransport } from "./useAudioTransport";
import { useStoryboardDraft } from "./useStoryboardDraft";

const isTyping = (t: EventTarget | null) =>
  t instanceof HTMLElement && (t.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName));

export function StoryboardStep() {
  const { project, jobs, openJobs } = useWorkspace();
  const id = project.id;
  const orientation = projectOrientation(project);
  const qc = useQueryClient();
  const toast = useToast();
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

  const thumbs = useMemo(() => {
    const out: Record<string, string | null> = {};
    const sets = keysQ.data?.sets;
    const thumbKey = orientation === "landscape" ? "landscape_thumb" : "portrait_thumb";
    for (const s of shots) out[s.id] = sets?.codex?.[s.id]?.[thumbKey] ?? sets?.comfy?.[s.id]?.[thumbKey] ?? null;
    return out;
  }, [keysQ.data, shots, orientation]);

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

  const persist = async (doc: Storyboard | null) => {
    if (!doc || !dirty) return;
    const saved = await api.saveStoryboard(id, doc);
    adopt(saved);
    qc.setQueryData(qk.storyboard(id), saved);
  };

  const save = useMutation({
    mutationFn: () => persist(draft),
    onSuccess: () => {
      toast("Storyboard zapisany", "ok");
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
      setConfirmPlan(false);
      toast(`Rozpisano ${doc.shots.length} ujęć`, "ok");
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
      toast("Reżyser pisze storyboard…", "info");
      openJobs();
    },
  );

  const openImage = (set: KeySet) => {
    if (!shot) return;
    const items: LightboxItem[] = [];
    let index = 0;
    for (const s of ["codex", "comfy"] as KeySet[]) {
      const src = keysQ.data?.sets[s]?.[shot.id]?.[orientation];
      if (!src) continue;
      if (s === set) index = items.length;
      items.push({ src, caption: `${shot.id} · ${s === "codex" ? "Codex" : "ComfyUI"} · ${orientation === "landscape" ? "16:9" : "9:16"}` });
    }
    setLightbox({ items, index });
  };

  const noAnalysis = !analysis.data && (!project.stage.analysis || isNotFound(analysis.error));
  if (!noAnalysis && analysis.isPending) return <Loading label="Wczytuję analizę…" />;
  if (noAnalysis || !analysis.data) {
    if (noAnalysis)
      return (
        <Empty title="Najpierw przeanalizuj utwór" action={<Link to="../wejscie" className="text-sm text-safe hover:underline">← Wejście</Link>}>
          Storyboard tnie ujęcia na downbeatach, więc potrzebuje bitów i sekcji z analizy.
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
        title="Storyboard"
        actions={
          <>
            {dirty && <Button variant="ghost" size="sm" onClick={discard} disabled={busyAny}>Odrzuć zmiany</Button>}
            <Button variant="secondary" disabled={!dirty || !!writing} busy={save.isPending} onClick={() => save.mutate()}>
              {dirty ? "Zapisz" : "Zapisano"}
            </Button>
            <Button variant="secondary" busy={plan.isPending} disabled={busyAny || !!writing} onClick={() => setConfirmPlan(true)}>
              Przelicz ujęcia
            </Button>
            <Button variant="primary" busy={write.isPending || !!writing} disabled={noStoryboard || busyAny} onClick={() => write.mutate(undefined)}>
              Napisz storyboard (Claude)
            </Button>
          </>
        }
      >
        Ujęcia po 2 takty, na downbeatach; twarde cięcia tylko na początkach sekcji, reszta płynie jako jedno ujęcie. Reżyser opisuje
        scenę i ruch każdego ujęcia
        {draft && (
          <>
            {" "}— opisanych <b className="text-ink-200">{written}/{shots.length}</b>.
            <span className="mt-2 flex items-center gap-2 font-mono text-[0.78rem] text-ink-300">
              <span aria-hidden className="grid h-4 w-4 place-items-center rounded-full bg-safe text-[0.6rem] text-ink-950">✂</span>
              {continuitySummary(shots)}
            </span>
          </>
        )}
      </StepHeader>
      <InlineError error={save.error ?? plan.error ?? write.error ?? (noStoryboard ? null : sbQ.error)} />

      {writing && (
        <div className="mb-4 rounded-xl border border-safe/40 bg-safe/[0.05] px-5 py-3">
          <div className="flex items-center justify-between gap-4 text-sm">
            <span>{writing.title} — edycja zablokowana do końca</span>
            <span className="truncate font-mono text-[0.75rem] text-ink-400">{writing.message}</span>
          </div>
          {writing.progress && <ProgressBar className="mt-2" value={writing.progress.done} total={writing.progress.total} />}
        </div>
      )}
      {stale && (
        <div className="mb-4 flex items-center justify-between gap-4 rounded-lg border border-warn/40 bg-warn/[0.06] px-4 py-2 text-sm">
          <span>Na serwerze jest nowsza wersja storyboardu, a Ty masz niezapisane zmiany.</span>
          <Button size="sm" variant="ghost" onClick={discard}>Wczytaj wersję z serwera</Button>
        </div>
      )}

      <Timeline
        duration={analysis.data.duration}
        peaks={peaks.data?.peaks}
        analysis={analysis.data}
        shots={shots}
        selected={selected}
        primary={primary}
        onPick={pickAndSeek}
        thumbs={thumbs}
        transport={transport}
      />
      {peaks.isError && <p className="mt-2 text-[0.75rem] text-err">Nie udało się pobrać przebiegu fali: {errorMessage(peaks.error)}</p>}

      <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div>
          {sbQ.isPending && !noStoryboard && <Loading label="Wczytuję storyboard…" />}
          {noStoryboard && (
            <Empty title="Brak storyboardu" action={<Button variant="primary" busy={plan.isPending} onClick={() => plan.mutate()}>Przelicz ujęcia</Button>}>
              Zacznij od pocięcia utworu na ujęcia — po 2 takty, na downbeatach. Potem reżyser (Claude) opisze każde z nich.
            </Empty>
          )}
          {shot && (
            <ShotEditor
              shot={shot}
              index={primaryIdx}
              total={shots.length}
              keys={{ codex: keysQ.data?.sets.codex?.[shot.id], comfy: keysQ.data?.sets.comfy?.[shot.id] }}
              orientation={orientation}
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
          <DirectorPanel
            draft={draft}
            disabled={!!writing}
            instructions={instructions}
            onInstructions={setInstructions}
            onChange={update}
            selectedCount={selected.size}
            busy={write.isPending}
            onRewrite={() => write.mutate([...selected])}
          />
        )}
      </div>

      <ConfirmDialog
        open={confirmPlan}
        title="Przeliczyć ujęcia?"
        confirmLabel="Przelicz"
        busy={plan.isPending}
        onConfirm={() => plan.mutate()}
        onClose={() => setConfirmPlan(false)}
      >
        Ujęcia zostaną pocięte od nowa na downbeatach (2 takty na ujęcie), a cięcia/przejścia ciągłe ustawione od nowa (cięcie na
        początku zwrotki, refrenu, bridge’u, breakdownu i outro). Teksty ujęć, które się nie zmienią, zostaną zachowane.
        {dirty && " Twoje niezapisane zmiany zostaną najpierw zapisane."}
        <InlineError error={plan.error} />
      </ConfirmDialog>
      <Lightbox items={lightbox.items} index={lightbox.index} onIndex={(i) => setLightbox((l) => ({ ...l, index: i }))} />
    </div>
  );
}
