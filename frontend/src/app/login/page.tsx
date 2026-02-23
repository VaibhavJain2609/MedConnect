"use client";

import { useEffect } from "react";
import { loginRedirect } from "@/lib/auth";

export default function LoginPage() {
  useEffect(() => {
    loginRedirect();
  }, []);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
    </div>
  );
}
