/**
 * Appointment API Functions
 * Handles appointment data operations
 */

import api from "../api";

export interface Appointment {
  id: string;
  patient_id: string;
  patient_name: string;
  patient_photo: string | null;
  doctor_id: string;
  doctor_name: string;
  doctor_photo: string | null;
  department: string;
  appointment_date: string;
  appointment_time: string;
  status: "upcoming" | "in_progress" | "completed" | "cancelled";
  type: string;
  notes?: string;
  created_at?: string;
  updated_at?: string;
}

export interface AppointmentsListParams {
  search?: string;
  status?: string;
  department?: string;
  date?: string;
  page?: number;
  limit?: number;
}

export interface AppointmentsListResponse {
  appointments: Appointment[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

export interface CreateAppointmentData {
  patient_id: string;
  doctor_id: string;
  appointment_date: string;
  appointment_time: string;
  type: string;
  notes?: string;
}

export interface UpdateAppointmentData {
  appointment_date?: string;
  appointment_time?: string;
  status?: "upcoming" | "in_progress" | "completed" | "cancelled";
  type?: string;
  notes?: string;
}

/**
 * Get paginated list of appointments
 */
export async function getAppointments(
  params: AppointmentsListParams = {}
): Promise<AppointmentsListResponse> {
  const queryParams = new URLSearchParams();

  if (params.search) queryParams.append("search", params.search);
  if (params.status) queryParams.append("status", params.status);
  if (params.department) queryParams.append("department", params.department);
  if (params.date) queryParams.append("date", params.date);
  if (params.page) queryParams.append("page", params.page.toString());
  if (params.limit) queryParams.append("limit", params.limit.toString());

  const response = await api.get(`/api/v1/admin/appointments?${queryParams}`);
  return response.data;
}

/**
 * Get appointment details by ID
 */
export async function getAppointment(id: string): Promise<Appointment> {
  const response = await api.get(`/api/v1/admin/appointments/${id}`);
  return response.data;
}

/**
 * Create new appointment
 */
export async function createAppointment(
  data: CreateAppointmentData
): Promise<Appointment> {
  const response = await api.post("/api/v1/admin/appointments", data);
  return response.data;
}

/**
 * Update appointment
 */
export async function updateAppointment(
  id: string,
  data: UpdateAppointmentData
): Promise<Appointment> {
  const response = await api.put(`/api/v1/admin/appointments/${id}`, data);
  return response.data;
}

/**
 * Cancel appointment (soft delete)
 */
export async function cancelAppointment(id: string): Promise<void> {
  await api.delete(`/api/v1/admin/appointments/${id}`);
}

/**
 * Get appointment departments (for filters)
 */
export async function getAppointmentDepartments(): Promise<string[]> {
  const response = await api.get("/api/v1/admin/appointments/departments");
  return response.data;
}
