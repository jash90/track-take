import type { Storyboard } from "../../api/types";
import { Button } from "../../components/ui";
import { useT } from "../../i18n";

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
  const t = useT();
  return (
    <aside className="flex flex-col gap-5">
      <section className="panel flex flex-col gap-4 p-5">
        <div>
          <div className="eyebrow">{t("director.bible")}</div>
          <div className="mt-0.5 font-display text-2xl">{t("director.wholeVideo")}</div>
        </div>
        <div>
          <label className="label" htmlFor="sb-style">{t("director.style")}</label>
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
          <label className="label" htmlFor="sb-heroine">{t("director.heroine")}</label>
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
          <div className="eyebrow">{t("director.eyebrow")}</div>
          <div className="mt-0.5 font-display text-2xl">{t("director.notes")}</div>
        </div>
        <label className="label sr-only" htmlFor="sb-instr">{t("director.instrLabel")}</label>
        <textarea
          id="sb-instr"
          rows={3}
          className="field resize-y text-[0.85rem] leading-relaxed"
          placeholder={t("director.instrPlaceholder")}
          value={instructions}
          onChange={(e) => onInstructions(e.target.value)}
        />
        <Button
          variant="secondary"
          disabled={selectedCount === 0 || disabled}
          busy={busy}
          onClick={onRewrite}
          title={selectedCount === 0 ? t("director.selectHint") : undefined}
        >
          {selectedCount > 0 ? t("director.rewriteN", { count: selectedCount }) : t("director.rewrite")}
        </Button>
        <p className="text-[0.72rem] leading-relaxed text-ink-500">
          {t("director.multiHint")}
        </p>
      </section>
    </aside>
  );
}
