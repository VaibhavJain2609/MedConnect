"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { Breadcrumb } from "@/components/ui/breadcrumb";

const LANGUAGE_OPTIONS = [
  { value: "en", label: "English" },
  { value: "hi", label: "Hindi" },
  { value: "mr", label: "Marathi" },
  { value: "ta", label: "Tamil" },
  { value: "te", label: "Telugu" },
  { value: "bn", label: "Bengali" },
  { value: "gu", label: "Gujarati" },
  { value: "kn", label: "Kannada" },
  { value: "ml", label: "Malayalam" },
  { value: "pa", label: "Punjabi" },
];

export default function PatientProfilePage() {
  const queryClient = useQueryClient();
  const [saved, setSaved] = useState(false);

  const { data: profile, isLoading } = useQuery({
    queryKey: ["patient-profile"],
    queryFn: async () => {
      const res = await api.get("/api/v1/patients/profile");
      return res.data;
    },
  });

  const [form, setForm] = useState({
    phone: "",
    language_pref: "en",
    emergency_contact_name: "",
    emergency_contact_phone: "",
  });

  // Sync form when profile loads
  useEffect(() => {
    if (profile) {
      setForm({
        phone: profile.phone ?? "",
        language_pref: profile.language_pref ?? "en",
        emergency_contact_name: profile.emergency_contact_name ?? "",
        emergency_contact_phone: profile.emergency_contact_phone ?? "",
      });
    }
  }, [profile]);

  const mutation = useMutation({
    mutationFn: async (data: typeof form) => {
      const payload: Record<string, string | null> = {};
      if (data.phone !== (profile?.phone ?? "")) payload.phone = data.phone || null;
      if (data.language_pref !== profile?.language_pref) payload.language_pref = data.language_pref;
      if (data.emergency_contact_name !== (profile?.emergency_contact_name ?? ""))
        payload.emergency_contact_name = data.emergency_contact_name || null;
      if (data.emergency_contact_phone !== (profile?.emergency_contact_phone ?? ""))
        payload.emergency_contact_phone = data.emergency_contact_phone || null;
      const res = await api.put("/api/v1/patients/profile", payload);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["patient-profile"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate(form);
  };

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-dreams-blue/20 border-t-dreams-blue" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: "My Profile" }]} />

      <div>
        <h1 className="text-3xl font-bold text-dreams-textPrimary">My Profile</h1>
        <p className="text-dreams-textSecondary mt-1">Manage your personal and contact information</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6 max-w-2xl">
        {/* Read-only info */}
        <div className="bg-white rounded-lg shadow-card p-6 space-y-4">
          <h2 className="text-lg font-semibold text-dreams-textPrimary border-b border-dreams-border pb-3">
            Account Information
          </h2>
          <div className="space-y-1">
            <label className="text-sm font-medium text-dreams-textSecondary">Full Name</label>
            <p className="text-dreams-textPrimary">{profile?.full_name}</p>
            <p className="text-xs text-dreams-textSecondary/60">Managed by your account provider</p>
          </div>
          <div className="space-y-1">
            <label className="text-sm font-medium text-dreams-textSecondary">Email</label>
            <p className="text-dreams-textPrimary">{profile?.email ?? "—"}</p>
            <p className="text-xs text-dreams-textSecondary/60">Managed by your account provider</p>
          </div>
        </div>

        {/* Editable fields */}
        <div className="bg-white rounded-lg shadow-card p-6 space-y-4">
          <h2 className="text-lg font-semibold text-dreams-textPrimary border-b border-dreams-border pb-3">
            Contact Details
          </h2>

          <div className="space-y-2">
            <label className="text-sm font-medium text-dreams-textPrimary" htmlFor="phone">
              Phone Number
            </label>
            <input
              id="phone"
              type="tel"
              value={form.phone}
              onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
              placeholder="+91 98765 43210"
              className="w-full h-10 rounded-lg border border-dreams-border px-3 py-2 text-sm bg-white focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-dreams-textPrimary" htmlFor="language_pref">
              Preferred Language
            </label>
            <select
              id="language_pref"
              value={form.language_pref}
              onChange={(e) => setForm((f) => ({ ...f, language_pref: e.target.value }))}
              className="w-full h-10 rounded-lg border border-dreams-border px-3 py-2 text-sm bg-white focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
            >
              {LANGUAGE_OPTIONS.map((l) => (
                <option key={l.value} value={l.value}>
                  {l.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-card p-6 space-y-4">
          <h2 className="text-lg font-semibold text-dreams-textPrimary border-b border-dreams-border pb-3">
            Emergency Contact
          </h2>

          <div className="space-y-2">
            <label className="text-sm font-medium text-dreams-textPrimary" htmlFor="ec_name">
              Contact Name
            </label>
            <input
              id="ec_name"
              type="text"
              value={form.emergency_contact_name}
              onChange={(e) => setForm((f) => ({ ...f, emergency_contact_name: e.target.value }))}
              placeholder="e.g. Priya Sharma"
              className="w-full h-10 rounded-lg border border-dreams-border px-3 py-2 text-sm bg-white focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-dreams-textPrimary" htmlFor="ec_phone">
              Contact Phone
            </label>
            <input
              id="ec_phone"
              type="tel"
              value={form.emergency_contact_phone}
              onChange={(e) => setForm((f) => ({ ...f, emergency_contact_phone: e.target.value }))}
              placeholder="+91 98765 43210"
              className="w-full h-10 rounded-lg border border-dreams-border px-3 py-2 text-sm bg-white focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
            />
          </div>
        </div>

        <div className="flex items-center gap-4">
          <button
            type="submit"
            disabled={mutation.isPending}
            className="h-10 px-6 rounded-lg bg-dreams-blue text-white text-sm font-medium hover:bg-dreams-blue/90 disabled:opacity-60 transition-colors"
          >
            {mutation.isPending ? "Saving..." : "Save Changes"}
          </button>
          {saved && (
            <p className="text-sm text-green-600 font-medium">Profile updated successfully.</p>
          )}
          {mutation.isError && (
            <p className="text-sm text-red-600">Failed to save. Please try again.</p>
          )}
        </div>
      </form>
    </div>
  );
}
