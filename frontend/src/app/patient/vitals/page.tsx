"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { AlertTriangle, Plus, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import {
  VITAL_META,
  VITAL_TYPES,
  createVital,
  getMyVitals,
  isVitalAbnormal,
  type VitalType,
} from "@/lib/api/vitals";
import { cn } from "@/lib/utils";

function formatDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "2-digit",
  });
}

function formatDateTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function TrendIndicator({ current, previous }: { current: number; previous?: number }) {
  if (!previous) return <Minus className="h-4 w-4 text-dreams-textSecondary" />;
  const diff = current - previous;
  if (Math.abs(diff) < 0.01) return <Minus className="h-4 w-4 text-dreams-textSecondary" />;
  if (diff > 0) return <TrendingUp className="h-4 w-4 text-red-500" />;
  return <TrendingDown className="h-4 w-4 text-green-500" />;
}

interface AddVitalFormProps {
  selectedType: VitalType;
  onClose: () => void;
  onSuccess: () => void;
}

function AddVitalForm({ selectedType, onClose, onSuccess }: AddVitalFormProps) {
  const meta = VITAL_META[selectedType];
  const [value, setValue] = useState("");
  const [unit, setUnit] = useState(meta.unit);
  const [notes, setNotes] = useState("");
  const [recordedAt, setRecordedAt] = useState(
    new Date().toISOString().slice(0, 16)
  );
  const [error, setError] = useState("");
  const [criticalWarning, setCriticalWarning] = useState("");

  const mutation = useMutation({
    mutationFn: createVital,
    onSuccess: (data) => {
      onSuccess();
      if (data.abnormal_flag) {
        setCriticalWarning(
          `Critical reading detected for ${meta.label}. Your doctor has been notified.`
        );
        // Keep modal open briefly to show warning, then close
        setTimeout(onClose, 3000);
      } else {
        onClose();
      }
    },
    onError: () => {
      setError("Failed to save reading. Please try again.");
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const numValue = parseFloat(value);
    if (isNaN(numValue)) {
      setError("Please enter a valid number.");
      return;
    }
    setError("");
    mutation.mutate({
      vital_type: selectedType,
      value: numValue,
      unit,
      recorded_at: new Date(recordedAt).toISOString(),
      notes: notes || undefined,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-dreams-textPrimary mb-1">
          {meta.label} value
        </label>
        <div className="flex gap-2">
          <input
            type="number"
            step="0.01"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={`e.g., 120`}
            className="flex-1 border border-dreams-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
            required
            autoFocus
          />
          <input
            type="text"
            value={unit}
            onChange={(e) => setUnit(e.target.value)}
            className="w-16 sm:w-24 border border-dreams-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
          />
        </div>
        <p className="text-xs text-dreams-textSecondary mt-1">
          Normal range: {meta.normalRange}
        </p>
      </div>
      <div>
        <label className="block text-sm font-medium text-dreams-textPrimary mb-1">
          Date & Time
        </label>
        <input
          type="datetime-local"
          value={recordedAt}
          onChange={(e) => setRecordedAt(e.target.value)}
          className="w-full border border-dreams-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-dreams-textPrimary mb-1">
          Notes (optional)
        </label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          placeholder="e.g., after exercise, fasting"
          className="w-full border border-dreams-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue resize-none"
        />
      </div>
      {error && <p className="text-sm text-red-500">{error}</p>}
      {criticalWarning && (
        <div className="flex items-start gap-2 rounded-lg border border-red-300 bg-red-50 p-3">
          <AlertTriangle className="h-4 w-4 text-red-500 mt-0.5 shrink-0" />
          <p className="text-sm text-red-700">{criticalWarning}</p>
        </div>
      )}
      <div className="flex gap-2 justify-end">
        <button
          type="button"
          onClick={onClose}
          className="px-4 py-2 text-sm border border-dreams-border rounded-lg hover:bg-dreams-lightBg transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={mutation.isPending}
          className="px-4 py-2 text-sm bg-dreams-blue text-white rounded-lg hover:bg-dreams-blue/90 transition-colors disabled:opacity-50"
        >
          {mutation.isPending ? "Saving..." : "Save Reading"}
        </button>
      </div>
    </form>
  );
}

export default function VitalsPage() {
  const [selectedType, setSelectedType] = useState<VitalType>("bp_systolic");
  const [days, setDays] = useState(30);
  const [showAddForm, setShowAddForm] = useState(false);
  const queryClient = useQueryClient();

  const meta = VITAL_META[selectedType];

  const { data, isLoading } = useQuery({
    queryKey: ["patient-vitals", selectedType, days],
    queryFn: () => getMyVitals({ type: selectedType, days, limit: 200 }),
  });

  const vitals = data?.data || [];
  // Chart data ordered chronologically (oldest first)
  const chartData = [...vitals]
    .reverse()
    .slice(-30)
    .map((v) => ({
      date: formatDate(v.recorded_at),
      value: Number(v.value),
    }));

  // Last 10 readings for table
  const tableData = vitals.slice(0, 10);

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: "Patient Portal", href: "/patient/timeline" },
          { label: "Vitals" },
        ]}
      />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-dreams-textPrimary">My Vitals</h1>
          <p className="text-dreams-textSecondary text-sm mt-1">
            Track your health metrics over time
          </p>
        </div>
        <button
          onClick={() => setShowAddForm(true)}
          className="flex items-center gap-2 px-4 py-2 bg-dreams-blue text-white rounded-lg hover:bg-dreams-blue/90 transition-colors text-sm font-medium"
        >
          <Plus className="h-4 w-4" />
          Add Reading
        </button>
      </div>

      {/* Add Reading Modal */}
      {showAddForm && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-4 sm:p-6">
            <h2 className="text-lg font-bold text-dreams-textPrimary mb-4">
              Add {meta.label} Reading
            </h2>
            <AddVitalForm
              selectedType={selectedType}
              onClose={() => setShowAddForm(false)}
              onSuccess={() =>
                queryClient.invalidateQueries({ queryKey: ["patient-vitals"] })
              }
            />
          </div>
        </div>
      )}

      {/* Vital Type Selector */}
      <div className="bg-white rounded-xl shadow-card border border-dreams-border p-4">
        <div className="flex flex-wrap gap-2">
          {VITAL_TYPES.map((type) => (
            <button
              key={type}
              onClick={() => setSelectedType(type)}
              className={cn(
                "px-3 py-1.5 text-sm rounded-lg font-medium transition-colors",
                selectedType === type
                  ? "bg-dreams-blue text-white"
                  : "bg-dreams-lightBg text-dreams-textSecondary hover:text-dreams-textPrimary"
              )}
            >
              {VITAL_META[type].label}
            </button>
          ))}
        </div>
      </div>

      {/* Chart */}
      <div className="bg-white rounded-xl shadow-card border border-dreams-border p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-semibold text-dreams-textPrimary">
              {meta.label}
            </h2>
            <p className="text-sm text-dreams-textSecondary">
              Normal range: {meta.normalRange}
            </p>
          </div>
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="text-sm border border-dreams-border rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-dreams-blue"
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </div>

        {isLoading ? (
          <div className="h-48 flex items-center justify-center text-dreams-textSecondary">
            Loading...
          </div>
        ) : chartData.length === 0 ? (
          <div className="h-48 flex items-center justify-center text-dreams-textSecondary">
            No readings recorded for this period.
          </div>
        ) : (
          <div className="h-48 sm:h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11, fill: "#6B7280" }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: "#6B7280" }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  contentStyle={{
                    border: "1px solid #E5E7EB",
                    borderRadius: "8px",
                    fontSize: "12px",
                  }}
                  formatter={(value: number) => [
                    `${value} ${meta.unit}`,
                    meta.label,
                  ]}
                />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke={meta.color}
                  strokeWidth={2}
                  dot={{ fill: meta.color, r: 3 }}
                  activeDot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Last 10 Readings Table */}
      <div className="bg-white rounded-xl shadow-card border border-dreams-border p-6">
        <h2 className="text-lg font-semibold text-dreams-textPrimary mb-4">
          Recent Readings
        </h2>
        {tableData.length === 0 ? (
          <p className="text-dreams-textSecondary text-sm">
            No readings found. Add your first reading above.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-dreams-border">
                  <th className="text-left py-2 pr-4 font-medium text-dreams-textSecondary">
                    Date & Time
                  </th>
                  <th className="text-left py-2 pr-4 font-medium text-dreams-textSecondary">
                    Value
                  </th>
                  <th className="text-left py-2 pr-4 font-medium text-dreams-textSecondary">
                    Trend
                  </th>
                  <th className="text-left py-2 font-medium text-dreams-textSecondary">
                    Notes
                  </th>
                </tr>
              </thead>
              <tbody>
                {tableData.map((vital, idx) => {
                  const next = tableData[idx + 1];
                  const abnormal =
                    vital.abnormal_flag ||
                    isVitalAbnormal(vital.vital_type as VitalType, Number(vital.value));
                  return (
                    <tr
                      key={vital.id}
                      className={cn(
                        "border-b border-dreams-border/50 hover:bg-dreams-lightBg/50",
                        abnormal && "bg-red-50"
                      )}
                    >
                      <td className="py-2.5 pr-4 text-dreams-textPrimary">
                        {formatDateTime(vital.recorded_at)}
                      </td>
                      <td className="py-2.5 pr-4">
                        <div className="flex items-center gap-2">
                          <span className={cn(
                            "font-semibold",
                            abnormal ? "text-red-600" : "text-dreams-textPrimary"
                          )}>
                            {vital.value} {vital.unit}
                          </span>
                          {abnormal && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
                              <AlertTriangle className="h-3 w-3" />
                              Critical
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-2.5 pr-4">
                        <TrendIndicator
                          current={vital.value}
                          previous={next?.value}
                        />
                      </td>
                      <td className="py-2.5 text-dreams-textSecondary">
                        {vital.notes || "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
