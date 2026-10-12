/** Tiny typed i18n: flat keys, {placeholder} interpolation, Intl.PluralRules plurals. */
export type Lang = "pl" | "en";
export type PluralEntry = { other: string } & Partial<Record<Intl.LDMLPluralRule, string>>;
export type Entry = string | PluralEntry;
export type Params = Record<string, string | number>;

export const LOCALES: Record<Lang, string> = { pl: "pl-PL", en: "en-US" };

let currentLang: Lang = "pl";
export const getLang = () => currentLang;
export const getLocale = () => LOCALES[currentLang];
export function setCurrentLang(l: Lang) {
  currentLang = l;
}

const pluralRules = new Map<string, Intl.PluralRules>();
function plural(locale: string, n: number): Intl.LDMLPluralRule {
  let r = pluralRules.get(locale);
  if (!r) {
    r = new Intl.PluralRules(locale);
    pluralRules.set(locale, r);
  }
  return r.select(n);
}

export function render(entry: Entry, lang: Lang, params?: Params): string {
  let text: string;
  if (typeof entry === "string") text = entry;
  else {
    const n = Number(params?.count ?? 0);
    text = entry[plural(LOCALES[lang], n)] ?? entry.other;
  }
  if (!params) return text;
  return text.replace(/\{(\w+)\}/g, (m, k: string) => {
    const v = params[k];
    if (v === undefined) return m;
    return typeof v === "number" ? v.toLocaleString(LOCALES[lang]) : v;
  });
}
