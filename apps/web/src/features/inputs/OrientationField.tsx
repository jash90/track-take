import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, qk } from "../../api/client";
import type { Orientation, Project } from "../../api/types";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { useToast } from "../../components/Toaster";
import { InlineError } from "../../components/ui";
import { cx } from "../../lib/cx";
import { FrameGlyph, ORIENTATIONS, orientationInfo, projectOrientation } from "../../lib/orientation";

/** Project format: shown prominently, changeable behind a confirmation (it is saved immediately). */
export function OrientationField({ project }: { project: Project }) {
  const current = projectOrientation(project);
  const [pending, setPending] = useState<Orientation | null>(null);
  const qc = useQueryClient();
  const toast = useToast();
  const change = useMutation({
    mutationFn: (o: Orientation) => api.patchProject(project.id, { orientation: o }),
    onSuccess: (p) => {
      qc.setQueryData(qk.project(project.id), p);
      for (const k of [qk.projects, qk.keys(project.id), qk.videos(project.id), ["project", project.id, "estimate"]]) {
        void qc.invalidateQueries({ queryKey: k });
      }
      setPending(null);
      toast(`Format zmieniony na ${orientationInfo(projectOrientation(p)).label.toLowerCase()} ${orientationInfo(projectOrientation(p)).ratio}`, "ok");
    },
  });
  const hasWork = (project.stage.keys.codex ?? 0) + (project.stage.keys.comfy ?? 0) > 0 ||
    (project.stage.videos.codex?.length ?? 0) + (project.stage.videos.comfy?.length ?? 0) > 0;
  const target = pending ? orientationInfo(pending) : null;

  return (
    <div>
      <div className="label" id="orient-label">Format teledysku</div>
      <div role="radiogroup" aria-labelledby="orient-label" className="grid grid-cols-2 gap-2">
        {ORIENTATIONS.map((o) => {
          const on = current === o.value;
          return (
            <button
              key={o.value}
              type="button"
              role="radio"
              aria-checked={on}
              onClick={() => !on && setPending(o.value)}
              className={cx(
                "flex items-center gap-3 rounded-md border px-3 py-2 text-left transition-colors",
                on ? "border-safe bg-safe/[0.07] text-ink-100" : "border-ink-600 text-ink-400 hover:border-ink-400 hover:text-ink-200",
              )}
            >
              <FrameGlyph orientation={o.value} size={22} className={on ? "text-safe" : undefined} />
              <span className="flex flex-col leading-tight">
                <span className="text-[0.88rem]">{o.label} <span className="font-mono text-[0.75rem]">{o.ratio}</span></span>
                <span className="text-[0.68rem] text-ink-500">{o.hint}</span>
              </span>
            </button>
          );
        })}
      </div>
      <p className="mt-1.5 text-[0.72rem] leading-relaxed text-ink-500">
        Klatki kluczowe i wideo powstają tylko w tym formacie. Zmiana później oznacza wygenerowanie ich od nowa.
      </p>
      <ConfirmDialog
        open={pending !== null}
        title="Zmienić format?"
        confirmLabel={target ? `Zmień na ${target.ratio}` : "Zmień"}
        busy={change.isPending}
        onConfirm={() => pending && change.mutate(pending)}
        onClose={() => setPending(null)}
      >
        {target && (
          <>
            Projekt przejdzie na format <b>{target.label.toLowerCase()} {target.ratio}</b> ({target.hint}).{" "}
            {hasWork
              ? "Klatki i filmy w obecnym formacie zostaną zachowane na dysku, ale przestaną być widoczne — dla nowego formatu trzeba wygenerować klatki i wyrenderować wideo od nowa."
              : "Klatki i wideo powstaną już w nowym formacie."}{" "}
            Storyboard i analiza zostają bez zmian.
          </>
        )}
        <InlineError error={change.error} />
      </ConfirmDialog>
    </div>
  );
}
