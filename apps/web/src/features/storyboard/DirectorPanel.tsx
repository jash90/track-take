import type { Storyboard } from "../../api/types";
import { Button } from "../../components/ui";
import { plural } from "../../lib/format";

interface Props {
  draft: Storyboard;
  disabled: boolean;
  instructions: string;
  onInstructions: (v: string) => void;
  onChange: (patch: Partial<Pick<Storyboard, "style" | "heroine">>) => void;
  selectedCount: number;
  busy: boolean;
  onRewrite: () => void;
}

/** Global storyboard fields + instructions for the Claude director. */
export function DirectorPanel({ draft, disabled, instructions, onInstructions, onChange, selectedCount, busy, onRewrite }: Props) {
  return (
    <aside className="flex flex-col gap-5">
      <section className="panel flex flex-col gap-4 p-5">
        <div>
          <div className="eyebrow">Biblia stylu</div>
          <div className="mt-0.5 font-display text-2xl">Cały teledysk</div>
        </div>
        <div>
          <label className="label" htmlFor="sb-style">Styl</label>
          <textarea
            id="sb-style"
            rows={4}
            disabled={disabled}
            className="field resize-y text-[0.88rem] leading-relaxed disabled:opacity-60"
            value={draft.style}
            onChange={(e) => onChange({ style: e.target.value })}
          />
        </div>
        <div>
          <label className="label" htmlFor="sb-heroine">Bohaterka — opis w każdym prompcie</label>
          <textarea
            id="sb-heroine"
            rows={5}
            disabled={disabled}
            className="field resize-y text-[0.88rem] leading-relaxed disabled:opacity-60"
            value={draft.heroine}
            onChange={(e) => onChange({ heroine: e.target.value })}
          />
        </div>
      </section>

      <section className="panel flex flex-col gap-3 p-5">
        <div>
          <div className="eyebrow">Reżyser · Claude</div>
          <div className="mt-0.5 font-display text-2xl">Uwagi do sceny</div>
        </div>
        <label className="label sr-only" htmlFor="sb-instr">Instrukcje dla reżysera</label>
        <textarea
          id="sb-instr"
          rows={3}
          className="field resize-y text-[0.85rem] leading-relaxed"
          placeholder="opcjonalnie, np. „w refrenach więcej deszczu i neonów, w bridge’u zbliżenia twarzy”"
          value={instructions}
          onChange={(e) => onInstructions(e.target.value)}
        />
        <Button
          variant="secondary"
          disabled={selectedCount === 0 || disabled}
          busy={busy}
          onClick={onRewrite}
          title={selectedCount === 0 ? "Zaznacz ujęcia na osi czasu (⌘/Shift+klik dla wielu)" : undefined}
        >
          Przepisz zaznaczone{selectedCount > 0 ? ` (${selectedCount} ${plural(selectedCount, "ujęcie", "ujęcia", "ujęć")})` : ""}
        </Button>
        <p className="text-[0.72rem] leading-relaxed text-ink-500">
          ⌘/Ctrl/Shift + klik na osi zaznacza kilka ujęć. Instrukcje działają też dla „Napisz storyboard”.
        </p>
      </section>
    </aside>
  );
}
