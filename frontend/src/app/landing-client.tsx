"use client";

import { useRouter } from "next/navigation";
import { loginRedirect, signupRedirect, logout } from "@/lib/auth";
import { useAuthStore } from "@/stores/auth-store";

export function LandingNav() {
  const router = useRouter();
  const { user } = useAuthStore();

  const handleLogout = () => {
    logout();
  };

  if (user) {
    return (
      <div className="flex items-center gap-4">
        <span className="text-sm font-medium text-gray-700">
          {user.full_name}
        </span>
        <button
          onClick={handleLogout}
          className="rounded-lg px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100"
        >
          Logout
        </button>
      </div>
    );
  }

  return (
    <div className="flex gap-3">
      <button
        onClick={loginRedirect}
        className="rounded-lg px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100"
      >
        Login
      </button>
      <button
        onClick={signupRedirect}
        className="rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
      >
        Sign Up
      </button>
    </div>
  );
}

export function LandingCTA() {
  return (
    <div className="flex gap-4">
      <button
        onClick={signupRedirect}
        className="rounded-lg bg-primary-600 px-6 py-3 text-sm font-medium text-white hover:bg-primary-700"
      >
        I&apos;m a Patient
      </button>
      <button
        onClick={() => {
          sessionStorage.setItem("register_intent", "doctor");
          signupRedirect();
        }}
        className="rounded-lg border border-primary-600 px-6 py-3 text-sm font-medium text-primary-600 hover:bg-primary-50"
      >
        I&apos;m a Doctor
      </button>
    </div>
  );
}
