"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { useAuthStore } from "@/stores/auth-store";
import { registerQueryClient } from "@/lib/auth";
import { Toaster } from "@/components/ui/toaster";
import { Spinner } from "@/components/ui/spinner";
import { setRateLimitToastCopy } from "@/lib/rate-limit";

// Routes that require a resolved auth state before rendering.
// Public routes (landing, login, signup, auth callback, etc.) render
// immediately while auth initializes in the background.
const PROTECTED_PREFIXES = ["/admin", "/doctor", "/patient"];

export function Providers({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const tCommon = useTranslations("common");
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 30_000, retry: 1 },
        },
      })
  );

  // Hand the transport layer the localized toast copy for rate-limit (429)
  // rejections — the interceptor owns the (deduped) toast so raw api.* calls
  // and React Query calls alike get the friendly message in the user's locale.
  useEffect(() => {
    setRateLimitToastCopy({
      title: tCommon("rateLimitedTitle"),
      describe: (retryAfter) =>
        retryAfter != null
          ? tCommon("rateLimitedRetry", { seconds: retryAfter })
          : tCommon("rateLimitedGeneric"),
    });
    return () => setRateLimitToastCopy(null);
  }, [tCommon]);

  const { initialized, initAuth } = useAuthStore();

  // Register the shared QueryClient so logout() can purge cached data
  useEffect(() => {
    registerQueryClient(queryClient);
    return () => registerQueryClient(null);
  }, [queryClient]);

  // check-sso is silent, so it's safe to init everywhere — public pages
  // use it to detect an existing session without blocking render.
  useEffect(() => {
    initAuth();
  }, [initAuth]);

  const isProtectedRoute = PROTECTED_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`)
  );

  if (isProtectedRoute && !initialized) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <Toaster />
    </QueryClientProvider>
  );
}
