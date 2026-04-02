"use client";

/**
 * MD-246: Prescription Print View
 * Minimal layout with no sidebar — print-friendly prescription.
 */

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import api from "@/lib/api";
import Link from "next/link";

interface PrescriptionPrintData {
  id: string;
  medicines: {
    brand_name: string;
    dose?: string;
    frequency?: string;
    duration?: string;
    route?: string;
    instructions?: string;
    // Legacy fields
    name?: string;
    dosage?: string;
    timing?: string;
    notes?: string;
  }[];
  diagnosis: string | null;
  notes: string | null;
  valid_until: string | null;
  created_at: string;
  patient_name: string | null;
  doctor: {
    name: string | null;
    specialization: string | null;
    license_number: string | null;
    facility_name: string | null;
    facility_city: string | null;
  } | null;
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString("en-IN", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export default function PrescriptionPrintPage() {
  const params = useParams();
  const id = params.id as string;

  const [data, setData] = useState<PrescriptionPrintData | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get(`/api/v1/doctors/prescriptions/${id}`)
      .then((res) => setData(res.data))
      .catch(() => setError("Could not load prescription."))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-200 border-t-blue-600" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <p className="text-red-600">{error || "Prescription not found."}</p>
        <Link href="/doctor/prescriptions" className="text-blue-600 underline no-print">
          Back to prescriptions
        </Link>
      </div>
    );
  }

  const doctor = data.doctor;

  return (
    <>
      <style>{`
        @media print {
          body { margin: 0; }
          .no-print { display: none !important; }
          /* Hide sidebar and header from doctor layout */
          nav, aside, header, [data-sidebar], [class*="sidebar"], [class*="Sidebar"] {
            display: none !important;
          }
          /* Make main content full width */
          main, [class*="main"], [class*="content"] {
            margin: 0 !important;
            padding: 0 !important;
            width: 100% !important;
            max-width: none !important;
          }
          @page { margin: 1.5cm; }
        }
      `}</style>

      {/* Action buttons */}
      <div className="no-print flex flex-wrap gap-3 p-4 border-b bg-gray-50">
        <button
          onClick={() => window.print()}
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
        >
          Print
        </button>
        <a
          href={`/api/v1/prescriptions/${id}/pdf?download=true`}
          target="_blank"
          rel="noopener noreferrer"
          className="px-4 py-2 bg-emerald-600 text-white text-sm font-medium rounded-lg hover:bg-emerald-700 transition-colors"
        >
          Download PDF
        </a>
        <a
          href={`/api/v1/prescriptions/${id}/pdf`}
          target="_blank"
          rel="noopener noreferrer"
          className="px-4 py-2 border border-gray-300 text-sm font-medium text-gray-700 rounded-lg hover:bg-gray-100 transition-colors"
        >
          Preview PDF
        </a>
        {data && (
          <a
            href={`https://wa.me/?text=${encodeURIComponent(
              `Here is your prescription from ${data.doctor?.name ? `Dr. ${data.doctor.name}` : "your doctor"}. Please keep this for your records. Prescription ID: ${id}`
            )}`}
            target="_blank"
            rel="noopener noreferrer"
            className="px-4 py-2 bg-green-500 text-white text-sm font-medium rounded-lg hover:bg-green-600 transition-colors"
          >
            Share on WhatsApp
          </a>
        )}
        <Link
          href="/doctor/prescriptions"
          className="px-4 py-2 border border-gray-300 text-sm font-medium text-gray-700 rounded-lg hover:bg-gray-100 transition-colors"
        >
          Close
        </Link>
      </div>

      {/* Prescription body */}
      <div className="max-w-2xl mx-auto p-8 font-serif print:p-0">
        {/* Header */}
        <div className="text-center mb-2">
          {doctor?.facility_name && (
            <h1 className="text-xl font-bold text-gray-900">
              {doctor.facility_name}
            </h1>
          )}
          {doctor?.facility_city && (
            <p className="text-sm text-gray-600">{doctor.facility_city}</p>
          )}
        </div>

        <hr className="border-gray-400 my-3" />

        {/* Doctor info */}
        <div className="flex items-start justify-between mb-4">
          <div>
            {doctor?.name && (
              <p className="font-semibold text-gray-900">Dr. {doctor.name}</p>
            )}
            {doctor?.specialization && (
              <p className="text-sm text-gray-600">{doctor.specialization}</p>
            )}
          </div>
          {doctor?.license_number && (
            <p className="text-sm text-gray-600">
              Reg: {doctor.license_number}
            </p>
          )}
        </div>

        <hr className="border-gray-300 mb-4" />

        {/* Patient & Date */}
        <div className="flex justify-between mb-6 text-sm">
          <div>
            <span className="text-gray-500">Patient: </span>
            <span className="font-semibold text-gray-900">
              {data.patient_name || "—"}
            </span>
          </div>
          <div>
            <span className="text-gray-500">Date: </span>
            <span className="font-semibold text-gray-900">
              {formatDate(data.created_at)}
            </span>
          </div>
        </div>

        {/* Rx heading */}
        <div className="mb-3">
          <p className="text-2xl font-bold text-gray-700 italic">Rx</p>
          <hr className="border-gray-300 mt-1" />
        </div>

        {/* Medicines */}
        <ol className="space-y-4 mb-6">
          {data.medicines.map((med, idx) => {
            const brandName = med.brand_name || med.name || "Unknown";
            const dose = med.dose || med.dosage || "";
            const freq = med.frequency || "";
            const dur = med.duration || "";
            const route = med.route || "";
            const instr = med.instructions || med.timing || med.notes || "";

            return (
              <li key={idx} className="text-sm">
                <div className="flex justify-between">
                  <span className="font-semibold text-gray-900">
                    {idx + 1}. {brandName}
                    {dose ? ` — ${dose}` : ""}
                  </span>
                  <span className="text-gray-700">
                    {freq}
                    {freq && dur ? " x " : ""}
                    {dur}
                  </span>
                </div>
                {(route || instr) && (
                  <p className="text-gray-500 ml-4 mt-0.5">
                    {route && `Route: ${route}`}
                    {route && instr ? " | " : ""}
                    {instr}
                  </p>
                )}
              </li>
            );
          })}
        </ol>

        {/* Diagnosis & Notes */}
        {data.diagnosis && (
          <p className="text-sm text-gray-800 mb-1">
            <span className="font-semibold">Diagnosis:</span> {data.diagnosis}
          </p>
        )}
        {data.notes && (
          <p className="text-sm text-gray-800 mb-4">
            <span className="font-semibold">Notes:</span> {data.notes}
          </p>
        )}

        {data.valid_until && (
          <p className="text-sm text-gray-600 mb-4">
            <span className="font-semibold">Valid until:</span>{" "}
            {formatDate(data.valid_until)}
          </p>
        )}

        <hr className="border-gray-300 mb-4" />

        {/* Signature */}
        <div className="text-right">
          {doctor?.name && (
            <p className="font-semibold text-gray-900">Dr. {doctor.name}</p>
          )}
          <div className="mt-6 border-t border-gray-400 inline-block w-40">
            <p className="text-xs text-gray-400 text-center pt-1">Signature</p>
          </div>
        </div>
      </div>
    </>
  );
}
