import type { Metadata, Viewport } from "next";
import "./globals.css";
import { NextIntlClientProvider } from "next-intl";
import { getLocale } from "next-intl/server";
import { Providers } from "@/components/layout/providers";
import { PWARegister } from "@/components/pwa-register";
import { SentryInit } from "@/components/sentry-init";

export const metadata: Metadata = {
  title: "MedConnect India",
  description: "EMR + Patient Portal for India's Digital Health Ecosystem",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
  },
};

// themeColor/viewport must live in the viewport export on Next 15+ —
// the metadata export no longer accepts them.
export const viewport: Viewport = {
  themeColor: "#4169E1",
  width: "device-width",
  initialScale: 1,
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // NEXT_LOCALE cookie → resolved by src/i18n/request.ts (no locale routing).
  const locale = await getLocale();
  return (
    <html lang={locale}>
      <head>
        <link rel="manifest" href="/manifest.json" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="default" />
      </head>
      <body className="min-h-screen bg-gray-50 text-gray-900 antialiased">
        <PWARegister />
        <SentryInit />
        {/* Inherits locale + messages from getRequestConfig (request.ts) */}
        <NextIntlClientProvider>
          <Providers>{children}</Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
