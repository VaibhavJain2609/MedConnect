/**
 * Lab Orders API Functions
 * Doctor-initiated lab test orders (POST/GET/PATCH /api/v1/lab-orders)
 */

import api from "../api";

export type LabOrderStatus = "ordered" | "completed" | "cancelled";

export interface LabOrder {
  id: string;
  patient_id: string;
  doctor_id: string;
  clinic_id: string | null;
  test_name: string;
  notes: string | null;
  status: LabOrderStatus;
  result_record_id: string | null;
  doctor_name?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateLabOrderData {
  patient_id: string;
  test_name: string;
  notes?: string;
}

export interface LabOrdersListParams {
  patient_id?: string;
  status?: LabOrderStatus;
  limit?: number;
}

/** POST /api/v1/lab-orders — doctor only; requires an active patient relationship. */
export async function createLabOrder(data: CreateLabOrderData): Promise<LabOrder> {
  const response = await api.post<LabOrder>("/api/v1/lab-orders", data);
  return response.data;
}

/** GET /api/v1/lab-orders — the calling doctor's own orders. */
export async function getDoctorLabOrders(
  params: LabOrdersListParams = {}
): Promise<{ data: LabOrder[] }> {
  const response = await api.get<{ data: LabOrder[] }>("/api/v1/lab-orders", {
    params: {
      patient_id: params.patient_id,
      status: params.status,
      limit: params.limit,
    },
  });
  return response.data;
}

/** GET /api/v1/lab-orders/mine — the calling patient's own orders. */
export async function getMyLabOrders(): Promise<{ data: LabOrder[] }> {
  const response = await api.get<{ data: LabOrder[] }>("/api/v1/lab-orders/mine");
  return response.data;
}

/** PATCH /api/v1/lab-orders/{id}/status — ordered → completed | cancelled. */
export async function updateLabOrderStatus(
  id: string,
  data: { status: "completed" | "cancelled"; result_record_id?: string }
): Promise<LabOrder> {
  const response = await api.patch<LabOrder>(
    `/api/v1/lab-orders/${id}/status`,
    data
  );
  return response.data;
}
