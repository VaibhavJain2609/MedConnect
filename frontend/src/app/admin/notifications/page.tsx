import { Bell } from "lucide-react";
import { Breadcrumb } from "@/components/ui/breadcrumb";

export default function AdminNotificationsPage() {
  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: "Notifications" }]} />

      <div>
        <h1 className="text-3xl font-bold text-dreams-textPrimary">Notifications</h1>
        <p className="text-dreams-textSecondary mt-1">
          Manage platform-wide notifications and alerts
        </p>
      </div>

      <div className="bg-white rounded-xl border border-dreams-border shadow-card p-12 flex flex-col items-center justify-center text-center">
        <div className="p-4 rounded-full bg-dreams-lightBg mb-4">
          <Bell className="h-10 w-10 text-dreams-textSecondary" />
        </div>
        <h2 className="text-xl font-semibold text-dreams-textPrimary mb-2">Coming Soon</h2>
        <p className="text-dreams-textSecondary max-w-sm">
          Notification management is under development. Check back soon for the ability to
          configure and send platform-wide notifications.
        </p>
      </div>
    </div>
  );
}
