import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, qk } from "../../api/client";
import { useVast } from "../../api/hooks";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { useToast } from "../../components/Toaster";
import { Button, Chip, ErrorBox, InlineError, Loading } from "../../components/ui";
import { formatUsd } from "../../lib/format";
import { useT } from "../../i18n";
import { VastInstances } from "./VastInstances";
import { useShell } from "../../components/AppShell";

export function VastPanel() {
  const vast = useVast(true);
  const qc = useQueryClient();
  const toast = useToast();
  const t = useT();
  const { openSettings } = useShell();
  const [confirm, setConfirm] = useState(false);
  const inUseCount = vast.data?.instances.filter((i) => i.in_use).length ?? 0;
  const down = useMutation({
    mutationFn: api.vastDown,
    onSuccess: (r) => {
      setConfirm(false);
      void qc.invalidateQueries({ queryKey: qk.vast });
      toast(t("vastPanel.freedToast", { count: r.freed, usd: formatUsd(r.usd) }), "ok");
    },
  });

  return (
    <section className="panel flex flex-col gap-4 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="eyebrow">{t("vastPanel.eyebrow")}</div>
          <h2 className="font-display text-2xl leading-tight">Vast.ai</h2>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => void vast.refetch()} className="text-[0.75rem] text-ink-400 hover:text-ink-100" aria-label={t("vastPanel.refresh")}>
            {vast.isFetching ? "…" : "↻"}
          </button>
          {vast.data && <Chip tone={vast.data.configured ? "ok" : "warn"}>{vast.data.configured ? t("vastPanel.connected") : t("settings.noKey")}</Chip>}
        </div>
      </div>
      {vast.isPending && <Loading label={t("vastPanel.asking")} />}
      {vast.isError && <ErrorBox error={vast.error} onRetry={() => void vast.refetch()} />}
      {vast.data && !vast.data.configured && (
        <button type="button" onClick={openSettings} className="self-start text-sm text-safe underline-offset-4 hover:underline">
          {t("render.addKey")} →
        </button>
      )}
      {vast.data?.error && <ErrorBox title={t("vast.errorTitle")} error={vast.data.error} />}
      {vast.data?.configured && (
        <>
          <div className="flex items-baseline justify-between">
            <span className="text-sm text-ink-400">{t("settings.balance")}</span>
            <span className="font-display text-4xl tabular">{formatUsd(vast.data.balance)}</span>
          </div>
          <div>
            <div className="label">{t("vastPanel.instances")}</div>
            {vast.data.instances.length === 0 ? (
              <p className="text-[0.82rem] text-ink-500">{t("vastPanel.idle")}</p>
            ) : (
              <VastInstances instances={vast.data.instances} />
            )}
          </div>
          <Button variant="danger" size="sm" className="self-start" disabled={vast.data.instances.length === 0} onClick={() => setConfirm(true)}>
            {t("vastPanel.releaseAll")}
          </Button>
        </>
      )}
      <ConfirmDialog
        open={confirm}
        title={t("vastPanel.releaseTitle")}
        confirmLabel={t("vastPanel.releaseConfirm")}
        danger
        busy={down.isPending}
        onConfirm={() => down.mutate()}
        onClose={() => setConfirm(false)}
      >
        {t("vastPanel.releaseBody")}
        {inUseCount > 0 && (
          <span className="mt-3 block rounded-lg border border-warn/40 bg-warn/[0.07] px-3 py-2 text-warn">
            {t("vastPanel.releaseInUseWarn", { count: inUseCount })}
          </span>
        )}
        <InlineError error={down.error} />
      </ConfirmDialog>
    </section>
  );
}
