"use client";

import * as React from "react";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn } from "@/lib/utils";
import { LineChart } from "@/components/charts/line-chart";
import {
  BloodPressureIcon,
  HeartRateIcon,
  SPO2Icon,
  TemperatureIcon,
  RespiratoryRateIcon,
  WeightIcon,
} from "@/components/icons/vital-icons";

export interface VitalData {
  id: string;
  name: string;
  value: string;
  unit: string;
  status: "normal" | "warning" | "critical";
  trend?: "up" | "down" | "stable";
  trendValue?: string;
  lastUpdated: string;
  icon: React.ComponentType<{ className?: string }>;
  historicalData?: { date: string; value: number }[];
  normalRange?: { min: number; max: number };
}

export interface VitalsDisplayProps {
  vitals: VitalData[];
  onViewHistory?: (vitalId: string) => void;
  className?: string;
}

/**
 * VitalsDisplay Component
 *
 * Enhanced vital signs display with trends and interactive cards
 *
 * Features:
 * - Color-coded status indicators
 * - Trend arrows with percentage change
 * - Click to view historical data
 * - Mini line chart on hover
 * - Normal range indicators
 *
 * @example
 * <VitalsDisplay
 *   vitals={patientVitals}
 *   onViewHistory={(id) => console.log("View history for", id)}
 * />
 */
export const VitalsDisplay: React.FC<VitalsDisplayProps> = ({
  vitals,
  onViewHistory,
  className,
}) => {
  const [selectedVital, setSelectedVital] = React.useState<string | null>(null);

  const getStatusColor = (status: VitalData["status"]) => {
    switch (status) {
      case "normal":
        return "text-status-completed border-status-completed/20 bg-status-completed/5";
      case "warning":
        return "text-status-pending border-status-pending/20 bg-status-pending/5";
      case "critical":
        return "text-status-overdue border-status-overdue/20 bg-status-overdue/5";
      default:
        return "text-dreams-textSecondary border-dreams-border bg-white";
    }
  };

  const getStatusBadgeColor = (status: VitalData["status"]) => {
    switch (status) {
      case "normal":
        return "bg-status-completed/10 text-status-completed";
      case "warning":
        return "bg-status-pending/10 text-status-pending";
      case "critical":
        return "bg-status-overdue/10 text-status-overdue";
      default:
        return "bg-gray-100 text-gray-600";
    }
  };

  const getTrendIcon = (trend?: VitalData["trend"]) => {
    switch (trend) {
      case "up":
        return <TrendingUp className="h-3 w-3" />;
      case "down":
        return <TrendingDown className="h-3 w-3" />;
      case "stable":
        return <Minus className="h-3 w-3" />;
      default:
        return null;
    }
  };

  const getTrendColor = (trend?: VitalData["trend"]) => {
    switch (trend) {
      case "up":
        return "text-status-overdue";
      case "down":
        return "text-status-completed";
      case "stable":
        return "text-dreams-textSecondary";
      default:
        return "text-dreams-textSecondary";
    }
  };

  return (
    <div className={cn("space-y-6", className)}>
      {/* Vitals Grid */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {vitals.map((vital) => {
          const Icon = vital.icon;
          const isSelected = selectedVital === vital.id;

          return (
            <div
              key={vital.id}
              className={cn(
                "p-6 rounded-lg border-2 transition-all cursor-pointer hover:shadow-lg",
                getStatusColor(vital.status),
                isSelected && "ring-2 ring-dreams-blue ring-offset-2"
              )}
              onClick={() => {
                setSelectedVital(isSelected ? null : vital.id);
                if (onViewHistory && !isSelected) {
                  onViewHistory(vital.id);
                }
              }}
            >
              <div className="flex items-start justify-between mb-4">
                <div className="p-3 rounded-lg bg-dreams-lightBg">
                  <Icon className="h-6 w-6 text-dreams-blue" />
                </div>
                <div className="flex flex-col items-end gap-1">
                  <span
                    className={cn(
                      "text-xs font-medium px-2 py-1 rounded",
                      getStatusBadgeColor(vital.status)
                    )}
                  >
                    {vital.status.toUpperCase()}
                  </span>
                  {vital.trend && vital.trendValue && (
                    <div
                      className={cn(
                        "flex items-center gap-1 text-xs font-medium",
                        getTrendColor(vital.trend)
                      )}
                    >
                      {getTrendIcon(vital.trend)}
                      <span>{vital.trendValue}</span>
                    </div>
                  )}
                </div>
              </div>

              <h4 className="text-sm text-dreams-textSecondary mb-2">
                {vital.name}
              </h4>

              <div className="flex items-baseline gap-2 mb-2">
                <span className="text-3xl font-bold text-dreams-textPrimary">
                  {vital.value}
                </span>
                <span className="text-sm text-dreams-textSecondary">
                  {vital.unit}
                </span>
              </div>

              {vital.normalRange && (
                <p className="text-xs text-dreams-textSecondary mb-2">
                  Normal: {vital.normalRange.min}-{vital.normalRange.max}{" "}
                  {vital.unit}
                </p>
              )}

              <p className="text-xs text-dreams-textSecondary">
                Updated {vital.lastUpdated}
              </p>

              {/* Mini chart on hover/selected */}
              {isSelected && vital.historicalData && (
                <div className="mt-4 pt-4 border-t border-dreams-border">
                  <LineChart
                    data={vital.historicalData}
                    categories={[
                      {
                        key: "value",
                        label: vital.name,
                        color: "#4169E1",
                      },
                    ]}
                    index="date"
                    height={120}
                    showLegend={false}
                    showGrid={false}
                    showDots={true}
                    curved={true}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Historical Data View (Optional Full Chart) */}
      {selectedVital && (
        <div className="bg-white rounded-lg shadow-card p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xl font-bold text-dreams-textPrimary">
              {vitals.find((v) => v.id === selectedVital)?.name} - Historical
              Trends
            </h3>
            <button
              onClick={() => setSelectedVital(null)}
              className="text-sm text-dreams-blue hover:underline"
            >
              Close
            </button>
          </div>

          {vitals.find((v) => v.id === selectedVital)?.historicalData && (
            <LineChart
              data={
                vitals.find((v) => v.id === selectedVital)?.historicalData || []
              }
              categories={[
                {
                  key: "value",
                  label: vitals.find((v) => v.id === selectedVital)?.name || "",
                  color: "#4169E1",
                },
              ]}
              index="date"
              height={300}
              showLegend={true}
              showGrid={true}
              showDots={true}
              curved={true}
            />
          )}
        </div>
      )}
    </div>
  );
};

VitalsDisplay.displayName = "VitalsDisplay";
