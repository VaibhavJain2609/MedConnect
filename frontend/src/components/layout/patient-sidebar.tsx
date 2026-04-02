"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  Activity,
  FileText,
  ChevronLeft,
  LogOut,
  Heart,
  HeartPulse,
  User,
  ClipboardList,
  Building2,
  Calendar,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { logout } from "@/lib/auth";

interface PatientSidebarProps {
  isOpen: boolean;
  isMobileMenuOpen: boolean;
  onToggle: () => void;
  onMobileClose: () => void;
}

interface NavItem {
  href: string;
  label: string;
  icon: any;
}

interface NavSection {
  label: string;
  items: NavItem[];
}

const navSections: NavSection[] = [
  {
    label: "MAIN",
    items: [
      { href: "/patient/timeline", label: "Health Timeline", icon: Activity },
      { href: "/patient/appointments", label: "Appointments", icon: Calendar },
    ],
  },
  {
    label: "HEALTH",
    items: [
      { href: "/patient/records", label: "My Records", icon: FileText },
      { href: "/patient/vitals", label: "Vitals", icon: HeartPulse },
      { href: "/patient/medical-history", label: "Medical History", icon: ClipboardList },
    ],
  },
  {
    label: "CLINICS",
    items: [
      { href: "/patient/clinics", label: "My Clinics", icon: Building2 },
    ],
  },
  {
    label: "ACCOUNT",
    items: [
      { href: "/patient/profile", label: "My Profile", icon: User },
    ],
  },
];

function SidebarNavItem({
  item,
  isOpen,
  pathname,
  onMobileClose,
}: {
  item: NavItem;
  isOpen: boolean;
  pathname: string;
  onMobileClose?: () => void;
}) {
  const Icon = item.icon;
  const isActive = pathname === item.href || pathname.startsWith(item.href + "/");

  return (
    <Link
      href={item.href}
      className={cn(
        "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
        isActive
          ? "bg-dreams-blue text-white"
          : "text-gray-300 hover:bg-white/10",
        !isOpen && "justify-center"
      )}
      title={!isOpen ? item.label : undefined}
      onClick={onMobileClose}
    >
      <Icon className="h-5 w-5 flex-shrink-0" />
      {isOpen && <span>{item.label}</span>}
    </Link>
  );
}

export function PatientSidebar({
  isOpen,
  isMobileMenuOpen,
  onToggle,
  onMobileClose,
}: PatientSidebarProps) {
  const pathname = usePathname();

  const SidebarContent = ({ mobile = false }: { mobile?: boolean }) => (
    <>
      {/* Header */}
      <div className="flex h-16 items-center justify-between px-4 border-b border-gray-800">
        {(isOpen || mobile) && (
          <Link
            href="/patient/timeline"
            className="flex items-center gap-2 text-lg font-bold text-white"
          >
            <Heart className="h-5 w-5 text-red-400" />
            MedConnect
          </Link>
        )}
        {!mobile && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggle}
            className={cn(
              "text-gray-400 hover:text-white hover:bg-white/10",
              !isOpen && "mx-auto"
            )}
          >
            <ChevronLeft
              className={cn(
                "h-4 w-4 transition-transform",
                !isOpen && "rotate-180"
              )}
            />
          </Button>
        )}
        {mobile && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onMobileClose}
            className="text-gray-400 hover:text-white hover:bg-white/10 min-h-[44px] min-w-[44px]"
            aria-label="Close menu"
          >
            <X className="h-5 w-5" />
          </Button>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-6 p-4 overflow-y-auto">
        {navSections.map((section) => (
          <div key={section.label}>
            {(isOpen || mobile) && (
              <h3 className="mb-2 px-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                {section.label}
              </h3>
            )}
            <div className="space-y-1">
              {section.items.map((item) => (
                <SidebarNavItem
                  key={item.href}
                  item={item}
                  isOpen={mobile ? true : isOpen}
                  pathname={pathname}
                  onMobileClose={onMobileClose}
                />
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* Logout */}
      <div className="p-4 border-t border-gray-800">
        <Button
          variant="ghost"
          className={cn(
            "w-full justify-start gap-3 text-red-400 hover:text-red-300 hover:bg-red-500/10",
            !isOpen && !mobile && "justify-center"
          )}
          onClick={logout}
        >
          <LogOut className="h-5 w-5" />
          {(isOpen || mobile) && <span>Logout</span>}
        </Button>
      </div>
    </>
  );

  return (
    <>
      {/* Desktop sidebar */}
      <aside
        className={cn(
          "hidden md:flex flex-col bg-dreams-darkSidebar border-r border-gray-800 transition-all duration-300",
          isOpen ? "w-64" : "w-16"
        )}
      >
        <SidebarContent />
      </aside>

      {/* Mobile sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-64 bg-dreams-darkSidebar border-r border-gray-800 flex flex-col transform transition-transform md:hidden",
          isMobileMenuOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <SidebarContent mobile />
      </aside>

      {/* Mobile overlay */}
      {isMobileMenuOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={onMobileClose}
        />
      )}
    </>
  );
}
