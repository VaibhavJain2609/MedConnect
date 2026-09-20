"use client"

import { X } from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { cn } from "@/lib/utils"

export function Toaster() {
  const { toasts, dismiss } = useToast()

  return (
    <div
      aria-live="polite"
      aria-label="Notifications"
      className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-full max-w-sm flex-col gap-2"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          role="status"
          className={cn(
            "pointer-events-auto rounded-lg border p-4 shadow-lg",
            t.variant === "destructive"
              ? "border-red-300 bg-red-50 text-red-900"
              : "border-dreams-border bg-white text-dreams-textPrimary"
          )}
        >
          <div className="flex items-start justify-between gap-3">
            <p className="text-sm font-semibold">{t.title}</p>
            <button
              type="button"
              onClick={() => dismiss(t.id)}
              aria-label="Dismiss notification"
              className="flex-shrink-0 rounded p-0.5 text-dreams-textSecondary hover:bg-black/5"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          {t.description && (
            <p className="mt-1 text-sm opacity-80">{t.description}</p>
          )}
        </div>
      ))}
    </div>
  )
}
