import { useSyncExternalStore } from "react"

type ToastType = "default" | "destructive"

export interface Toast {
  id: string
  title: string
  description?: string
  variant?: ToastType
}

const TOAST_DURATION_MS = 4000

// Module-level store so toasts triggered anywhere are rendered by the
// single <Toaster /> mounted in Providers.
let toasts: Toast[] = []
const listeners = new Set<() => void>()
const EMPTY: Toast[] = []

function emit() {
  listeners.forEach((listener) => listener())
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

function getSnapshot(): Toast[] {
  return toasts
}

function getServerSnapshot(): Toast[] {
  return EMPTY
}

export function toast({ title, description, variant = "default" }: Omit<Toast, "id">) {
  const id = Math.random().toString(36).substring(2, 10)
  toasts = [...toasts, { id, title, description, variant }]
  emit()

  setTimeout(() => dismiss(id), TOAST_DURATION_MS)

  return { id }
}

export function dismiss(toastId: string) {
  toasts = toasts.filter((t) => t.id !== toastId)
  emit()
}

export function useToast() {
  const current = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)

  return {
    toast,
    dismiss,
    toasts: current,
  }
}
