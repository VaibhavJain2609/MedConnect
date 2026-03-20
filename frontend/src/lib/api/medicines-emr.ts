/**
 * EMR Medicine API Client
 * Connects to new normalized pharmaceutical database
 */

import api from '@/lib/api';

// ============================================================================
// TYPES
// ============================================================================

export interface SaltStrength {
  salt_strength_id: string;
  salt_id: string;
  strength_value: string;
  strength_unit: string;
  display_strength: string;
  is_standard_strength: boolean;
  pediatric_approved: boolean;
}

export interface Salt {
  salt_id: string;
  salt_name: string;
  description?: string;
  chemical_formula?: string;
  habit_forming: boolean;
  prescription_required: boolean;
  schedule?: string;
  pregnancy_category?: string;
  lactation_safe?: boolean;
  chemical_class?: {
    chemical_class_id: string;
    class_name: string;
  };
  therapeutic_class?: {
    therapeutic_class_id: string;
    class_name: string;
  };
  action_class?: {
    action_class_id: string;
    class_name: string;
  };
  strengths: SaltStrength[];
  created_at: string;
  updated_at: string;
}

export interface Manufacturer {
  manufacturer_id: string;
  manufacturer_name: string;
  country?: string;
  license_number?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface BrandComposition {
  composition_id: string;
  salt_name: string;
  strength_value: string;
  strength_unit: string;
  display_strength: string;
  sequence: number;
}

export interface Brand {
  brand_id: string;
  brand_name: string;
  manufacturer?: Manufacturer;
  compositions: BrandComposition[];
  salt_composition: string;
  is_discontinued: boolean;
  drug_type: string;
  launch_date?: string;
  discontinuation_date?: string;
  ndhm_code?: string;
  created_at: string;
  updated_at: string;
}

export interface UnifiedSearchResponse {
  salts: Array<{
    id: string;
    name: string;
    type: 'salt';
    chemical_class?: string;
    therapeutic_class?: string;
    strengths: Array<{
      id: string;
      value: string;
      unit: string;
      display: string;
    }>;
  }>;
  brands: Array<{
    id: string;
    name: string;
    type: 'brand';
    manufacturer?: string;
    composition: string;
    is_discontinued: boolean;
  }>;
  total_salts: number;
  total_brands: number;
}

export interface SaltListResponse {
  salts: Salt[];
  total: number;
  page: number;
  pages: number;
}

export interface BrandListResponse {
  brands: Brand[];
  total: number;
  page: number;
  pages: number;
}

export interface BrandForSalt {
  id: string;
  name: string;
  manufacturer?: string;
  composition: string;
  is_discontinued: boolean;
}

// ============================================================================
// API FUNCTIONS
// ============================================================================

/**
 * Unified search across salts and brands
 */
export async function searchMedicines(
  query: string,
  limit: number = 50
): Promise<UnifiedSearchResponse> {
  const params = new URLSearchParams({
    q: query,
    limit: String(limit),
  });

  return (await api.get(`/api/v1/medicines/search?${params}`)).data;
}

/**
 * List salts with filters
 */
export async function listSalts(params: {
  search?: string;
  chemical_class_id?: string;
  therapeutic_class_id?: string;
  page?: number;
  limit?: number;
}): Promise<SaltListResponse> {
  const queryParams = new URLSearchParams();

  if (params.search) queryParams.append('search', params.search);
  if (params.chemical_class_id) queryParams.append('chemical_class_id', params.chemical_class_id);
  if (params.therapeutic_class_id) queryParams.append('therapeutic_class_id', params.therapeutic_class_id);
  if (params.page) queryParams.append('page', String(params.page));
  if (params.limit) queryParams.append('limit', String(params.limit));

  return (await api.get(`/api/v1/salts?${queryParams}`)).data;
}

/**
 * Get salt details by ID
 */
export async function getSalt(saltId: string): Promise<Salt> {
  return (await api.get(`/api/v1/salts/${saltId}`)).data;
}

/**
 * Get all strengths for a salt
 */
export async function getSaltStrengths(saltId: string): Promise<SaltStrength[]> {
  return (await api.get(`/api/v1/salts/${saltId}/strengths`)).data;
}

/**
 * Get brands for a salt (optionally filtered by strength)
 */
export async function getBrandsForSalt(
  saltId: string,
  strengthValue?: number,
  strengthUnit?: string,
  limit: number = 50
): Promise<BrandForSalt[]> {
  const params = new URLSearchParams({ limit: String(limit) });

  if (strengthValue) params.append('strength_value', String(strengthValue));
  if (strengthUnit) params.append('strength_unit', strengthUnit);

  return (await api.get(`/api/v1/salts/${saltId}/brands?${params}`)).data;
}

/**
 * List brands with filters
 */
export async function listBrands(params: {
  search?: string;
  salt_id?: string;
  manufacturer_id?: string;
  include_discontinued?: boolean;
  page?: number;
  limit?: number;
}): Promise<BrandListResponse> {
  const queryParams = new URLSearchParams();

  if (params.search) queryParams.append('search', params.search);
  if (params.salt_id) queryParams.append('salt_id', params.salt_id);
  if (params.manufacturer_id) queryParams.append('manufacturer_id', params.manufacturer_id);
  if (params.include_discontinued !== undefined) {
    queryParams.append('include_discontinued', String(params.include_discontinued));
  }
  if (params.page) queryParams.append('page', String(params.page));
  if (params.limit) queryParams.append('limit', String(params.limit));

  return (await api.get(`/api/v1/brands?${queryParams}`)).data;
}

/**
 * Get brand details by ID
 */
export async function getBrand(brandId: string): Promise<Brand> {
  return (await api.get(`/api/v1/brands/${brandId}`)).data;
}

/**
 * Get alternative brands with same composition
 */
export async function getBrandAlternatives(brandId: string): Promise<Brand[]> {
  return (await api.get(`/api/v1/brands/${brandId}/alternatives`)).data;
}

/**
 * List manufacturers
 */
export async function listManufacturers(
  search?: string,
  isActive: boolean = true,
  limit: number = 50,
  offset: number = 0
): Promise<Manufacturer[]> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });

  if (search) params.append('search', search);
  if (isActive !== undefined) params.append('is_active', String(isActive));

  return (await api.get(`/api/v1/manufacturers?${params}`)).data;
}

/**
 * Get manufacturer by ID
 */
export async function getManufacturer(manufacturerId: string): Promise<Manufacturer> {
  return (await api.get(`/api/v1/manufacturers/${manufacturerId}`)).data;
}

/**
 * Get database statistics (combining salts and brands)
 */
export async function getMedicineStats(): Promise<{
  total_salts: number;
  total_brands: number;
  total_manufacturers: number;
  total_strengths: number;
}> {
  const [saltsResp, brandsResp, mfrsResp] = await Promise.all([
    listSalts({ limit: 1, page: 1 }),
    listBrands({ limit: 1, page: 1 }),
    listManufacturers('', true, 1, 0),
  ]);

  // Count total strengths from first page of salts
  const strengthsCount = saltsResp.salts.reduce(
    (sum, salt) => sum + salt.strengths.length,
    0
  );

  return {
    total_salts: saltsResp.total,
    total_brands: brandsResp.total,
    total_manufacturers: mfrsResp.length, // This is approximate
    total_strengths: strengthsCount * saltsResp.total / (saltsResp.salts.length || 1), // Estimate
  };
}

// ============================================================================
// ADMIN API FUNCTIONS
// ============================================================================

export interface BrandCompositionInput {
  salt_strength_id: string;
  sequence: number;
}

export interface CreateBrandRequest {
  brand_name: string;
  manufacturer_id: string;
  is_discontinued?: boolean;
  drug_type?: "allopathy" | "ayurveda" | "homeopathy";
  launch_date?: string;
  discontinuation_date?: string;
  ndhm_code?: string;
  compositions: BrandCompositionInput[];
}

export interface UpdateBrandRequest {
  brand_name?: string;
  manufacturer_id?: string;
  is_discontinued?: boolean;
  drug_type?: "allopathy" | "ayurveda" | "homeopathy";
  launch_date?: string;
  discontinuation_date?: string;
  ndhm_code?: string;
  compositions?: BrandCompositionInput[];
}

export interface BrandResponse {
  brand_id: string;
  brand_name: string;
  manufacturer_id: string;
  manufacturer_name: string;
  salt_composition: string;
  is_discontinued: boolean;
  drug_type: string;
  launch_date?: string;
  discontinuation_date?: string;
  ndhm_code?: string;
}

/**
 * Create a new brand (Admin only)
 */
export async function createBrand(
  data: CreateBrandRequest,
  _token?: string
): Promise<BrandResponse> {
  return (await api.post('/api/v1/admin/brands', data)).data;
}

/**
 * Update a brand (Admin only)
 */
export async function updateBrand(
  brandId: string,
  data: UpdateBrandRequest,
  _token?: string
): Promise<BrandResponse> {
  return (await api.put(`/api/v1/admin/brands/${brandId}`, data)).data;
}

/**
 * Delete a brand (Admin only)
 */
export async function deleteBrand(brandId: string, _token?: string): Promise<void> {
  await api.delete(`/api/v1/admin/brands/${brandId}`);
}

// ============================================================================
// DRUG INTERACTIONS API (MD-18)
// ============================================================================

export interface DrugInteraction {
  interaction_id: string;
  salt_1: {
    id: string;
    name: string;
  };
  salt_2: {
    id: string;
    name: string;
  };
  severity: 'minor' | 'moderate' | 'major' | 'contraindicated';
  effect: string;
  mechanism?: string;
  management?: string;
  evidence_level?: 'theoretical' | 'case-report' | 'study-based';
}

export interface CheckInteractionsRequest {
  salt_ids: string[];
}

/**
 * Check for drug interactions between multiple salts
 * Use this when creating prescriptions with multiple medicines
 */
export async function checkDrugInteractions(
  saltIds: string[]
): Promise<DrugInteraction[]> {
  return (await api.post('/api/v1/interactions/check', { salt_ids: saltIds })).data;
}

/**
 * Get all known interactions for a specific salt
 * Useful for displaying warnings on medicine detail pages
 */
export async function getSaltInteractions(
  saltId: string,
  severity?: 'minor' | 'moderate' | 'major' | 'contraindicated'
): Promise<DrugInteraction[]> {
  const params = new URLSearchParams();
  if (severity) params.append('severity', severity);

  return (await api.get(`/api/v1/interactions/salts/${saltId}${params.toString() ? '?' + params.toString() : ''}`)).data;
}

/**
 * Create a new drug interaction (Admin only)
 */
export async function createInteraction(
  data: {
    salt_id_1: string;
    salt_id_2: string;
    severity: 'minor' | 'moderate' | 'major' | 'contraindicated';
    effect: string;
    mechanism?: string;
    management?: string;
    evidence_level?: 'theoretical' | 'case-report' | 'study-based';
  },
  _token?: string
): Promise<DrugInteraction> {
  return (await api.post('/api/v1/interactions', data)).data;
}

/**
 * Delete a drug interaction (Admin only)
 */
export async function deleteInteraction(
  interactionId: string,
  _token?: string
): Promise<void> {
  await api.delete(`/api/v1/interactions/${interactionId}`);
}

// ============================================================================
// MEDICINE AUTOCOMPLETE API (MD-72)
// ============================================================================

export interface MedicineAutocompleteResult {
  brand_id: string;
  brand_name: string;
  salt_composition: string;
  manufacturer_name: string;
  manufacturer_id: string;
  dosage_form: string;
  strength: string;
  salt_id?: string;  // Primary salt ID for drug interaction checking (MD-244)
}

export interface MedicineAutocompleteResponse {
  results: MedicineAutocompleteResult[];
  count: number;
}

/**
 * Autocomplete medicines for prescription forms
 * Optimized endpoint returning top 10 brand matches with <100ms response time
 *
 * @param query - Search query (minimum 2 characters)
 * @returns Autocomplete results with brand details
 */
export async function autocompleteMedicines(
  query: string
): Promise<MedicineAutocompleteResponse> {
  if (query.length < 2) {
    return { results: [], count: 0 };
  }

  const params = new URLSearchParams({ q: query });

  return (await api.get(`/api/v1/medicines/autocomplete?${params}`)).data;
}
