/**
 * Appointment Waitlist API Functions
 */

import api from "../api";

export type WaitlistStatus = "pending" | "notified" | "expired" | "cancelled";
export type WaitlistSlotWindow = "morning" | "afternoon" | "any";

export interface WaitlistEntry {
  id: string;
  patient_id: string;
  patient_name: string | null;
  doctor_id: string;
  doctor_name: string | null;
  clinic_id: string | null;
  clinic_name: string | null;
  /** "YYYY-MM-DD" */
  desired_date: string;
  slot_window: WaitlistSlotWindow;
  status: WaitlistStatus;
  notified_at: string | null;
  created_at: string | null;
}

export interface JoinWaitlistData {
  doctor_id: string;
  /** "YYYY-MM-DD" */
  desired_date: string;
  slot_window?: WaitlistSlotWindow;
  clinic_id?: string | null;
}

/**
 * Join a doctor's waitlist for a fully-booked day (patient).
 * 409 WAITLIST_ALREADY_PENDING when a pending entry already exists.
 */
export async function joinWaitlist(data: JoinWaitlistData): Promise<WaitlistEntry> {
  const response = await api.post("/api/v1/appointments/waitlist", data);
  return response.data;
}

/**
 * List the current patient's waitlist entries (newest first).
 */
export async function getMyWaitlist(status?: WaitlistStatus): Promise<WaitlistEntry[]> {
  const params = status ? `?status=${status}` : "";
  const response = await api.get(`/api/v1/appointments/waitlist/mine${params}`);
  return response.data.data;
}

/**
 * Cancel one of the patient's own waitlist entries.
 */
export async function cancelWaitlistEntry(id: string): Promise<void> {
  await api.delete(`/api/v1/appointments/waitlist/${id}`);
}

/**
 * Clinic-scoped waitlist for front-desk staff. Requires X-Clinic-Id.
 */
export async function getClinicWaitlist(
  clinicId: string,
  params: { status?: WaitlistStatus; date?: string } = {}
): Promise<WaitlistEntry[]> {
  const queryParams = new URLSearchParams();
  if (params.status) queryParams.append("status", params.status);
  if (params.date) queryParams.append("date", params.date);
  const qs = queryParams.toString();
  const response = await api.get(`/api/v1/appointments/waitlist${qs ? `?${qs}` : ""}`, {
    headers: { "X-Clinic-Id": clinicId },
  });
  return response.data.data;
}
