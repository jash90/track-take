import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, qk } from "../../api/client";
import type { Orientation, Project } from "../../api/types";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { useToast } from "../../components/Toaster";
import { InlineError } from "../../components/ui";
import { cx } from "../../lib/cx";
import { FrameGlyph, ORIENTATIONS, orientationInfo, projectOrientation } from "../../lib/orientation";
import { Trans, useT } from "../../i18n";

/** Project format: shown prominently, changeable behind a confirmation (it is saved immediately). */
export function OrientationField({ project }: { project: Project }) {
  const current = projectOrientation(project);
  const [pending, setPending] = useState<Orientation | null>(null);
  const qc = useQueryClient();
  const toast = useToast();
  const t = useT();
  const change = useMutation({
    mutationFn: (o: Orientation) => api.patchProject(project.id, { orientation: o }),
    onSuccess: (p) => {
      qc.setQueryData(qk.project(project.id), p);
      for (const k of [qk.projects, qk.keys(project.id), qk.videos(project.id), ["project", project.id, "estimate"]]) {
        void qc.invalidateQueries({ queryKey: k });
      }
      setPending(null);
      const info = orientationInfo(projectOrientation(p));
      toast(t("orientField.toast", { label: t(info.label).toLowerCase(), ratio: info.ratio }), "ok");
    },
  });
  const hasWork = (project.stage.keys.codex ?? 0) + (project.stage.keys.comfy ?? 0) > 0 ||
    (project.stage.videos.codex?.length ?? 0) + (project.stage.videos.comfy?.length ?? 0) > 0;
  const target = pending ? orientationInfo(pending) : null;

  return (
    <div>
      <div className="label" id="orient-label">{t("orientField.label")}</div>
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
                <span className="text-[0.88rem]">{t(o.label)} <span className="font-mono text-[0.75rem]">{o.ratio}</span></span>
                <span className="text-[0.68rem] text-ink-500">{t(o.hint)}</span>
              </span>
            </button>
          );
        })}
      </div>
      <p className="mt-1.5 text-[0.72rem] leading-relaxed text-ink-500">
        {t("orientField.note")}
      </p>
      <ConfirmDialog
        open={pending !== null}
        title={t("orientField.confirmTitle")}
        confirmLabel={target ? t("orientField.confirmTo", { ratio: target.ratio }) : t("orientField.confirm")}
        busy={change.isPending}
        onConfirm={() => pending && change.mutate(pending)}
        onClose={() => setPending(null)}
      >
        {target && (
          <>
            <Trans
              k="orientField.body"
              values={{ target: <b>{t(target.label).toLowerCase()} {target.ratio}</b>, hint: t(target.hint) }}
            />{" "}
            {hasWork
              ? t("orientField.hasWork")
              : t("orientField.noWork")}{" "}
            {t("orientField.keeps")}
          </>
        )}
        <InlineError error={change.error} />
      </ConfirmDialog>
    </div>
  );
}
