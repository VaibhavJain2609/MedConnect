'use client';

/**
 * PrescriptionCard Component
 *
 * Displays prescription information in an interactive, user-friendly format
 * for both patient timeline and doctor's charts view.
 *
 * Features:
 * - Medicine cards with dosage, frequency, timing
 * - Visual meal time indicators (breakfast, lunch, dinner icons)
 * - Diagnosis and notes sections
 * - Doctor information
 * - Responsive layout
 * - Collapsible view for patient timeline
 */

import { useState } from "react";
import { formatDate } from "@/lib/utils";

interface Medicine {
  name: string;
  dosage: string;
  frequency: string;
  duration: string;
  timing?: string;
  notes?: string;
}

interface PrescriptionCardProps {
  prescription: {
    id: string;
    medicines: Medicine[];
    diagnosis?: string;
    notes?: string;
    created_at: string;
    doctor_name?: string;
    valid_until?: string;
  };
  variant?: 'patient' | 'doctor';
  collapsible?: boolean;
  defaultExpanded?: boolean;
  className?: string;
}

// Map frequency text to meal icons
const getMealIcons = (frequency: string): string[] => {
  const icons: string[] = [];

  if (frequency.toLowerCase().includes('breakfast')) icons.push('🌅');
  if (frequency.toLowerCase().includes('lunch')) icons.push('☀️');
  if (frequency.toLowerCase().includes('tea')) icons.push('☕');
  if (frequency.toLowerCase().includes('dinner')) icons.push('🌙');
  if (frequency.toLowerCase().includes('bedtime')) icons.push('😴');

  // If no specific meals mentioned, show generic pill icon
  if (icons.length === 0) icons.push('💊');

  return icons;
};

// Map timing to icon
const getTimingIcon = (timing?: string): string => {
  if (!timing) return '✅';

  const t = timing.toLowerCase();
  if (t.includes('empty stomach')) return '🚫';
  if (t.includes('with food')) return '🍽️';
  if (t.includes('after food')) return '✅';
  if (t.includes('anytime')) return '⏰';

  return '✅';
};

export function PrescriptionCard({
  prescription,
  variant = 'patient',
  collapsible = false,
  defaultExpanded = false,
  className = ''
}: PrescriptionCardProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  const toggleExpanded = () => {
    if (collapsible) {
      setIsExpanded(!isExpanded);
    }
  };

  return (
    <div className={`rounded-xl border bg-white shadow-sm ${className}`}>
      {/* Header - Always visible */}
      <div
        className={`border-b bg-gradient-to-r from-blue-50 to-indigo-50 px-6 py-4 ${
          collapsible ? 'cursor-pointer hover:from-blue-100 hover:to-indigo-100 transition-colors' : ''
        }`}
        onClick={toggleExpanded}
      >
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="text-2xl">📋</span>
              <h3 className="text-lg font-semibold text-gray-900">Prescription</h3>
              {collapsible && (
                <button
                  type="button"
                  className="ml-2 rounded-full p-1 hover:bg-white/50 transition-colors"
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleExpanded();
                  }}
                >
                  <svg
                    className={`h-5 w-5 text-gray-600 transition-transform ${
                      isExpanded ? 'rotate-180' : ''
                    }`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M19 9l-7 7-7-7"
                    />
                  </svg>
                </button>
              )}
            </div>

            {/* Summary info - always visible */}
            <div className="mt-2 space-y-1">
              <p className="text-sm text-gray-600">
                {formatDate(prescription.created_at)}
                {prescription.valid_until && (
                  <span className="ml-2 text-gray-500">
                    • Valid until {formatDate(prescription.valid_until)}
                  </span>
                )}
              </p>

              {/* Show diagnosis in collapsed view */}
              {collapsible && !isExpanded && prescription.diagnosis && (
                <p className="text-sm font-medium text-gray-700">
                  <span className="text-gray-500">Diagnosis:</span> {prescription.diagnosis}
                </p>
              )}

              {/* Show medicine count in collapsed view */}
              {collapsible && !isExpanded && (
                <div className="flex items-center gap-2">
                  <p className="text-sm text-gray-600">
                    💊 {prescription.medicines.length} medicine{prescription.medicines.length !== 1 ? 's' : ''} prescribed
                  </p>
                  <span className="text-xs text-primary-600 font-medium">
                    Click to view details →
                  </span>
                </div>
              )}
            </div>
          </div>

          {prescription.doctor_name && variant === 'patient' && (
            <div className="text-right ml-4">
              <p className="text-xs text-gray-500">Prescribed by</p>
              <p className="font-medium text-gray-900">{prescription.doctor_name}</p>
            </div>
          )}
        </div>
      </div>

      {/* Detailed content - shown when expanded or not collapsible */}
      {(!collapsible || isExpanded) && (
        <>
          {/* Diagnosis */}
          {prescription.diagnosis && (
            <div className="border-b bg-amber-50 px-6 py-4">
              <div className="flex items-start gap-2">
                <span className="text-lg">🩺</span>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-gray-600">Diagnosis</p>
                  <p className="mt-1 text-sm font-medium text-gray-900">{prescription.diagnosis}</p>
                </div>
              </div>
            </div>
          )}

          {/* Medicines */}
          <div className="p-6">
        <div className="mb-4 flex items-center gap-2">
          <span className="text-lg">💊</span>
          <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-700">
            Medicines ({prescription.medicines.length})
          </h4>
        </div>

        <div className="space-y-4">
          {prescription.medicines.map((medicine, idx) => (
            <div
              key={idx}
              className="rounded-lg border-2 border-gray-100 bg-gradient-to-br from-white to-gray-50 p-4 transition-all hover:border-primary-200 hover:shadow-md"
            >
              {/* Medicine Name & Dosage */}
              <div className="mb-3">
                <div className="flex items-start justify-between">
                  <div>
                    <h5 className="text-base font-semibold text-gray-900">{medicine.name}</h5>
                    <p className="mt-1 text-sm text-gray-600">{medicine.dosage}</p>
                  </div>
                  <span className="rounded-full bg-primary-100 px-3 py-1 text-xs font-medium text-primary-700">
                    #{idx + 1}
                  </span>
                </div>
              </div>

              {/* Frequency & Timing */}
              <div className="grid gap-3 sm:grid-cols-2">
                {/* When to take */}
                <div className="rounded-md bg-white px-3 py-2 shadow-sm">
                  <p className="mb-1 text-xs font-medium text-gray-500">When to take</p>
                  <div className="flex items-center gap-2">
                    <div className="flex gap-1">
                      {getMealIcons(medicine.frequency).map((icon, i) => (
                        <span key={i} className="text-lg">
                          {icon}
                        </span>
                      ))}
                    </div>
                    <p className="text-sm font-medium text-gray-900">{medicine.frequency}</p>
                  </div>
                </div>

                {/* Food relation */}
                {medicine.timing && (
                  <div className="rounded-md bg-white px-3 py-2 shadow-sm">
                    <p className="mb-1 text-xs font-medium text-gray-500">Food relation</p>
                    <div className="flex items-center gap-2">
                      <span className="text-lg">{getTimingIcon(medicine.timing)}</span>
                      <p className="text-sm font-medium text-gray-900">{medicine.timing}</p>
                    </div>
                  </div>
                )}
              </div>

              {/* Duration */}
              <div className="mt-3 rounded-md bg-blue-50 px-3 py-2">
                <div className="flex items-center gap-2">
                  <span className="text-lg">⏱️</span>
                  <p className="text-xs font-medium text-gray-600">Duration:</p>
                  <p className="text-sm font-semibold text-blue-900">{medicine.duration}</p>
                </div>
              </div>

              {/* Medicine-specific notes */}
              {medicine.notes && (
                <div className="mt-3 rounded-md bg-yellow-50 px-3 py-2">
                  <div className="flex items-start gap-2">
                    <span className="text-base">📝</span>
                    <div>
                      <p className="text-xs font-medium text-gray-600">Instructions</p>
                      <p className="mt-1 text-sm text-gray-900">{medicine.notes}</p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

          {/* General Notes */}
          {prescription.notes && (
            <div className="border-t bg-gray-50 px-6 py-4">
              <div className="flex items-start gap-2">
                <span className="text-lg">📌</span>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-gray-600">
                    Additional Notes
                  </p>
                  <p className="mt-1 text-sm text-gray-700">{prescription.notes}</p>
                </div>
              </div>
            </div>
          )}

          {/* Footer */}
          <div className="border-t bg-gray-50 px-6 py-3">
            <p className="text-xs text-gray-400">Prescription ID: {prescription.id}</p>
          </div>
        </>
      )}
    </div>
  );
}
