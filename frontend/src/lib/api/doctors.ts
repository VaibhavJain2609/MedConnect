/**
 * Doctor API Functions
 * Handles doctor data operations
 */

import api from "../api";

export interface Doctor {
  id: string;
  name: string;
  photo: string | null;
  specialty: string;
  experience: number;
  appointmentsCount: number;
  email: string;
  phone: string;
  department: string;
}

export interface DoctorsListParams {
  search?: string;
  specialty?: string;
  page?: number;
  limit?: number;
}

export interface DoctorsListResponse {
  doctors: Doctor[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

/**
 * Get paginated list of doctors
 */
export async function getDoctors(
  params: DoctorsListParams = {}
): Promise<DoctorsListResponse> {
  const queryParams = new URLSearchParams();

  if (params.search) queryParams.append("search", params.search);
  if (params.specialty) queryParams.append("specialty", params.specialty);
  if (params.page) queryParams.append("page", params.page.toString());
  if (params.limit) queryParams.append("limit", params.limit.toString());

  const response = await api.get(`/api/v1/admin/doctors?${queryParams}`);
  return response.data;
}

/**
 * Get doctor details by ID
 */
export async function getDoctor(id: string): Promise<Doctor> {
  const response = await api.get(`/api/v1/doctors/${id}`);
  return response.data;
}

/**
 * Create new doctor
 */
export async function createDoctor(data: Partial<Doctor>): Promise<Doctor> {
  const response = await api.post("/api/v1/admin/doctors", data);
  return response.data;
}

/**
 * Update doctor
 */
export async function updateDoctor(
  id: string,
  data: Partial<Doctor>
): Promise<Doctor> {
  const response = await api.put(`/api/v1/admin/doctors/${id}`, data);
  return response.data;
}

/**
 * Delete doctor (soft delete)
 */
export async function deleteDoctor(id: string): Promise<void> {
  await api.delete(`/api/v1/admin/doctors/${id}`);
}

/**
 * Get doctor's specialties (for filters)
 */
export async function getDoctorSpecialties(): Promise<string[]> {
  const response = await api.get("/api/v1/admin/doctors/specialties");
  return response.data;
}
