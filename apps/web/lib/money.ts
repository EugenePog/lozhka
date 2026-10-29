import { LOCALE, type Lang } from "./i18n";

/** Cents to a euro string with the language's decimal comma/point. */
export function euro(cents: number, lang: Lang = "nl"): string {
  return new Intl.NumberFormat(LOCALE[lang], { style: "currency", currency: "EUR" }).format(cents / 100);
}

export function formatDay(iso: string, lang: Lang): string {
  return new Intl.DateTimeFormat(LOCALE[lang], { weekday: "short", day: "numeric", month: "short", timeZone: "Europe/Amsterdam" }).format(new Date(iso));
}

export function formatTime(iso: string, lang: Lang): string {
  return new Intl.DateTimeFormat(LOCALE[lang], { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Amsterdam" }).format(new Date(iso));
}

export function formatDateTime(iso: string, lang: Lang): string {
  return `${formatDay(iso, lang)} ${formatTime(iso, lang)}`;
}

export function dayFromDate(date: string, lang: Lang): string {
  return new Intl.DateTimeFormat(LOCALE[lang], { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" }).format(new Date(`${date}T12:00:00Z`));
}

export function countdown(iso: string, now = Date.now()): string {
  const ms = Math.max(0, new Date(iso).getTime() - now);
  const h = Math.floor(ms / 3_600_000);
  const m = Math.floor((ms % 3_600_000) / 60_000);
  return h > 0 ? `${h}:${String(m).padStart(2, "0")} h` : `${m} min`;
}
