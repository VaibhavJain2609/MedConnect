"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { DoctorSidebar } from "./doctor-sidebar";
import { Button } from "@/components/ui/button";
import { GlobalSearch, GlobalSearchTrigger } from "@/components/ui/global-search";
import { NotificationCenter } from "@/components/layout/notification-center";
import { UserMenu } from "@/components/layout/user-menu";
import {
  Menu,
  Settings,
} from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";
import { ClinicSelector } from "@/components/layout/clinic-selector";
import api from "@/lib/api";

export function DoctorLayout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { user } = useAuthStore();
  const pathname = usePathname();
  const router = useRouter();

  // Check onboarding status and redirect if incomplete
  const { data: onboardingStatus } = useQuery({
    queryKey: ["onboarding-status"],
    queryFn: () =>
      api.get("/api/v1/onboarding/status").then((r) => r.data).catch(() => null),
    enabled: !!user && user.role === "doctor",
    staleTime: 30_000,
  });

  useEffect(() => {
    if (!onboardingStatus) return;
    const isOnboardingPage = pathname.startsWith("/doctor/onboarding");
    const isComplete = onboardingStatus.onboarding_step === "completed" && onboardingStatus.verified;
    const isPendingVerification = onboardingStatus.onboarding_step === "completed" && !onboardingStatus.verified;

    if (!isOnboardingPage && !isComplete && !isPendingVerification) {
      router.replace("/doctor/onboarding");
    }
    if (!isOnboardingPage && isPendingVerification) {
      router.replace("/doctor/onboarding");
    }
  }, [onboardingStatus, pathname, router]);

  return (
    <div className="flex h-screen overflow-hidden bg-dreams-lightBg">
      {/* Sidebar */}
      <DoctorSidebar
        isOpen={sidebarOpen}
        isMobileMenuOpen={mobileMenuOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        onMobileClose={() => setMobileMenuOpen(false)}
      />

      {/* Main content area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex h-16 items-center justify-between border-b border-dreams-border bg-white px-4 md:px-6 shadow-sm">
          <div className="flex items-center gap-4 flex-1">
            {/* Mobile menu button */}
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden"
              onClick={() => setMobileMenuOpen(true)}
              aria-label="Open menu"
            >
              <Menu className="h-5 w-5" />
            </Button>

            {/* Global search trigger */}
            <GlobalSearchTrigger />

            {/* Clinic selector */}
            <ClinicSelector />
          </div>

          {/* Utility icons */}
          <div className="flex items-center gap-2">
            {/* Notifications */}
            <NotificationCenter />

            {/* Settings */}
            <Button
              variant="ghost"
              size="icon"
              className="text-gray-600 hover:text-dreams-blue"
              title="Notifications"
              aria-label="Notifications"
              onClick={() => router.push("/doctor/notifications")}
            >
              <Settings className="h-5 w-5" />
            </Button>

            {/* Divider */}
            <div className="h-8 w-px bg-gray-200 mx-2" />

            {/* User dropdown */}
            <UserMenu role="doctor" />
          </div>
        </header>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          {children}
        </main>
      </div>

      {/* Global Search Modal */}
      <GlobalSearch />
    </div>
  );
}
