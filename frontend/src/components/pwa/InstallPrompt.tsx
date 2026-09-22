"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Download, X } from "lucide-react";

const DISMISS_KEY = "medconnect-install-dismissed";
const DISMISS_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

// beforeinstallprompt is not in the TS DOM lib — declare the minimal shape.
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

function dismissedRecently(): boolean {
  try {
    const ts = Number(localStorage.getItem(DISMISS_KEY));
    return Number.isFinite(ts) && ts > 0 && Date.now() - ts < DISMISS_MS;
  } catch {
    return false;
  }
}

function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    // iOS Safari
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  );
}

/**
 * Bottom banner offering the browser's native PWA install flow. Only rendered
 * in the patient layout. Hidden when the app is already installed, when the
 * browser never fires beforeinstallprompt (e.g. iOS), or when the user
 * dismissed it within the last 7 days.
 */
export function InstallPrompt() {
  const t = useTranslations("pwa.installPrompt");
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(
    null,
  );
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (isStandalone() || dismissedRecently()) return;

    const onBeforeInstallPrompt = (e: Event) => {
      e.preventDefault();
      setDeferred(e as BeforeInstallPromptEvent);
      setVisible(true);
    };
    const onAppInstalled = () => {
      setVisible(false);
      setDeferred(null);
    };

    window.addEventListener("beforeinstallprompt", onBeforeInstallPrompt);
    window.addEventListener("appinstalled", onAppInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onBeforeInstallPrompt);
      window.removeEventListener("appinstalled", onAppInstalled);
    };
  }, []);

  if (!visible || !deferred) return null;

  const dismiss = () => {
    try {
      localStorage.setItem(DISMISS_KEY, String(Date.now()));
    } catch {
      // storage unavailable — just hide for this session
    }
    setVisible(false);
    setDeferred(null);
  };

  const install = async () => {
    try {
      await deferred.prompt();
      const { outcome } = await deferred.userChoice;
      if (outcome === "accepted") {
        setVisible(false);
        setDeferred(null);
        return;
      }
    } catch {
      // prompt() rejected — treat like a dismiss
    }
    dismiss();
  };

  return (
    <div
      role="dialog"
      aria-label={t("title")}
      className="fixed inset-x-4 bottom-4 z-50 mx-auto flex max-w-md items-center gap-3 rounded-xl border border-dreams-border bg-white p-4 shadow-lg"
    >
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-dreams-blue text-white">
        <Download className="h-5 w-5" aria-hidden />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-dreams-textPrimary">
          {t("title")}
        </p>
        <p className="truncate text-xs text-dreams-textSecondary">
          {t("subtitle")}
        </p>
      </div>
      <button
        type="button"
        onClick={install}
        className="shrink-0 rounded-lg bg-dreams-blue px-3 py-2 text-sm font-medium text-white hover:opacity-90"
      >
        {t("install")}
      </button>
      <button
        type="button"
        onClick={dismiss}
        aria-label={t("dismiss")}
        className="shrink-0 rounded-lg p-1.5 text-dreams-textSecondary hover:bg-gray-100"
      >
        <X className="h-4 w-4" aria-hidden />
      </button>
    </div>
  );
}
