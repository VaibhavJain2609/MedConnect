"use client";

import { useTranslations } from "next-intl";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { QuickActions } from "@/components/dashboard/quick-actions";
import { TodaySchedule } from "@/components/dashboard/today-schedule";
import { QueueWidget } from "@/components/dashboard/queue-widget";
import { PatientsWidget } from "@/components/dashboard/patients-widget";
import { useAuthStore } from "@/stores/auth-store";

export default function DoctorDashboard() {
  const t = useTranslations("doctorDashboard");
  const { user } = useAuthStore();

  const todayLabel = new Date().toLocaleDateString("en-IN", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: t("breadcrumb") }]} />

      <div>
        <h1 className="text-3xl font-bold text-dreams-textPrimary">{t("title")}</h1>
        <p className="text-dreams-textSecondary mt-1">
          {user?.full_name
            ? t("welcomeNamed", { name: user.full_name, date: todayLabel })
            : t("welcome", { date: todayLabel })}
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
