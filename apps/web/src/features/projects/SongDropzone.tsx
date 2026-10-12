import { useRef, useState, type DragEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { api, qk } from "../../api/client";
import type { Orientation } from "../../api/types";
import { useToast } from "../../components/Toaster";
import { Spinner } from "../../components/ui";
import { useT } from "../../i18n";
import { cx } from "../../lib/cx";
import { errorMessage } from "../../lib/format";
import { FrameGlyph, ORIENTATIONS } from "../../lib/orientation";

const isAudio = (f: File) => f.type.startsWith("audio/") || /\.(mp3|wav)$/i.test(f.name);

/** "Song (Final) [v2].mp3" -> "Song (Final) v2" */
export function nameFromFile(file: string): string {
  return file
    .replace(/\.[^.]+$/, "")
    .replace(/[_]+/g, " ")
    .replace(/[[\]{}]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 80);
}

/** Drop a Suno song → project created, song uploaded, Inputs step opened. */
export function SongDropzone() {
  const t = useT();
  const qc = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [orientation, setOrientation] = useState<Orientation>("landscape");

  const create = useMutation({
    mutationFn: async (file: File) => {
      const p = await api.createProject({ name: nameFromFile(file.name) || t("newProject.defaultName"), orientation });
      return api.uploadInputs(p.id, { song: file });
    },
    onSuccess: (p) => {
      qc.setQueryData(qk.project(p.id), p);
      void qc.invalidateQueries({ queryKey: qk.projects });
      navigate(`/p/${encodeURIComponent(p.id)}/wejscie`);
    },
    onError: (err) => toast(t("drop.error", { error: errorMessage(err) }), "err"),
  });

  const take = (f: File | undefined) => {
    if (!f) return;
    if (!isAudio(f)) {
      toast(t("drop.notAudio"), "err");
      return;
    }
    create.mutate(f);
  };
  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    take(e.dataTransfer.files[0]);
  };

  return (
    <section
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
      className={cx(
        "mb-8 flex flex-col items-start gap-5 rounded-2xl border-2 border-dashed px-8 py-8 transition-colors md:flex-row md:items-center",
        over ? "border-safe bg-safe/[0.07]" : "border-ink-600 bg-ink-900/40 hover:border-ink-400",
      )}
    >
      <button
        type="button"
        disabled={create.isPending}
        onClick={() => input.current?.click()}
        className="group flex flex-1 items-center gap-5 text-left"
      >
        <span className="grid h-16 w-16 shrink-0 place-items-center rounded-full border-2 border-safe text-3xl text-safe transition-transform group-hover:scale-105">
          {create.isPending ? <Spinner /> : "♪"}
        </span>
        <span className="flex flex-col">
          <span className="font-display text-[2.2rem] leading-none">{create.isPending ? t("drop.creating") : t("drop.title")}</span>
          <span className="mt-1 text-sm text-ink-400">
            {t("drop.sub")} · <span className="text-ink-200 underline underline-offset-4">{t("drop.pick")}</span>
          </span>
        </span>
      </button>
      <div className="flex flex-col gap-1.5">
        <span className="label mb-0" id="drop-format">{t("drop.format")}</span>
        <div role="radiogroup" aria-labelledby="drop-format" className="flex rounded-md border border-ink-600 p-0.5">
          {ORIENTATIONS.map((o) => (
            <button
              key={o.value}
              type="button"
              role="radio"
              aria-checked={orientation === o.value}
              title={t(o.hint)}
              onClick={() => setOrientation(o.value)}
              className={cx(
                "flex items-center gap-2 rounded px-3 py-1.5 font-mono text-[0.78rem]",
                orientation === o.value ? "bg-ink-100 text-ink-950" : "text-ink-300 hover:text-ink-100",
              )}
            >
              <FrameGlyph orientation={o.value} size={14} />
              {o.ratio}
            </button>
          ))}
        </div>
      </div>
      <input
        ref={input}
        type="file"
        accept="audio/mpeg,audio/wav,audio/x-wav,.mp3,.wav"
        className="hidden"
        onChange={(e) => {
          take(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
    </section>
  );
}
