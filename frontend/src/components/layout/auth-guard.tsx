"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ShieldOff } from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";

export function AuthGuard({
  children,
  requiredRole,
}: {
  children: React.ReactNode;
  requiredRole?: "patient" | "doctor" | "admin";
}) {
  const router = useRouter();
  const { user, loading, initialized } = useAuthStore();

  useEffect(() => {
    if (!initialized || loading) return;
    if (!user) {
      // Not authenticated — redirect to login page (not Keycloak directly)
      // This avoids redirect loops: the login page handles the Keycloak redirect
      router.push("/login");
    }
  }, [user, loading, initialized, router]);

  if (!initialized || loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
      </div>
    );
  }

  if (!user) return null;

  if (requiredRole && user.role !== requiredRole) {
    const backHref =
      user.role === "admin"
        ? "/admin/dashboard"
        : user.role === "doctor"
        ? "/doctor/dashboard"
        : "/patient/timeline";

    return (
      <div className="flex min-h-screen items-center justify-center bg-dreams-lightBg px-4">
        <div className="max-w-md w-full bg-white rounded-xl border border-dreams-border shadow-card p-10 text-center">
          <div className="flex items-center justify-center mb-6">
            <div className="h-16 w-16 rounded-full bg-red-50 flex items-center justify-center">
              <ShieldOff className="h-8 w-8 text-red-500" />
            </div>
          </div>
          <h1 className="text-2xl font-bold text-dreams-textPrimary mb-2">
            Access Denied
          </h1>
          <p className="text-dreams-textSecondary mb-1">
            You do not have permission to view this page.
          </p>
          <p className="text-sm text-dreams-textSecondary mb-8">
            This area requires the <span className="font-medium text-dreams-textPrimary">{requiredRole}</span> role.
            Your current role is <span className="font-medium text-dreams-textPrimary">{user.role}</span>.
          </p>
          <Link
            href={backHref}
            className="inline-flex items-center justify-center px-6 py-2.5 rounded-lg bg-dreams-blue text-white text-sm font-medium hover:bg-dreams-blue/90 transition-colors"
          >
            Go to my dashboard
          </Link>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
