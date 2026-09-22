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
  Bell,
  FlaskConical,
  Pill,
  Receipt,
  Stethoscope,
  X,
  Ticket,
  SlidersHorizontal,
  Users,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { logout } from "@/lib/auth";
import { LanguageSwitcher } from "@/components/layout/language-switcher";

// Keys validated against messages/en.json — the source of truth for the
// "nav" namespace. Adding a label: add the key to en.json + hi.json, then
// reference it here (see docs/i18n.md).
type EnMessages = typeof import("../../../messages/en.json");
type NavLabelKey = Exclude<keyof EnMessages["nav"], "sections">;
type NavSectionKey = keyof EnMessages["nav"]["sections"];

interface PatientSidebarProps {
  isOpen: boolean;
  isMobileMenuOpen: boolean;
  onToggle: () => void;
  onMobileClose: () => void;
}

interface NavItem {
  href: string;
  labelKey: NavLabelKey;
  icon: any;
}

interface NavSection {
  labelKey: NavSectionKey;
  items: NavItem[];
}

const navSections: NavSection[] = [
  {
    labelKey: "main",
    items: [
      { href: "/patient/timeline", labelKey: "healthTimeline", icon: Activity },
      { href: "/patient/appointments", labelKey: "appointments", icon: Calendar },
      { href: "/patient/notifications", labelKey: "notifications", icon: Bell },
    ],
  },
  {
    labelKey: "health",
    items: [
      { href: "/patient/records", labelKey: "myRecords", icon: FileText },
      { href: "/patient/lab-results", labelKey: "labResults", icon: FlaskConical },
      { href: "/patient/medications", labelKey: "medications", icon: Pill },
      { href: "/patient/vitals", labelKey: "vitals", icon: HeartPulse },
      { href: "/patient/visits", labelKey: "visits", icon: Stethoscope },
      { href: "/patient/medical-history", labelKey: "medicalHistory", icon: ClipboardList },
      { href: "/patient/family", labelKey: "familyMembers", icon: Users },
    ],
  },
  {
    labelKey: "clinics",
    items: [
      { href: "/patient/clinics", labelKey: "myClinics", icon: Building2 },
      { href: "/patient/queue", labelKey: "queueStatus", icon: Users },
      { href: "/invite", labelKey: "joinAClinic", icon: Ticket },
    ],
  },
  {
    labelKey: "account",
    items: [
      { href: "/patient/billing", labelKey: "billing", icon: Receipt },
      { href: "/patient/preferences", labelKey: "preferences", icon: SlidersHorizontal },
      { href: "/patient/profile", labelKey: "myProfile", icon: User },
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
  const t = useTranslations("nav");
  const Icon = item.icon;
  const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
  const label = t(item.labelKey);

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
      title={!isOpen ? label : undefined}
      onClick={onMobileClose}
    >
      <Icon className="h-5 w-5 flex-shrink-0" />
      {isOpen && <span>{label}</span>}
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
  const t = useTranslations("nav");

  // Plain render function (not a component) — a component created inside
  // render gets a new identity each render, which remounts its subtree.
  const renderSidebarContent = ({ mobile = false }: { mobile?: boolean }) => (
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
        )}
        {mobile && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onMobileClose}
            className="text-gray-400 hover:text-white hover:bg-white/10 min-h-[44px] min-w-[44px]"
            aria-label={t("closeMenu")}
          >
            <X className="h-5 w-5" />
          </Button>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-6 p-4 overflow-y-auto">
        {navSections.map((section) => (
          <div key={section.labelKey}>
            {(isOpen || mobile) && (
              <h3 className="mb-2 px-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                {t(`sections.${section.labelKey}`)}
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

      {/* Language + Logout */}
      <div className="p-4 border-t border-gray-800 space-y-2">
        {(isOpen || mobile) && (
          <LanguageSwitcher className="px-1 pb-1" />
        )}
        <Button
          variant="ghost"
          className={cn(
            "w-full justify-start gap-3 text-red-400 hover:text-red-300 hover:bg-red-500/10",
            !isOpen && !mobile && "justify-center"
          )}
          onClick={logout}
        >
          <LogOut className="h-5 w-5" />
          {(isOpen || mobile) && <span>{t("logout")}</span>}
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
        {renderSidebarContent({})}
      </aside>

      {/* Mobile sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-64 bg-dreams-darkSidebar border-r border-gray-800 flex flex-col transform transition-transform md:hidden",
          isMobileMenuOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {renderSidebarContent({ mobile: true })}
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
