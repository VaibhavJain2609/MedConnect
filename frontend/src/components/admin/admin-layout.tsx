"use client";

import { useState } from "react";
import { AdminSidebar } from "./admin-sidebar";
import { Button } from "@/components/ui/button";
import { Avatar } from "@/components/ui/avatar";
import {
  Menu,
  LogOut,
  Search,
  Grid3x3,
  Globe,
  Bell,
  Settings,
  ChevronDown,
} from "lucide-react";
import { logout } from "@/lib/auth";
import { useAuthStore } from "@/stores/auth-store";

export function AdminLayout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const { user } = useAuthStore();

  return (
    <div className="flex h-screen overflow-hidden bg-dreams-lightBg">
      {/* Sidebar */}
      <AdminSidebar
        isOpen={sidebarOpen}
        isMobileMenuOpen={mobileMenuOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        onMobileClose={() => setMobileMenuOpen(false)}
      />

      {/* Main content area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top bar - Dreams EMR Style */}
        <header className="flex h-16 items-center justify-between border-b border-dreams-border bg-white px-4 md:px-6 shadow-sm">
          <div className="flex items-center gap-4 flex-1">
            {/* Mobile menu button */}
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden"
              onClick={() => setMobileMenuOpen(true)}
            >
              <Menu className="h-5 w-5" />
            </Button>

            {/* Global search */}
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search patients, doctors, appointments..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full h-10 pl-10 pr-4 rounded-lg border border-dreams-border bg-dreams-lightBg/50 text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue focus:border-transparent"
              />
            </div>
          </div>

          {/* Utility icons */}
          <div className="flex items-center gap-2">
            {/* Grid/Layout toggle */}
            <Button
              variant="ghost"
              size="icon"
              className="text-gray-600 hover:text-dreams-blue"
              title="Layout Settings"
            >
              <Grid3x3 className="h-5 w-5" />
            </Button>

            {/* Language selector */}
            <Button
              variant="ghost"
              size="icon"
              className="text-gray-600 hover:text-dreams-blue"
              title="Language"
            >
              <Globe className="h-5 w-5" />
            </Button>

            {/* Notifications */}
            <Button
              variant="ghost"
              size="icon"
              className="relative text-gray-600 hover:text-dreams-blue"
              title="Notifications"
            >
              <Bell className="h-5 w-5" />
              <span className="absolute top-1 right-1 h-2 w-2 bg-red-500 rounded-full" />
            </Button>

            {/* Settings */}
            <Button
              variant="ghost"
              size="icon"
              className="text-gray-600 hover:text-dreams-blue"
              title="Settings"
            >
              <Settings className="h-5 w-5" />
            </Button>

            {/* Divider */}
            <div className="h-8 w-px bg-gray-200 mx-2" />

            {/* User dropdown */}
            <button className="flex items-center gap-2 hover:bg-gray-50 rounded-lg px-2 py-1.5 transition-colors">
              <Avatar
                src={null}
                fallback={user?.full_name || "U"}
                size="sm"
              />
              <div className="hidden md:block text-left">
                <p className="text-sm font-medium text-gray-900">
                  {user?.full_name || "User"}
                </p>
                <p className="text-xs text-gray-500 capitalize">{user?.role}</p>
              </div>
              <ChevronDown className="h-4 w-4 text-gray-400" />
            </button>
          </div>
        </header>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
