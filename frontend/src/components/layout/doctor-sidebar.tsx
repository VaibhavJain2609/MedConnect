"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  FileText,
  Pill,
  FilePlus,
  Users,
  ChevronLeft,
  LogOut,
  Stethoscope,
  Building2,
  UserPlus,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { logout } from "@/lib/auth";

interface DoctorSidebarProps {
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
      { href: "/doctor/dashboard", label: "Dashboard", icon: LayoutDashboard },
    ],
  },
  {
    label: "CLINICAL",
    items: [
      { href: "/doctor/prescriptions", label: "My Prescriptions", icon: Pill },
      { href: "/doctor/clinic", label: "My Clinic", icon: Building2 },
      { href: "/doctor/patients/link", label: "Link Patient", icon: UserPlus },
    ],
  },
  {
    label: "ACTIONS",
    items: [
      { href: "/doctor/prescriptions/new", label: "New Prescription", icon: FilePlus },
      { href: "/doctor/records/new", label: "New Record", icon: FileText },
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
  // Exact match for action pages to avoid highlighting "new" when on list page
  const isActive =
    pathname === item.href ||
    (item.href !== "/doctor/prescriptions/new" &&
      item.href !== "/doctor/records/new" &&
      pathname.startsWith(item.href + "/"));

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

export function DoctorSidebar({
  isOpen,
  isMobileMenuOpen,
  onToggle,
  onMobileClose,
}: DoctorSidebarProps) {
  const pathname = usePathname();

  const SidebarContent = ({ mobile = false }: { mobile?: boolean }) => (
    <>
      {/* Header */}
      <div className="flex h-16 items-center justify-between px-4 border-b border-gray-800">
        {(isOpen || mobile) && (
          <Link
            href="/doctor/dashboard"
            className="flex items-center gap-2 text-lg font-bold text-white"
          >
            <Stethoscope className="h-5 w-5 text-blue-400" />
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
            className="text-gray-400 hover:text-white hover:bg-white/10"
          >
            <ChevronLeft className="h-4 w-4" />
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
