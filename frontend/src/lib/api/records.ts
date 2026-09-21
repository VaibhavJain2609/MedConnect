/**
 * Medical Record API Functions
 * Patient-facing record version history (amendment chain).
 */

import api from "../api";

export interface RecordVersion {
  id: string;
  /** 1 = original record, 2..n = amendments in chronological order */
  version: number;
  is_latest: boolean;
  record_type: string;
  title: string;
  description: string | null;
  fhir_bundle: Record<string, unknown> | null;
  document_url: string | null;
  source: string;
  amended_from_id: string | null;
  doctor_id: string | null;
  doctor_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface RecordVersionsResponse {
  data: RecordVersion[];
  total: number;
  root_record_id: string;
}

/**
 * Get the full version chain (original + amendments) for one of the
 * current patient's records. `recordId` may be the original or any
 * amendment — the chain always resolves to the original.
 */
export async function getRecordVersions(
  recordId: string
): Promise<RecordVersionsResponse> {
  const response = await api.get(`/api/v1/patients/records/${recordId}/versions`);
  return response.data;
}
