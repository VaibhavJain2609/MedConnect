/**
 * Search API Functions
 * Handles global search operations
 */

import api from "../api";

export interface SearchResult {
  id: string;
  type: "patient" | "doctor" | "appointment" | "medicine";
  title: string;
  subtitle?: string;
  description?: string;
  photo?: string | null;
  url?: string;
  score?: number;
  metadata?: Record<string, any>;
}

export interface SearchParams {
  q: string;
  type?: "patient" | "doctor" | "appointment" | "medicine" | "all";
  limit?: number;
  offset?: number;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  query: string;
  took_ms?: number;
}

/**
 * Global search across all entities
 */
export async function globalSearch(
  params: SearchParams
): Promise<SearchResponse> {
  const queryParams = new URLSearchParams();

  queryParams.append("q", params.q);
  if (params.type && params.type !== "all") {
    queryParams.append("type", params.type);
  }
  if (params.limit) {
    queryParams.append("limit", params.limit.toString());
  }
  if (params.offset) {
    queryParams.append("offset", params.offset.toString());
  }

  const response = await api.get(`/api/v1/search?${queryParams}`);
  return response.data;
}

/**
 * Search patients only
 */
export async function searchPatients(query: string, limit = 10): Promise<SearchResult[]> {
  const response = await globalSearch({ q: query, type: "patient", limit });
  return response.results;
}

/**
 * Search doctors only
 */
export async function searchDoctors(query: string, limit = 10): Promise<SearchResult[]> {
  const response = await globalSearch({ q: query, type: "doctor", limit });
  return response.results;
}

/**
 * Search appointments only
 */
export async function searchAppointments(query: string, limit = 10): Promise<SearchResult[]> {
  const response = await globalSearch({ q: query, type: "appointment", limit });
  return response.results;
}

/**
 * Search medicines only
 */
export async function searchMedicines(query: string, limit = 10): Promise<SearchResult[]> {
  const response = await globalSearch({ q: query, type: "medicine", limit });
  return response.results;
}

/**
 * Get search suggestions (autocomplete)
 */
export async function getSearchSuggestions(query: string, limit = 5): Promise<string[]> {
  const queryParams = new URLSearchParams();
  queryParams.append("q", query);
  queryParams.append("limit", limit.toString());

  const response = await api.get(`/api/v1/search/suggestions?${queryParams}`);
  return response.data.suggestions || [];
}
