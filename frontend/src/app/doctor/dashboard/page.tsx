"use client";

import { Breadcrumb } from "@/components/ui/breadcrumb";
import { QuickActions } from "@/components/dashboard/quick-actions";
import { TodaySchedule } from "@/components/dashboard/today-schedule";
import { QueueWidget } from "@/components/dashboard/queue-widget";
import { PatientsWidget } from "@/components/dashboard/patients-widget";
import { useAuthStore } from "@/stores/auth-store";

export default function DoctorDashboard() {
  const { user } = useAuthStore();

  const todayLabel = new Date().toLocaleDateString("en-IN", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: "Dashboard" }]} />

      <div>
        <h1 className="text-3xl font-bold text-dreams-textPrimary">Dashboard</h1>
        <p className="text-dreams-textSecondary mt-1">
          Welcome back{user?.full_name ? `, Dr. ${user.full_name}` : ", Doctor"} —{" "}
          {todayLabel}
        </p>
      </div>

      <QuickActions />

      <div className="grid gap-6 lg:grid-cols-2">
        <TodaySchedule />
        <QueueWidget />
      </div>

      <PatientsWidget />
    </div>
  );
}
