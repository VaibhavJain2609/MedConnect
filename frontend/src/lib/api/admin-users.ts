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
}

export interface AdminUserUpdateResponse {
  id: string;
  full_name: string;
  is_active: boolean;
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

export async function toggleUserActive(
  id: string,
  isActive: boolean
): Promise<AdminUserUpdateResponse> {
  const response = await api.put(`/api/v1/admin/users/${id}`, {
    is_active: isActive,
  });
  return response.data;
}
