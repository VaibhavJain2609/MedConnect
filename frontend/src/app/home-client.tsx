"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { LandingNav, LandingCTA } from "./landing-client";

export function HomeClient() {
  const router = useRouter();
  const { user, initialized, loading } = useAuthStore();

  useEffect(() => {
    if (initialized && user) {
      // Redirect authenticated users to their dashboard
      const dashboardUrl = user.role === "doctor" ? "/doctor/dashboard" : "/patient/timeline";
      router.push(dashboardUrl);
    }
  }, [initialized, user, router]);

  // Show loading while initializing auth
  if (!initialized || loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
      </div>
    );
  }

  // Show landing page only if not authenticated
  return (
    <main className="flex min-h-screen flex-col">
      <nav className="border-b bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <span className="text-xl font-bold text-primary-700">MedConnect</span>
          <LandingNav />
        </div>
      </nav>

      <section className="flex flex-1 flex-col items-center justify-center px-4 py-20 text-center">
        <h1 className="mb-4 text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl">
          Your Health Records,
          <br />
          <span className="text-primary-600">One Platform</span>
        </h1>
        <p className="mb-8 max-w-2xl text-lg text-gray-600">
          MedConnect gives doctors a simple way to create digital records and
          gives patients a single place to view, search, and understand their
          complete health history.
        </p>
        <LandingCTA />
      </section>

      <section className="border-t bg-white px-4 py-16">
        <div className="mx-auto grid max-w-5xl gap-8 md:grid-cols-3">
          <div className="text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-lg bg-blue-100 text-2xl">
              📋
            </div>
            <h3 className="mb-2 font-semibold">Digital Records</h3>
            <p className="text-sm text-gray-600">
              Doctors create structured medical records and prescriptions digitally.
            </p>
          </div>
          <div className="text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-lg bg-green-100 text-2xl">
              📱
            </div>
            <h3 className="mb-2 font-semibold">Patient Timeline</h3>
            <p className="text-sm text-gray-600">
              Patients view their complete health history in one chronological timeline.
            </p>
          </div>
          <div className="text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-lg bg-purple-100 text-2xl">
              🔒
            </div>
            <h3 className="mb-2 font-semibold">FHIR R4 Ready</h3>
            <p className="text-sm text-gray-600">
              Records stored in international health data standard, ready for ABDM integration.
            </p>
          </div>
        </div>
      </section>

      <footer className="border-t px-4 py-6 text-center text-sm text-gray-500">
        MedConnect India — Your health, your records, your language.
      </footer>
    </main>
  );
}
