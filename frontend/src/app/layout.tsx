import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/layout/providers";
import { PWARegister } from "@/components/pwa-register";

export const metadata: Metadata = {
  title: "MedConnect India",
  description: "EMR + Patient Portal for India's Digital Health Ecosystem",
  manifest: "/manifest.json",
  themeColor: "#4169E1",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
  },
  viewport: {
    width: "device-width",
    initialScale: 1,
    maximumScale: 1,
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="manifest" href="/manifest.json" />
        <meta name="theme-color" content="#4169E1" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="default" />
      </head>
      <body className="min-h-screen bg-gray-50 text-gray-900 antialiased">
        <PWARegister />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
