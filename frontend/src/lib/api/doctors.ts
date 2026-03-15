/**
 * Doctor API Functions
 * Handles doctor data operations
 */

import api from "../api";

export interface Doctor {
  id: string;
  user_id: string;
  name: string;
  email: string | null;
  specialization: string | null;
  license_number: string | null;
  facility_name: string | null;
  facility_city: string | null;
  verified: boolean;
  created_at: string;
  // Legacy display fields kept for existing card components
  photo?: string | null;
  specialty?: string;
  experience?: number;
  appointmentsCount?: number;
  phone?: string;
  department?: string;
}

export interface AdminDoctorDetail {
  id: string;
  user_id: string;
  name: string;
  email: string | null;
  phone: string | null;
  specialization: string | null;
  license_number: string | null;
  facility_name: string | null;
  facility_city: string | null;
  verified: boolean;
  created_at: string;
  updated_at: string;
  is_active: boolean;
  prescriptions_count: number;
  records_count: number;
}

export interface DoctorsListParams {
  search?: string;
  specialty?: string;
  verified?: "true" | "false";
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

export interface DoctorVerifyRequest {
  action: "approve" | "reject";
  reason?: string;
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
  if (params.verified) queryParams.append("verified", params.verified);
  if (params.page) queryParams.append("page", params.page.toString());
  if (params.limit) queryParams.append("limit", params.limit.toString());

  const response = await api.get(`/api/v1/admin/doctors?${queryParams}`);
  return response.data;
}

/**
 * Get doctor details by ID (public endpoint)
 */
export async function getDoctor(id: string): Promise<Doctor> {
  const response = await api.get(`/api/v1/doctors/${id}`);
  return response.data;
}

/**
 * Get full doctor detail for admin review (MD-65)
 */
export async function getAdminDoctor(id: string): Promise<AdminDoctorDetail> {
  const response = await api.get(`/api/v1/admin/doctors/${id}`);
  return response.data;
}

/**
 * Approve or reject a doctor verification (MD-66)
 */
export async function verifyDoctor(
  id: string,
  body: DoctorVerifyRequest
): Promise<{ id: string; verified: boolean; message: string }> {
  const response = await api.put(`/api/v1/admin/doctors/${id}/verify`, body);
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
 * Get distinct specializations for filter dropdown
 */
export async function getDoctorSpecialties(): Promise<string[]> {
  const response = await api.get("/api/v1/admin/doctors/specialties");
  return response.data;
}

export interface DoctorPatient {
  id: string;
  full_name: string;
  email: string | null;
  phone: string | null;
}

export interface DoctorPatientsResponse {
  data: DoctorPatient[];
  total: number;
}

/**
 * Get patients linked to the currently authenticated doctor
 */
export async function getDoctorPatients(params: {
  search?: string;
  limit?: number;
} = {}): Promise<DoctorPatientsResponse> {
  const queryParams = new URLSearchParams();
  if (params.search) queryParams.append("search", params.search);
  if (params.limit) queryParams.append("limit", params.limit.toString());
  const response = await api.get(`/api/v1/doctors/patients?${queryParams}`);
  return response.data;
}
