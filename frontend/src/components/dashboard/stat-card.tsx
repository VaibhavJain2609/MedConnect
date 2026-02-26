"use client";

import * as React from "react";
import { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { Sparkline } from "@/components/charts/sparkline";

export interface StatCardProps {
  title: string;
  value: number | string;
  trend?: number;
  icon: LucideIcon;
  color?: "blue" | "green" | "purple" | "orange" | "red";
  sparklineData?: number[];
  className?: string;
}

const colorVariants = {
  blue: {
    bg: "bg-status-upcoming/10",
    text: "text-status-upcoming",
    icon: "bg-status-upcoming",
  },
  green: {
    bg: "bg-status-completed/10",
    text: "text-status-completed",
    icon: "bg-status-completed",
  },
  purple: {
    bg: "bg-status-inProgress/10",
    text: "text-status-inProgress",
    icon: "bg-status-inProgress",
  },
  orange: {
    bg: "bg-status-pending/10",
    text: "text-status-pending",
    icon: "bg-status-pending",
  },
  red: {
    bg: "bg-status-overdue/10",
    text: "text-status-overdue",
    icon: "bg-status-overdue",
  },
};

/**
 * StatCard Component
 *
 * Displays a metric card with icon, value, trend, and optional sparkline chart
 *
 * Features:
 * - Icon with colored background
 * - Large metric display
 * - Trend indicator (+/-%)
 * - Optional mini sparkline chart
 * - Color variants (blue, green, purple, orange, red)
 *
 * @example
 * <StatCard
 *   title="All Patients"
 *   value={108}
 *   trend={20}
 *   icon={Users}
 *   color="blue"
 *   sparklineData={[45, 52, 48, 55, 60, 58, 65]}
 * />
 */
export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  trend,
  icon: Icon,
  color = "blue",
  sparklineData,
  className,
}) => {
  const colors = colorVariants[color];

  return (
    <div
      className={cn(
        "bg-white rounded-lg shadow-card p-6 hover:shadow-card-hover transition-shadow",
        className
      )}
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <p className="text-sm text-dreams-textSecondary font-medium mb-1">
            {title}
          </p>
          <div className="flex items-baseline gap-2">
            <h3 className="text-3xl font-bold text-dreams-textPrimary">
              {typeof value === "number" ? value.toLocaleString() : value}
            </h3>
            {trend !== undefined && (
              <span
                className={cn(
                  "text-sm font-medium",
                  trend >= 0 ? "text-status-completed" : "text-status-overdue"
                )}
              >
                {trend >= 0 ? "+" : ""}
                {trend}%
              </span>
            )}
          </div>
        </div>
        <div
          className={cn(
            "flex items-center justify-center h-12 w-12 rounded-lg",
            colors.icon
          )}
        >
          <Icon className="h-6 w-6 text-white" />
        </div>
      </div>

      {sparklineData && sparklineData.length > 0 && (
        <div className="mt-4">
          <Sparkline data={sparklineData} color={color} height={40} />
        </div>
      )}
    </div>
  );
};

StatCard.displayName = "StatCard";
