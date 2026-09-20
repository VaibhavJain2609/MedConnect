/**
 * Doctor Availability API Functions
 *
 * NOTE: availability start_time/end_time are naive clinic-local wall-clock
 * times ("HH:MM[:SS]") — see the timezone assumption documented in
 * backend/app/models/doctor_availability.py.
 */

import api from "../api";

export interface AvailabilityWindow {
  id: string;
  doctor_id: string;
  doctor_name?: string | null;
  clinic_id: string | null;
  branch_id: string | null;
  /** 0 = Monday .. 6 = Sunday (matches date.weekday() / JS getDay() - 1 mod 7) */
  weekday: number;
  /** "HH:MM" naive clinic-local time */
  start_time: string;
  /** "HH:MM" naive clinic-local time */
  end_time: string;
  slot_duration_minutes: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateAvailabilityWindowData {
  weekday: number;
  start_time: string; // "HH:MM"
  end_time: string; // "HH:MM"
  slot_duration_minutes?: number;
  clinic_id?: string | null;
  branch_id?: string | null;
  is_active?: boolean;
}

export interface UpdateAvailabilityWindowData {
  weekday?: number;
  start_time?: string;
  end_time?: string;
  slot_duration_minutes?: number;
  clinic_id?: string | null;
  branch_id?: string | null;
  is_active?: boolean;
}

export interface DoctorLeave {
  id: string;
  doctor_id: string;
  /** "YYYY-MM-DD" */
  date: string;
  reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateLeaveData {
  date: string; // "YYYY-MM-DD"
  reason?: string | null;
}

export interface AvailabilitySlot {
  /** ISO datetime of slot start */
  start: string;
  /** ISO datetime of slot end */
  end: string;
  /** "HH:MM" wall-clock start */
  start_time: string;
  /** "HH:MM" wall-clock end */
  end_time: string;
  clinic_id: string | null;
  branch_id: string | null;
}

export interface DoctorSlotsResponse {
  doctor_id: string;
  date: string;
  slots: AvailabilitySlot[];
}

/** List the authenticated doctor's availability windows. */
export async function getMyAvailability(): Promise<AvailabilityWindow[]> {
  const response = await api.get("/api/v1/availability/me");
  return response.data.data;
}

export async function createAvailabilityWindow(
  data: CreateAvailabilityWindowData
): Promise<AvailabilityWindow> {
  const response = await api.post("/api/v1/availability/me", data);
  return response.data;
}

export async function updateAvailabilityWindow(
  id: string,
  data: UpdateAvailabilityWindowData
): Promise<AvailabilityWindow> {
  const response = await api.put(`/api/v1/availability/me/${id}`, data);
  return response.data;
}

export async function deleteAvailabilityWindow(id: string): Promise<void> {
  await api.delete(`/api/v1/availability/me/${id}`);
}

/** List the authenticated doctor's leave days. */
export async function getMyLeaves(): Promise<DoctorLeave[]> {
  const response = await api.get("/api/v1/availability/me/leaves");
  return response.data.data;
}

export async function createLeave(data: CreateLeaveData): Promise<DoctorLeave> {
  const response = await api.post("/api/v1/availability/me/leaves", data);
  return response.data;
}

export async function deleteLeave(id: string): Promise<void> {
  await api.delete(`/api/v1/availability/me/leaves/${id}`);
}

/** List availability windows of all doctors in the active clinic. */
export async function getClinicAvailability(
  clinicId: string
): Promise<AvailabilityWindow[]> {
  const response = await api.get("/api/v1/availability/clinic", {
    headers: { "X-Clinic-Id": clinicId },
  });
  return response.data.data;
}

/** Compute bookable slots for a doctor on a given date (YYYY-MM-DD). */
export async function getDoctorSlots(
  doctorId: string,
  date: string,
  clinicId?: string
): Promise<DoctorSlotsResponse> {
  const params = new URLSearchParams({ date });
  if (clinicId) params.append("clinic_id", clinicId);
  const response = await api.get(
    `/api/v1/availability/doctors/${doctorId}/slots?${params}`
  );
  return response.data;
}
