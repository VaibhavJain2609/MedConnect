/**
 * Medication adherence reminders — patient opt-in per prescription.
 * Backend: /api/v1/medication-reminders (POST upserts, GET lists, PATCH
 * updates times/enabled, DELETE soft-deletes). The ARQ worker emits a
 * deduped in-app notification at each configured "HH:MM" (Asia/Kolkata).
 */

import api from "../api";

export interface MedicationReminder {
  id: string;
  user_id: string;
  prescription_id: string;
  /** Sorted "HH:MM" 24h strings, e.g. ["08:00", "20:00"]. */
  times_of_day: string[];
  enabled: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export async function getMedicationReminders(params: {
  prescription_id?: string;
} = {}): Promise<MedicationReminder[]> {
  const qs = params.prescription_id
    ? `?prescription_id=${encodeURIComponent(params.prescription_id)}`
    : "";
  const response = await api.get(`/api/v1/medication-reminders${qs}`);
  return response.data.data;
}

/**
 * Create-or-replace: one live reminder per (patient, prescription), so a
 * repeated call updates the schedule in place (returns 200 instead of 201).
 */
export async function upsertMedicationReminder(input: {
  prescription_id: string;
  times_of_day: string[];
  enabled: boolean;
}): Promise<MedicationReminder> {
  const response = await api.post(`/api/v1/medication-reminders`, input);
  return response.data;
}

export async function updateMedicationReminder(
  id: string,
  patch: { times_of_day?: string[]; enabled?: boolean }
): Promise<MedicationReminder> {
  const response = await api.patch(`/api/v1/medication-reminders/${id}`, patch);
  return response.data;
}

export async function deleteMedicationReminder(id: string): Promise<void> {
  await api.delete(`/api/v1/medication-reminders/${id}`);
}
