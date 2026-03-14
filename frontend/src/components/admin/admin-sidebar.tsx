"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Pill,
  Users,
  UserCheck,
  FileText,
  Settings,
  ChevronLeft,
  ChevronDown,
  ChevronRight,
  LogOut,
  Activity,
  Calendar,
  Stethoscope,
  TestTube,
  Bell,
  Shield,
  Layers,
  Building2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { logout } from "@/lib/auth";

interface AdminSidebarProps {
  isOpen: boolean;
  isMobileMenuOpen: boolean;
  onToggle: () => void;
  onMobileClose: () => void;
}

interface NavItem {
  href?: string;
  label: string;
  icon: any;
  children?: NavItem[];
}

interface NavSection {
  label: string;
  items: NavItem[];
}

const navSections: NavSection[] = [
  {
    label: "MAIN",
    items: [
      { href: "/admin/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/admin/applications", label: "Applications", icon: Layers },
    ],
  },
  {
    label: "HEALTH CARE",
    items: [
      { href: "/admin/patients", label: "Patients", icon: Users },
      { href: "/admin/doctors", label: "Doctors", icon: Stethoscope },
      {
        label: "Appointments",
        icon: Calendar,
        children: [
          { href: "/admin/appointments", label: "All Appointments", icon: Calendar },
          { href: "/admin/appointments/consultation", label: "Consultation", icon: Activity },
        ],
      },
      { href: "/admin/visits", label: "Visits", icon: Activity },
      {
        label: "Laboratory",
        icon: TestTube,
        children: [
          { href: "/admin/lab-results", label: "Lab Results", icon: TestTube },
          { href: "/admin/medical-results", label: "Medical Results", icon: FileText },
        ],
      },
      { href: "/admin/medicines", label: "Pharmacy", icon: Pill },
    ],
  },
  {
    label: "MANAGEMENT",
    items: [
      { href: "/admin/users", label: "Users", icon: Users },
      { href: "/admin/clinics", label: "Clinics", icon: Building2 },
      { href: "/admin/notifications", label: "Notifications", icon: Bell },
      { href: "/admin/settings", label: "Settings", icon: Settings },
    ],
  },
  {
    label: "PAGES",
    items: [
      { href: "/admin/doctors/pending", label: "Doctor Verification", icon: UserCheck },
      { href: "/admin/audit-logs", label: "Audit Logs", icon: Shield },
    ],
  },
];

function SidebarNavItem({
  item,
  isOpen,
  pathname,
  onMobileClose,
  depth = 0,
}: {
  item: NavItem;
  isOpen: boolean;
  pathname: string;
  onMobileClose?: () => void;
  depth?: number;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const Icon = item.icon;
  const hasChildren = item.children && item.children.length > 0;
  const isActive = item.href === pathname;

  if (hasChildren) {
    return (
      <div>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className={cn(
            "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
            "text-gray-300 hover:bg-white/10",
            !isOpen && "justify-center"
          )}
        >
          <Icon className="h-5 w-5 flex-shrink-0" />
          {isOpen && (
            <>
              <span className="flex-1 text-left">{item.label}</span>
              {isExpanded ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </>
          )}
        </button>
        {isOpen && isExpanded && (
          <div className="ml-6 mt-1 space-y-1">
            {item.children!.map((child) => (
              <SidebarNavItem
                key={child.href || child.label}
                item={child}
                isOpen={isOpen}
                pathname={pathname}
                onMobileClose={onMobileClose}
                depth={depth + 1}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <Link
      href={item.href!}
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

export function AdminSidebar({
  isOpen,
  isMobileMenuOpen,
  onToggle,
  onMobileClose,
}: AdminSidebarProps) {
  const pathname = usePathname();

  return (
    <>
      {/* Desktop sidebar */}
      <aside
        className={cn(
          "hidden md:flex flex-col bg-dreams-darkSidebar border-r border-gray-800 transition-all duration-300",
          isOpen ? "w-64" : "w-16"
        )}
      >
        {/* Header */}
        <div className="flex h-16 items-center justify-between px-4 border-b border-gray-800">
          {isOpen && (
            <Link
              href="/admin/dashboard"
              className="text-lg font-bold text-white"
            >
              MedConnect
            </Link>
          )}
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
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-6 p-4 overflow-y-auto">
          {navSections.map((section) => (
            <div key={section.label}>
              {isOpen && (
                <h3 className="mb-2 px-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                  {section.label}
                </h3>
              )}
              <div className="space-y-1">
                {section.items.map((item) => (
                  <SidebarNavItem
                    key={item.href || item.label}
                    item={item}
                    isOpen={isOpen}
                    pathname={pathname}
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
              !isOpen && "justify-center"
            )}
            onClick={logout}
          >
            <LogOut className="h-5 w-5" />
            {isOpen && <span>Logout</span>}
          </Button>
        </div>
      </aside>

      {/* Mobile sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-64 bg-dreams-darkSidebar border-r border-gray-800 transform transition-transform md:hidden",
          isMobileMenuOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Header */}
        <div className="flex h-16 items-center justify-between px-4 border-b border-gray-800">
          <Link
            href="/admin/dashboard"
            className="text-lg font-bold text-white"
          >
            MedConnect
          </Link>
          <Button
            variant="ghost"
            size="icon"
            onClick={onMobileClose}
            className="text-gray-400 hover:text-white hover:bg-white/10"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-6 p-4 overflow-y-auto">
          {navSections.map((section) => (
            <div key={section.label}>
              <h3 className="mb-2 px-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                {section.label}
              </h3>
              <div className="space-y-1">
                {section.items.map((item) => (
                  <SidebarNavItem
                    key={item.href || item.label}
                    item={item}
                    isOpen={true}
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
            className="w-full justify-start gap-3 text-red-400 hover:text-red-300 hover:bg-red-500/10"
            onClick={logout}
          >
            <LogOut className="h-5 w-5" />
            <span>Logout</span>
          </Button>
        </div>
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
