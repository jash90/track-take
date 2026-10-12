import { useVast } from "../api/hooks";
import { formatUsd } from "../lib/format";
import { Dialog } from "./Dialog";
import { Chip, ErrorBox, Loading } from "./ui";
import { VastKeyForm } from "./VastKeyForm";
import { useT } from "../i18n";

export function SettingsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const vast = useVast();
  const t = useT();
  return (
    <Dialog open={open} onClose={onClose} title={t("settings.title")}>
      <section className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="eyebrow">{t("settings.cloud")}</div>
            <div className="mt-0.5 font-display text-xl">Vast.ai</div>
          </div>
          {vast.data && (
            <Chip tone={vast.data.configured ? "ok" : "warn"}>{vast.data.configured ? t("settings.configured") : t("settings.noKey")}</Chip>
          )}
        </div>
        {vast.isPending && <Loading label={t("settings.checking")} />}
        {vast.isError && <ErrorBox error={vast.error} onRetry={() => void vast.refetch()} />}
        {vast.data && (
          <>
            {vast.data.configured && (
              <dl className="grid grid-cols-2 gap-3 rounded-lg border border-ink-700 bg-ink-900 p-4 text-sm">
                <dt className="text-ink-400">{t("settings.balance")}</dt>
                <dd className="text-right font-mono tabular">{formatUsd(vast.data.balance)}</dd>
                <dt className="text-ink-400">{t("settings.runningCards")}</dt>
                <dd className="text-right font-mono tabular">{vast.data.instances.length}</dd>
              </dl>
            )}
            {vast.data.error && <ErrorBox title={t("vast.errorTitle")} error={vast.data.error} />}
            <VastKeyForm replacing={vast.data.configured} />
          </>
        )}
      </section>
    </Dialog>
  );
}
