import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { WifiOff } from "lucide-react";

/**
 * Offline fallback — the service worker (public/sw.js) precaches this page at
 * install time and serves it for same-origin navigation requests that fail
 * while offline. Keep it dependency-free: no API calls, no client hooks.
 */
export default async function OfflinePage() {
  const t = await getTranslations("offline");

  return (
    <div className="flex min-h-screen items-center justify-center bg-dreams-lightBg p-4">
      <div className="w-full max-w-md space-y-4 rounded-lg bg-white p-8 text-center shadow-lg">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-dreams-blue/10">
          <WifiOff className="h-7 w-7 text-dreams-blue" aria-hidden />
        </div>
        <h1 className="text-2xl font-bold text-dreams-textPrimary">
          {t("title")}
        </h1>
        <p className="text-sm text-dreams-textSecondary">{t("body")}</p>
        <Link
          href="/"
          className="inline-block rounded-lg bg-dreams-blue px-6 py-3 text-white transition-opacity hover:opacity-90"
        >
          {t("retry")}
        </Link>
      </div>
    </div>
  );
}
