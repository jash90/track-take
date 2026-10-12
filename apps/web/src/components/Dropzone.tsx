import { useId, useRef, useState, type DragEvent, type ReactNode } from "react";
import { cx } from "../lib/cx";
import { useT } from "../i18n";

interface DropzoneProps {
  accept: string;
  /** e.g. ["audio/", ".mp3", ".wav"] — MIME prefixes or extensions accepted on drop. */
  match: string[];
  label: string;
  hint: string;
  file: File | null;
  onFile: (f: File) => void;
  children?: ReactNode;
  className?: string;
}

function accepts(file: File, match: string[]): boolean {
  const name = file.name.toLowerCase();
  return match.some((m) => (m.startsWith(".") ? name.endsWith(m) : file.type.startsWith(m)));
}

export function Dropzone({ accept, match, label, hint, file, onFile, children, className }: DropzoneProps) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [reject, setReject] = useState<string | null>(null);
  const t = useT();

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    const f = e.dataTransfer.files[0];
    if (!f) return;
    if (!accepts(f, match)) {
      setReject(t("dropzone.unsupported", { name: f.name }));
      return;
    }
    setReject(null);
    onFile(f);
  };

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
      className={cx(
        "relative flex flex-col overflow-hidden rounded-xl border border-dashed transition-colors",
        over ? "border-safe bg-safe/[0.06]" : "border-ink-600 bg-ink-900/50 hover:border-ink-400",
        className,
      )}
    >
      {children}
      <div className="flex items-center gap-3 px-4 py-3">
        <button
          type="button"
          onClick={() => input.current?.click()}
          className="rounded-md border border-ink-600 bg-ink-800 px-3 py-1.5 text-[0.8rem] text-ink-100 hover:border-ink-400"
          aria-describedby={`${id}-hint`}
        >
          {label}
        </button>
        <div id={`${id}-hint`} className="min-w-0 text-[0.75rem] text-ink-400">
          {file ? <span className="truncate text-ink-200">{t("dropzone.new", { name: file.name })}</span> : hint}
          {reject && <div className="text-err">{reject}</div>}
        </div>
      </div>
      <input
        ref={input}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) {
            setReject(null);
            onFile(f);
          }
          e.target.value = "";
        }}
      />
    </div>
  );
}
