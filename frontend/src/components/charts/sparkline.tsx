"use client";

import * as React from "react";
import {
  LineChart,
  Line,
  ResponsiveContainer,
  YAxis,
} from "recharts";

export interface SparklineProps {
  data: number[];
  color?: "blue" | "green" | "purple" | "orange" | "red";
  height?: number;
  strokeWidth?: number;
}

const colorMap = {
  blue: "#3B82F6",
  green: "#10B981",
  purple: "#8B5CF6",
  orange: "#F59E0B",
  red: "#EF4444",
};

/**
 * Sparkline Component
 *
 * Displays a mini line chart for showing trends in stat cards
 *
 * @example
 * <Sparkline data={[45, 52, 48, 55, 60, 58, 65]} color="blue" height={40} />
 */
export const Sparkline: React.FC<SparklineProps> = ({
  data,
  color = "blue",
  height = 40,
  strokeWidth = 2,
}) => {
  const chartData = data.map((value, index) => ({
    value,
    index,
  }));

  const strokeColor = colorMap[color];

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={chartData}>
        <YAxis domain={["dataMin", "dataMax"]} hide />
        <Line
          type="monotone"
          dataKey="value"
          stroke={strokeColor}
          strokeWidth={strokeWidth}
          dot={false}
          animationDuration={500}
        />
      </LineChart>
    </ResponsiveContainer>
  );
};

Sparkline.displayName = "Sparkline";
