/**
 * Encounter API Functions
 * Doctor-facing SOAP encounter (visit note) operations
 */

import api from "../api";
import type { Appointment } from "./appointments";

export interface FollowUpSummary {
  id: string;
  scheduled_at: string;
  duration_minutes: number;
  type: "in-person" | "teleconsult" | "follow-up";
  status: "scheduled" | "arrived" | "in-progress" | "completed" | "cancelled" | "no-show";
  notes: string | null;
}

export interface Encounter {
  id: string;
  patient_id: string;
  patient_name: string | null;
  doctor_id: string;
  doctor_name: string | null;
  appointment_id: string | null;
  clinic_id: string | null;
  clinic_name: string | null;
  subjective: string | null;
  objective: string | null;
  assessment: string | null;
  plan: string | null;
  vitals_snapshot: Record<string, unknown> | null;
  follow_up: FollowUpSummary | null;
  created_at: string;
  updated_at: string;
}

export interface EncountersListParams {
  patient_id?: string;
  appointment_id?: string;
  date?: string; // YYYY-MM-DD
  limit?: number;
  offset?: number;
}

export interface EncountersListResponse {
  data: Encounter[];
  total: number;
  limit: number;
  offset: number;
}

export interface CreateEncounterData {
  patient_id: string;
  appointment_id?: string | null;
  clinic_id?: string | null;
  subjective?: string | null;
  objective?: string | null;
  assessment?: string | null;
  plan?: string | null;
  vitals_snapshot?: Record<string, unknown> | null;
}

export interface UpdateEncounterData {
  appointment_id?: string | null;
  clinic_id?: string | null;
  subjective?: string | null;
  objective?: string | null;
  assessment?: string | null;
  plan?: string | null;
  vitals_snapshot?: Record<string, unknown> | null;
}

/**
 * List encounters (doctor: own, patient: own, admin: all)
 */
export async function getEncounters(
  params: EncountersListParams = {}
): Promise<EncountersListResponse> {
  const queryParams = new URLSearchParams();

  if (params.patient_id) queryParams.append("patient_id", params.patient_id);
  if (params.appointment_id)
    queryParams.append("appointment_id", params.appointment_id);
  if (params.date) queryParams.append("date", params.date);
  if (params.limit) queryParams.append("limit", params.limit.toString());
  if (params.offset) queryParams.append("offset", params.offset.toString());

  const response = await api.get(`/api/v1/encounters?${queryParams}`);
  return response.data;
}

/**
 * Get a single encounter by ID
 */
export async function getEncounter(id: string): Promise<Encounter> {
  const response = await api.get(`/api/v1/encounters/${id}`);
  return response.data;
}

/**
 * Create a new encounter (verified doctor)
 */
export async function createEncounter(
  data: CreateEncounterData
): Promise<Encounter> {
  const response = await api.post("/api/v1/encounters", data);
  return response.data;
}

/**
 * Update an encounter (authoring doctor only)
 */
export async function updateEncounter(
  id: string,
  data: UpdateEncounterData
): Promise<Encounter> {
  const response = await api.patch(`/api/v1/encounters/${id}`, data);
  return response.data;
}

/**
 * Soft-delete an encounter (author or admin)
 */
export async function deleteEncounter(id: string): Promise<void> {
  await api.delete(`/api/v1/encounters/${id}`);
}

export interface CreateFollowUpData {
  /** Combined date+time, ISO-8601 (naive values treated as UTC). */
  scheduled_at: string;
  duration_minutes?: number;
  type?: "in-person" | "teleconsult" | "follow-up";
  notes?: string | null;
}

/**
 * Book a follow-up appointment from an encounter (verified doctor; author or
 * clinic member). Idempotent — returns the existing follow-up appointment
 * when one is already linked to the encounter.
 */
export async function createEncounterFollowUp(
  encounterId: string,
  data: CreateFollowUpData
): Promise<Appointment> {
  const response = await api.post(
    `/api/v1/encounters/${encounterId}/follow-up`,
    data
  );
  return response.data;
}
