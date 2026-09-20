/**
 * Visit API Functions
 * Admin-facing encounter/visit data operations (backed by /api/v1/admin/visits)
 */

import api from "../api";

export interface Visit {
  id: string;
  patient_id: string;
  patient_name: string | null;
  doctor_id: string;
  doctor_name: string | null;
  clinic_id: string | null;
  clinic_name: string | null;
  appointment_id: string | null;
  subjective: string | null;
  objective: string | null;
  assessment: string | null;
  plan: string | null;
  vitals_snapshot: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface VisitsListParams {
  search?: string;
  date?: string;
  patient_id?: string;
  doctor_id?: string;
  page?: number;
  limit?: number;
}

export interface VisitsListResponse {
  visits: Visit[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

/**
 * Get paginated list of visits (encounters)
 */
export async function getVisits(
  params: VisitsListParams = {}
): Promise<VisitsListResponse> {
  const queryParams = new URLSearchParams();

  if (params.search) queryParams.append("search", params.search);
  if (params.date) queryParams.append("date", params.date);
  if (params.patient_id) queryParams.append("patient_id", params.patient_id);
  if (params.doctor_id) queryParams.append("doctor_id", params.doctor_id);
  if (params.page) queryParams.append("page", params.page.toString());
  if (params.limit) queryParams.append("limit", params.limit.toString());

  const response = await api.get(`/api/v1/admin/visits?${queryParams}`);
  return response.data;
}

/**
 * Get visit details by ID
 */
export async function getVisit(id: string): Promise<Visit> {
  const response = await api.get(`/api/v1/admin/visits/${id}`);
  return response.data;
}

/**
 * Delete visit (soft delete)
 */
export async function deleteVisit(id: string): Promise<void> {
  await api.delete(`/api/v1/admin/visits/${id}`);
}
