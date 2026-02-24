"use client";

import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { StatCard } from "@/components/admin/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Users, Pill, UserCheck, FileText } from "lucide-react";

export default function AdminDashboardPage() {
  // Future: Replace with actual API call to /api/v1/admin/stats (MD-34 backend)
  const { data, isLoading } = useQuery({
    queryKey: ["admin-stats"],
    queryFn: async () => {
      // Placeholder - will be replaced with actual endpoint in MD-34
      return {
        total_users: 1234,
        total_medicines: 52483,
        pending_verifications: 8,
        audit_logs_today: 142,
      };
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
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-600 mt-1">
          Overview of your healthcare platform
        </p>
      </div>

      {/* Summary statistics */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Users"
          value={data?.total_users.toLocaleString() || "0"}
          description="Patients and doctors"
          icon={Users}
          variant="default"
        />
        <StatCard
          title="Medicines"
          value={data?.total_medicines.toLocaleString() || "0"}
          description="Active in database"
          icon={Pill}
          variant="success"
        />
        <StatCard
          title="Pending Verifications"
          value={data?.pending_verifications || 0}
          description="Doctors awaiting approval"
          icon={UserCheck}
          variant="warning"
        />
        <StatCard
          title="Audit Logs Today"
          value={data?.audit_logs_today || 0}
          description="Admin actions logged"
          icon={FileText}
          variant="default"
        />
      </div>

      {/* Recent activity placeholder */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent Users</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-gray-500">
              User list will be implemented in MD-54
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Pending Verifications</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-gray-500">
              Verification queue will be implemented in MD-64
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
