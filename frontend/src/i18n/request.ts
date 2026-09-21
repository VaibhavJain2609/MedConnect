import { cookies } from "next/headers";
import { getRequestConfig } from "next-intl/server";
import { DEFAULT_LOCALE, isLocale, LOCALE_COOKIE } from "./locale";

/**
 * next-intl request configuration — "App Router without i18n routing" setup.
 * There is no [locale] URL segment; the locale comes from the NEXT_LOCALE
 * cookie (set by LanguageSwitcher) and falls back to English.
 *
 * NOTE: reading cookies() makes every route that renders translations
 * dynamic (opted out of full static rendering). That is the accepted
 * trade-off for cookie-based locale selection.
 */
export default getRequestConfig(async () => {
  const store = await cookies();
  const raw = store.get(LOCALE_COOKIE)?.value;
  const locale = isLocale(raw) ? raw : DEFAULT_LOCALE;

  return {
    locale,
    messages: (await import(`../../messages/${locale}.json`)).default,
  };
});
