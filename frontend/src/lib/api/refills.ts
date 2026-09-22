/**
 * Prescription refill / renewal request API utilities.
 *
 * Backend: app/routers/refill_requests.py
 * - POST /api/v1/prescriptions/{id}/refill-request   (patient)
 * - GET  /api/v1/prescriptions/refill-requests/mine (patient)
 * - GET  /api/v1/prescriptions/refill-requests      (doctor; clinic-scoped via X-Clinic-Id)
 * - POST /api/v1/refill-requests/{id}/respond       (doctor)
 */

import api from "@/lib/api";
import type { PrescriptionMedicine } from "./patient-portal";

export type RefillStatus = "pending" | "approved" | "declined";

export interface RefillRequest {
  id: string;
  prescription_id: string;
  patient_id: string;
  patient_name: string | null;
  doctor_id: string;
  clinic_id: string | null;
  note: string | null;
  status: RefillStatus;
  response_note: string | null;
  new_prescription_id: string | null;
  responded_at: string | null;
  created_at: string;
  /** Original prescription context (present in the doctor list payload). */
  medicines: PrescriptionMedicine[] | null;
  diagnosis: string | null;
  valid_until: string | null;
  prescribed_at: string | null;
}

/** Patient: request a refill of one of their own prescriptions. */
export async function requestRefill(
  prescriptionId: string,
  note?: string
): Promise<RefillRequest> {
  return (
    await api.post(`/api/v1/prescriptions/${prescriptionId}/refill-request`, {
      note: note?.trim() || null,
    })
  ).data;
}

/** Patient: list own refill requests (newest first). */
export async function getMyRefillRequests(): Promise<RefillRequest[]> {
  return (await api.get("/api/v1/prescriptions/refill-requests/mine")).data.data;
}

/** Doctor: list refill requests (clinic-scoped via X-Clinic-Id when set). */
export async function getRefillRequests(
  status?: RefillStatus
): Promise<RefillRequest[]> {
  return (
    await api.get("/api/v1/prescriptions/refill-requests", {
      params: status ? { status } : {},
    })
  ).data.data;
}

/** Doctor: approve (issues a cloned prescription) or decline with a note. */
export async function respondToRefillRequest(
  requestId: string,
  action: "approve" | "decline",
  note?: string
): Promise<RefillRequest> {
  return (
    await api.post(`/api/v1/refill-requests/${requestId}/respond`, {
      action,
      note: note?.trim() || null,
    })
  ).data;
}
