import { useI18n, type Lang } from "../i18n";
import { cx } from "../lib/cx";

const LANGS: Lang[] = ["pl", "en"];

/** "PL | EN" toggle in the top bar — instant, persisted in localStorage. */
export function LangSwitch() {
  const { lang, setLang, t } = useI18n();
  return (
    <div role="radiogroup" aria-label={t("shell.language")} className="flex items-center rounded-md border border-ink-700 p-0.5 font-mono text-[0.68rem]">
      {LANGS.map((l) => (
        <button
          key={l}
          type="button"
          role="radio"
          aria-checked={lang === l}
          lang={l}
          onClick={() => setLang(l)}
          className={cx(
            "rounded px-2 py-0.5 uppercase tracking-wider transition-colors",
            lang === l ? "bg-ink-100 text-ink-950" : "text-ink-400 hover:text-ink-100",
          )}
        >
          {l}
        </button>
      ))}
    </div>
  );
}
