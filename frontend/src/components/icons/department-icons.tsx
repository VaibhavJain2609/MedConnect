import * as React from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export interface DepartmentBadgeProps {
  department: string;
  className?: string;
}

const departmentColors: Record<
  string,
  { bg: string; text: string; icon?: string }
> = {
  cardiology: {
    bg: "bg-red-100",
    text: "text-red-700",
    icon: "❤️",
  },
  neurology: {
    bg: "bg-purple-100",
    text: "text-purple-700",
    icon: "🧠",
  },
  orthopedics: {
    bg: "bg-blue-100",
    text: "text-blue-700",
    icon: "🦴",
  },
  pediatrics: {
    bg: "bg-pink-100",
    text: "text-pink-700",
    icon: "👶",
  },
  dermatology: {
    bg: "bg-orange-100",
    text: "text-orange-700",
    icon: "🔬",
  },
  ophthalmology: {
    bg: "bg-cyan-100",
    text: "text-cyan-700",
    icon: "👁️",
  },
  ent: {
    bg: "bg-teal-100",
    text: "text-teal-700",
    icon: "👂",
  },
  dentistry: {
    bg: "bg-indigo-100",
    text: "text-indigo-700",
    icon: "🦷",
  },
  gynecology: {
    bg: "bg-rose-100",
    text: "text-rose-700",
    icon: "🤰",
  },
  psychiatry: {
    bg: "bg-violet-100",
    text: "text-violet-700",
    icon: "🧘",
  },
  radiology: {
    bg: "bg-gray-100",
    text: "text-gray-700",
    icon: "📷",
  },
  emergency: {
    bg: "bg-red-200",
    text: "text-red-800",
    icon: "🚨",
  },
  general: {
    bg: "bg-green-100",
    text: "text-green-700",
    icon: "🏥",
  },
};

/**
 * DepartmentBadge Component
 *
 * Displays a colored badge with icon for different medical departments
 *
 * @example
 * <DepartmentBadge department="cardiology" />
 * <DepartmentBadge department="neurology" />
 */
export const DepartmentBadge: React.FC<DepartmentBadgeProps> = ({
  department,
  className,
}) => {
  const normalizedDept = department.toLowerCase().replace(/\s+/g, "");
  const colors =
    departmentColors[normalizedDept] || departmentColors["general"];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium",
        colors.bg,
        colors.text,
        className
      )}
    >
      {colors.icon && <span>{colors.icon}</span>}
      <span className="capitalize">{department}</span>
    </span>
  );
};

/**
 * Get department color scheme
 */
export const getDepartmentColor = (department: string) => {
  const normalizedDept = department.toLowerCase().replace(/\s+/g, "");
  return departmentColors[normalizedDept] || departmentColors["general"];
};
