"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Ticket } from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";
import { redeemInvite } from "@/lib/api/clinics";
import api from "@/lib/api";
import { Spinner } from "@/components/ui/spinner";

/**
 * Standalone invite redemption — reachable by any authenticated user.
 *
 * Doctor invites elevate the account role first (POST /auth/set-role gated by
 * the invite code) and then redeem the invite for clinic membership.
 * Receptionist invites just create the membership — the account keeps its
 * role and the clinic membership scopes portal access.
 */
function InviteForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, initialized, fetchUser } = useAuthStore();
  const [code, setCode] = useState(searchParams.get("code") ?? "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (initialized && !user) router.replace("/login");
  }, [initialized, user, router]);

  if (!initialized || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-dreams-lightBg">
        <Spinner size="lg" />
      </div>
    );
  }

  const errMessage = (err: unknown): string => {
    const ax = err as {
      userMessage?: string;
      response?: { data?: { detail?: { error?: { message?: string } } | { error?: { message?: string } } } };
    };
    const detail = ax?.response?.data?.detail;
    return (
      ax?.userMessage ??
      (typeof detail === "object" ? detail?.error?.message : undefined) ??
      "Could not redeem this invite code"
    );
  };

  const handleRedeem = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim()) return;
    setLoading(true);
    setError(null);
    setSuccess(null);
    const cleanCode = code.trim().toUpperCase();
    try {
      let res;
      try {
        res = await redeemInvite(cleanCode);
      } catch (err) {
        // A 403 on redeem means the invite is a doctor invite and this account
        // isn't a doctor yet — elevate the role with the invite code first.
        const status = (err as { response?: { status?: number } })?.response?.status;
        if (status !== 403) throw err;
        await api.post("/api/v1/auth/set-role", { role: "doctor", invite_code: cleanCode });
        res = await redeemInvite(cleanCode);
      }
      await fetchUser(); // refresh role/clinic state
      setSuccess(`You've joined the clinic as ${res.role}. Redirecting…`);
      router.push(res.role === "doctor" ? "/doctor/onboarding" : "/doctor/queue");
    } catch (err) {
      setError(errMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-dreams-lightBg px-4">
      <div className="w-full max-w-md rounded-xl border border-dreams-border bg-white p-10 shadow-card">
        <div className="mb-6 flex items-center justify-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-dreams-blue/10">
            <Ticket className="h-8 w-8 text-dreams-blue" />
          </div>
        </div>
        <h1 className="mb-2 text-center text-2xl font-bold text-dreams-textPrimary">
          Join a Clinic
        </h1>
        <p className="mb-8 text-center text-sm text-dreams-textSecondary">
          Enter the invite code shared by your clinic to join as a doctor or
          receptionist.
        </p>

        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}
        {success && (
          <div className="mb-4 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
            {success}
          </div>
        )}

        <form onSubmit={handleRedeem} className="space-y-4">
          <input
            type="text"
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            placeholder="INVITE CODE"
            maxLength={24}
            autoFocus
            className="w-full rounded-lg border border-dreams-border px-4 py-3 text-center font-mono text-lg tracking-widest text-dreams-textPrimary placeholder:text-dreams-textSecondary/60 focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
          />
          <button
            type="submit"
            disabled={loading || !code.trim()}
            className="w-full rounded-lg bg-dreams-blue px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-dreams-blue/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? "Joining…" : "Redeem Invite"}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-dreams-textSecondary">
          Don't have a code? Ask your clinic administrator to create one under{" "}
          <span className="font-medium">Doctor portal → Staff &amp; Invites</span>.
        </p>
      </div>
    </div>
  );
}

export default function InvitePage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-dreams-lightBg">
          <Spinner size="lg" />
        </div>
      }
    >
      <InviteForm />
    </Suspense>
  );
}
