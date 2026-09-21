/**
 * Locale primitives shared by the server request config (src/i18n/request.ts)
 * and the client-side LanguageSwitcher.
 *
 * No locale routing: the app has a single URL space and the active locale is
 * stored in the NEXT_LOCALE cookie. See docs/i18n.md.
 */
export const LOCALES = ["en", "hi"] as const;
export type Locale = (typeof LOCALES)[number];

export const DEFAULT_LOCALE: Locale = "en";

/** Cookie that carries the locale preference. Read server-side per request. */
export const LOCALE_COOKIE = "NEXT_LOCALE";

/** Native-script labels shown in the language switcher (never translated). */
export const LOCALE_LABELS: Record<Locale, string> = {
  en: "English",
  hi: "हिन्दी",
};

export function isLocale(value: string | undefined | null): value is Locale {
  return !!value && (LOCALES as readonly string[]).includes(value);
}
