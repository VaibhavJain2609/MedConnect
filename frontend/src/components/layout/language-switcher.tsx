"use client";

import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LOCALES,
  LOCALE_COOKIE,
  LOCALE_LABELS,
  type Locale,
} from "@/i18n/locale";

/**
 * EN/HI language toggle. Writes the NEXT_LOCALE cookie and calls
 * router.refresh() — the root layout re-renders server-side with the new
 * locale, so every useTranslations/getTranslations call updates.
 *
 * Styled for the dark sidebar by default; pass className to adapt.
 */
export function LanguageSwitcher({ className }: { className?: string }) {
  const locale = useLocale();
  const t = useTranslations("languageSwitcher");
  const router = useRouter();

  function select(next: Locale) {
    if (next === locale) return;
    // 1-year preference cookie; read by src/i18n/request.ts on each request.
    document.cookie = `${LOCALE_COOKIE}=${next};path=/;max-age=31536000;samesite=lax`;
    router.refresh();
  }

  return (
    <div
      role="group"
      aria-label={t("label")}
      className={cn("flex items-center gap-1", className)}
    >
      {LOCALES.map((l) => (
        <button
          key={l}
          type="button"
          onClick={() => select(l)}
          aria-pressed={locale === l}
          aria-label={t("switchTo", { language: LOCALE_LABELS[l] })}
          className={cn(
            "rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors",
            locale === l
              ? "bg-white/15 text-white"
              : "text-gray-400 hover:bg-white/10 hover:text-white"
          )}
        >
          {LOCALE_LABELS[l]}
        </button>
      ))}
    </div>
  );
}
