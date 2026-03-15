import { Settings } from "lucide-react";
import { Breadcrumb } from "@/components/ui/breadcrumb";

export default function AdminSettingsPage() {
  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: "Settings" }]} />

      <div>
        <h1 className="text-3xl font-bold text-dreams-textPrimary">Settings</h1>
        <p className="text-dreams-textSecondary mt-1">
          Platform configuration and system settings
        </p>
      </div>

      <div className="bg-white rounded-xl border border-dreams-border shadow-card p-12 flex flex-col items-center justify-center text-center">
        <div className="p-4 rounded-full bg-dreams-lightBg mb-4">
          <Settings className="h-10 w-10 text-dreams-textSecondary" />
        </div>
        <h2 className="text-xl font-semibold text-dreams-textPrimary mb-2">Coming Soon</h2>
        <p className="text-dreams-textSecondary max-w-sm">
          System settings are under development. Check back soon for configuration options
          including platform preferences, integrations, and access controls.
        </p>
      </div>
    </div>
  );
}
