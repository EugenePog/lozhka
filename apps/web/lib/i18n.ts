export const LANGS = ["nl", "en", "ru"] as const;
export type Lang = (typeof LANGS)[number];
export const DEFAULT_LANG: Lang = "nl";
export const LANG_LABEL: Record<Lang, string> = { nl: "NL", en: "EN", ru: "RU" };
export const isLang = (v: string): v is Lang => (LANGS as readonly string[]).includes(v);
export const LOCALE: Record<Lang, string> = { nl: "nl-NL", en: "en-GB", ru: "ru-RU" };
