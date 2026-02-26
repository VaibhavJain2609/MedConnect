"use client";

import { useQuery } from "@tanstack/react-query";
import { useState, useMemo } from "react";
import {
  getDashboardStats,
  getPatientTrend,
  getAppointmentTrend,
  getDoctorTrend,
  getTransactionTrend,
  getPatientStatistics,
  getAppointmentRequests,
  approveAppointmentRequest,
  rejectAppointmentRequest,
} from "@/lib/api/stats";
import { StatCard } from "@/components/dashboard/stat-card";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import {
  Users,
  Calendar,
  Stethoscope,
  DollarSign,
  Clock,
  Check,
  X,
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

  // Calculate date range params
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

  // Fetch dashboard stats
  const { data: stats, isLoading, error } = useQuery({
    queryKey: ["admin-stats", dateParams],
    queryFn: () => getDashboardStats(dateParams),
  });

  // Fetch trend data for sparklines
  const { data: patientTrend } = useQuery({
    queryKey: ["patient-trend", dateParams],
    queryFn: () => getPatientTrend(dateParams),
  });

  const { data: appointmentTrend } = useQuery({
    queryKey: ["appointment-trend", dateParams],
    queryFn: () => getAppointmentTrend(dateParams),
  });

  const { data: doctorTrend } = useQuery({
    queryKey: ["doctor-trend", dateParams],
    queryFn: () => getDoctorTrend(dateParams),
  });

  const { data: transactionTrend } = useQuery({
    queryKey: ["transaction-trend", dateParams],
    queryFn: () => getTransactionTrend(dateParams),
  });

  // Fetch appointment requests
  const { data: appointmentRequests } = useQuery({
    queryKey: ["appointment-requests"],
    queryFn: () => getAppointmentRequests(5),
  });

  // Fetch patient statistics for chart
  const { data: patientStatsData } = useQuery({
    queryKey: ["patient-stats", dateParams],
    queryFn: () => getPatientStatistics(dateParams),
  });

  // Transform patient stats for chart
  const patientStats = useMemo(() => {
    if (!patientStatsData) return [];

    return patientStatsData.map((stat) => ({
      month: new Date(stat.date).toLocaleDateString("en-US", { month: "short" }),
      new: stat.new_patients,
      existing: stat.returning_patients,
    }));
  }, [patientStatsData]);

  // Transform trend data for sparklines
  const patientSparkline = useMemo(
    () => patientTrend?.map((d) => d.value) || [],
    [patientTrend]
  );
  const appointmentSparkline = useMemo(
    () => appointmentTrend?.map((d) => d.value) || [],
    [appointmentTrend]
  );
  const doctorSparkline = useMemo(
    () => doctorTrend?.map((d) => d.value) || [],
    [doctorTrend]
  );
  const transactionSparkline = useMemo(
    () => transactionTrend?.map((d) => d.value) || [],
    [transactionTrend]
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
      {/* Breadcrumb */}
      <Breadcrumb items={[{ label: "Dashboard" }]} />

      {/* Header with date range selector */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-dreams-textPrimary">
            Dashboard
          </h1>
          <p className="text-dreams-textSecondary mt-1">
            Overview of your healthcare platform
          </p>
        </div>

        {/* Date range selector */}
        <div className="flex items-center gap-2">
          <select
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value)}
            className="h-10 px-4 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
          >
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="90d">Last 90 days</option>
            <option value="custom">Custom range</option>
          </select>
        </div>
      </div>

      {/* Stat Cards Grid - 4 columns */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="All Patients"
          value={stats?.total_patients || 0}
          trend={stats?.patient_trend}
          icon={Users}
          color="blue"
          sparklineData={patientSparkline}
        />
        <StatCard
          title="Appointments"
          value={stats?.total_appointments || 0}
          trend={stats?.appointment_trend}
          icon={Calendar}
          color="green"
          sparklineData={appointmentSparkline}
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
          title="Transactions"
          value={stats?.total_transactions || 0}
          trend={stats?.transaction_trend}
          icon={DollarSign}
          color="orange"
          sparklineData={transactionSparkline}
        />
      </div>

      {/* Widgets Grid - 2 columns */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Appointment Requests Widget */}
        <div className="bg-white rounded-lg shadow-card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-dreams-textPrimary">
              Appointment Requests
            </h2>
            <Badge variant="pending">
              {appointmentRequests?.length || 0} Pending
            </Badge>
          </div>

          <div className="space-y-4">
            {appointmentRequests && appointmentRequests.length > 0 ? (
              appointmentRequests.map((request) => (
                <div
                  key={request.id}
                  className="flex items-center gap-4 p-4 rounded-lg border border-dreams-border hover:bg-dreams-lightBg/50 transition-colors"
                >
                  <Avatar
                    src={request.patient_photo}
                    fallback={request.patient_name}
                    size="md"
                  />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-dreams-textPrimary truncate">
                      {request.patient_name}
                    </p>
                    <p className="text-sm text-dreams-textSecondary">
                      {request.doctor_name} • {request.department}
                    </p>
                    <p className="text-xs text-dreams-textSecondary mt-1">
                      <Clock className="inline h-3 w-3 mr-1" />
                      {request.requested_date} at {request.requested_time}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <button className="p-2 rounded-md bg-status-completed/10 text-status-completed hover:bg-status-completed/20 transition-colors">
                      <Check className="h-4 w-4" />
                    </button>
                    <button className="p-2 rounded-md bg-status-overdue/10 text-status-overdue hover:bg-status-overdue/20 transition-colors">
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              ))
            ) : (
              <p className="text-sm text-dreams-textSecondary py-8 text-center">
                No pending appointment requests
              </p>
            )}
          </div>
        </div>

        {/* Patient Statistics Chart */}
        <div className="bg-white rounded-lg shadow-card p-6">
          <h2 className="text-xl font-bold text-dreams-textPrimary mb-4">
            Patient Statistics
          </h2>

          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={patientStats}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
              <XAxis
                dataKey="month"
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
                dataKey="existing"
                fill="#10B981"
                name="Existing Patients"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
