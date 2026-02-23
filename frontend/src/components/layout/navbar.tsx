"use client";

import Link from "next/link";
import { useAuthStore } from "@/stores/auth-store";
import { loginRedirect, signupRedirect, logout } from "@/lib/auth";

export function Navbar() {
  const { user } = useAuthStore();

  return (
    <nav className="border-b bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link href="/" className="text-xl font-bold text-primary-700">
          MedConnect
        </Link>

        <div className="flex items-center gap-4">
          {user ? (
            <>
              <span className="text-sm text-gray-600">
                {user.full_name}{" "}
                <span className="rounded bg-primary-100 px-2 py-0.5 text-xs font-medium text-primary-700">
                  {user.role}
                </span>
              </span>
              {user.role === "patient" && (
                <Link
                  href="/patient/timeline"
                  className="text-sm text-gray-600 hover:text-primary-700"
                >
                  Timeline
                </Link>
              )}
              {user.role === "doctor" && (
                <>
                  <Link
                    href="/doctor/dashboard"
                    className="text-sm text-gray-600 hover:text-primary-700"
                  >
                    Dashboard
                  </Link>
                  <Link
                    href="/doctor/records/new"
                    className="text-sm text-gray-600 hover:text-primary-700"
                  >
                    New Record
                  </Link>
                  <Link
                    href="/doctor/prescriptions/new"
                    className="text-sm text-gray-600 hover:text-primary-700"
                  >
                    New Rx
                  </Link>
                </>
              )}
              <button
                onClick={logout}
                className="text-sm text-red-600 hover:text-red-800"
              >
                Logout
              </button>
            </>
          ) : (
            <>
              <button
                onClick={loginRedirect}
                className="text-sm text-gray-600 hover:text-primary-700"
              >
                Login
              </button>
              <button
                onClick={signupRedirect}
                className="rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
              >
                Sign Up
              </button>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
