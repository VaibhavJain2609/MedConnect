import * as React from "react";
import Link from "next/link";
import { ChevronRight, Home } from "lucide-react";
import { cn } from "@/lib/utils";

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

export interface BreadcrumbProps {
  items: BreadcrumbItem[];
  className?: string;
}

/**
 * Breadcrumb Component
 *
 * Displays navigation breadcrumbs with Home > Section > Page format
 *
 * @example
 * <Breadcrumb
 *   items={[
 *     { label: "Patients", href: "/admin/patients" },
 *     { label: "John Doe" }
 *   ]}
 * />
 */
export const Breadcrumb: React.FC<BreadcrumbProps> = ({
  items,
  className,
}) => {
  return (
    <nav className={cn("flex items-center space-x-2 text-sm", className)}>
      <Link
        href="/"
        className="text-dreams-textSecondary hover:text-dreams-blue transition-colors"
      >
        <Home className="h-4 w-4" />
      </Link>

      {items.map((item, index) => (
        <React.Fragment key={index}>
          <ChevronRight className="h-4 w-4 text-gray-400" />
          {item.href ? (
            <Link
              href={item.href}
              className="text-dreams-textSecondary hover:text-dreams-blue transition-colors"
            >
              {item.label}
            </Link>
          ) : (
            <span className="text-dreams-textPrimary font-medium">
              {item.label}
            </span>
          )}
        </React.Fragment>
      ))}
    </nav>
  );
};

Breadcrumb.displayName = "Breadcrumb";
