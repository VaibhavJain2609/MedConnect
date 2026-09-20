"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { PatientSidebar } from "./patient-sidebar";
import { Button } from "@/components/ui/button";
import { GlobalSearch, GlobalSearchTrigger } from "@/components/ui/global-search";
import { NotificationCenter } from "@/components/layout/notification-center";
import { UserMenu } from "@/components/layout/user-menu";
import {
  Menu,
  Settings,
} from "lucide-react";

export function PatientLayout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const router = useRouter();

  return (
    <div className="flex h-screen overflow-hidden bg-dreams-lightBg">
      {/* Sidebar */}
      <PatientSidebar
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
              onClick={() => router.push("/patient/notifications")}
            >
              <Settings className="h-5 w-5" />
            </Button>

            {/* Divider */}
            <div className="h-8 w-px bg-gray-200 mx-2" />

            {/* User dropdown */}
            <UserMenu role="patient" />
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
