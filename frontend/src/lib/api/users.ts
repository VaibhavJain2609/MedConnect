/**
 * User API Functions
 * Handles user profile and authentication operations
 */

import api from "../api";

export interface UserProfile {
  id: string;
  email: string | null;
  phone: string | null;
  full_name: string;
  role: "patient" | "doctor" | "admin";
  language_pref: string;
  photo_url?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface UpdateProfileData {
  full_name?: string;
  phone?: string;
  language_pref?: string;
}

/**
 * Get current user profile
 */
export async function getMe(): Promise<UserProfile> {
  const response = await api.get("/api/v1/auth/me");
  return response.data;
}

/**
 * Update current user profile
 */
export async function updateProfile(
  data: UpdateProfileData
): Promise<UserProfile> {
  const response = await api.put("/api/v1/users/me", data);
  return response.data;
}

/**
 * Upload user photo
 * @param file - Image file to upload
 * @returns Updated user profile with new photo URL
 */
export async function uploadPhoto(file: File): Promise<UserProfile> {
  const formData = new FormData();
  formData.append("photo", file);

  const response = await api.post("/api/v1/users/photo", formData);

  return response.data;
}

/**
 * Delete user photo
 */
export async function deletePhoto(): Promise<UserProfile> {
  const response = await api.delete("/api/v1/users/photo");
  return response.data;
}

/**
 * Verify user has specific role
 */
export function hasRole(user: UserProfile | null, role: string): boolean {
  if (!user) return false;
  return user.role === role;
}

/**
 * Check if user has admin privileges
 */
export function isAdmin(user: UserProfile | null): boolean {
  return hasRole(user, "admin");
}

/**
 * Check if user has doctor privileges
 */
export function isDoctor(user: UserProfile | null): boolean {
  return hasRole(user, "doctor");
}

/**
 * Check if user has patient privileges
 */
export function isPatient(user: UserProfile | null): boolean {
  return hasRole(user, "patient");
}
