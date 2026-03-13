import api from '@/lib/api'

// ── Types ────────────────────────────────────────────────────────────────

export interface ClinicBranch {
  id: string
  clinic_id: string
  name: string
  address: string | null
  city: string | null
  state: string | null
  phone: string | null
  is_active: boolean
  created_at: string
}

export interface Clinic {
  id: string
  name: string
  address: string | null
  city: string | null
  state: string | null
  phone: string | null
  email: string | null
  logo_url: string | null
  is_active: boolean
  record_sharing_mode: 'per_clinic' | 'per_doctor'
  created_by: string | null
  created_at: string
  updated_at: string
}

export interface ClinicMember {
  id: string
  user_id: string
  full_name: string
  email: string | null
  role: 'owner' | 'admin' | 'doctor'
  branch_id: string | null
  is_active: boolean
  joined_at: string
}

export interface ClinicListResponse {
  data: Clinic[]
  total: number
}

export interface ClinicMemberListResponse {
  data: ClinicMember[]
  total: number
}

export interface AdminClinicListItem {
  id: string
  name: string
  city: string | null
  state: string | null
  is_active: boolean
  record_sharing_mode: string
  member_count: number
  created_at: string
}

export interface AdminClinicDetail extends Clinic {
  member_count: number
  record_count: number
  prescription_count: number
  branches: ClinicBranch[]
}

export interface AdminClinicsListResponse {
  data: AdminClinicListItem[]
  total: number
  page: number
  limit: number
  totalPages: number
}

// ── Doctor-facing API ─────────────────────────────────────────────────────

export async function createClinic(data: {
  name: string
  address?: string
  city?: string
  state?: string
  phone?: string
  email?: string
}): Promise<Clinic> {
  const res = await api.post('/api/v1/clinics', data)
  return res.data
}

export async function getMyClinicss(): Promise<ClinicListResponse> {
  const res = await api.get('/api/v1/clinics/my')
  return res.data
}

export async function getClinic(id: string): Promise<Clinic> {
  const res = await api.get(`/api/v1/clinics/${id}`)
  return res.data
}

export async function updateClinic(id: string, data: Partial<Clinic>): Promise<Clinic> {
  const res = await api.put(`/api/v1/clinics/${id}`, data)
  return res.data
}

export async function getClinicMembers(id: string): Promise<ClinicMemberListResponse> {
  const res = await api.get(`/api/v1/clinics/${id}/members`)
  return res.data
}

export async function updateClinicSettings(
  id: string,
  record_sharing_mode: 'per_clinic' | 'per_doctor'
): Promise<Clinic> {
  const res = await api.put(`/api/v1/clinics/${id}/settings`, { record_sharing_mode })
  return res.data
}

export async function createBranch(
  clinicId: string,
  data: { name: string; address?: string; city?: string; state?: string; phone?: string }
): Promise<ClinicBranch> {
  const res = await api.post(`/api/v1/clinics/${clinicId}/branches`, data)
  return res.data
}

// ── Admin API ─────────────────────────────────────────────────────────────

export interface ClinicCreatePayload {
  name: string
  address?: string
  city?: string
  state?: string
  phone?: string
  email?: string
}

export async function createAdminClinic(data: ClinicCreatePayload): Promise<AdminClinicDetail> {
  const res = await api.post('/api/v1/admin/clinics', data)
  return res.data
}

export async function getAdminClinics(params?: {
  search?: string
  is_active?: boolean
  page?: number
  limit?: number
}): Promise<AdminClinicsListResponse> {
  const res = await api.get('/api/v1/admin/clinics', { params })
  return res.data
}

export async function getAdminClinic(id: string): Promise<AdminClinicDetail> {
  const res = await api.get(`/api/v1/admin/clinics/${id}`)
  return res.data
}

export async function updateAdminClinic(id: string, data: Partial<Clinic>): Promise<AdminClinicDetail> {
  const res = await api.put(`/api/v1/admin/clinics/${id}`, data)
  return res.data
}

export async function deleteAdminClinic(id: string): Promise<void> {
  await api.delete(`/api/v1/admin/clinics/${id}`)
}
