"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";

export function Providers({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 30_000, retry: 1 },
        },
      })
  );

  const { initialized, initAuth } = useAuthStore();

  // Skip auth for public pages
  const publicPages = ["/test-design-system"];
  const isPublicPage = publicPages.includes(pathname);

  useEffect(() => {
    if (!isPublicPage) {
      initAuth();
    }
  }, [initAuth, isPublicPage]);

  // Skip auth initialization for public pages
  if (isPublicPage) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  }

  if (!initialized) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
      </div>
    );
  }

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
