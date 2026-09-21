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

/**
 * Get current user profile
 */
export async function getMe(): Promise<UserProfile> {
  const response = await api.get("/api/v1/auth/me");
  return response.data;
}

