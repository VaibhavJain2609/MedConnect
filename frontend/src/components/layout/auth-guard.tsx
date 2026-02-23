"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { loginRedirect } from "@/lib/auth";

export function AuthGuard({
  children,
  requiredRole,
}: {
  children: React.ReactNode;
  requiredRole?: "patient" | "doctor" | "admin";
}) {
  const router = useRouter();
  const { user, loading, initialized, fetchUser } = useAuthStore();

  useEffect(() => {
    if (!initialized) return;
    if (!user && !loading) {
      loginRedirect();
      return;
    }
  }, [user, loading, initialized, fetchUser]);

  useEffect(() => {
    if (!loading && user && requiredRole && user.role !== requiredRole) {
      router.push(user.role === "doctor" ? "/doctor/dashboard" : "/patient/timeline");
    }
  }, [user, loading, requiredRole, router]);

  if (!initialized || loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
      </div>
    );
  }

  if (!user) return null;
  if (requiredRole && user.role !== requiredRole) return null;

  return <>{children}</>;
}
