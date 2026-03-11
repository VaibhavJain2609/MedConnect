/**
 * Dashboard Statistics API Functions
 * Handles dashboard metrics and analytics
 */

import api from "../api";

export interface DashboardStats {
  total_patients: number;
  total_doctors: number;
  verified_doctors: number;
  unverified_doctors: number;
  total_records: number;
  total_prescriptions: number;
  total_medicines: number;
  patient_trend?: number;
  record_trend?: number;
  prescription_trend?: number;
  doctor_trend?: number;
}

export interface TrendDataPoint {
  date: string;
  value: number;
}

export interface PatientStatistics {
  date: string;
  new_patients: number;
  returning_patients: number;
}

export interface AppointmentRequest {
  id: string;
  patient_id: string;
  patient_name: string;
  patient_photo: string | null;
  doctor_id: string;
  doctor_name: string;
  department: string;
  requested_date: string;
  requested_time: string;
  status: "pending" | "approved" | "rejected";
  created_at: string;
}

export interface StatsParams {
  start_date?: string;
  end_date?: string;
}

/**
 * Get dashboard statistics
 */
export async function getDashboardStats(
  params: StatsParams = {}
): Promise<DashboardStats> {
  const queryParams = new URLSearchParams();

  if (params.start_date) {
    queryParams.append("start_date", params.start_date);
  }
  if (params.end_date) {
    queryParams.append("end_date", params.end_date);
  }

  const response = await api.get(`/api/v1/admin/stats?${queryParams}`);
  return response.data;
}

/**
 * Get patient trend data for sparklines
 */
export async function getPatientTrend(
  params: StatsParams = {}
): Promise<TrendDataPoint[]> {
  const queryParams = new URLSearchParams();

  if (params.start_date) {
    queryParams.append("start_date", params.start_date);
  }
  if (params.end_date) {
    queryParams.append("end_date", params.end_date);
  }

  const response = await api.get(
    `/api/v1/admin/stats/patient-trend?${queryParams}`
  );
  return response.data.trend || [];
}

/**
 * Get medical record trend data for sparklines
 */
export async function getRecordTrend(
  params: StatsParams = {}
): Promise<TrendDataPoint[]> {
  const queryParams = new URLSearchParams();

  if (params.start_date) {
    queryParams.append("start_date", params.start_date);
  }
  if (params.end_date) {
    queryParams.append("end_date", params.end_date);
  }

  const response = await api.get(
    `/api/v1/admin/stats/record-trend?${queryParams}`
  );
  return response.data.trend || [];
}

/**
 * Get doctor trend data for sparklines
 */
export async function getDoctorTrend(
  params: StatsParams = {}
): Promise<TrendDataPoint[]> {
  const queryParams = new URLSearchParams();

  if (params.start_date) {
    queryParams.append("start_date", params.start_date);
  }
  if (params.end_date) {
    queryParams.append("end_date", params.end_date);
  }

  const response = await api.get(
    `/api/v1/admin/stats/doctor-trend?${queryParams}`
  );
  return response.data.trend || [];
}

/**
 * Get prescription trend data for sparklines
 */
export async function getPrescriptionTrend(
  params: StatsParams = {}
): Promise<TrendDataPoint[]> {
  const queryParams = new URLSearchParams();

  if (params.start_date) {
    queryParams.append("start_date", params.start_date);
  }
  if (params.end_date) {
    queryParams.append("end_date", params.end_date);
  }

  const response = await api.get(
    `/api/v1/admin/stats/prescription-trend?${queryParams}`
  );
  return response.data.trend || [];
}

/**
 * Get patient statistics for chart (new vs returning)
 */
export async function getPatientStatistics(
  params: StatsParams = {}
): Promise<PatientStatistics[]> {
  const queryParams = new URLSearchParams();

  if (params.start_date) {
    queryParams.append("start_date", params.start_date);
  }
  if (params.end_date) {
    queryParams.append("end_date", params.end_date);
  }

  const response = await api.get(
    `/api/v1/admin/stats/patient-statistics?${queryParams}`
  );
  return response.data.statistics || [];
}

/**
 * Get pending appointment requests
 */
export async function getAppointmentRequests(
  limit = 5
): Promise<AppointmentRequest[]> {
  const response = await api.get(
    `/api/v1/admin/appointment-requests?limit=${limit}`
  );
  return response.data.requests || [];
}

/**
 * Approve appointment request
 */
export async function approveAppointmentRequest(
  id: string
): Promise<AppointmentRequest> {
  const response = await api.post(
    `/api/v1/admin/appointment-requests/${id}/approve`
  );
  return response.data;
}

/**
 * Reject appointment request
 */
export async function rejectAppointmentRequest(
  id: string,
  reason?: string
): Promise<AppointmentRequest> {
  const response = await api.post(
    `/api/v1/admin/appointment-requests/${id}/reject`,
    { reason }
  );
  return response.data;
}

/**
 * Export dashboard report
 */
export async function exportReport(
  format: "csv" | "pdf",
  params: StatsParams = {}
): Promise<Blob> {
  const queryParams = new URLSearchParams();

  queryParams.append("format", format);
  if (params.start_date) {
    queryParams.append("start_date", params.start_date);
  }
  if (params.end_date) {
    queryParams.append("end_date", params.end_date);
  }

  const response = await api.get(
    `/api/v1/admin/reports/export?${queryParams}`,
    {
      responseType: "blob",
    }
  );

  return response.data;
}

/**
 * Download exported report
 */
export function downloadReport(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}
