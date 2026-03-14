import api from "@/lib/api";

export interface AdminUserListItem {
  id: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface AdminUsersListResponse {
  data: AdminUserListItem[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

export interface AdminUserDetail extends AdminUserListItem {
  language_pref: string;
  blood_group: string | null;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
  updated_at: string;
  doctor_profile: {
    id: string;
    user_id: string;
    specialization: string | null;
    license_number: string | null;
    facility_name: string | null;
    facility_city: string | null;
    verified: boolean;
  } | null;
  records_count: number;
  prescriptions_count: number;
  allergies: string[] | null;
  chronic_conditions: string[] | null;
  height_cm: number | null;
  weight_kg: number | null;
  last_visit: string | null;
}

export interface AdminUserPrescriptionItem {
  id: string;
  doctor_name: string;
  diagnosis: string | null;
  notes: string | null;
  medicines: Record<string, any>;
  valid_until: string | null;
  created_at: string;
}

export interface AdminUserPrescriptionsResponse {
  data: AdminUserPrescriptionItem[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

export interface AdminUserRecordItem {
  id: string;
  record_type: string;
  title: string;
  description: string | null;
  source: string;
  doctor_name: string | null;
  created_at: string;
}

export interface AdminUserRecordsResponse {
  data: AdminUserRecordItem[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

export interface AdminUserUpdateRequest {
  full_name?: string;
  email?: string;
  phone?: string;
  role?: string;
  is_active?: boolean;
  language_pref?: string;
}

export interface AdminUserUpdateResponse {
  id: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  role: string;
  is_active: boolean;
  language_pref: string;
  message: string;
}

export interface AdminUserDeleteResponse {
  id: string;
  message: string;
}

export async function getAdminUsers(params?: {
  search?: string;
  role?: string;
  is_active?: boolean;
  page?: number;
  limit?: number;
}): Promise<AdminUsersListResponse> {
  const response = await api.get("/api/v1/admin/users", { params });
  return response.data;
}

export async function getAdminUser(id: string): Promise<AdminUserDetail> {
  const response = await api.get(`/api/v1/admin/users/${id}`);
  return response.data;
}

export async function updateAdminUser(
  id: string,
  data: AdminUserUpdateRequest
): Promise<AdminUserUpdateResponse> {
  const response = await api.put(`/api/v1/admin/users/${id}`, data);
  return response.data;
}

export async function toggleUserActive(
  id: string,
  isActive: boolean
): Promise<AdminUserUpdateResponse> {
  return updateAdminUser(id, { is_active: isActive });
}

export async function deleteAdminUser(
  id: string
): Promise<AdminUserDeleteResponse> {
  const response = await api.delete(`/api/v1/admin/users/${id}`);
  return response.data;
}

export async function getAdminUserPrescriptions(
  userId: string,
  params?: { page?: number; limit?: number }
): Promise<AdminUserPrescriptionsResponse> {
  const response = await api.get(`/api/v1/admin/users/${userId}/prescriptions`, { params });
  return response.data;
}

export async function getAdminUserRecords(
  userId: string,
  params?: { page?: number; limit?: number }
): Promise<AdminUserRecordsResponse> {
  const response = await api.get(`/api/v1/admin/users/${userId}/records`, { params });
  return response.data;
}
