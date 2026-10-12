import { Button } from "../../components/ui";
import { useT } from "../../i18n";

interface Props {
  src: string | null;
  busy: boolean;
  running: boolean;
  onGenerate: () => void;
  onOpen: () => void;
}

export function CharacterSheet({ src, busy, running, onGenerate, onOpen }: Props) {
  const t = useT();
  return (
    <section className="panel flex flex-col gap-4 overflow-hidden p-5 md:flex-row md:items-center">
      {src ? (
        <button type="button" onClick={onOpen} aria-label={t("sheet.enlarge")} className="shrink-0 overflow-hidden rounded-lg border border-ink-600 hover:border-safe">
          <img src={src} alt={t("keys.sheet")} className="h-44 w-auto max-w-[420px] object-contain" />
        </button>
      ) : (
        <div className="grid h-44 w-72 shrink-0 place-items-center rounded-lg border border-dashed border-ink-600 font-display text-xl italic text-ink-600">
          {t("sheet.empty")}
        </div>
      )}
      <div className="flex flex-col gap-2">
        <div className="eyebrow">{t("sheet.eyebrow")}</div>
        <h2 className="font-display text-3xl leading-none">{t("keys.sheet")}</h2>
        <p className="max-w-md text-[0.85rem] leading-relaxed text-ink-400">
          {t("sheet.body")}
        </p>
        <div>
          <Button variant={src ? "secondary" : "primary"} busy={busy || running} onClick={onGenerate}>
            {src ? t("sheet.regen") : t("sheet.gen")}
          </Button>
        </div>
      </div>
    </section>
  );
}
