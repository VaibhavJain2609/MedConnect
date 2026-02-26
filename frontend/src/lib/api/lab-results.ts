/**
 * Lab Results API Functions
 * Handles laboratory test results data operations
 */

import api from "../api";

export interface LabResult {
  id: string;
  test_id: string;
  patient_id: string;
  patient_name: string;
  patient_photo: string | null;
  gender: string;
  appointment_date: string;
  doctor_id: string;
  doctor_name: string;
  doctor_photo: string | null;
  test_name: string;
  test_category?: string;
  status: "received" | "in_progress" | "completed" | "pending";
  result_value?: string;
  result_unit?: string;
  normal_range?: string;
  abnormal_flag?: boolean;
  notes?: string;
  created_at?: string;
  updated_at?: string;
}

export interface LabResultsListParams {
  search?: string;
  status?: string;
  test_category?: string;
  date?: string;
  page?: number;
  limit?: number;
}

export interface LabResultsListResponse {
  results: LabResult[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

export interface CreateLabResultData {
  patient_id: string;
  doctor_id: string;
  test_name: string;
  test_category?: string;
  appointment_date: string;
  notes?: string;
}

export interface UpdateLabResultData {
  status?: "received" | "in_progress" | "completed" | "pending";
  result_value?: string;
  result_unit?: string;
  normal_range?: string;
  abnormal_flag?: boolean;
  notes?: string;
}

/**
 * Get paginated list of lab results
 */
export async function getLabResults(
  params: LabResultsListParams = {}
): Promise<LabResultsListResponse> {
  const queryParams = new URLSearchParams();

  if (params.search) queryParams.append("search", params.search);
  if (params.status) queryParams.append("status", params.status);
  if (params.test_category)
    queryParams.append("test_category", params.test_category);
  if (params.date) queryParams.append("date", params.date);
  if (params.page) queryParams.append("page", params.page.toString());
  if (params.limit) queryParams.append("limit", params.limit.toString());

  const response = await api.get(`/api/v1/admin/lab-results?${queryParams}`);
  return response.data;
}

/**
 * Get lab result details by ID
 */
export async function getLabResult(id: string): Promise<LabResult> {
  const response = await api.get(`/api/v1/admin/lab-results/${id}`);
  return response.data;
}

/**
 * Create new lab result order
 */
export async function createLabResult(
  data: CreateLabResultData
): Promise<LabResult> {
  const response = await api.post("/api/v1/admin/lab-results", data);
  return response.data;
}

/**
 * Update lab result
 */
export async function updateLabResult(
  id: string,
  data: UpdateLabResultData
): Promise<LabResult> {
  const response = await api.put(`/api/v1/admin/lab-results/${id}`, data);
  return response.data;
}

/**
 * Delete lab result (soft delete)
 */
export async function deleteLabResult(id: string): Promise<void> {
  await api.delete(`/api/v1/admin/lab-results/${id}`);
}

/**
 * Get lab test categories (for filters)
 */
export async function getLabTestCategories(): Promise<string[]> {
  const response = await api.get("/api/v1/admin/lab-results/categories");
  return response.data;
}
