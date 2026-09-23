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

/**
 * Patient-facing live queue position (GET /api/v1/queue/my-position).
 * All fields are null/empty when the patient isn't checked in anywhere today.
 */
export interface MyQueuePosition {
  queue_entry_id: string | null;
  clinic_id: string | null;
  clinic_name: string | null;
  doctor_name: string | null;
  queue_number: number | null;
  position: number | null;
  status: QueueEntry["status"] | null;
  ahead_count: number;
  estimated_wait_minutes: number | null;
}

export async function getMyQueuePosition(): Promise<MyQueuePosition> {
  const res = await api.get("/api/v1/queue/my-position");
  return res.data;
}

/**
 * Anonymized waiting-room board (GET /api/v1/queue/display).
 * Token labels only — the payload carries no patient identifiers, names,
 * or notes, so it is safe to render on a public-facing TV.
 */
export interface QueueDisplayToken {
  token: string; // e.g. "Q-12"
  status: "waiting" | "in_consultation";
  position: number | null; // 1-based place among waiting entries
  called_at: string | null;
}

export interface QueueDisplayResponse {
  now_serving: QueueDisplayToken[];
  up_next: QueueDisplayToken[];
  waiting_count: number; // total waiting (up_next may be truncated by limit)
  generated_at: string;
}

export async function getQueueDisplay(limit = 8): Promise<QueueDisplayResponse> {
  // X-Clinic-Id is attached automatically by the axios interceptor.
  const res = await api.get("/api/v1/queue/display", { params: { limit } });
  return res.data;
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
