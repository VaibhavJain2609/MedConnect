"use client";

import { useQuery } from "@tanstack/react-query";
import { useState, useMemo } from "react";
import {
  getDashboardStats,
  getPatientTrend,
  getRecordTrend,
  getDoctorTrend,
  getPrescriptionTrend,
  getPatientStatistics,
  getAppointmentRequests,
} from "@/lib/api/stats";
import { StatCard } from "@/components/dashboard/stat-card";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import {
  Users,
  FileText,
  Stethoscope,
  ClipboardList,
  Clock,
  CheckCircle,
  AlertCircle,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";

export default function AdminDashboardPage() {
  const [dateRange, setDateRange] = useState("30d");

  const dateParams = useMemo(() => {
    const end_date = new Date().toISOString().split("T")[0];
    const start_date = new Date();

    switch (dateRange) {
      case "7d":
        start_date.setDate(start_date.getDate() - 7);
        break;
      case "30d":
        start_date.setDate(start_date.getDate() - 30);
        break;
      case "90d":
        start_date.setDate(start_date.getDate() - 90);
        break;
      default:
        start_date.setDate(start_date.getDate() - 30);
    }

    return {
      start_date: start_date.toISOString().split("T")[0],
      end_date,
    };
  }, [dateRange]);

  const { data: stats, isLoading, error } = useQuery({
    queryKey: ["admin-stats", dateParams],
    queryFn: () => getDashboardStats(dateParams),
  });

  const { data: patientTrend, error: patientTrendError } = useQuery({
    queryKey: ["patient-trend", dateParams],
    queryFn: () => getPatientTrend(dateParams),
  });

  const { data: recordTrend, error: recordTrendError } = useQuery({
    queryKey: ["record-trend", dateParams],
    queryFn: () => getRecordTrend(dateParams),
  });

  const { data: doctorTrend, error: doctorTrendError } = useQuery({
    queryKey: ["doctor-trend", dateParams],
    queryFn: () => getDoctorTrend(dateParams),
  });

  const { data: prescriptionTrend, error: prescriptionTrendError } = useQuery({
    queryKey: ["prescription-trend", dateParams],
    queryFn: () => getPrescriptionTrend(dateParams),
  });

  const { data: recentActivity, error: recentActivityError } = useQuery({
    queryKey: ["appointment-requests"],
    queryFn: () => getAppointmentRequests(5),
  });

  const { data: patientStatsData, error: patientStatsError } = useQuery({
    queryKey: ["patient-stats", dateParams],
    queryFn: () => getPatientStatistics(dateParams),
  });

  const patientStats = useMemo(() => {
    if (!patientStatsData) return [];
    return patientStatsData.map((stat) => ({
      date: new Date(stat.date).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      new: stat.new_patients,
      active: stat.returning_patients,
    }));
  }, [patientStatsData]);

  const patientSparkline = useMemo(
    () => patientTrendError ? [] : patientTrend?.map((d) => d.value) || [],
    [patientTrend, patientTrendError]
  );
  const recordSparkline = useMemo(
    () => recordTrendError ? [] : recordTrend?.map((d) => d.value) || [],
    [recordTrend, recordTrendError]
  );
  const doctorSparkline = useMemo(
    () => doctorTrendError ? [] : doctorTrend?.map((d) => d.value) || [],
    [doctorTrend, doctorTrendError]
  );
  const prescriptionSparkline = useMemo(
    () => prescriptionTrendError ? [] : prescriptionTrend?.map((d) => d.value) || [],
    [prescriptionTrend, prescriptionTrendError]
  );

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12 space-y-4">
        <p className="text-red-600 font-medium">Failed to load dashboard data</p>
        <p className="text-dreams-textSecondary text-sm">
          {error instanceof Error ? error.message : "An error occurred"}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: "Dashboard" }]} />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-dreams-textPrimary">
            Dashboard
          </h1>
          <p className="text-dreams-textSecondary mt-1">
            Overview of your healthcare platform
          </p>
        </div>

        <select
          value={dateRange}
          onChange={(e) => setDateRange(e.target.value)}
          className="h-10 px-4 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
        >
          <option value="7d">Last 7 days</option>
          <option value="30d">Last 30 days</option>
          <option value="90d">Last 90 days</option>
        </select>
      </div>

      {/* Stat Cards */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Patients"
          value={stats?.total_patients || 0}
          trend={stats?.patient_trend}
          icon={Users}
          color="blue"
          sparklineData={patientSparkline}
        />
        <StatCard
          title="Medical Records"
          value={stats?.total_records || 0}
          trend={stats?.record_trend}
          icon={FileText}
          color="green"
          sparklineData={recordSparkline}
        />
        <StatCard
          title="Total Doctors"
          value={stats?.total_doctors || 0}
          trend={stats?.doctor_trend}
          icon={Stethoscope}
          color="purple"
          sparklineData={doctorSparkline}
        />
        <StatCard
          title="Prescriptions"
          value={stats?.total_prescriptions || 0}
          trend={stats?.prescription_trend}
          icon={ClipboardList}
          color="orange"
          sparklineData={prescriptionSparkline}
        />
      </div>

      {/* Doctor Verification Summary */}
      {(stats?.unverified_doctors ?? 0) > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex items-center gap-3">
          <AlertCircle className="h-5 w-5 text-amber-600 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-sm font-medium text-amber-800">
              {stats?.unverified_doctors} doctor{(stats?.unverified_doctors ?? 0) > 1 ? "s" : ""} pending verification
            </p>
            <p className="text-xs text-amber-600 mt-0.5">
              {stats?.verified_doctors} of {stats?.total_doctors} doctors verified
            </p>
          </div>
          <a
            href="/admin/doctors/pending"
            className="text-xs font-medium text-amber-700 hover:text-amber-900 underline"
          >
            Review
          </a>
        </div>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        {/* Recent Activity */}
        <div className="bg-white rounded-lg shadow-card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-dreams-textPrimary">
              Recent Activity
            </h2>
            <Badge variant="pending">
              {recentActivity?.length || 0} Recent
            </Badge>
          </div>

          {recentActivityError ? (
            <p className="text-sm text-red-500 py-8 text-center">
              Failed to load recent activity
            </p>
          ) : (
            <div className="space-y-4">
              {recentActivity && recentActivity.length > 0 ? (
                recentActivity.map((item) => (
                  <div
                    key={item.id}
                    className="flex items-center gap-4 p-4 rounded-lg border border-dreams-border hover:bg-dreams-lightBg/50 transition-colors"
                  >
                    <Avatar
                      src={item.patient_photo}
                      fallback={item.patient_name}
                      size="md"
                    />
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-dreams-textPrimary truncate">
                        {item.patient_name}
                      </p>
                      <p className="text-sm text-dreams-textSecondary">
                        {item.department}
                      </p>
                      <p className="text-xs text-dreams-textSecondary mt-1">
                        <Clock className="inline h-3 w-3 mr-1" />
                        {item.requested_date} at {item.requested_time}
                      </p>
                    </div>
                    <CheckCircle className="h-5 w-5 text-status-completed flex-shrink-0" />
                  </div>
                ))
              ) : (
                <p className="text-sm text-dreams-textSecondary py-8 text-center">
                  No recent activity
                </p>
              )}
            </div>
          )}
        </div>

        {/* Patient Activity Chart */}
        <div className="bg-white rounded-lg shadow-card p-6">
          <h2 className="text-xl font-bold text-dreams-textPrimary mb-4">
            Patient Activity
          </h2>

          {patientStatsError ? (
            <div className="flex items-center justify-center h-[300px]">
              <p className="text-sm text-red-500">Failed to load patient activity data</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={patientStats}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis
                  dataKey="date"
                  tick={{ fill: "#6B7280", fontSize: 12 }}
                />
                <YAxis tick={{ fill: "#6B7280", fontSize: 12 }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "white",
                    border: "1px solid #E5E7EB",
                    borderRadius: "8px",
                  }}
                />
                <Legend />
                <Bar
                  dataKey="new"
                  fill="#4169E1"
                  name="New Patients"
                  radius={[4, 4, 0, 0]}
                />
                <Bar
                  dataKey="active"
                  fill="#10B981"
                  name="Active Patients"
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Quick Stats Row */}
      <div className="grid gap-4 md:grid-cols-3">
        <div className="bg-white rounded-lg shadow-card p-5">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-dreams-blue/10 flex items-center justify-center">
              <CheckCircle className="h-5 w-5 text-dreams-blue" />
            </div>
            <div>
              <p className="text-sm text-dreams-textSecondary">Verified Doctors</p>
              <p className="text-2xl font-bold text-dreams-textPrimary">
                {stats?.verified_doctors || 0}
              </p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow-card p-5">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-amber-100 flex items-center justify-center">
              <AlertCircle className="h-5 w-5 text-amber-600" />
            </div>
            <div>
              <p className="text-sm text-dreams-textSecondary">Pending Verification</p>
              <p className="text-2xl font-bold text-dreams-textPrimary">
                {stats?.unverified_doctors || 0}
              </p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow-card p-5">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-green-100 flex items-center justify-center">
              <FileText className="h-5 w-5 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-dreams-textSecondary">Total Medicines</p>
              <p className="text-2xl font-bold text-dreams-textPrimary">
                {(stats?.total_medicines || 0).toLocaleString()}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
