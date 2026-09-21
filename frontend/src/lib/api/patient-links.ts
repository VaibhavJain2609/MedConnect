import api from "@/lib/api";
import type { ClinicLink } from "./patients";

export type { ClinicLink };
export { getMyClinicLinks } from "./patients";

/**
 * The patient's weekly link code (GET /api/v1/patients/link-code).
 * Shared with a doctor so their clinic can initiate a PatientClinicLink.
 */
export interface PatientLinkCode {
  code: string;
  expires_at: string;
}

export async function getPatientLinkCode(): Promise<PatientLinkCode> {
  const res = await api.get("/api/v1/patients/link-code");
  return res.data;
}

/**
 * Update consent on a patient ↔ clinic link
 * (PUT /api/v1/patients/clinic-links/{link_id}/consent).
 *
 * action="approved" grants the clinic write access (also used to restore a
 * revoked link); action="revoked" removes it. Revocation only blocks new
 * writes — the clinic keeps read access to records created beforehand.
 */
export async function updateClinicLinkConsent(
  linkId: string,
  action: "approved" | "revoked"
): Promise<{ consent_status: "pending" | "approved" | "revoked" }> {
  const res = await api.put(`/api/v1/patients/clinic-links/${linkId}/consent`, {
    action,
  });
  return res.data;
}
