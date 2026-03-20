/**
 * Medicine API Client
 * Connects to backend medicine endpoints
 */

import api from '@/lib/api';

export interface MedicineComponent {
  component_id: string;
  component_name: string;
  strength: number | string;  // Can be string from API (Decimal type)
  unit: string;
  sequence: number;
}

export interface Medicine {
  id: string;
  brand_name: string;
  manufacturer: string | null;
  dosage_form: string | null;
  strength: string | null;
  pack_size: string | null;
  therapeutic_class: string | null;
  schedule: string | null;
  mrp: number | string | null;  // Can be string from API (Decimal type)
  is_discontinued: boolean;
  habit_forming: boolean;
  components: MedicineComponent[];
  alternatives?: any;
  interactions?: {
    side_effects?: string[];
    uses?: string[];
    chemical_class?: string;
    action_class?: string;
  };
  salt_composition?: string;
  created_at?: string;
  updated_at?: string;
}

export interface MedicineSearchParams {
  search?: string;
  component_id?: string;
  therapeutic_class?: string;
  include_discontinued?: boolean;
  limit?: number;
  page?: number;
}

export interface MedicineSearchResponse {
  medicines: Medicine[];
  total: number;
  page: number;
  pages: number;
}

export interface Component {
  id: string;
  name: string;
  common_names: string | null;
  category: string | null;
  description: string | null;
  medicine_count?: number;
  created_at: string;
  updated_at: string;
}

export interface ComponentSearchResponse {
  components: Component[];
  total: number;
}

/**
 * Search medicines with filters
 */
export async function searchMedicines(
  params: MedicineSearchParams = {}
): Promise<MedicineSearchResponse> {
  const queryParams = new URLSearchParams();

  if (params.search) queryParams.append('q', params.search);
  if (params.component_id) queryParams.append('component_id', params.component_id);
  if (params.therapeutic_class) queryParams.append('therapeutic_class', params.therapeutic_class);
  if (params.include_discontinued !== undefined) {
    queryParams.append('include_discontinued', String(params.include_discontinued));
  }
  if (params.limit) queryParams.append('limit', String(params.limit));
  if (params.page) queryParams.append('page', String(params.page));

  return (await api.get(`/api/v1/medicines/search?${queryParams}`)).data;
}

/**
 * Get medicine by ID
 */
export async function getMedicine(id: string): Promise<Medicine> {
  return (await api.get(`/api/v1/medicines/${id}`)).data;
}

/**
 * Get medicine alternatives
 */
export async function getMedicineAlternatives(id: string): Promise<any> {
  return (await api.get(`/api/v1/medicines/${id}/alternatives`)).data;
}

/**
 * Search components (Admin)
 */
export async function searchComponents(
  search?: string,
  limit: number = 50,
  offset: number = 0
): Promise<ComponentSearchResponse> {
  const queryParams = new URLSearchParams();

  if (search) queryParams.append('search', search);
  queryParams.append('limit', String(limit));
  queryParams.append('offset', String(offset));

  return (await api.get(`/api/v1/admin/components?${queryParams}`)).data;
}

/**
 * Create medicine (Admin)
 */
export async function createMedicine(data: {
  brand_name: string;
  manufacturer?: string;
  components: Array<{
    component_id: string;
    strength: number;
    unit: string;
  }>;
  dosage_form?: string;
  pack_size?: string;
  therapeutic_class?: string;
  mrp?: number;
  is_discontinued?: boolean;
  habit_forming?: boolean;
  alternatives?: any;
  interactions?: any;
}): Promise<Medicine> {
  return (await api.post('/api/v1/admin/medicines', data)).data;
}

/**
 * Update medicine (Admin)
 */
export async function updateMedicine(
  id: string,
  data: Partial<{
    brand_name: string;
    manufacturer: string;
    components: Array<{
      component_id: string;
      strength: number;
      unit: string;
    }>;
    dosage_form: string;
    pack_size: string;
    therapeutic_class: string;
    mrp: number;
    is_discontinued: boolean;
    habit_forming: boolean;
    alternatives: any;
    interactions: any;
  }>
): Promise<Medicine> {
  return (await api.put(`/api/v1/admin/medicines/${id}`, data)).data;
}

/**
 * Delete medicine (Admin)
 */
export async function deleteMedicine(id: string): Promise<void> {
  await api.delete(`/api/v1/admin/medicines/${id}`);
}

/**
 * Get database statistics
 */
export async function getMedicineStats(): Promise<{
  total: number;
  active: number;
  discontinued: number;
  components: number;
}> {
  // Get total and discontinued from main search
  const [allResult, discontinuedResult, componentsResult] = await Promise.all([
    searchMedicines({ include_discontinued: true, limit: 1 }),
    searchMedicines({ include_discontinued: true, limit: 1 }).then(async () => {
      // Count discontinued separately
      const resp = await api.get('/api/v1/medicines/search?include_discontinued=true&limit=1000');
      return resp.data.medicines.filter((m: Medicine) => m.is_discontinued).length;
    }),
    searchComponents('', 1, 0),
  ]);

  const total = allResult.total;
  const discontinued = discontinuedResult;
  const active = total - discontinued;
  const components = componentsResult.total;

  return {
    total,
    active,
    discontinued,
    components,
  };
}
