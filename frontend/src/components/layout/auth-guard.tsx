"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ShieldOff } from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";
import { Spinner } from "@/components/ui/spinner";
import { getMyClinics } from "@/lib/api/clinics";

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

  // Non-doctor users holding an active clinic membership (e.g.
  // receptionists) are allowed into the doctor portal — the backend scopes
  // them to non-clinical surfaces via ClinicMembership.role, and the sidebar
  // hides clinical nav items. Hook must run unconditionally (above early
  // returns) — it is a no-op unless this guard protects the doctor portal
  // for a non-doctor user.
  const { data: myClinics, isFetched: clinicsFetched } = useQuery({
    queryKey: ["my-clinics-guard"],
    queryFn: getMyClinics,
    enabled: !!user && requiredRole === "doctor" && user.role !== "doctor",
    staleTime: 60_000,
    retry: false,
  });

  if (!initialized || loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!user) return null;

  const membershipBypass =
    requiredRole === "doctor" &&
    user.role !== "doctor" &&
    clinicsFetched &&
    (myClinics?.data?.length ?? 0) > 0;

  // While the membership probe is in flight, keep the spinner up rather than
  // flashing an access-denied screen at a legitimate receptionist.
  if (requiredRole === "doctor" && user.role !== "doctor" && !membershipBypass && !clinicsFetched) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (requiredRole && user.role !== requiredRole && !membershipBypass) {
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
