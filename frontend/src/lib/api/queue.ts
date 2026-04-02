import api from "@/lib/api";

export interface QueueEntry {
  id: string;
  clinic_id: string;
  branch_id: string | null;
  patient_id: string;
  patient_name: string | null;
  doctor_id: string | null;
  doctor_name: string | null;
  appointment_id: string | null;
  queue_number: number;
  status: "waiting" | "in_consultation" | "completed" | "cancelled";
  notes: string | null;
  called_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface QueueListResponse {
  data: QueueEntry[];
  total: number;
}

export async function getQueue(
  clinicId: string,
  params?: { status?: string; doctor_id?: string }
): Promise<QueueListResponse> {
  const res = await api.get("/api/v1/queue", {
    headers: { "X-Clinic-Id": clinicId },
    params,
  });
  return res.data;
}

export async function addToQueue(
  clinicId: string,
  data: {
    patient_id: string;
    doctor_id?: string;
    appointment_id?: string;
    notes?: string;
  }
): Promise<QueueEntry> {
  const res = await api.post("/api/v1/queue", data, {
    headers: { "X-Clinic-Id": clinicId },
  });
  return res.data;
}

export async function updateQueueStatus(
  clinicId: string,
  entryId: string,
  status: "in_consultation" | "completed" | "cancelled"
): Promise<QueueEntry> {
  const res = await api.patch(
    `/api/v1/queue/${entryId}/status`,
    { status },
    { headers: { "X-Clinic-Id": clinicId } }
  );
  return res.data;
}

export async function removeFromQueue(
  clinicId: string,
  entryId: string
): Promise<void> {
  await api.delete(`/api/v1/queue/${entryId}`, {
    headers: { "X-Clinic-Id": clinicId },
  });
}
