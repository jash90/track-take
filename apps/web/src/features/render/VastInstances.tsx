import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, qk } from "../../api/client";
import { useProjects } from "../../api/hooks";
import type { VastInstance } from "../../api/types";
import { Dialog } from "../../components/Dialog";
import { useToast } from "../../components/Toaster";
import { Button } from "../../components/ui";
import { useT } from "../../i18n";
import { cx } from "../../lib/cx";
import { errorMessage, formatUsd } from "../../lib/format";

/** Rows of rented Vast cards, each with its own "Release" action. */
export function VastInstances({ instances }: { instances: VastInstance[] }) {
  const t = useT();
  const qc = useQueryClient();
  const toast = useToast();
  const projects = useProjects();
  const [target, setTarget] = useState<VastInstance | null>(null);
  const projectName = (id: string | null | undefined) => (id ? (projects.data?.find((p) => p.id === id)?.name ?? id) : "—");

  const release = useMutation({
    mutationFn: ({ inst, force }: { inst: VastInstance; force: boolean }) => api.vastRelease(inst.id, force),
    onSuccess: (_r, { inst }) => {
      setTarget(null);
      toast(t("vastInst.released", { gpu: inst.gpu, id: String(inst.id) }), "ok");
    },
    onError: (err) => toast(t("vastInst.releaseError", { error: errorMessage(err) }), "err"),
    onSettled: () => void qc.invalidateQueries({ queryKey: qk.vast }),
  });
  const cancelRender = useMutation({
    mutationFn: (inst: VastInstance) => api.cancelJob(inst.job ?? ""),
    onSuccess: (_j, inst) => {
      setTarget(null);
      toast(t("vastInst.renderCancelled"), "info");
      if (inst.project) void qc.invalidateQueries({ queryKey: qk.jobs(inst.project) });
    },
    onError: (err) => toast(t("vastInst.cancelError", { error: errorMessage(err) }), "err"),
    onSettled: () => void qc.invalidateQueries({ queryKey: qk.vast }),
  });

  const busy = release.isPending || cancelRender.isPending;
  const inUse = !!target?.in_use;
  const orphan = target?.known === false;

  return (
    <>
      <ul className="flex flex-col gap-1.5">
        {instances.map((i) => (
          <li key={i.id} className="rounded-md border border-ink-700 bg-ink-900 px-3 py-2 font-mono text-[0.75rem]">
            <div className="flex items-center gap-3">
              <span className={cx("h-1.5 w-1.5 shrink-0 rounded-full", i.in_use ? "animate-pulse-dot bg-safe" : "bg-ink-400")} />
              <span className="truncate text-ink-200" title={i.name || `#${i.id}`}>{i.gpu}</span>
              <span className="ml-auto text-ink-300">{i.status}</span>
              <span className="text-ink-100">{formatUsd(i.dph, 3)}/h</span>
              <button
                type="button"
                onClick={() => setTarget(i)}
                className="rounded border border-err/50 px-2 py-0.5 font-sans text-[0.72rem] text-err hover:border-err hover:bg-err/10"
              >
                {t("vastInst.release")}
              </button>
            </div>
            {(i.in_use || i.known === false) && (
              <div className="mt-1.5 flex flex-wrap gap-1.5 pl-[18px]">
                {i.in_use && (
                  <span className="rounded-full border border-safe/50 bg-safe/10 px-2 py-px text-[0.65rem] text-safe-hi">
                    {t("vastInst.inUse", { project: projectName(i.project) })}
                  </span>
                )}
                {i.known === false && (
                  <span title={t("vastInst.orphanTip")} className="rounded-full border border-warn/50 bg-warn/10 px-2 py-px text-[0.65rem] text-warn">
                    {t("vastInst.orphan")}
                  </span>
                )}
              </div>
            )}
          </li>
        ))}
      </ul>

      <Dialog
        open={target !== null}
        onClose={() => !busy && setTarget(null)}
        title={inUse ? t("vastInst.inUseTitle") : t("vastInst.confirmTitle")}
        footer={
          target && (
            <>
              <Button variant="ghost" onClick={() => setTarget(null)} disabled={busy} autoFocus>
                {inUse ? t("vastInst.back") : t("common.cancel")}
              </Button>
              {inUse && target.job && (
                <Button variant="primary" busy={cancelRender.isPending} disabled={busy} onClick={() => cancelRender.mutate(target)}>
                  {t("vastInst.cancelRender")}
                </Button>
              )}
              <Button variant="danger" busy={release.isPending} disabled={busy} onClick={() => release.mutate({ inst: target, force: inUse })}>
                {inUse ? t("vastInst.forceRelease") : t("vastInst.release")}
              </Button>
            </>
          )
        }
      >
        {target && (
          <div className="flex flex-col gap-3 text-sm leading-relaxed text-ink-200">
            <p>{t("vastInst.confirmBody", { gpu: target.gpu, dph: formatUsd(target.dph, 2) })}</p>
            {inUse && (
              <p className="rounded-lg border border-warn/40 bg-warn/[0.07] px-3 py-2 text-warn">
                {t("vastInst.inUseBody", { project: projectName(target.project) })}
              </p>
            )}
            {orphan && <p className="text-ink-400">{t("vastInst.orphanBody")}</p>}
          </div>
        )}
      </Dialog>
    </>
  );
}
