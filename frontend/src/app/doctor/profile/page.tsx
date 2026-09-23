"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import api from "@/lib/api";
import { FileUpload } from "@/components/ui/file-upload";

// ── Types ─────────────────────────────────────────────────────────────────

interface DoctorProfile {
  id: string;
  user_id: string;
  specialization: string | null;
  license_number: string | null;
  facility_name: string | null;
  facility_city: string | null;
  qualifications: string | null;
  registration_number: string | null;
  signature_url: string | null;
  verified: boolean;
}

const getProfile = () =>
  api.get<DoctorProfile>("/api/v1/doctors/profile").then((r) => r.data);
const saveProfile = (d: object) =>
  api.put<DoctorProfile>("/api/v1/doctors/profile", d).then((r) => r.data);

const inputCls =
  "w-full h-10 rounded-lg border border-dreams-border px-3 py-2 text-sm bg-white focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20";

export default function DoctorProfilePage() {
  const queryClient = useQueryClient();
  const [saved, setSaved] = useState(false);
  const [uploading, setUploading] = useState(false);

  const { data: profile, isLoading } = useQuery({
    queryKey: ["doctor-profile"],
    queryFn: getProfile,
  });

  const [form, setForm] = useState({
    specialization: "",
    qualifications: "",
    registration_number: "",
    license_number: "",
    facility_name: "",
    facility_city: "",
    signature_url: null as string | null,
  });

  // Sync form when the profile loads / refetches (adjusted during render).
  const [prevProfile, setPrevProfile] = useState(profile);
  if (profile !== prevProfile) {
    setPrevProfile(profile);
    if (profile) {
      setForm({
        specialization: profile.specialization ?? "",
        qualifications: profile.qualifications ?? "",
        registration_number: profile.registration_number ?? "",
        license_number: profile.license_number ?? "",
        facility_name: profile.facility_name ?? "",
        facility_city: profile.facility_city ?? "",
        signature_url: profile.signature_url ?? null,
      });
    }
  }

  const mutation = useMutation({
    mutationFn: saveProfile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["doctor-profile"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate({
      specialization: form.specialization || null,
      qualifications: form.qualifications || null,
      registration_number: form.registration_number || null,
      license_number: form.license_number || null,
      facility_name: form.facility_name || null,
      facility_city: form.facility_city || null,
      signature_url: form.signature_url,
    });
  };

  if (isLoading || !profile) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="h-8 w-8 animate-spin text-dreams-blue" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-dreams-textPrimary">My Profile</h1>
        <p className="text-dreams-textSecondary mt-1">
          Credentials shown on your prescriptions — keep them current for NMC compliance.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6 max-w-2xl">
        <div className="bg-white rounded-lg shadow-card p-6 space-y-4">
          <h2 className="text-lg font-semibold text-dreams-textPrimary border-b border-dreams-border pb-3">
            Professional Details
          </h2>

          <div className="space-y-2">
            <label className="text-sm font-medium text-dreams-textPrimary" htmlFor="specialization">
              Specialization
            </label>
            <input
              id="specialization"
              type="text"
              value={form.specialization}
              onChange={(e) => setForm((f) => ({ ...f, specialization: e.target.value }))}
              placeholder="General Physician"
              className={inputCls}
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-dreams-textPrimary" htmlFor="qualifications">
              Qualifications
            </label>
            <input
              id="qualifications"
              type="text"
              value={form.qualifications}
              onChange={(e) => setForm((f) => ({ ...f, qualifications: e.target.value }))}
              placeholder="MBBS, MD (Medicine)"
              className={inputCls}
            />
            <p className="text-xs text-dreams-textSecondary/70">
              Printed under your name on prescription PDFs.
            </p>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-dreams-textPrimary" htmlFor="registration_number">
              Registration Number (NMC / State Medical Council)
            </label>
            <input
              id="registration_number"
              type="text"
              value={form.registration_number}
              onChange={(e) => setForm((f) => ({ ...f, registration_number: e.target.value }))}
              placeholder="MMC-2011-04567"
              maxLength={50}
              className={inputCls}
            />
            <p className="text-xs text-dreams-textSecondary/70">
              Printed as &quot;Reg. No.&quot; on prescriptions.
            </p>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-dreams-textPrimary" htmlFor="license_number">
              License Number
            </label>
            <input
              id="license_number"
              type="text"
              value={form.license_number}
              onChange={(e) => setForm((f) => ({ ...f, license_number: e.target.value }))}
              placeholder="MH-12345"
              className={inputCls}
            />
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-card p-6 space-y-4">
          <h2 className="text-lg font-semibold text-dreams-textPrimary border-b border-dreams-border pb-3">
            Facility
          </h2>

          <div className="space-y-2">
            <label className="text-sm font-medium text-dreams-textPrimary" htmlFor="facility_name">
              Facility Name
            </label>
            <input
              id="facility_name"
              type="text"
              value={form.facility_name}
              onChange={(e) => setForm((f) => ({ ...f, facility_name: e.target.value }))}
              placeholder="City Health Clinic"
              className={inputCls}
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-dreams-textPrimary" htmlFor="facility_city">
              City
            </label>
            <input
              id="facility_city"
              type="text"
              value={form.facility_city}
              onChange={(e) => setForm((f) => ({ ...f, facility_city: e.target.value }))}
              placeholder="Mumbai"
              className={inputCls}
            />
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-card p-6 space-y-4">
          <h2 className="text-lg font-semibold text-dreams-textPrimary border-b border-dreams-border pb-3">
            Signature
          </h2>
          <FileUpload
            label="Signature Image"
            hint="JPG or PNG — printed on prescription PDFs"
            accept=".jpg,.jpeg,.png"
            allowedTypes={["image/jpeg", "image/png"]}
            maxSizeMb={5}
            initialFileName="Signature on file"
            initialObjectKey={profile.signature_url}
            onUploaded={(key) => setForm((f) => ({ ...f, signature_url: key }))}
            onUploadingChange={setUploading}
          />
        </div>

        <div className="flex items-center gap-4">
          <button
            type="submit"
            disabled={mutation.isPending || uploading}
            className="h-10 px-6 rounded-lg bg-dreams-blue text-white text-sm font-medium hover:bg-dreams-blue/90 disabled:opacity-60 transition-colors"
          >
            {mutation.isPending ? "Saving…" : "Save Changes"}
          </button>
          {saved && <p className="text-sm text-green-600 font-medium">Saved</p>}
          {mutation.isError && (
            <p className="text-sm text-red-600">Could not save. Please try again.</p>
          )}
        </div>
      </form>
    </div>
  );
}
