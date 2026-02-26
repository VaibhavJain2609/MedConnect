"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import api from "@/lib/api";
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

  // Fetch dashboard stats
  const { data: stats, isLoading } = useQuery({
    queryKey: ["admin-stats", dateRange],
    queryFn: async () => {
      // TODO: Replace with actual API call to /api/v1/admin/stats
      // For now, return mock data
      return {
        total_patients: 108,
        patient_trend: 20,
        patient_sparkline: [45, 52, 48, 55, 60, 58, 65],
        total_appointments: 42,
        appointment_trend: 12,
        appointment_sparkline: [20, 25, 22, 28, 30, 35, 42],
        total_doctors: 24,
        doctor_trend: 8,
        doctor_sparkline: [18, 19, 20, 21, 22, 23, 24],
        total_transactions: 156,
        transaction_trend: 15,
        transaction_sparkline: [100, 110, 120, 130, 140, 150, 156],
      };
    },
  });

  // Fetch appointment requests
  const { data: appointmentRequests } = useQuery({
    queryKey: ["appointment-requests"],
    queryFn: async () => {
      // TODO: Replace with actual API call to /api/v1/admin/appointment-requests
      return [
        {
          id: "1",
          patient_name: "John Doe",
          patient_photo: null,
          doctor_name: "Dr. Smith",
          department: "Cardiology",
          date: "2026-02-27",
          time: "10:00 AM",
          status: "pending",
        },
        {
          id: "2",
          patient_name: "Jane Smith",
          patient_photo: null,
          doctor_name: "Dr. Johnson",
          department: "Neurology",
          date: "2026-02-27",
          time: "2:30 PM",
          status: "pending",
        },
        {
          id: "3",
          patient_name: "Mike Wilson",
          patient_photo: null,
          doctor_name: "Dr. Brown",
          department: "Orthopedics",
          date: "2026-02-28",
          time: "11:00 AM",
          status: "pending",
        },
      ];
    },
  });

  // Fetch patient statistics for chart
  const { data: patientStats } = useQuery({
    queryKey: ["patient-stats", dateRange],
    queryFn: async () => {
      // TODO: Replace with actual API call to /api/v1/admin/stats/patient-trends
      return [
        { month: "Jan", new: 12, existing: 45 },
        { month: "Feb", new: 18, existing: 52 },
        { month: "Mar", new: 15, existing: 58 },
        { month: "Apr", new: 22, existing: 65 },
        { month: "May", new: 20, existing: 72 },
        { month: "Jun", new: 25, existing: 80 },
      ];
    },
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
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
          sparklineData={stats?.patient_sparkline}
        />
        <StatCard
          title="Appointments"
          value={stats?.total_appointments || 0}
          trend={stats?.appointment_trend}
          icon={Calendar}
          color="green"
          sparklineData={stats?.appointment_sparkline}
        />
        <StatCard
          title="Total Doctors"
          value={stats?.total_doctors || 0}
          trend={stats?.doctor_trend}
          icon={Stethoscope}
          color="purple"
          sparklineData={stats?.doctor_sparkline}
        />
        <StatCard
          title="Transactions"
          value={stats?.total_transactions || 0}
          trend={stats?.transaction_trend}
          icon={DollarSign}
          color="orange"
          sparklineData={stats?.transaction_sparkline}
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
                      {request.date} at {request.time}
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
