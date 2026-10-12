import { Fragment, createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { LOCALES, render, setCurrentLang, type Lang, type Params } from "./core";
import { en } from "./en";
import { pl, type Key } from "./pl";

export type { Key } from "./pl";
export type { Lang } from "./core";
export type TFn = (key: Key, params?: Params) => string;

const DICTS = { pl, en } as const;
const STORAGE_KEY = "tracktake.lang";

function initialLang(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "pl" || saved === "en") return saved;
  } catch {
    /* storage unavailable */
  }
  return navigator.language?.toLowerCase().startsWith("pl") ? "pl" : "en";
}

/** Plain translate for code outside React (uses the active language). */
export function translate(lang: Lang, key: Key, params?: Params): string {
  return render(DICTS[lang][key], lang, params);
}

interface I18nValue {
  lang: Lang;
  locale: string;
  setLang: (l: Lang) => void;
  t: TFn;
}

const I18nCtx = createContext<I18nValue | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => {
    const l = initialLang();
    setCurrentLang(l);
    return l;
  });

  const setLang = useCallback((l: Lang) => {
    setCurrentLang(l);
    setLangState(l);
    try {
      localStorage.setItem(STORAGE_KEY, l);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
    document.title = translate(lang, "app.title");
  }, [lang]);

  const value = useMemo<I18nValue>(
    () => ({ lang, locale: LOCALES[lang], setLang, t: (key, params) => translate(lang, key, params) }),
    [lang, setLang],
  );
  return <I18nCtx.Provider value={value}>{children}</I18nCtx.Provider>;
}

export function useI18n(): I18nValue {
  const v = useContext(I18nCtx);
  if (!v) throw new Error("useI18n outside I18nProvider");
  return v;
}

export function useT(): TFn {
  return useI18n().t;
}

/** Translation with React nodes in place of {placeholders}, e.g. bold words inside a sentence. */
export function Trans({ k, values }: { k: Key; values: Record<string, ReactNode> }) {
  const t = useT();
  const text = t(k);
  const parts = text.split(/(\{\w+\})/g);
  return (
    <>
      {parts.map((part, i) => {
        const m = /^\{(\w+)\}$/.exec(part);
        if (m && m[1] && m[1] in values) return <Fragment key={i}>{values[m[1]]}</Fragment>;
        return <Fragment key={i}>{part}</Fragment>;
      })}
    </>
  );
}
