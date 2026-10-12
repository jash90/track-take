import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, qk } from "../api/client";
import { Button, InlineError } from "./ui";
import { useToast } from "./Toaster";

/** Password field for the Vast.ai API key. The key is sent once and never shown again. */
export function VastKeyForm({ replacing = false }: { replacing?: boolean }) {
  const [key, setKey] = useState("");
  const qc = useQueryClient();
  const toast = useToast();
  const save = useMutation({
    mutationFn: (k: string) => api.vastKey(k),
    onSuccess: (status) => {
      qc.setQueryData(qk.vast, status);
      setKey("");
      toast(status.error ? `Klucz zapisany, ale Vast zgłasza: ${status.error}` : "Klucz Vast zapisany", status.error ? "err" : "ok");
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const k = key.trim();
    if (k) save.mutate(k);
  };
  return (
    <form onSubmit={submit} className="flex flex-col gap-2">
      <label className="label" htmlFor="vast-key">
        {replacing ? "Nowy klucz API Vast.ai" : "Klucz API Vast.ai"}
      </label>
      <div className="flex gap-2">
        <input
          id="vast-key"
          type="password"
          autoComplete="off"
          spellCheck={false}
          className="field font-mono"
          placeholder="wklej klucz z console.vast.ai → Account → API Keys"
          value={key}
          onChange={(e) => setKey(e.target.value)}
        />
        <Button type="submit" variant="primary" busy={save.isPending} disabled={!key.trim()}>
          Zapisz
        </Button>
      </div>
      <p className="text-[0.75rem] text-ink-500">Klucz trafia tylko do lokalnego backendu (jak `vastai set api-key`). Interfejs nigdy go nie wyświetla.</p>
      <InlineError error={save.error} />
    </form>
  );
}
