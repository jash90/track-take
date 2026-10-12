import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { api, qk } from "../../api/client";
import type { Orientation } from "../../api/types";
import { Button, InlineError } from "../../components/ui";
import { cx } from "../../lib/cx";
import { ORIENTATIONS } from "../../lib/orientation";

export function NewProjectTile() {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [orientation, setOrientation] = useState<Orientation | null>(null);
  const qc = useQueryClient();
  const navigate = useNavigate();
  const create = useMutation({
    mutationFn: (payload: { name: string; orientation: Orientation }) => api.createProject(payload),
    onSuccess: (p) => {
      void qc.invalidateQueries({ queryKey: qk.projects });
      qc.setQueryData(qk.project(p.id), p);
      navigate(`/p/${encodeURIComponent(p.id)}/wejscie`);
    },
  });
  const ready = !!name.trim() && orientation !== null;
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (ready && orientation) create.mutate({ name: name.trim(), orientation });
  };
  const close = () => {
    setEditing(false);
    create.reset();
  };

  if (!editing) {
    return (
      <button
        type="button"
        onClick={() => setEditing(true)}
        className="group flex aspect-[1/1.18] flex-col items-center justify-center gap-4 rounded-xl border border-dashed border-ink-600 text-ink-400 transition-colors hover:border-safe/70 hover:text-ink-100"
      >
        <span className="grid h-14 w-14 place-items-center rounded-full border border-ink-600 text-3xl font-light transition-colors group-hover:border-safe group-hover:text-safe">
          +
        </span>
        <span className="font-display text-2xl italic">Nowy projekt</span>
        <span className="text-xs text-ink-500">utwór z Suno → teledysk</span>
      </button>
    );
  }

  return (
    <form
      onSubmit={submit}
      onKeyDown={(e) => {
        if (e.key === "Escape") close();
      }}
      className="flex min-h-full flex-col gap-4 rounded-xl border border-safe/50 bg-ink-850 p-5 sm:col-span-2"
    >
      <div>
        <div className="eyebrow">Nowy projekt</div>
        <div className="mt-1 font-display text-2xl italic">Jak się nazywa utwór?</div>
      </div>
      <input
        autoFocus
        className="field"
        placeholder="np. Silence"
        aria-label="Nazwa projektu"
        value={name}
        maxLength={80}
        onChange={(e) => setName(e.target.value)}
      />
      <fieldset>
        <legend className="label">Format teledysku — jeden na projekt</legend>
        <div role="radiogroup" aria-required className="grid grid-cols-2 gap-3">
          {ORIENTATIONS.map((o) => {
            const on = orientation === o.value;
            return (
              <button
                key={o.value}
                type="button"
                role="radio"
                aria-checked={on}
                onClick={() => setOrientation(o.value)}
                className={cx(
                  "flex items-center gap-4 rounded-lg border px-4 py-3 text-left transition-colors",
                  on ? "border-safe bg-safe/[0.08]" : "border-ink-600 hover:border-ink-400",
                )}
              >
                <span className="grid h-[64px] w-[64px] shrink-0 place-items-center">
                  <span
                    className={cx(
                      "block rounded-[4px] border-2 transition-colors",
                      on ? "border-safe bg-safe/15" : "border-ink-400 bg-ink-800",
                      o.value === "landscape" ? "h-[34px] w-[60px]" : "h-[60px] w-[34px]",
                    )}
                  />
                </span>
                <span className="flex min-w-0 flex-col">
                  <span className="font-display text-[1.45rem] leading-tight">
                    {o.label} <span className="font-mono text-[0.85rem] text-ink-300">{o.ratio}</span>
                  </span>
                  <span className="text-[0.75rem] text-ink-400">{o.hint}</span>
                </span>
              </button>
            );
          })}
        </div>
        {orientation === null && <p className="mt-2 text-[0.72rem] text-ink-500">Wybierz format — klatki i wideo powstają tylko w nim.</p>}
      </fieldset>
      <InlineError error={create.error} />
      <div className="mt-auto flex gap-2">
        <Button type="submit" variant="primary" busy={create.isPending} disabled={!ready}>
          Utwórz
        </Button>
        <Button variant="ghost" onClick={close}>
          Anuluj
        </Button>
      </div>
    </form>
  );
}
