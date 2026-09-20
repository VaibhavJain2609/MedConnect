"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import keycloak from "@/lib/keycloak";
import api from "@/lib/api";

export default function AuthCallbackPage() {
  const router = useRouter();
  const { user, initialized, fetchUser } = useAuthStore();
  const handledRef = useRef(false);

  useEffect(() => {
    if (!initialized || handledRef.current) return;

    async function handleCallback() {
      handledRef.current = true;

      if (!user) {
        router.replace("/");
        return;
      }

      const intent = sessionStorage.getItem("register_intent");

      if (intent === "doctor" && user.role !== "doctor") {
        try {
          await api.post("/api/v1/auth/set-role", { role: "doctor" });
          sessionStorage.removeItem("register_intent");
          // Force Keycloak to issue a new token with the doctor role
          await keycloak?.updateToken(-1);
          // Re-fetch user from backend with the refreshed token
          await fetchUser();
          router.replace("/doctor/onboarding");
        } catch (err) {
          // set-role now requires a clinic invite code — send the user to the
          // invite redemption page instead of silently landing as a patient.
          console.error("Doctor role requires an invite code:", err);
          sessionStorage.removeItem("register_intent");
          router.replace("/invite");
        }
        return;
      }

      sessionStorage.removeItem("register_intent");

      if (user.role === "admin") {
        router.replace("/admin/dashboard");
      } else if (user.role === "doctor") {
        router.replace("/doctor/dashboard");
      } else {
        router.replace("/patient/timeline");
      }
    }

    handleCallback();
  }, [initialized, user, router, fetchUser]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
    </div>
  );
}
