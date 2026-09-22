/**
 * Family member (dependent profile) API functions.
 * Dependents are data profiles owned by the patient — not full user accounts.
 */

import api from "../api";

export type FamilyRelationship = "child" | "spouse" | "parent" | "sibling" | "other";

export const FAMILY_RELATIONSHIPS: FamilyRelationship[] = [
  "child",
  "spouse",
  "parent",
  "sibling",
  "other",
];

export interface FamilyMember {
  id: string;
  member_id: string;
  full_name: string;
  dob: string;
  /** Whole years elapsed since dob (computed server-side) */
  age: number;
  gender: string | null;
  relationship: FamilyRelationship;
  blood_group: string | null;
  notes: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface FamilyMemberInput {
  full_name: string;
  dob: string;
  relationship: FamilyRelationship;
  gender?: string | null;
  blood_group?: string | null;
  notes?: string | null;
}

export async function listFamilyMembers(): Promise<FamilyMember[]> {
  const res = await api.get("/api/v1/family/members");
  return res.data.data ?? [];
}

export async function createFamilyMember(
  input: FamilyMemberInput
): Promise<FamilyMember> {
  const res = await api.post("/api/v1/family/members", input);
  return res.data;
}

export async function updateFamilyMember(
  memberId: string,
  input: Partial<FamilyMemberInput>
): Promise<FamilyMember> {
  const res = await api.patch(`/api/v1/family/members/${memberId}`, input);
  return res.data;
}

export async function deleteFamilyMember(memberId: string): Promise<void> {
  await api.delete(`/api/v1/family/members/${memberId}`);
}
