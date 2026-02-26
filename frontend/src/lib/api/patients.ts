/**
 * Patient API Functions
 * Handles patient data operations
 */

import api from "../api";

export interface Patient {
  id: string;
  name: string;
  photo: string | null;
  status: "inProgress" | "completed" | "pending";
  statusLabel: string;
  lastVisit: string;
  gender: string;
  location: string;
  doctor: string;
  department: string;
  age: number;
  bloodType?: string;
  phone?: string;
  email?: string;
  address?: string;
  city?: string;
  state?: string;
  zipCode?: string;
  emergencyContact?: string;
  emergencyPhone?: string;
}

export interface PatientVital {
  id: string;
  name: string;
  value: string;
  unit: string;
  status: "normal" | "warning" | "critical";
  trend?: "up" | "down" | "stable";
  trendValue?: string;
  lastUpdated: string;
  normalRange?: { min: number; max: number };
}

export interface PatientVitalHistory {
  date: string;
  value: number;
}

export interface PatientAppointment {
  id: string;
  doctor: string;
  doctorPhoto: string | null;
  department: string;
  date: string;
  time: string;
  status: "upcoming" | "completed" | "cancelled";
  type: string;
  notes?: string;
}

export interface PatientsListParams {
  search?: string;
  status?: string;
  page?: number;
  limit?: number;
}

export interface PatientsListResponse {
  patients: Patient[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

/**
 * Get paginated list of patients
 */
export async function getPatients(
  params: PatientsListParams = {}
): Promise<PatientsListResponse> {
  const queryParams = new URLSearchParams();

  if (params.search) queryParams.append("search", params.search);
  if (params.status) queryParams.append("status", params.status);
  if (params.page) queryParams.append("page", params.page.toString());
  if (params.limit) queryParams.append("limit", params.limit.toString());

  const response = await api.get(`/api/v1/admin/patients?${queryParams}`);
  return response.data;
}

/**
 * Get patient details by ID
 */
export async function getPatient(id: string): Promise<Patient> {
  const response = await api.get(`/api/v1/patients/${id}`);
  return response.data;
}

/**
 * Get patient current vitals
 */
export async function getPatientVitals(id: string): Promise<PatientVital[]> {
  const response = await api.get(`/api/v1/patients/${id}/vitals`);
  return response.data;
}

/**
 * Get patient vitals history
 */
export async function getPatientVitalsHistory(
  id: string,
  vitalType: string
): Promise<PatientVitalHistory[]> {
  const response = await api.get(
    `/api/v1/patients/${id}/vitals/history?type=${vitalType}`
  );
  return response.data;
}

/**
 * Get patient appointments
 */
export async function getPatientAppointments(
  id: string
): Promise<PatientAppointment[]> {
  const response = await api.get(`/api/v1/patients/${id}/appointments`);
  return response.data;
}

/**
 * Create new patient
 */
export async function createPatient(data: Partial<Patient>): Promise<Patient> {
  const response = await api.post("/api/v1/admin/patients", data);
  return response.data;
}

/**
 * Update patient
 */
export async function updatePatient(
  id: string,
  data: Partial<Patient>
): Promise<Patient> {
  const response = await api.put(`/api/v1/admin/patients/${id}`, data);
  return response.data;
}

/**
 * Delete patient (soft delete)
 */
export async function deletePatient(id: string): Promise<void> {
  await api.delete(`/api/v1/admin/patients/${id}`);
}
