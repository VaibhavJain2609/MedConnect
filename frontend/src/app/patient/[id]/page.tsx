"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Calendar, FileText, Activity, TestTube, Pill, Clock, File, User } from "lucide-react";
import api from "@/lib/api";
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
  name: string;
  photo: string | null;
  age: number;
  gender: string;
  bloodType: string;
  phone: string;
  email: string;
  address: string;
  city: string;
  state: string;
  zipCode: string;
  emergencyContact: string;
  emergencyPhone: string;
}

interface Vital {
  id: string;
  name: string;
  value: string;
  unit: string;
  status: "normal" | "warning" | "critical";
  icon: React.ComponentType<{ className?: string }>;
  lastUpdated: string;
}

interface Appointment {
  id: string;
  doctor: string;
  doctorPhoto: string | null;
  department: string;
  date: string;
  time: string;
  status: "upcoming" | "completed" | "cancelled";
  type: string;
  notes?: string;
}

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

  // Fetch patient data
  const { data: patient, isLoading: isLoadingPatient } = useQuery({
    queryKey: ["patient", patientId],
    queryFn: async () => {
      // TODO: Replace with actual API call to /api/v1/patients/{id}
      return {
        id: patientId,
        name: "John Doe",
        photo: null,
        age: 45,
        gender: "Male",
        bloodType: "A+",
        phone: "+1 (555) 123-4567",
        email: "john.doe@example.com",
        address: "123 Main Street",
        city: "New York",
        state: "NY",
        zipCode: "10001",
        emergencyContact: "Jane Doe",
        emergencyPhone: "+1 (555) 987-6543",
      } as Patient;
    },
  });

  // Fetch vital signs
  const { data: vitals } = useQuery({
    queryKey: ["patient-vitals", patientId],
    queryFn: async () => {
      // TODO: Replace with actual API call to /api/v1/patients/{id}/vitals
      return [
        {
          id: "1",
          name: "Blood Pressure",
          value: "120/80",
          unit: "mmHg",
          status: "normal",
          icon: BloodPressureIcon,
          lastUpdated: "2 hours ago",
        },
        {
          id: "2",
          name: "Heart Rate",
          value: "72",
          unit: "bpm",
          status: "normal",
          icon: HeartRateIcon,
          lastUpdated: "2 hours ago",
        },
        {
          id: "3",
          name: "SPO2",
          value: "98",
          unit: "%",
          status: "normal",
          icon: SPO2Icon,
          lastUpdated: "2 hours ago",
        },
        {
          id: "4",
          name: "Temperature",
          value: "98.6",
          unit: "°F",
          status: "normal",
          icon: TemperatureIcon,
          lastUpdated: "2 hours ago",
        },
        {
          id: "5",
          name: "Respiratory Rate",
          value: "16",
          unit: "/min",
          status: "normal",
          icon: RespiratoryRateIcon,
          lastUpdated: "2 hours ago",
        },
        {
          id: "6",
          name: "Weight",
          value: "75",
          unit: "kg",
          status: "normal",
          icon: WeightIcon,
          lastUpdated: "1 week ago",
        },
      ] as Vital[];
    },
  });

  // Fetch appointments
  const { data: appointments } = useQuery({
    queryKey: ["patient-appointments", patientId],
    queryFn: async () => {
      // TODO: Replace with actual API call to /api/v1/patients/{id}/appointments
      return [
        {
          id: "1",
          doctor: "Dr. Sarah Smith",
          doctorPhoto: null,
          department: "Cardiology",
          date: "2026-02-28",
          time: "10:00 AM",
          status: "upcoming",
          type: "Follow-up",
        },
        {
          id: "2",
          doctor: "Dr. Michael Johnson",
          doctorPhoto: null,
          department: "General Medicine",
          date: "2026-02-20",
          time: "2:30 PM",
          status: "completed",
          type: "Consultation",
          notes: "Regular checkup completed. All vitals normal.",
        },
        {
          id: "3",
          doctor: "Dr. Emily Davis",
          doctorPhoto: null,
          department: "Cardiology",
          date: "2026-01-15",
          time: "11:00 AM",
          status: "completed",
          type: "Consultation",
          notes: "ECG performed. Results normal.",
        },
      ] as Appointment[];
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

  const getVitalStatusColor = (status: Vital["status"]) => {
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
          { label: patient.name },
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
              fallback={patient.name}
              size="2xl"
              className="mb-4"
            />
            <h2 className="text-xl font-bold text-dreams-textPrimary">
              {patient.name}
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
                {patient.bloodType}
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
                {patient.address}
                <br />
                {patient.city}, {patient.state} {patient.zipCode}
              </p>
            </div>

            <div className="pt-4 border-t border-dreams-border">
              <p className="text-xs text-dreams-textSecondary uppercase mb-1">
                Emergency Contact
              </p>
              <p className="text-sm font-medium text-dreams-textPrimary">
                {patient.emergencyContact}
              </p>
              <p className="text-sm text-dreams-textSecondary">
                {patient.emergencyPhone}
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
                      {patient.name}
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
                  {vitals?.map((vital) => {
                    const Icon = vital.icon;
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
                              getVitalStatusColor(vital.status)
                            )}
                          >
                            {vital.status.toUpperCase()}
                          </span>
                        </div>

                        <h4 className="text-sm text-dreams-textSecondary mb-2">
                          {vital.name}
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
                          Updated {vital.lastUpdated}
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
                  {appointments?.map((appointment) => (
                    <div
                      key={appointment.id}
                      className="p-6 rounded-lg border border-dreams-border hover:border-dreams-blue/50 transition-colors"
                    >
                      <div className="flex items-start justify-between mb-4">
                        <Badge variant={appointment.status}>
                          {appointment.status === "upcoming"
                            ? "Upcoming"
                            : appointment.status === "completed"
                            ? "Completed"
                            : "Cancelled"}
                        </Badge>
                        <span className="text-xs text-dreams-textSecondary">
                          {appointment.type}
                        </span>
                      </div>

                      <div className="flex items-center gap-3 mb-4">
                        <Avatar
                          src={appointment.doctorPhoto}
                          fallback={appointment.doctor}
                          size="md"
                        />
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-dreams-textPrimary">
                            {appointment.doctor}
                          </p>
                          <p className="text-sm text-dreams-textSecondary">
                            {appointment.department}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-4 mb-3">
                        <div className="flex items-center gap-2 text-sm text-dreams-textSecondary">
                          <Calendar className="h-4 w-4" />
                          <span>{appointment.date}</span>
                        </div>
                        <div className="flex items-center gap-2 text-sm text-dreams-textSecondary">
                          <Clock className="h-4 w-4" />
                          <span>{appointment.time}</span>
                        </div>
                      </div>

                      {appointment.notes && (
                        <div className="pt-3 border-t border-dreams-border">
                          <p className="text-sm text-dreams-textSecondary">
                            {appointment.notes}
                          </p>
                        </div>
                      )}

                      {appointment.status === "upcoming" && (
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

            {/* Placeholder for other tabs */}
            {activeTab === "visits" && (
              <div className="text-center py-12">
                <Clock className="h-12 w-12 text-dreams-textSecondary mx-auto mb-4" />
                <p className="text-dreams-textSecondary">
                  Visit history will be displayed here
                </p>
              </div>
            )}

            {activeTab === "lab-results" && (
              <div className="text-center py-12">
                <TestTube className="h-12 w-12 text-dreams-textSecondary mx-auto mb-4" />
                <p className="text-dreams-textSecondary">
                  Lab results will be displayed here
                </p>
              </div>
            )}

            {activeTab === "prescriptions" && (
              <div className="text-center py-12">
                <Pill className="h-12 w-12 text-dreams-textSecondary mx-auto mb-4" />
                <p className="text-dreams-textSecondary">
                  Prescriptions will be displayed here
                </p>
              </div>
            )}

            {activeTab === "medical-history" && (
              <div className="text-center py-12">
                <FileText className="h-12 w-12 text-dreams-textSecondary mx-auto mb-4" />
                <p className="text-dreams-textSecondary">
                  Medical history will be displayed here
                </p>
              </div>
            )}

            {activeTab === "billings" && (
              <div className="text-center py-12">
                <FileText className="h-12 w-12 text-dreams-textSecondary mx-auto mb-4" />
                <p className="text-dreams-textSecondary">
                  Billing information will be displayed here
                </p>
              </div>
            )}

            {activeTab === "documents" && (
              <div className="text-center py-12">
                <File className="h-12 w-12 text-dreams-textSecondary mx-auto mb-4" />
                <p className="text-dreams-textSecondary">
                  Documents will be displayed here
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
