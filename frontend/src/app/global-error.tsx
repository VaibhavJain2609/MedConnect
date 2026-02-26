"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Global error:", error);
  }, [error]);

  return (
    <html>
      <body>
        <div className="flex min-h-screen items-center justify-center bg-gray-50">
          <div className="w-full max-w-md space-y-6 rounded-lg bg-white p-8 shadow-lg">
            <div className="space-y-2 text-center">
              <h1 className="text-3xl font-bold text-gray-900">
                Critical Error
              </h1>
              <p className="text-gray-600">
                A critical error occurred. Please try refreshing the page.
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
                className="flex-1 rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
              >
                Try again
              </button>
              <button
                onClick={() => (window.location.href = "/")}
                className="flex-1 rounded-lg border border-gray-300 px-4 py-2 text-gray-700 hover:bg-gray-50"
              >
                Go home
              </button>
            </div>
          </div>
        </div>
      </body>
    </html>
  );
}
