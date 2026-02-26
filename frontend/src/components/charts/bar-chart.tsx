"use client";

import * as React from "react";
import {
  BarChart as RechartsBarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  TooltipProps,
} from "recharts";
import { cn } from "@/lib/utils";

export interface BarChartProps {
  data: any[];
  categories: {
    key: string;
    label: string;
    color: string;
  }[];
  index: string;
  height?: number;
  showLegend?: boolean;
  showGrid?: boolean;
  className?: string;
}

const CustomTooltip = ({ active, payload, label }: TooltipProps<any, any>) => {
  if (!active || !payload) return null;

  return (
    <div className="bg-white border border-dreams-border rounded-lg shadow-lg p-3">
      <p className="font-medium text-dreams-textPrimary mb-2">{label}</p>
      {payload.map((entry: any, index: number) => (
        <div key={index} className="flex items-center gap-2 text-sm">
          <div
            className="w-3 h-3 rounded-sm"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-dreams-textSecondary">{entry.name}:</span>
          <span className="font-medium text-dreams-textPrimary">
            {entry.value}
          </span>
        </div>
      ))}
    </div>
  );
};

/**
 * BarChart Component
 *
 * Enhanced bar chart using Recharts with Dreams EMR styling
 *
 * @example
 * <BarChart
 *   data={monthlyData}
 *   categories={[
 *     { key: "new", label: "New Patients", color: "#4169E1" },
 *     { key: "existing", label: "Existing Patients", color: "#10B981" }
 *   ]}
 *   index="month"
 *   height={300}
 * />
 */
export const BarChart: React.FC<BarChartProps> = ({
  data,
  categories,
  index,
  height = 300,
  showLegend = true,
  showGrid = true,
  className,
}) => {
  return (
    <div className={cn("w-full", className)}>
      <ResponsiveContainer width="100%" height={height}>
        <RechartsBarChart data={data}>
          {showGrid && (
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
          )}
          <XAxis
            dataKey={index}
            tick={{ fill: "#6B7280", fontSize: 12 }}
            tickLine={{ stroke: "#E5E7EB" }}
          />
          <YAxis
            tick={{ fill: "#6B7280", fontSize: 12 }}
            tickLine={{ stroke: "#E5E7EB" }}
          />
          <Tooltip content={<CustomTooltip />} />
          {showLegend && <Legend />}
          {categories.map((category) => (
            <Bar
              key={category.key}
              dataKey={category.key}
              fill={category.color}
              name={category.label}
              radius={[4, 4, 0, 0]}
            />
          ))}
        </RechartsBarChart>
      </ResponsiveContainer>
    </div>
  );
};

BarChart.displayName = "BarChart";
