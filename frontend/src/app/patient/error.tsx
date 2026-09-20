"use client";

import { RouteError } from "@/components/shared/route-boundaries";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <RouteError
      error={error}
      reset={reset}
      homeHref="/patient/timeline"
      homeLabel="Go to timeline"
    />
  );
}
