/**
 * Visit API Functions
 * Handles patient visit data operations
 */

import api from "../api";

export interface Visit {
  id: string;
  visit_id: string;
  patient_id: string;
  patient_name: string;
  patient_photo: string | null;
  doctor_id: string;
  doctor_name: string;
  doctor_photo: string | null;
  department: string;
  visit_date: string;
  visit_time?: string;
  status: "scheduled" | "in_progress" | "completed" | "cancelled";
  reason?: string;
  diagnosis?: string;
  treatment?: string;
  notes?: string;
  created_at?: string;
  updated_at?: string;
}

export interface VisitsListParams {
  search?: string;
  status?: string;
  department?: string;
  date?: string;
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

export interface CreateVisitData {
  patient_id: string;
  doctor_id: string;
  visit_date: string;
  visit_time?: string;
  reason?: string;
  notes?: string;
}

export interface UpdateVisitData {
  visit_date?: string;
  visit_time?: string;
  status?: "scheduled" | "in_progress" | "completed" | "cancelled";
  reason?: string;
  diagnosis?: string;
  treatment?: string;
  notes?: string;
}

/**
 * Get paginated list of visits
 */
export async function getVisits(
  params: VisitsListParams = {}
): Promise<VisitsListResponse> {
  const queryParams = new URLSearchParams();

  if (params.search) queryParams.append("search", params.search);
  if (params.status) queryParams.append("status", params.status);
  if (params.department) queryParams.append("department", params.department);
  if (params.date) queryParams.append("date", params.date);
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
 * Create new visit
 */
export async function createVisit(data: CreateVisitData): Promise<Visit> {
  const response = await api.post("/api/v1/admin/visits", data);
  return response.data;
}

/**
 * Update visit
 */
export async function updateVisit(
  id: string,
  data: UpdateVisitData
): Promise<Visit> {
  const response = await api.put(`/api/v1/admin/visits/${id}`, data);
  return response.data;
}

/**
 * Cancel visit (soft delete)
 */
export async function cancelVisit(id: string): Promise<void> {
  await api.delete(`/api/v1/admin/visits/${id}`);
}

/**
 * Get visit departments (for filters)
 */
export async function getVisitDepartments(): Promise<string[]> {
  const response = await api.get("/api/v1/admin/visits/departments");
  return response.data;
}
