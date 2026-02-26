"use client";

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Application error:", error);
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-dreams-lightBg">
      <div className="w-full max-w-md space-y-6 rounded-lg bg-white p-8 shadow-lg">
        <div className="space-y-2 text-center">
          <h1 className="text-3xl font-bold text-dreams-textPrimary">
            Something went wrong
          </h1>
          <p className="text-dreams-textSecondary">
            An error occurred while loading this page.
          </p>
        </div>

        {error.message && (
          <div className="rounded-lg bg-red-50 p-4">
            <p className="text-sm text-red-800">{error.message}</p>
          </div>
        )}

        <div className="flex gap-3">
          <button
            onClick={reset}
            className="flex-1 rounded-lg bg-dreams-blue px-4 py-2 text-white hover:opacity-90 transition-opacity"
          >
            Try again
          </button>
          <button
            onClick={() => (window.location.href = "/")}
            className="flex-1 rounded-lg border border-dreams-border px-4 py-2 text-dreams-textPrimary hover:bg-dreams-lightBg transition-colors"
          >
            Go home
          </button>
        </div>
      </div>
    </div>
  );
}
