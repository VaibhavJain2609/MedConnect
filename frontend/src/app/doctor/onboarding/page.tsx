"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, User, FileText, Building2, Loader2 } from "lucide-react";
import api from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────

interface OnboardingStatus {
  onboarding_step: string;
  verified: boolean;
  nhr_verification_status: string;
  profile: { full_name: string; email: string; phone: string | null; specialization: string | null };
  license: { license_number: string | null; license_council: string | null; license_year: number | null };
}

// ── API helpers ───────────────────────────────────────────────────────────

const getStatus = () => api.get<OnboardingStatus>("/api/v1/onboarding/status").then((r) => r.data);
const saveProfile = (d: object) => api.put("/api/v1/onboarding/profile", d).then((r) => r.data);
const saveLicense = (d: object) => api.put("/api/v1/onboarding/license", d).then((r) => r.data);
const saveClinic = (d: object) => api.post("/api/v1/onboarding/clinic", d).then((r) => r.data);

// ── Step indicator ────────────────────────────────────────────────────────

const STEPS = [
  { key: "profile", label: "Profile", icon: User },
  { key: "license", label: "License", icon: FileText },
  { key: "clinic", label: "Clinic", icon: Building2 },
];

function StepIndicator({ current }: { current: string }) {
  const order = ["pending", "profile", "license", "clinic", "completed"];
  const idx = order.indexOf(current);

  return (
    <div className="mb-8 flex items-center justify-center gap-0">
      {STEPS.map((step, i) => {
        const stepIdx = i + 1;
        const done = idx > stepIdx;
        const active = idx === stepIdx;
        const Icon = step.icon;
        return (
          <div key={step.key} className="flex items-center">
            <div className="flex flex-col items-center">
              <div
                className={`flex h-10 w-10 items-center justify-center rounded-full border-2 transition-colors ${
                  done
                    ? "border-dreams-blue bg-dreams-blue text-white"
                    : active
                    ? "border-dreams-blue bg-white text-dreams-blue"
                    : "border-gray-300 bg-white text-gray-400"
                }`}
              >
                {done ? <Check className="h-5 w-5" /> : <Icon className="h-5 w-5" />}
              </div>
              <p className={`mt-1 text-xs ${active ? "font-semibold text-dreams-blue" : "text-dreams-textSecondary"}`}>
                {step.label}
              </p>
            </div>
            {i < STEPS.length - 1 && (
              <div className={`mb-4 h-0.5 w-16 ${done ? "bg-dreams-blue" : "bg-gray-200"}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Specializations ───────────────────────────────────────────────────────

const SPECIALIZATIONS = [
  "General Physician",
  "Cardiologist",
  "Dermatologist",
  "ENT Specialist",
  "Gastroenterologist",
  "General Surgeon",
  "Gynaecologist & Obstetrician",
  "Neurologist",
  "Oncologist",
  "Ophthalmologist",
  "Orthopaedic Surgeon",
  "Paediatrician",
  "Psychiatrist",
  "Pulmonologist",
  "Radiologist",
  "Urologist",
  "Other",
];

// ── Step components ───────────────────────────────────────────────────────

function StepProfile({ status, onDone }: { status: OnboardingStatus; onDone: () => void }) {
  const [name, setName] = useState(status.profile.full_name ?? "");
  const [phone, setPhone] = useState(status.profile.phone ?? "+91 ");
  const [spec, setSpec] = useState(status.profile.specialization ?? "");
  const mut = useMutation({ mutationFn: saveProfile, onSuccess: onDone });

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-dreams-textPrimary">Your Profile</h2>
      <p className="text-sm text-dreams-textSecondary">Let us know who you are.</p>

      <div>
        <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">Full Name</label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Dr. Priya Sharma"
          className="w-full rounded-lg border border-dreams-border px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
        />
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">Phone</label>
        <div className="flex items-center rounded-lg border border-dreams-border focus-within:ring-2 focus-within:ring-dreams-blue overflow-hidden">
          <span className="bg-gray-50 px-3 py-2.5 text-sm text-dreams-textSecondary border-r border-dreams-border select-none">
            +91
          </span>
          <input
            type="tel"
            value={phone.replace(/^\+91\s?/, "")}
            onChange={(e) => setPhone("+91 " + e.target.value)}
            placeholder="98765 43210"
            className="flex-1 px-3 py-2.5 text-sm focus:outline-none"
          />
        </div>
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">Specialization</label>
        <select
          value={spec}
          onChange={(e) => setSpec(e.target.value)}
          className="w-full rounded-lg border border-dreams-border px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue bg-white"
        >
          <option value="">Select specialization…</option>
          {SPECIALIZATIONS.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      <button
        onClick={() => mut.mutate({ full_name: name, phone, specialization: spec })}
        disabled={!name || mut.isPending}
        className="w-full rounded-lg bg-dreams-blue px-4 py-2.5 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {mut.isPending ? <Loader2 className="mx-auto h-5 w-5 animate-spin" /> : "Continue"}
      </button>
    </div>
  );
}

const MEDICAL_COUNCILS = [
  "Medical Council of India (MCI)",
  "National Medical Commission (NMC)",
  "Andhra Pradesh Medical Council",
  "Arunachal Pradesh Medical Council",
  "Assam Medical Council",
  "Bihar Medical Council",
  "Chhattisgarh Medical Council",
  "Delhi Medical Council",
  "Goa Medical Council",
  "Gujarat Medical Council",
  "Haryana Medical Council",
  "Himachal Pradesh Medical Council",
  "Jammu & Kashmir Medical Council",
  "Jharkhand Medical Council",
  "Karnataka Medical Council",
  "Kerala Medical Council",
  "Madhya Pradesh Medical Council",
  "Maharashtra Medical Council",
  "Manipur Medical Council",
  "Meghalaya Medical Council",
  "Mizoram Medical Council",
  "Nagaland Medical Council",
  "Odisha Medical Council",
  "Punjab Medical Council",
  "Rajasthan Medical Council",
  "Sikkim Medical Council",
  "Tamil Nadu Medical Council",
  "Telangana Medical Council",
  "Tripura Medical Council",
  "Uttar Pradesh Medical Council",
  "Uttarakhand Medical Council",
  "West Bengal Medical Council",
  "Other",
];

function StepLicense({ status, onDone }: { status: OnboardingStatus; onDone: () => void }) {
  const [num, setNum] = useState(status.license.license_number ?? "");
  const [council, setCouncil] = useState(status.license.license_council ?? "");
  const [year, setYear] = useState(status.license.license_year?.toString() ?? "");
  const mut = useMutation({ mutationFn: saveLicense, onSuccess: onDone });

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-dreams-textPrimary">License Details</h2>
      <p className="text-sm text-dreams-textSecondary">
        Enter your medical council registration details.
      </p>

      <div>
        <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">License Number</label>
        <input
          type="text"
          value={num}
          onChange={(e) => setNum(e.target.value)}
          placeholder="MH-12345"
          className="w-full rounded-lg border border-dreams-border px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
        />
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">Issuing Council</label>
        <select
          value={council}
          onChange={(e) => setCouncil(e.target.value)}
          className="w-full rounded-lg border border-dreams-border px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue bg-white"
        >
          <option value="">Select council…</option>
          {MEDICAL_COUNCILS.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">Year of Registration</label>
        <input
          type="text"
          value={year}
          onChange={(e) => setYear(e.target.value)}
          placeholder="2015"
          className="w-full rounded-lg border border-dreams-border px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
        />
      </div>

      <button
        onClick={() =>
          mut.mutate({ license_number: num, license_council: council, license_year: parseInt(year) })
        }
        disabled={!num || !council || !year || mut.isPending}
        className="w-full rounded-lg bg-dreams-blue px-4 py-2.5 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {mut.isPending ? <Loader2 className="mx-auto h-5 w-5 animate-spin" /> : "Continue"}
      </button>
    </div>
  );
}

function StepClinic({ onDone }: { onDone: () => void }) {
  const [action, setAction] = useState<"create" | null>(null);
  const [clinicName, setClinicName] = useState("");
  const [city, setCity] = useState("");
  const mut = useMutation({
    mutationFn: saveClinic,
    onSuccess: onDone,
  });

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-dreams-textPrimary">Your Clinic</h2>
      <p className="text-sm text-dreams-textSecondary">
        Create a new clinic or join an existing one.
      </p>

      {!action ? (
        <div className="space-y-3">
          <button
            onClick={() => setAction("create")}
            className="w-full rounded-lg border-2 border-dreams-blue bg-blue-50 p-4 text-left hover:bg-blue-100"
          >
            <p className="font-medium text-dreams-blue">Create New Clinic</p>
            <p className="text-sm text-dreams-textSecondary mt-1">Set up your own clinic and become its owner</p>
          </button>
          <button
            disabled
            className="w-full rounded-lg border border-dreams-border p-4 text-left opacity-50 cursor-not-allowed"
          >
            <p className="font-medium text-dreams-textPrimary">Join with Invite Code</p>
            <p className="text-sm text-dreams-textSecondary mt-1">Coming soon — available in the next release</p>
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <button
            onClick={() => setAction(null)}
            className="text-sm text-dreams-blue hover:underline"
          >
            ← Back
          </button>
          <div>
            <label className="mb-1 block text-sm font-medium">Clinic Name</label>
            <input
              value={clinicName}
              onChange={(e) => setClinicName(e.target.value)}
              placeholder="City Health Clinic"
              className="w-full rounded-lg border border-dreams-border px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">City</label>
            <input
              value={city}
              onChange={(e) => setCity(e.target.value)}
              placeholder="Mumbai"
              className="w-full rounded-lg border border-dreams-border px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
            />
          </div>
          <button
            onClick={() =>
              mut.mutate({ action: "create", clinic_data: { name: clinicName, city } })
            }
            disabled={!clinicName || mut.isPending}
            className="w-full rounded-lg bg-dreams-blue px-4 py-2.5 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {mut.isPending ? <Loader2 className="mx-auto h-5 w-5 animate-spin" /> : "Create & Continue"}
          </button>
          {mut.isError && (
            <p className="text-sm text-red-600">Something went wrong. Please try again.</p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Pending Verification ──────────────────────────────────────────────────

function PendingVerification({ status }: { status: OnboardingStatus }) {
  return (
    <div className="rounded-xl border border-dreams-border bg-white p-8 text-center shadow-card">
      <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-yellow-50">
        <Loader2 className="h-8 w-8 text-yellow-600 animate-spin" />
      </div>
      <h2 className="text-xl font-semibold text-dreams-textPrimary">Pending Verification</h2>
      <p className="mt-2 text-sm text-dreams-textSecondary">
        Your profile is complete. Our team will review and verify your credentials.
        You will receive an email once approved.
      </p>
      <div className="mt-6 rounded-lg bg-gray-50 p-4 text-left space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-sm text-dreams-textSecondary">Profile</span>
          <Check className="h-4 w-4 text-green-500" />
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-dreams-textSecondary">License</span>
          <Check className="h-4 w-4 text-green-500" />
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-dreams-textSecondary">Clinic</span>
          <Check className="h-4 w-4 text-green-500" />
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-dreams-textSecondary">Platform Verification</span>
          <span className="rounded-full bg-yellow-100 px-2 py-0.5 text-xs text-yellow-700">Pending</span>
        </div>
      </div>
      <p className="mt-4 text-xs text-dreams-textSecondary">
        Questions? Contact <a href="mailto:support@medconnect.in" className="text-dreams-blue">support@medconnect.in</a>
      </p>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────

export default function OnboardingPage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data: status, isLoading } = useQuery({
    queryKey: ["onboarding-status"],
    queryFn: getStatus,
  });

  // Redirect to dashboard once fully verified
  useEffect(() => {
    if (status?.onboarding_step === "completed" && status?.verified) {
      router.replace("/doctor/dashboard");
    }
  }, [status, router]);

  const refetch = () => queryClient.invalidateQueries({ queryKey: ["onboarding-status"] });

  if (isLoading || !status) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="h-8 w-8 animate-spin text-dreams-blue" />
      </div>
    );
  }

  // Show pending dashboard if onboarding is complete but not verified
  if (status.onboarding_step === "completed" && !status.verified) {
    return <PendingVerification status={status} />;
  }

  return (
    <div className="rounded-xl border border-dreams-border bg-white p-8 shadow-card">
      <StepIndicator current={status.onboarding_step} />

      {(status.onboarding_step === "pending" || status.onboarding_step === "profile") && (
        <StepProfile status={status} onDone={refetch} />
      )}
      {status.onboarding_step === "license" && (
        <StepLicense status={status} onDone={refetch} />
      )}
      {status.onboarding_step === "clinic" && (
        <StepClinic onDone={refetch} />
      )}
    </div>
  );
}
