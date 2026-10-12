import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, qk } from "../../api/client";
import { useVast } from "../../api/hooks";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { useToast } from "../../components/Toaster";
import { Button, Chip, ErrorBox, InlineError, Loading } from "../../components/ui";
import { VastKeyForm } from "../../components/VastKeyForm";
import { formatUsd } from "../../lib/format";

export function VastPanel() {
  const vast = useVast(true);
  const qc = useQueryClient();
  const toast = useToast();
  const [confirm, setConfirm] = useState(false);
  const down = useMutation({
    mutationFn: api.vastDown,
    onSuccess: (r) => {
      setConfirm(false);
      void qc.invalidateQueries({ queryKey: qk.vast });
      toast(`Zwolniono ${r.freed} kart (${formatUsd(r.usd)}/h)`, "ok");
    },
  });

  return (
    <section className="panel flex flex-col gap-4 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="eyebrow">Karty w chmurze</div>
          <h2 className="font-display text-2xl leading-tight">Vast.ai</h2>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => void vast.refetch()} className="text-[0.75rem] text-ink-400 hover:text-ink-100" aria-label="Odśwież status Vast">
            {vast.isFetching ? "…" : "↻"}
          </button>
          {vast.data && <Chip tone={vast.data.configured ? "ok" : "warn"}>{vast.data.configured ? "połączony" : "brak klucza"}</Chip>}
        </div>
      </div>
      {vast.isPending && <Loading label="Pytam Vast…" />}
      {vast.isError && <ErrorBox error={vast.error} onRetry={() => void vast.refetch()} />}
      {vast.data && !vast.data.configured && <VastKeyForm />}
      {vast.data?.error && <ErrorBox title="Vast zgłasza błąd" error={vast.data.error} />}
      {vast.data?.configured && (
        <>
          <div className="flex items-baseline justify-between">
            <span className="text-sm text-ink-400">Saldo</span>
            <span className="font-display text-4xl tabular">{formatUsd(vast.data.balance)}</span>
          </div>
          <div>
            <div className="label">Uruchomione instancje</div>
            {vast.data.instances.length === 0 ? (
              <p className="text-[0.82rem] text-ink-500">Żadna karta nie pracuje — nic nie płacisz.</p>
            ) : (
              <ul className="flex flex-col gap-1.5">
                {vast.data.instances.map((i) => (
                  <li key={i.id} className="flex items-center gap-3 rounded-md border border-ink-700 bg-ink-900 px-3 py-2 font-mono text-[0.75rem]">
                    <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-safe" />
                    <span className="text-ink-200">{i.gpu}</span>
                    <span className="truncate text-ink-500">{i.name || `#${i.id}`}</span>
                    <span className="ml-auto text-ink-300">{i.status}</span>
                    <span className="text-ink-100">{formatUsd(i.dph, 3)}/h</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <Button variant="danger" size="sm" className="self-start" disabled={vast.data.instances.length === 0} onClick={() => setConfirm(true)}>
            Zwolnij wszystkie karty
          </Button>
        </>
      )}
      <ConfirmDialog
        open={confirm}
        title="Zwolnić wszystkie karty?"
        confirmLabel="Zwolnij karty"
        danger
        busy={down.isPending}
        onConfirm={() => down.mutate()}
        onClose={() => setConfirm(false)}
      >
        Wszystkie instancje Vast na tym koncie zostaną zniszczone. Trwający render zostanie przerwany, a niepobrane wyniki przepadną.
        <InlineError error={down.error} />
      </ConfirmDialog>
    </section>
  );
}
