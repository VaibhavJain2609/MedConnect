"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ClipboardList, Download } from "lucide-react";
import { getEncounters, Encounter } from "@/lib/api/encounters";
import { downloadFile } from "@/lib/download";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const VITAL_LABELS: Record<string, string> = {
  bp_systolic: "BP Systolic",
  bp_diastolic: "BP Diastolic",
  pulse: "Pulse",
  spo2: "SpO2",
  temperature_c: "Temperature",
  weight_kg: "Weight",
  height_cm: "Height",
  respiratory_rate: "Resp. Rate",
};

function formatDateTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function EncounterCard({ enc }: { enc: Encounter }) {
  const [expanded, setExpanded] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState("");

  const handleDownload = async () => {
    if (downloading) return;
    setDownloading(true);
    setDownloadError("");
    try {
      await downloadFile(
        `/api/v1/encounters/${enc.id}/summary-pdf?download=true`
      );
    } catch {
      setDownloadError("Download failed. Please try again.");
    } finally {
      setDownloading(false);
    }
  };

  const soapSections = [
    { label: "Subjective", value: enc.subjective },
    { label: "Objective", value: enc.objective },
    { label: "Assessment", value: enc.assessment },
    { label: "Plan", value: enc.plan },
  ];

  return (
    <div className="rounded-xl border border-dreams-border bg-white">
      {/* Row — click to expand */}
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
        className="flex w-full items-center justify-between gap-4 px-4 py-3 text-left hover:bg-dreams-lightBg/60 transition-colors rounded-xl"
      >
        <div className="min-w-0">
          <p className="font-medium text-dreams-textPrimary truncate">
            {enc.doctor_name ? `Dr. ${enc.doctor_name}` : "Visit"}
          </p>
          <p className="text-xs text-dreams-textSecondary truncate mt-0.5">
            {enc.assessment
              ? `Dx: ${enc.assessment}`
              : enc.subjective ?? "No details recorded"}
          </p>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          {enc.clinic_name && (
            <span className="hidden sm:block text-xs text-dreams-textSecondary">
              {enc.clinic_name}
            </span>
          )}
          <span className="text-xs text-dreams-textSecondary whitespace-nowrap">
            {formatDateTime(enc.created_at)}
          </span>
          <ChevronDown
            className={cn(
              "h-4 w-4 text-gray-400 transition-transform",
              expanded && "rotate-180"
            )}
          />
        </div>
      </button>

      {/* Detail — vitals + SOAP + download */}
      {expanded && (
        <div className="border-t border-dreams-border px-4 py-4 space-y-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-dreams-textSecondary">
              {formatDateTime(enc.created_at)}
              {enc.clinic_name ? ` · ${enc.clinic_name}` : ""}
              {enc.appointment_id ? " · Linked to appointment" : ""}
            </p>
            <button
              onClick={handleDownload}
              disabled={downloading}
              className="flex items-center gap-2 px-3 py-1.5 border border-dreams-border text-xs rounded-lg hover:bg-dreams-lightBg disabled:opacity-40 transition-colors flex-shrink-0"
            >
              <Download className="h-3.5 w-3.5" />
              {downloading ? "Downloading..." : "Download summary"}
            </button>
          </div>

          {downloadError && (
            <p className="text-xs text-red-600">{downloadError}</p>
          )}

          {enc.vitals_snapshot &&
            Object.keys(enc.vitals_snapshot).length > 0 && (
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-dreams-textSecondary mb-2">
                  Vitals
                </h3>
                <div className="flex flex-wrap gap-x-4 gap-y-1">
                  {Object.entries(enc.vitals_snapshot).map(([key, val]) => (
                    <div key={key} className="text-sm">
                      <span className="text-dreams-textSecondary">
                        {VITAL_LABELS[key] ?? key}:
                      </span>{" "}
                      <span className="font-medium text-dreams-textPrimary">
                        {String(val)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {soapSections.map((s) => (
              <div
                key={s.label}
                className="rounded-lg border border-dreams-border bg-dreams-lightBg/40 p-3"
              >
                <h3 className="text-xs font-semibold uppercase tracking-wider text-dreams-textSecondary mb-1.5">
                  {s.label}
                </h3>
                <p className="text-sm text-dreams-textPrimary whitespace-pre-wrap">
                  {s.value || (
                    <span className="text-dreams-textSecondary italic">
                      Not recorded
                    </span>
                  )}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function PatientVisitsPage() {
  const [page, setPage] = useState(0);
  const limit = 20;

  const { data, isLoading, error } = useQuery({
    queryKey: ["patient-encounters", page],
    queryFn: () => getEncounters({ limit, offset: page * limit }),
  });

  const encounters: Encounter[] = data?.data ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / limit));

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: "Timeline", href: "/patient/timeline" },
          { label: "Visits" },
        ]}
      />

      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold text-dreams-textPrimary">
              Visits
            </h1>
            <Badge variant="pending" className="text-base px-3 py-1">
              {total}
            </Badge>
          </div>
          <p className="text-dreams-textSecondary mt-1">
            Consultation notes from your doctor visits
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-200 border-t-blue-600" />
        </div>
      ) : error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          Failed to load visits.
        </div>
      ) : encounters.length === 0 ? (
        <div className="text-center py-16 text-dreams-textSecondary">
          <ClipboardList className="h-10 w-10 mx-auto mb-3 text-gray-300" />
          <p>No visit notes yet.</p>
          <p className="text-sm mt-1">
            When your doctor writes a consultation note, it will appear here.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {encounters.map((enc) => (
            <EncounterCard key={enc.id} enc={enc} />
          ))}
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-dreams-textSecondary">
            Page {page + 1} of {totalPages} · {total} visits
          </p>
          <div className="flex gap-2">
            <button
              disabled={page === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              className="px-4 py-2 text-sm rounded-lg border border-dreams-border bg-white disabled:opacity-40 hover:bg-dreams-lightBg transition-colors"
            >
              Previous
            </button>
            <button
              disabled={page + 1 >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="px-4 py-2 text-sm rounded-lg border border-dreams-border bg-white disabled:opacity-40 hover:bg-dreams-lightBg transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
