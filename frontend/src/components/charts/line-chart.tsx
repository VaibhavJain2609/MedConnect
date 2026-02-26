"use client";

import * as React from "react";
import {
  LineChart as RechartsLineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  TooltipProps,
} from "recharts";
import { cn } from "@/lib/utils";

export interface LineChartProps {
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
  showDots?: boolean;
  curved?: boolean;
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
            className="w-3 h-3 rounded-full"
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
 * LineChart Component
 *
 * Enhanced line chart using Recharts with Dreams EMR styling
 *
 * @example
 * <LineChart
 *   data={vitalsTrends}
 *   categories={[
 *     { key: "systolic", label: "Systolic BP", color: "#4169E1" },
 *     { key: "diastolic", label: "Diastolic BP", color: "#10B981" }
 *   ]}
 *   index="date"
 *   height={300}
 *   curved={true}
 * />
 */
export const LineChart: React.FC<LineChartProps> = ({
  data,
  categories,
  index,
  height = 300,
  showLegend = true,
  showGrid = true,
  showDots = true,
  curved = false,
  className,
}) => {
  return (
    <div className={cn("w-full", className)}>
      <ResponsiveContainer width="100%" height={height}>
        <RechartsLineChart data={data}>
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
            <Line
              key={category.key}
              type={curved ? "monotone" : "linear"}
              dataKey={category.key}
              stroke={category.color}
              strokeWidth={2}
              name={category.label}
              dot={showDots ? { fill: category.color, r: 4 } : false}
              activeDot={{ r: 6 }}
            />
          ))}
        </RechartsLineChart>
      </ResponsiveContainer>
    </div>
  );
};

LineChart.displayName = "LineChart";
