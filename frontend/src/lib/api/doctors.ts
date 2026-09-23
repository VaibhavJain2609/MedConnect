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
  /** Storage object key for the uploaded license document (download via /api/v1/uploads/{key}) */
  license_document_url?: string | null;
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
  /** Storage object key for the uploaded license document (download via /api/v1/uploads/{key}) */
  license_document_url: string | null;
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

/** Own doctor profile (GET /api/v1/doctors/profile). */
export interface DoctorProfile {
  id: string;
  user_id: string;
  specialization: string | null;
  license_number: string | null;
  facility_name: string | null;
  facility_city: string | null;
  verified: boolean;
}

/**
 * Get the authenticated doctor's profile — the `id` here is the Doctor
 * profile id used by availability/slot endpoints (not the User id).
 */
export async function getMyDoctorProfile(): Promise<DoctorProfile> {
  const response = await api.get("/api/v1/doctors/profile");
  return response.data;
}

/**
 * Doctor analytics payload (GET /api/v1/doctors/analytics).
 * Everything is scoped to the authenticated doctor.
 */
export interface DoctorAnalytics {
  /** All-time appointment counts keyed by status. */
  appointments_by_status: Record<string, number>;
  /** Completed appointments per ISO week, oldest → newest (8 entries). */
  weekly_completions: { week_start: string; count: number }[];
  /** Mean queue consultation time; absent when not derivable. */
  avg_consult_minutes?: number;
  /** Up to 10 most-prescribed medicine names. */
  top_medicines: { name: string; count: number }[];
  /** Today's queue counts — only present with an active clinic context. */
  queue_today?: {
    waiting: number;
    in_consultation: number;
    completed: number;
    cancelled: number;
    total: number;
  };
}

/**
 * Get aggregated analytics for the authenticated doctor.
 * Passes X-Clinic-Id automatically via the api interceptor when a clinic is
 * selected, which enables the `queue_today` section of the response.
 */
export async function getDoctorAnalytics(): Promise<DoctorAnalytics> {
  const response = await api.get("/api/v1/doctors/analytics");
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
  pagination: { next_cursor: string | null; has_more: boolean; limit: number };
}

/**
 * Get patients linked to the currently authenticated doctor
 */
export async function getDoctorPatients(params: {
  search?: string;
  limit?: number;
  cursor?: string;
} = {}): Promise<DoctorPatientsResponse> {
  const queryParams = new URLSearchParams();
  if (params.search) queryParams.append("search", params.search);
  if (params.limit) queryParams.append("limit", params.limit.toString());
  if (params.cursor) queryParams.append("cursor", params.cursor);
  const response = await api.get(`/api/v1/doctors/patients?${queryParams}`);
  return response.data;
}
