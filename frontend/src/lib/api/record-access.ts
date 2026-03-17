import api from "@/lib/api";

export interface RecordAccessConsent {
  id: string;
  status: "pending" | "approved" | "rejected" | "revoked";
  purpose: string | null;
  access_duration_days: number;
  expires_at: string | null;
  consented_at: string | null;
  created_at: string;
  doctor_name?: string;
  doctor_specialization?: string | null;
  clinic_name?: string;
  patient_id?: string;
}

export async function requestRecordAccess(
  patientId: string,
  body: { purpose?: string; access_duration_days?: number }
): Promise<RecordAccessConsent> {
  const res = await api.post(
    `/api/v1/doctors/patients/${patientId}/record-access`,
    body
  );
  return res.data;
}

export async function getMyRecordAccessConsent(
  patientId: string
): Promise<RecordAccessConsent | null> {
  const res = await api.get(
    `/api/v1/doctors/patients/${patientId}/record-access`
  );
  return res.data;
}

export async function getPatientRecordAccessRequests(params?: {
  status?: string;
}): Promise<{ data: RecordAccessConsent[] }> {
  const res = await api.get("/api/v1/patients/record-access-requests", {
    params,
  });
  return res.data;
}

export async function actOnRecordAccessRequest(
  consentId: string,
  action: "approved" | "rejected" | "revoked"
): Promise<RecordAccessConsent> {
  const res = await api.put(
    `/api/v1/patients/record-access-requests/${consentId}`,
    { action }
  );
  return res.data;
}
