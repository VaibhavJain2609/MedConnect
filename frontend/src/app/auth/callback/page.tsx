"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";

export default function AuthCallbackPage() {
  const router = useRouter();
  const { user, initialized } = useAuthStore();

  useEffect(() => {
    if (initialized) {
      if (user) {
        // Redirect based on user role
        if (user.role === "admin") {
          router.replace("/admin/dashboard");
        } else if (user.role === "doctor") {
          router.replace("/doctor/dashboard");
        } else {
          router.replace("/patient/timeline");
        }
      } else {
        router.replace("/");
      }
    }
  }, [initialized, user, router]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
    </div>
  );
}
