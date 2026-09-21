"use client";

import { AlertTriangle } from "lucide-react";

interface PatientAllergyBannerProps {
  allergies: string[];
  chronicConditions?: string[];
  className?: string;
}

/**
 * Amber safety banner shown on the new-prescription form once a patient is
 * selected. Surfaces `User.allergies` / `User.chronic_conditions` returned by
 * GET /api/v1/doctors/patients/{id}/profile so the prescriber can check the
 * medicine list against them before submitting.
 */
export default function PatientAllergyBanner({
  allergies,
  chronicConditions = [],
  className = "",
}: PatientAllergyBannerProps) {
  if (allergies.length === 0 && chronicConditions.length === 0) {
    return null;
  }

  return (
    <div
      role="alert"
      className={`rounded-lg border border-amber-200 bg-amber-50 p-4 flex items-start gap-3 ${className}`}
    >
      <AlertTriangle className="h-5 w-5 mt-0.5 flex-shrink-0 text-amber-500" />
      <div className="flex-1">
        {allergies.length > 0 && (
          <div>
            <p className="text-sm font-semibold text-amber-900">
              Known allergies ({allergies.length})
            </p>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {allergies.map((allergy) => (
                <span
                  key={allergy}
                  className="rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800"
                >
                  {allergy}
                </span>
              ))}
            </div>
            <p className="mt-1.5 text-xs text-amber-700">
              Cross-check prescribed medicines against these allergies before
              submitting.
            </p>
          </div>
        )}
        {chronicConditions.length > 0 && (
          <p
            className={`text-xs text-amber-800 ${
              allergies.length > 0
                ? "mt-2 border-t border-amber-200 pt-2"
                : ""
            }`}
          >
            <span className="font-semibold">Chronic conditions:</span>{" "}
            {chronicConditions.join(", ")}
          </p>
        )}
      </div>
    </div>
  );
}
