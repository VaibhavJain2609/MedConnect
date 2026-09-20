"use client";

import * as React from "react";
import Link from "next/link";
import { Avatar } from "@/components/ui/avatar";
import { ChevronDown, User, Bell, LogOut } from "lucide-react";
import { logout } from "@/lib/auth";
import { useAuthStore } from "@/stores/auth-store";

/**
 * UserMenu — avatar dropdown in portal headers.
 *
 * Replaces the previously dead avatar "button" with a real menu:
 * Profile, Notifications, Logout. Role-aware destinations.
 */
export function UserMenu({ role }: { role: "doctor" | "patient" }) {
  const { user } = useAuthStore();
  const [open, setOpen] = React.useState(false);
  const menuRef = React.useRef<HTMLDivElement>(null);

  const profileHref = role === "doctor" ? "/doctor/clinic" : "/patient/profile";
  const profileLabel = role === "doctor" ? "My Clinic" : "My Profile";
  const notificationsHref = `/${role}/notifications`;

  // Close on outside click / Escape
  React.useEffect(() => {
    if (!open) return;
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 hover:bg-gray-50 rounded-lg px-2 py-1.5 transition-colors"
        aria-label="Account menu"
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <Avatar src={null} fallback={user?.full_name || "U"} size="sm" />
        <div className="hidden md:block text-left">
          <p className="text-sm font-medium text-gray-900">
            {user?.full_name || (role === "doctor" ? "Doctor" : "Patient")}
          </p>
          <p className="text-xs text-gray-500 capitalize">{user?.role}</p>
        </div>
        <ChevronDown
          className={`h-4 w-4 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 mt-2 w-48 rounded-lg border border-dreams-border bg-white py-1 shadow-lg z-50"
        >
          <Link
            href={profileHref}
            role="menuitem"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 px-4 py-2 text-sm text-dreams-textPrimary hover:bg-dreams-lightBg transition-colors"
          >
            <User className="h-4 w-4 text-dreams-textSecondary" />
            {profileLabel}
          </Link>
          <Link
            href={notificationsHref}
            role="menuitem"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 px-4 py-2 text-sm text-dreams-textPrimary hover:bg-dreams-lightBg transition-colors"
          >
            <Bell className="h-4 w-4 text-dreams-textSecondary" />
            Notifications
          </Link>
          <button
            role="menuitem"
            onClick={() => {
              setOpen(false);
              logout();
            }}
            className="flex w-full items-center gap-2 px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
          >
            <LogOut className="h-4 w-4" />
            Logout
          </button>
        </div>
      )}
    </div>
  );
}
