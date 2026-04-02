"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Calendar, FileText, Activity, TestTube, Pill, Clock, File, User, AlertCircle, DollarSign } from "lucide-react";
import api from "@/lib/api";
import { getMyVitals, VITAL_META, isVitalAbnormal, type VitalType, type Vital } from "@/lib/api/vitals";
import { getAppointments } from "@/lib/api/appointments";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import {
  BloodPressureIcon,
  HeartRateIcon,
  SPO2Icon,
  TemperatureIcon,
  RespiratoryRateIcon,
  WeightIcon,
} from "@/components/icons/vital-icons";
import { cn } from "@/lib/utils";

interface Patient {
  id: string;
  full_name: string;
  phone: string | null;
  email: string | null;
  language_pref?: string | null;
  blood_group?: string | null;
  allergies?: string[];
  chronic_conditions?: string[];
  height_cm?: number | null;
  weight_kg?: number | null;
  age?: number | null;
  gender?: string | null;
  photo?: string | null;
  address?: string | null;
  city?: string | null;
  state?: string | null;
  zip_code?: string | null;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
}

const VITAL_ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  bp_systolic: BloodPressureIcon,
  bp_diastolic: BloodPressureIcon,
  pulse: HeartRateIcon,
  spo2: SPO2Icon,
  temperature_c: TemperatureIcon,
  weight_kg: WeightIcon,
  glucose_fasting: HeartRateIcon,
  glucose_pp: HeartRateIcon,
};

type TabValue =
  | "profile"
  | "appointments"
  | "vitals"
  | "visits"
  | "lab-results"
  | "prescriptions"
  | "medical-history"
  | "billings"
  | "documents";

interface Tab {
  value: TabValue;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const tabs: Tab[] = [
  { value: "profile", label: "Patient Profile", icon: User },
  { value: "appointments", label: "Appointments", icon: Calendar },
  { value: "vitals", label: "Vital Signs", icon: Activity },
  { value: "visits", label: "Visit History", icon: Clock },
  { value: "lab-results", label: "Lab Results", icon: TestTube },
  { value: "prescriptions", label: "Prescription", icon: Pill },
  { value: "medical-history", label: "Medical History", icon: FileText },
  { value: "billings", label: "Billings", icon: FileText },
  { value: "documents", label: "Documents", icon: File },
];

export default function PatientDetailsPage() {
  const params = useParams();
  const router = useRouter();
  const patientId = params.id as string;
  const [activeTab, setActiveTab] = useState<TabValue>("vitals");

  // Fetch patient profile from real API
  const { data: patient, isLoading: isLoadingPatient, isError: isPatientError } = useQuery({
    queryKey: ["patient-own-profile", patientId],
    queryFn: async () => {
      const res = await api.get("/api/v1/patients/profile");
      return res.data as Patient;
    },
  });

  // Fetch vital signs from real API (patient's own vitals, last 90 days)
  const { data: vitalsData, isLoading: isLoadingVitals } = useQuery({
    queryKey: ["patient-own-vitals-latest"],
    queryFn: () => getMyVitals({ days: 90, limit: 200 }),
  });

  // Deduplicate — keep only the latest reading per vital type
  const latestVitals = (() => {
    const seen = new Set<string>();
    const result: typeof vitalsData extends { data: infer T } ? T : never[] = [];
    for (const v of vitalsData?.data ?? []) {
      if (!seen.has(v.vital_type)) {
        seen.add(v.vital_type);
        (result as NonNullable<typeof vitalsData>["data"]).push(v);
      }
    }
    return result as NonNullable<typeof vitalsData>["data"];
  })();

  // Fetch appointments from real API
  const { data: appointmentsData, isLoading: isLoadingAppointments } = useQuery({
    queryKey: ["patient-own-appointments"],
    queryFn: () => getAppointments({}),
  });

  // Fetch prescriptions
  const { data: prescriptionsData, isLoading: isLoadingPrescriptions } = useQuery({
    queryKey: ["patient-prescriptions"],
    queryFn: async () => {
      const res = await api.get("/api/v1/patients/prescriptions");
      return res.data as { data: Array<{ id: string; diagnosis: string | null; medicines: Array<{ name: string }>; valid_until: string | null; created_at: string }>; pagination: { total: number } };
    },
  });

  // Fetch billing
  const { data: billingsData, isLoading: isLoadingBillings } = useQuery({
    queryKey: ["patient-billings"],
    queryFn: async () => {
      const res = await api.get("/api/v1/billing");
      return res.data as { data: Array<{ id: string; amount: string; status: string; payment_method: string | null; notes: string | null; created_at: string }>; pagination: { total: number } };
    },
  });

  // Fetch lab results (records of type lab_report)
  const { data: labResultsData, isLoading: isLoadingLabResults } = useQuery({
    queryKey: ["patient-lab-results"],
    queryFn: async () => {
      const res = await api.get("/api/v1/patients/records?type=lab_report&limit=50");
      return res.data as { data: Array<{ id: string; title: string; doctor_name: string | null; document_url: string | null; created_at: string }> };
    },
  });

  // Fetch documents (records with a document_url)
  const { data: recordsData, isLoading: isLoadingDocuments } = useQuery({
    queryKey: ["patient-all-records"],
    queryFn: async () => {
      const res = await api.get("/api/v1/patients/records?limit=100");
      return res.data as { data: Array<{ id: string; title: string; record_type: string; doctor_name: string | null; document_url: string | null; created_at: string }> };
    },
  });

  // Fetch medical history
  const { data: medicalHistory, isLoading: isLoadingMedHistory } = useQuery({
    queryKey: ["patient-medical-history"],
    queryFn: async () => {
      const res = await api.get("/api/v1/patients/medical-history");
      return res.data as { blood_group: string | null; allergies: string[]; chronic_conditions: string[]; height_cm: number | null; weight_kg: number | null };
    },
  });

  if (isLoadingPatient) {
    return (
      <div className="flex justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
      </div>
    );
  }

  if (!patient) {
    return (
      <div className="text-center py-12">
        <p className="text-dreams-textSecondary">Patient not found</p>
      </div>
    );
  }

  const getVitalStatusColor = (status: string) => {
    switch (status) {
      case "normal":
        return "text-status-completed";
      case "warning":
        return "text-status-pending";
      case "critical":
        return "text-status-overdue";
      default:
        return "text-dreams-textSecondary";
    }
  };

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <Breadcrumb
        items={[
          { label: "Health Timeline", href: "/patient/timeline" },
          { label: patient.full_name },
        ]}
      />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-dreams-textPrimary">
            Patient Details
          </h1>
          <p className="text-dreams-textSecondary mt-1">
            View and manage patient information
          </p>
        </div>

        <button
          onClick={() => router.back()}
          className="flex items-center gap-2 px-4 py-2 text-dreams-textSecondary hover:text-dreams-textPrimary transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          <span>Back to Patients</span>
        </button>
      </div>

      {/* Main Content */}
      <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
        {/* Left Sidebar - Patient Profile Card */}
        <div className="bg-white rounded-lg shadow-card p-6">
          <div className="flex flex-col items-center">
            <Avatar
              src={patient.photo}
              fallback={patient.full_name}
              size="2xl"
              className="mb-4"
            />
            <h2 className="text-xl font-bold text-dreams-textPrimary">
              {patient.full_name}
            </h2>
            <p className="text-sm text-dreams-textSecondary mb-4">
              ID: {patient.id}
            </p>
          </div>

          <div className="space-y-4 mt-6">
            <div>
              <p className="text-xs text-dreams-textSecondary uppercase mb-1">
                Age / Gender
              </p>
              <p className="text-sm font-medium text-dreams-textPrimary">
                {patient.age} years / {patient.gender}
              </p>
            </div>

            <div>
              <p className="text-xs text-dreams-textSecondary uppercase mb-1">
                Blood Type
              </p>
              <p className="text-sm font-medium text-dreams-textPrimary">
                {patient.blood_group ?? "—"}
              </p>
            </div>

            <div>
              <p className="text-xs text-dreams-textSecondary uppercase mb-1">
                Phone
              </p>
              <p className="text-sm font-medium text-dreams-textPrimary">
                {patient.phone}
              </p>
            </div>

            <div>
              <p className="text-xs text-dreams-textSecondary uppercase mb-1">
                Email
              </p>
              <p className="text-sm font-medium text-dreams-textPrimary break-all">
                {patient.email}
              </p>
            </div>

            <div>
              <p className="text-xs text-dreams-textSecondary uppercase mb-1">
                Address
              </p>
              <p className="text-sm font-medium text-dreams-textPrimary">
                {patient.address ?? "—"}
                {(patient.city || patient.state) && (
                  <>
                    <br />
                    {[patient.city, patient.state, patient.zip_code].filter(Boolean).join(", ")}
                  </>
                )}
              </p>
            </div>

            <div className="pt-4 border-t border-dreams-border">
              <p className="text-xs text-dreams-textSecondary uppercase mb-1">
                Emergency Contact
              </p>
              <p className="text-sm font-medium text-dreams-textPrimary">
                {patient.emergency_contact_name ?? "—"}
              </p>
              <p className="text-sm text-dreams-textSecondary">
                {patient.emergency_contact_phone}
              </p>
            </div>
          </div>
        </div>

        {/* Right Content - Tabs */}
        <div className="bg-white rounded-lg shadow-card">
          {/* Tab Navigation */}
          <div className="border-b border-dreams-border overflow-x-auto">
            <div className="flex min-w-max">
              {tabs.map((tab) => {
                const Icon = tab.icon;
                return (
                  <button
                    key={tab.value}
                    onClick={() => setActiveTab(tab.value)}
                    className={cn(
                      "flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap",
                      activeTab === tab.value
                        ? "border-dreams-blue text-dreams-blue"
                        : "border-transparent text-dreams-textSecondary hover:text-dreams-textPrimary"
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    <span>{tab.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Tab Content */}
          <div className="p-6">
            {/* Patient Profile Tab */}
            {activeTab === "profile" && (
              <div className="space-y-6">
                <h3 className="text-xl font-bold text-dreams-textPrimary">
                  Patient Profile
                </h3>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="p-4 rounded-lg border border-dreams-border">
                    <p className="text-sm text-dreams-textSecondary mb-1">
                      Full Name
                    </p>
                    <p className="font-medium text-dreams-textPrimary">
                      {patient.full_name}
                    </p>
                  </div>
                  <div className="p-4 rounded-lg border border-dreams-border">
                    <p className="text-sm text-dreams-textSecondary mb-1">
                      Patient ID
                    </p>
                    <p className="font-medium text-dreams-textPrimary">
                      {patient.id}
                    </p>
                  </div>
                  <div className="p-4 rounded-lg border border-dreams-border">
                    <p className="text-sm text-dreams-textSecondary mb-1">Age</p>
                    <p className="font-medium text-dreams-textPrimary">
                      {patient.age} years
                    </p>
                  </div>
                  <div className="p-4 rounded-lg border border-dreams-border">
                    <p className="text-sm text-dreams-textSecondary mb-1">
                      Gender
                    </p>
                    <p className="font-medium text-dreams-textPrimary">
                      {patient.gender}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Vital Signs Tab */}
            {activeTab === "vitals" && (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <h3 className="text-xl font-bold text-dreams-textPrimary">
                    Vital Signs
                  </h3>
                  <button className="text-sm text-dreams-blue hover:underline">
                    View Past Data
                  </button>
                </div>

                <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                  {latestVitals?.map((vital) => {
                    const Icon = VITAL_ICON_MAP[vital.vital_type] ?? Activity;
                    const meta = VITAL_META[vital.vital_type as VitalType];
                    const abnormal = isVitalAbnormal(vital.vital_type as VitalType, vital.value);
                    const status = vital.abnormal_flag ?? abnormal ? "warning" : "normal";
                    return (
                      <div
                        key={vital.id}
                        className="p-6 rounded-lg border border-dreams-border hover:border-dreams-blue/50 transition-colors"
                      >
                        <div className="flex items-start justify-between mb-4">
                          <div className="p-3 rounded-lg bg-dreams-lightBg">
                            <Icon className="h-6 w-6 text-dreams-blue" />
                          </div>
                          <span
                            className={cn(
                              "text-xs font-medium",
                              getVitalStatusColor(status)
                            )}
                          >
                            {status.toUpperCase()}
                          </span>
                        </div>

                        <h4 className="text-sm text-dreams-textSecondary mb-2">
                          {meta?.label ?? vital.vital_type}
                        </h4>

                        <div className="flex items-baseline gap-2 mb-2">
                          <span className="text-3xl font-bold text-dreams-textPrimary">
                            {vital.value}
                          </span>
                          <span className="text-sm text-dreams-textSecondary">
                            {vital.unit}
                          </span>
                        </div>

                        <p className="text-xs text-dreams-textSecondary">
                          Updated {new Date(vital.recorded_at).toLocaleDateString()}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Appointments Tab */}
            {activeTab === "appointments" && (
              <div className="space-y-6">
                <h3 className="text-xl font-bold text-dreams-textPrimary">
                  Appointments
                </h3>

                <div className="grid gap-6 md:grid-cols-2">
                  {appointmentsData?.data?.map((appointment) => (
                    <div
                      key={appointment.id}
                      className="p-6 rounded-lg border border-dreams-border hover:border-dreams-blue/50 transition-colors"
                    >
                      <div className="flex items-start justify-between mb-4">
                        <Badge variant={
                          appointment.status === "scheduled" ? "upcoming"
                          : appointment.status === "arrived" ? "pending"
                          : appointment.status === "in-progress" ? "inProgress"
                          : appointment.status === "no-show" ? "destructive"
                          : appointment.status as "completed" | "cancelled"
                        }>
                          {appointment.status === "scheduled" ? "Scheduled"
                            : appointment.status === "arrived" ? "Arrived"
                            : appointment.status === "in-progress" ? "In Progress"
                            : appointment.status === "completed" ? "Completed"
                            : appointment.status === "no-show" ? "No Show"
                            : "Cancelled"}
                        </Badge>
                        <span className="text-xs text-dreams-textSecondary">
                          {appointment.type}
                        </span>
                      </div>

                      <div className="flex items-center gap-3 mb-4">
                        <Avatar
                          src={appointment.doctor_photo}
                          fallback={appointment.doctor_name ?? "Doctor"}
                          size="md"
                        />
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-dreams-textPrimary">
                            {appointment.doctor_name}
                          </p>
                          <p className="text-sm text-dreams-textSecondary">
                            {appointment.department ?? appointment.clinic_name}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-4 mb-3">
                        <div className="flex items-center gap-2 text-sm text-dreams-textSecondary">
                          <Calendar className="h-4 w-4" />
                          <span>{new Date(appointment.scheduled_at).toLocaleDateString()}</span>
                        </div>
                        <div className="flex items-center gap-2 text-sm text-dreams-textSecondary">
                          <Clock className="h-4 w-4" />
                          <span>{new Date(appointment.scheduled_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                        </div>
                      </div>

                      {appointment.notes && (
                        <div className="pt-3 border-t border-dreams-border">
                          <p className="text-sm text-dreams-textSecondary">
                            {appointment.notes}
                          </p>
                        </div>
                      )}

                      {appointment.status === "scheduled" && (
                        <div className="flex gap-2 mt-4">
                          <button className="flex-1 px-3 py-2 text-sm bg-dreams-blue text-white rounded-lg hover:opacity-90 transition-opacity">
                            Join Call
                          </button>
                          <button className="px-3 py-2 text-sm border border-dreams-border text-dreams-textSecondary rounded-lg hover:bg-dreams-lightBg transition-colors">
                            Reschedule
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Visit History Tab */}
            {activeTab === "visits" && (
              <div className="space-y-4">
                <h3 className="text-xl font-bold text-dreams-textPrimary">Visit History</h3>
                {isLoadingAppointments ? (
                  <div className="flex justify-center py-8"><div className="h-6 w-6 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" /></div>
                ) : (() => {
                  const visits = appointmentsData?.data?.filter((a) => a.status === "completed") ?? [];
                  return visits.length === 0 ? (
                    <div className="text-center py-12">
                      <Clock className="h-12 w-12 text-dreams-textSecondary mx-auto mb-4" />
                      <p className="text-dreams-textSecondary">No completed visits yet</p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {visits.map((visit) => (
                        <div key={visit.id} className="p-4 rounded-lg border border-dreams-border flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <Avatar src={visit.doctor_photo} fallback={visit.doctor_name ?? "Doctor"} size="md" />
                            <div>
                              <p className="font-medium text-dreams-textPrimary">{visit.doctor_name}</p>
                              <p className="text-sm text-dreams-textSecondary">{visit.department ?? visit.clinic_name}</p>
                            </div>
                          </div>
                          <div className="flex items-center gap-3">
                            <span className="text-sm text-dreams-textSecondary">{new Date(visit.scheduled_at).toLocaleDateString()}</span>
                            <span className="px-2 py-0.5 bg-green-100 text-green-800 rounded-full text-xs font-medium">Completed</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  );
                })()}
              </div>
            )}

            {activeTab === "lab-results" && (
              <div className="space-y-4">
                <h3 className="text-xl font-bold text-dreams-textPrimary">Lab Results</h3>
                {isLoadingLabResults ? (
                  <div className="flex justify-center py-8"><div className="h-6 w-6 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" /></div>
                ) : (labResultsData?.data?.length ?? 0) === 0 ? (
                  <div className="text-center py-12">
                    <TestTube className="h-12 w-12 text-dreams-textSecondary mx-auto mb-4" />
                    <p className="text-dreams-textSecondary">No lab results yet</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {labResultsData?.data?.map((r) => (
                      <a
                        key={r.id}
                        href={r.document_url ?? `/api/v1/patients/records/${r.id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center justify-between p-4 rounded-lg border border-dreams-border hover:border-dreams-blue/50 transition-colors"
                      >
                        <div>
                          <p className="font-medium text-dreams-textPrimary">{r.title}</p>
                          {r.doctor_name && <p className="text-sm text-dreams-textSecondary">Dr. {r.doctor_name}</p>}
                        </div>
                        <span className="text-xs text-dreams-textSecondary">{new Date(r.created_at).toLocaleDateString()}</span>
                      </a>
                    ))}
                  </div>
                )}
              </div>
            )}

            {activeTab === "prescriptions" && (
              <div className="space-y-4">
                <h3 className="text-xl font-bold text-dreams-textPrimary">Prescriptions</h3>
                {isLoadingPrescriptions ? (
                  <div className="flex justify-center py-8"><div className="h-6 w-6 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" /></div>
                ) : prescriptionsData?.data?.length === 0 ? (
                  <div className="text-center py-12">
                    <Pill className="h-12 w-12 text-dreams-textSecondary mx-auto mb-4" />
                    <p className="text-dreams-textSecondary">No prescriptions yet</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {prescriptionsData?.data?.map((rx) => (
                      <div key={rx.id} className="p-4 rounded-lg border border-dreams-border hover:border-dreams-blue/50 transition-colors">
                        <div className="flex items-start justify-between">
                          <div className="flex-1 min-w-0">
                            <p className="font-medium text-dreams-textPrimary">{rx.diagnosis ?? "No diagnosis noted"}</p>
                            <p className="text-sm text-dreams-textSecondary mt-1">
                              {rx.medicines?.length ?? 0} medicine{(rx.medicines?.length ?? 0) !== 1 ? "s" : ""}
                              {rx.valid_until && ` · Valid until ${new Date(rx.valid_until).toLocaleDateString()}`}
                            </p>
                          </div>
                          <div className="flex items-center gap-3 ml-4">
                            <span className="text-xs text-dreams-textSecondary">{new Date(rx.created_at).toLocaleDateString()}</span>
                            <a
                              href={`/api/v1/prescriptions/${rx.id}/pdf`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="px-3 py-1 text-xs bg-dreams-blue text-white rounded-lg hover:opacity-90 transition-opacity"
                            >
                              Download PDF
                            </a>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {activeTab === "medical-history" && (
              <div className="space-y-6">
                <h3 className="text-xl font-bold text-dreams-textPrimary">Medical History</h3>
                {isLoadingMedHistory ? (
                  <div className="flex justify-center py-8"><div className="h-6 w-6 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" /></div>
                ) : (
                  <div className="space-y-6">
                    <div className="grid gap-4 md:grid-cols-3">
                      <div className="p-4 rounded-lg border border-dreams-border">
                        <p className="text-xs text-dreams-textSecondary uppercase mb-2">Blood Group</p>
                        {medicalHistory?.blood_group ? (
                          <span className="px-3 py-1 bg-red-100 text-red-800 rounded-full text-sm font-semibold">{medicalHistory.blood_group}</span>
                        ) : (
                          <p className="text-sm text-dreams-textSecondary">Not recorded</p>
                        )}
                      </div>
                      <div className="p-4 rounded-lg border border-dreams-border">
                        <p className="text-xs text-dreams-textSecondary uppercase mb-2">Height</p>
                        <p className="font-medium text-dreams-textPrimary">{medicalHistory?.height_cm ? `${medicalHistory.height_cm} cm` : "—"}</p>
                      </div>
                      <div className="p-4 rounded-lg border border-dreams-border">
                        <p className="text-xs text-dreams-textSecondary uppercase mb-2">Weight</p>
                        <p className="font-medium text-dreams-textPrimary">{medicalHistory?.weight_kg ? `${medicalHistory.weight_kg} kg` : "—"}</p>
                      </div>
                    </div>
                    <div className="p-4 rounded-lg border border-dreams-border">
                      <p className="text-xs text-dreams-textSecondary uppercase mb-3">Allergies</p>
                      {medicalHistory?.allergies?.length ? (
                        <div className="flex flex-wrap gap-2">
                          {medicalHistory.allergies.map((a) => (
                            <span key={a} className="px-2 py-1 bg-orange-100 text-orange-800 rounded-full text-sm">{a}</span>
                          ))}
                        </div>
                      ) : (
                        <p className="text-sm text-dreams-textSecondary">No known allergies</p>
                      )}
                    </div>
                    <div className="p-4 rounded-lg border border-dreams-border">
                      <p className="text-xs text-dreams-textSecondary uppercase mb-3">Chronic Conditions</p>
                      {medicalHistory?.chronic_conditions?.length ? (
                        <div className="flex flex-wrap gap-2">
                          {medicalHistory.chronic_conditions.map((c) => (
                            <span key={c} className="px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">{c}</span>
                          ))}
                        </div>
                      ) : (
                        <p className="text-sm text-dreams-textSecondary">No chronic conditions recorded</p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            {activeTab === "billings" && (
              <div className="space-y-4">
                <h3 className="text-xl font-bold text-dreams-textPrimary">Billings</h3>
                {isLoadingBillings ? (
                  <div className="flex justify-center py-8"><div className="h-6 w-6 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" /></div>
                ) : billingsData?.data?.length === 0 ? (
                  <div className="text-center py-12">
                    <DollarSign className="h-12 w-12 text-dreams-textSecondary mx-auto mb-4" />
                    <p className="text-dreams-textSecondary">No billing records yet</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {billingsData?.data?.map((bill) => {
                      const statusColors: Record<string, string> = {
                        paid: "bg-green-100 text-green-800",
                        pending: "bg-yellow-100 text-yellow-800",
                        cancelled: "bg-red-100 text-red-700",
                        refunded: "bg-gray-100 text-gray-600",
                      };
                      return (
                        <div key={bill.id} className="p-4 rounded-lg border border-dreams-border flex items-center justify-between">
                          <div>
                            <p className="font-medium text-dreams-textPrimary">₹{parseFloat(bill.amount).toLocaleString("en-IN")}</p>
                            <p className="text-sm text-dreams-textSecondary mt-0.5">
                              {bill.payment_method ? bill.payment_method.toUpperCase() : "—"}
                              {bill.notes && ` · ${bill.notes}`}
                            </p>
                          </div>
                          <div className="flex items-center gap-3">
                            <span className="text-xs text-dreams-textSecondary">{new Date(bill.created_at).toLocaleDateString()}</span>
                            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColors[bill.status] ?? "bg-gray-100 text-gray-600"}`}>
                              {bill.status.charAt(0).toUpperCase() + bill.status.slice(1)}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {activeTab === "documents" && (
              <div className="space-y-4">
                <h3 className="text-xl font-bold text-dreams-textPrimary">Documents</h3>
                {isLoadingDocuments ? (
                  <div className="flex justify-center py-8"><div className="h-6 w-6 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" /></div>
                ) : (() => {
                    const docs = (recordsData?.data ?? []).filter((r) => !!r.document_url);
                    return docs.length === 0 ? (
                      <div className="text-center py-12">
                        <File className="h-12 w-12 text-dreams-textSecondary mx-auto mb-4" />
                        <p className="text-dreams-textSecondary">No documents available yet</p>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {docs.map((doc) => (
                          <a
                            key={doc.id}
                            href={doc.document_url!}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center justify-between p-4 rounded-lg border border-dreams-border hover:border-dreams-blue/50 transition-colors"
                          >
                            <div className="flex items-center gap-3">
                              <File className="h-5 w-5 text-dreams-blue flex-shrink-0" />
                              <div>
                                <p className="font-medium text-dreams-textPrimary">{doc.title}</p>
                                {doc.doctor_name && <p className="text-sm text-dreams-textSecondary">Dr. {doc.doctor_name}</p>}
                              </div>
                            </div>
                            <span className="text-xs text-dreams-textSecondary">{new Date(doc.created_at).toLocaleDateString()}</span>
                          </a>
                        ))}
                      </div>
                    );
                  })()
                }
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
