import type { FormatName, KeySet, VideoFiles } from "../../api/types";
import { cx } from "../../lib/cx";
import { formatRatio } from "../../lib/orientation";
import { SmartVideo } from "./SmartVideo";

function Downloads({ files }: { files: VideoFiles }) {
  const links: { label: string; note: string; href: string | null; mb?: number }[] = [
    { label: "Podgląd", note: "HEVC, do obejrzenia", href: files.preview, mb: files.size_mb.preview },
    { label: "Master", note: "pełna jakość, do publikacji", href: files.master, mb: files.size_mb.master },
  ];
  return (
    <ul className="flex flex-col gap-2">
      {links.map((l) => (
        <li key={l.label}>
          {l.href ? (
            <a
              href={l.href}
              download
              className="group flex items-center gap-3 rounded-lg border border-ink-700 bg-ink-900 px-4 py-2.5 transition-colors hover:border-safe"
            >
              <span className="text-lg text-ink-400 group-hover:text-safe">↓</span>
              <span className="flex flex-col leading-tight">
                <span className="text-sm text-ink-100">{l.label}</span>
                <span className="text-[0.7rem] text-ink-500">{l.note}</span>
              </span>
              {l.mb !== undefined && <span className="ml-auto font-mono text-[0.75rem] text-ink-400">{l.mb.toFixed(0)} MB</span>}
            </a>
          ) : (
            <span className="block rounded-lg border border-dashed border-ink-700 px-4 py-2.5 text-sm text-ink-600">{l.label} — brak</span>
          )}
        </li>
      ))}
    </ul>
  );
}

/** One player in the project format plus download links. */
export function SetPlayers({ set, format, files }: { set: KeySet; format: FormatName; files: VideoFiles }) {
  const portrait = format === "9x16";
  return (
    <section className="panel p-5">
      <div className="mb-4 flex items-baseline justify-between">
        <h2 className="font-display text-3xl">{set === "codex" ? "Codex" : "ComfyUI"}</h2>
        <span className="eyebrow">zestaw {set} · {formatRatio(format)}</span>
      </div>
      <div className={cx("grid items-start gap-6", portrait ? "grid-cols-[minmax(0,300px)_minmax(0,1fr)]" : "xl:grid-cols-[minmax(0,1fr)_260px]")}>
        <SmartVideo
          controls
          preload="metadata"
          sources={[files.preview, files.master]}
          className={cx("w-full rounded-lg bg-black", portrait ? "aspect-[9/16]" : "aspect-video")}
          aria-label={`${set} ${formatRatio(format)}`}
        />
        <Downloads files={files} />
      </div>
    </section>
  );
}
