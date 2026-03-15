/**
 * Appointment API Functions
 */

import api from "../api";

export interface Appointment {
  id: string;
  patient_id: string;
  patient_name: string | null;
  patient_photo?: string | null;
  doctor_id: string;
  doctor_name: string | null;
  doctor_photo?: string | null;
  clinic_id: string | null;
  clinic_name: string | null;
  branch_id: string | null;
  branch_name: string | null;
  scheduled_at: string;
  duration_minutes: number;
  type: "in-person" | "teleconsult" | "follow-up";
  status: "scheduled" | "arrived" | "in-progress" | "completed" | "cancelled" | "no-show";
  chief_complaint: string | null;
  notes: string | null;
  cancelled_reason: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  // Legacy fields kept for admin table compatibility
  department?: string;
  appointment_date?: string;
  appointment_time?: string;
}

export interface AppointmentsListParams {
  date?: string;
  status?: string;
  upcoming?: boolean;
  all?: boolean;
  // Admin/legacy search params
  search?: string;
  page?: number;
  limit?: number;
}

export interface AppointmentsListResponse {
  data: Appointment[];
  total: number;
  // Legacy pagination fields for admin table
  appointments?: Appointment[];
  totalPages?: number;
  page?: number;
}

export interface CreateAppointmentData {
  patient_id: string;
  doctor_id?: string | null;
  clinic_id?: string | null;
  branch_id?: string | null;
  scheduled_at: string;
  duration_minutes?: number;
  type: "in-person" | "teleconsult" | "follow-up";
  chief_complaint?: string | null;
  notes?: string | null;
}

export interface UpdateAppointmentStatusData {
  status: "scheduled" | "arrived" | "in-progress" | "completed" | "cancelled" | "no-show";
  cancelled_reason?: string | null;
}

export interface UpdateAppointmentData {
  doctor_id?: string | null;
  clinic_id?: string | null;
  branch_id?: string | null;
  scheduled_at?: string;
  duration_minutes?: number;
  type?: "in-person" | "teleconsult" | "follow-up";
  chief_complaint?: string | null;
  notes?: string | null;
}

/**
 * Get list of appointments.
 * - Doctors get today's schedule by default (use date/upcoming params)
 * - Patients get their own appointments
 * - Admins with all=true get all appointments
 */
export async function getAppointments(
  params: AppointmentsListParams = {}
): Promise<AppointmentsListResponse> {
  const queryParams = new URLSearchParams();

  if (params.date) queryParams.append("date", params.date);
  if (params.status) queryParams.append("status", params.status);
  if (params.upcoming) queryParams.append("upcoming", "true");
  if (params.all) queryParams.append("all", "true");

  const response = await api.get(`/api/v1/appointments?${queryParams}`);
  const result = response.data as AppointmentsListResponse;

  // Provide legacy-compatible shape for the admin table which expects { appointments, totalPages }
  if (!result.appointments) {
    result.appointments = result.data;
    result.totalPages = 1;
    result.page = 1;
  }

  return result;
}

/**
 * Get appointment details by ID
 */
export async function getAppointment(id: string): Promise<Appointment> {
  const response = await api.get(`/api/v1/appointments/${id}`);
  return response.data;
}

/**
 * Create new appointment
 */
export async function createAppointment(
  data: CreateAppointmentData
): Promise<Appointment> {
  const response = await api.post("/api/v1/appointments", data);
  return response.data;
}

/**
 * Update appointment status
 */
export async function updateAppointmentStatus(
  id: string,
  data: UpdateAppointmentStatusData
): Promise<Appointment> {
  const response = await api.put(`/api/v1/appointments/${id}/status`, data);
  return response.data;
}

/**
 * Update appointment details (doctor, time, type, etc.). Only works for scheduled appointments.
 */
export async function updateAppointment(
  id: string,
  data: UpdateAppointmentData
): Promise<Appointment> {
  const response = await api.put(`/api/v1/appointments/${id}`, data);
  return response.data;
}

/**
 * Cancel appointment with optional reason.
 */
export async function cancelAppointment(id: string, reason?: string): Promise<void> {
  await api.put(`/api/v1/appointments/${id}/status`, {
    status: "cancelled",
    cancelled_reason: reason || null,
  });
}
