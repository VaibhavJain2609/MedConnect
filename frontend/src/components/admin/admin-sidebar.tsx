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
  Building2,
  CreditCard,
  TrendingUp,
  HeartPulse,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { logout } from "@/lib/auth";
import { LanguageSwitcher } from "@/components/layout/language-switcher";

// Keys validated against messages/en.json — the source of truth for the
// "nav" namespace (same convention as doctor-sidebar.tsx, see docs/i18n.md).
type EnMessages = typeof import("../../../messages/en.json");
type NavLabelKey = Exclude<keyof EnMessages["nav"], "sections">;
type NavSectionKey = keyof EnMessages["nav"]["sections"];

interface AdminSidebarProps {
  isOpen: boolean;
  isMobileMenuOpen: boolean;
  onToggle: () => void;
  onMobileClose: () => void;
}

interface NavItem {
  href?: string;
  labelKey: NavLabelKey;
  icon: any;
  children?: NavItem[];
}

interface NavSection {
  labelKey: NavSectionKey;
  items: NavItem[];
}

const navSections: NavSection[] = [
  {
    labelKey: "main",
    items: [
      { href: "/admin/dashboard", labelKey: "adminDashboard", icon: LayoutDashboard },
    ],
  },
  {
    labelKey: "healthCare",
    items: [
      { href: "/admin/patients", labelKey: "adminPatients", icon: Users },
      { href: "/admin/doctors", labelKey: "adminDoctors", icon: Stethoscope },
      { href: "/admin/appointments", labelKey: "appointments", icon: Calendar },
      { href: "/admin/billing", labelKey: "billing", icon: CreditCard },
      { href: "/admin/revenue", labelKey: "adminRevenue", icon: TrendingUp },
      { href: "/admin/visits", labelKey: "visits", icon: Activity },
      { href: "/admin/lab-results", labelKey: "labResults", icon: TestTube },
      {
        labelKey: "adminCatalog",
        icon: Pill,
        children: [
          { href: "/admin/medicines", labelKey: "adminMedicines", icon: Pill },
          { href: "/admin/salts", labelKey: "adminSalts", icon: Activity },
          { href: "/admin/manufacturers", labelKey: "adminManufacturers", icon: Building2 },
          { href: "/admin/medicines/import", labelKey: "adminBulkImport", icon: TrendingUp },
          { href: "/admin/medicines/new", labelKey: "adminAddMedicine", icon: Pill },
        ],
      },
    ],
  },
  {
    labelKey: "management",
    items: [
      { href: "/admin/users", labelKey: "adminUsers", icon: Users },
      { href: "/admin/clinics", labelKey: "adminClinics", icon: Building2 },
      { href: "/admin/notifications", labelKey: "notifications", icon: Bell },
      { href: "/admin/settings", labelKey: "adminSettings", icon: Settings },
    ],
  },
  {
    labelKey: "pages",
    items: [
      { href: "/admin/doctors/pending", labelKey: "adminDoctorVerification", icon: UserCheck },
      { href: "/admin/audit-logs", labelKey: "adminAuditLogs", icon: Shield },
      { href: "/admin/system", labelKey: "adminSystemHealth", icon: HeartPulse },
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
  const t = useTranslations("nav");
  const Icon = item.icon;
  const label = t(item.labelKey);
  const hasChildren = item.children && item.children.length > 0;
  const isActive = item.href === pathname;
  const childActive =
    hasChildren && item.children!.some((c) => c.href === pathname);
  const [isExpanded, setIsExpanded] = useState(childActive);

  if (hasChildren) {
    return (
      <div>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className={cn(
            "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
            childActive
              ? "bg-dreams-blue/20 text-white"
              : "text-gray-300 hover:bg-white/10",
            !isOpen && "justify-center"
          )}
        >
          <Icon className="h-5 w-5 flex-shrink-0" />
          {isOpen && (
            <>
              <span className="flex-1 text-left">{label}</span>
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
                key={child.href || child.labelKey}
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
      title={!isOpen ? label : undefined}
      onClick={onMobileClose}
    >
      <Icon className="h-5 w-5 flex-shrink-0" />
      {isOpen && <span>{label}</span>}
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
  const t = useTranslations("nav");

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
            aria-label={isOpen ? t("collapseSidebar") : t("expandSidebar")}
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
            <div key={section.labelKey}>
              {isOpen && (
                <h3 className="mb-2 px-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                  {t(`sections.${section.labelKey}`)}
                </h3>
              )}
              <div className="space-y-1">
                {section.items.map((item) => (
                  <SidebarNavItem
                    key={item.href || item.labelKey}
                    item={item}
                    isOpen={isOpen}
                    pathname={pathname}
                  />
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* Language + Logout */}
        <div className="p-4 border-t border-gray-800 space-y-2">
          {isOpen && <LanguageSwitcher className="px-1 pb-1" />}
          <Button
            variant="ghost"
            className={cn(
              "w-full justify-start gap-3 text-red-400 hover:text-red-300 hover:bg-red-500/10",
              !isOpen && "justify-center"
            )}
            onClick={logout}
          >
            <LogOut className="h-5 w-5" />
            {isOpen && <span>{t("logout")}</span>}
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
            aria-label={t("closeMenu")}
            className="text-gray-400 hover:text-white hover:bg-white/10"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-6 p-4 overflow-y-auto">
          {navSections.map((section) => (
            <div key={section.labelKey}>
              <h3 className="mb-2 px-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                {t(`sections.${section.labelKey}`)}
              </h3>
              <div className="space-y-1">
                {section.items.map((item) => (
                  <SidebarNavItem
                    key={item.href || item.labelKey}
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

        {/* Language + Logout */}
        <div className="p-4 border-t border-gray-800 space-y-2">
          <LanguageSwitcher className="px-1 pb-1" />
          <Button
            variant="ghost"
            className="w-full justify-start gap-3 text-red-400 hover:text-red-300 hover:bg-red-500/10"
            onClick={logout}
          >
            <LogOut className="h-5 w-5" />
            <span>{t("logout")}</span>
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
