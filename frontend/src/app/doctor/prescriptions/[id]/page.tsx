"use client";

/**
 * Doctor Prescription Detail Page
 *
 * Prescription summary plus the persisted "Safety check" section (R13) —
 * which alerts the clinical safety gate surfaced at issue time and the
 * override reason when a major alert was overridden.
 */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import axios from "axios";
import { Printer, ShieldAlert, ShieldCheck } from "lucide-react";

import api from "@/lib/api";
import {
  getPrescriptionSafetyCheck,
  type SafetyCheckAlert,
} from "@/lib/api/prescriptions";
import { Breadcrumb } from "@/components/ui/breadcrumb";

interface PrescriptionDetail {
  id: string;
  record_id: string;
  medicines: {
    brand_name?: string;
    name?: string;
    dose?: string;
    dosage?: string;
    frequency?: string;
    duration?: string;
    route?: string;
    instructions?: string;
  }[];
  diagnosis: string | null;
  notes: string | null;
  valid_until: string | null;
  created_at: string;
  patient_name: string | null;
  doctor: {
    name: string | null;
    specialization: string | null;
  } | null;
}

const SEVERITY_STYLES: Record<string, string> = {
  contraindicated: "bg-red-100 text-red-800 border-red-200",
  major: "bg-orange-100 text-orange-800 border-orange-200",
  moderate: "bg-amber-100 text-amber-800 border-amber-200",
  minor: "bg-gray-100 text-gray-700 border-gray-200",
};

// Literal-keyed maps — next-intl type-checks message keys, so dynamic
// template keys (`kind.${kind}`) don't compile.
const SEVERITY_KEYS = {
  minor: "severity.minor",
  moderate: "severity.moderate",
  major: "severity.major",
  contraindicated: "severity.contraindicated",
} as const;

const KIND_KEYS = {
  interaction: "kind.interaction",
  allergy: "kind.allergy",
  duplicate_therapy: "kind.duplicate_therapy",
  contraindication: "kind.contraindication",
  unresolved_item: "kind.unresolved_item",
} as const;

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString();
}

function SafetyAlertRow({ alert }: { alert: SafetyCheckAlert }) {
  const t = useTranslations("doctorPrescriptionDetail.safetyCheck");
  const severity = alert.severity in SEVERITY_STYLES ? alert.severity : "minor";
  const sevKey = SEVERITY_KEYS[alert.severity as keyof typeof SEVERITY_KEYS];
  const kindKey = KIND_KEYS[alert.kind as keyof typeof KIND_KEYS];
  const kindLabel = kindKey ? t(kindKey) : alert.kind;
  const severityLabel = sevKey ? t(sevKey) : alert.severity;

  return (
    <li className="flex items-start gap-3 py-3">
      <span
        className={`mt-0.5 inline-flex shrink-0 items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${SEVERITY_STYLES[severity]}`}
      >
        {severityLabel}
      </span>
      <div className="min-w-0">
        <p className="text-xs font-medium uppercase tracking-wide text-dreams-textSecondary">
          {kindLabel}
        </p>
        <p className="mt-0.5 text-sm text-dreams-textPrimary">{alert.detail}</p>
        {alert.salts && alert.salts.length > 0 && (
          <p className="mt-0.5 text-xs text-dreams-textSecondary">
            {alert.salts.join(" + ")}
          </p>
        )}
      </div>
    </li>
  );
}

export default function DoctorPrescriptionDetailPage() {
  const t = useTranslations("doctorPrescriptionDetail");
  const params = useParams();
  const id = params.id as string;

  const rxQuery = useQuery<PrescriptionDetail>({
    queryKey: ["doctor-prescription", id],
    queryFn: async () => (await api.get(`/api/v1/doctors/prescriptions/${id}`)).data,
  });

  const safetyQuery = useQuery({
    queryKey: ["prescription-safety-check", id],
    queryFn: () => getPrescriptionSafetyCheck(id),
    retry: false,
  });

  const safetyNotFound =
    axios.isAxiosError(safetyQuery.error) && safetyQuery.error.response?.status === 404;

  if (rxQuery.isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
      </div>
    );
  }

  if (rxQuery.isError || !rxQuery.data) {
    return (
      <div className="space-y-6">
        <Breadcrumb items={[{ label: t("breadcrumb") }]} />
        <div className="bg-white rounded-lg shadow-card p-12 text-center">
          <p className="text-red-500 font-medium">{t("loadError")}</p>
        </div>
      </div>
    );
  }

  const rx = rxQuery.data;
  const check = safetyQuery.data;

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: t("breadcrumb") }]} />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-dreams-textPrimary">{t("title")}</h1>
          <p className="text-dreams-textSecondary mt-1">
            {t("patient")}: {rx.patient_name ?? "—"} · {t("date")}:{" "}
            {new Date(rx.created_at).toLocaleDateString()}
          </p>
        </div>
        <Link
          href={`/doctor/prescriptions/${id}/print`}
          className="flex items-center gap-2 px-4 py-2 bg-dreams-blue text-white rounded-lg hover:opacity-90 transition-opacity text-sm font-medium"
        >
          <Printer className="h-4 w-4" />
          {t("print")}
        </Link>
      </div>

      {/* Medicines */}
      <div className="bg-white rounded-lg shadow-card p-6">
        <h2 className="text-lg font-semibold text-dreams-textPrimary mb-4">
          {t("medicines")}
        </h2>
        <ol className="space-y-3">
          {rx.medicines.map((med, idx) => {
            const name = med.brand_name || med.name || "Unknown";
            const dose = med.dose || med.dosage || "";
            return (
              <li key={idx} className="text-sm">
                <div className="flex justify-between gap-4">
                  <span className="font-medium text-dreams-textPrimary">
                    {idx + 1}. {name}
                    {dose ? ` — ${dose}` : ""}
                  </span>
                  <span className="text-dreams-textSecondary">
                    {[med.frequency, med.duration].filter(Boolean).join(" × ")}
                  </span>
                </div>
                {(med.route || med.instructions) && (
                  <p className="ml-5 mt-0.5 text-xs text-dreams-textSecondary">
                    {[med.route, med.instructions].filter(Boolean).join(" · ")}
                  </p>
                )}
              </li>
            );
          })}
        </ol>

        {(rx.diagnosis || rx.notes || rx.valid_until) && (
          <div className="mt-4 space-y-1 border-t border-dreams-border pt-4 text-sm">
            {rx.diagnosis && (
              <p className="text-dreams-textPrimary">
                <span className="font-medium">{t("diagnosis")}:</span> {rx.diagnosis}
              </p>
            )}
            {rx.notes && (
              <p className="text-dreams-textPrimary">
                <span className="font-medium">{t("notes")}:</span> {rx.notes}
              </p>
            )}
            {rx.valid_until && (
              <p className="text-dreams-textSecondary">
                <span className="font-medium">{t("validUntil")}:</span>{" "}
                {new Date(rx.valid_until).toLocaleDateString()}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Safety check (R13) */}
      <div className="bg-white rounded-lg shadow-card p-6">
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-lg font-semibold text-dreams-textPrimary">
            {check && check.alerts.length > 0 ? (
              <ShieldAlert className="h-5 w-5 text-amber-600" />
            ) : (
              <ShieldCheck className="h-5 w-5 text-emerald-600" />
            )}
            {t("safetyCheck.title")}
          </h2>
          {check && (
            <span className="text-xs text-dreams-textSecondary">
              {t("safetyCheck.checkedAt", { timestamp: formatDateTime(check.checked_at) })}
            </span>
          )}
        </div>

        <div className="mt-4">
          {safetyQuery.isLoading ? (
            <div className="flex justify-center py-6">
              <div className="h-6 w-6 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
            </div>
          ) : safetyNotFound ? (
            <p className="text-sm text-dreams-textSecondary">{t("safetyCheck.empty")}</p>
          ) : safetyQuery.isError ? (
            <p className="text-sm text-red-500">{t("safetyCheck.loadError")}</p>
          ) : check && check.alerts.length === 0 ? (
            <p className="text-sm text-emerald-700">{t("safetyCheck.noAlerts")}</p>
          ) : check ? (
            <>
              <ul className="divide-y divide-dreams-border">
                {check.alerts.map((alert, idx) => (
                  <SafetyAlertRow key={idx} alert={alert} />
                ))}
              </ul>
              {check.override_reason && (
                <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3">
                  <p className="text-xs font-medium uppercase tracking-wide text-amber-800">
                    {t("safetyCheck.overrideReason")}
                  </p>
                  <p className="mt-1 text-sm text-amber-900">{check.override_reason}</p>
                </div>
              )}
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
