import type messages from "./messages/en.json";
import type { Locale } from "./src/i18n/locale";

/**
 * TypeScript augmentation for next-intl — gives `useTranslations` /
 * `getTranslations` compile-time checked message keys (against en.json as
 * the source of truth) and narrows `useLocale()` to 'en' | 'hi'.
 * See https://next-intl.dev/docs/workflows/typescript
 */
declare module "next-intl" {
  interface AppConfig {
    Locale: Locale;
    Messages: typeof messages;
  }
}
