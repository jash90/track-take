import { useVast } from "../api/hooks";
import { formatUsd } from "../lib/format";
import { Dialog } from "./Dialog";
import { Chip, ErrorBox, Loading } from "./ui";
import { VastKeyForm } from "./VastKeyForm";

export function SettingsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const vast = useVast();
  return (
    <Dialog open={open} onClose={onClose} title="Ustawienia">
      <section className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="eyebrow">Render w chmurze</div>
            <div className="mt-0.5 font-display text-xl">Vast.ai</div>
          </div>
          {vast.data && (
            <Chip tone={vast.data.configured ? "ok" : "warn"}>{vast.data.configured ? "skonfigurowany" : "brak klucza"}</Chip>
          )}
        </div>
        {vast.isPending && <Loading label="Sprawdzam Vast…" />}
        {vast.isError && <ErrorBox error={vast.error} onRetry={() => void vast.refetch()} />}
        {vast.data && (
          <>
            {vast.data.configured && (
              <dl className="grid grid-cols-2 gap-3 rounded-lg border border-ink-700 bg-ink-900 p-4 text-sm">
                <dt className="text-ink-400">Saldo</dt>
                <dd className="text-right font-mono tabular">{formatUsd(vast.data.balance)}</dd>
                <dt className="text-ink-400">Uruchomione karty</dt>
                <dd className="text-right font-mono tabular">{vast.data.instances.length}</dd>
              </dl>
            )}
            {vast.data.error && <ErrorBox title="Vast zgłasza błąd" error={vast.data.error} />}
            <VastKeyForm replacing={vast.data.configured} />
          </>
        )}
      </section>
    </Dialog>
  );
}
