import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface StatCardProps {
  title: string;
  value: string | number;
  description?: string;
  icon?: LucideIcon;
  trend?: {
    value: number;
    label: string;
    direction: "up" | "down";
  };
  variant?: "default" | "success" | "warning" | "danger";
}

const variantStyles = {
  default: "text-primary-600 bg-primary-50",
  success: "text-green-600 bg-green-50",
  warning: "text-amber-600 bg-amber-50",
  danger: "text-red-600 bg-red-50",
};

export function StatCard({
  title,
  value,
  description,
  icon: Icon,
  trend,
  variant = "default",
}: StatCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-gray-600">
          {title}
        </CardTitle>
        {Icon && (
          <div className={cn("p-2 rounded-lg", variantStyles[variant])}>
            <Icon className="h-4 w-4" />
          </div>
        )}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold text-gray-900">{value}</div>
        {description && (
          <p className="text-xs text-gray-500 mt-1">{description}</p>
        )}
        {trend && (
          <div className="flex items-center gap-1 mt-2 text-xs">
            <span className={cn(trend.direction === "up" ? "text-green-600" : "text-red-600")}>
              {trend.direction === "up" ? "↑" : "↓"} {trend.value}%
            </span>
            <span className="text-gray-500">{trend.label}</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
