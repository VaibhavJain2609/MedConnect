/**
 * EMR Medicine API Client
 * Connects to new normalized pharmaceutical database
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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

  const response = await fetch(
    `${API_BASE_URL}/api/v1/medicines/search?${params}`,
    {
      headers: { 'Content-Type': 'application/json' },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to search medicines: ${response.statusText}`);
  }

  return response.json();
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

  const response = await fetch(
    `${API_BASE_URL}/api/v1/salts?${queryParams}`,
    {
      headers: { 'Content-Type': 'application/json' },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to list salts: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get salt details by ID
 */
export async function getSalt(saltId: string): Promise<Salt> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/salts/${saltId}`,
    {
      headers: { 'Content-Type': 'application/json' },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to get salt: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get all strengths for a salt
 */
export async function getSaltStrengths(saltId: string): Promise<SaltStrength[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/salts/${saltId}/strengths`,
    {
      headers: { 'Content-Type': 'application/json' },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to get salt strengths: ${response.statusText}`);
  }

  return response.json();
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

  const response = await fetch(
    `${API_BASE_URL}/api/v1/salts/${saltId}/brands?${params}`,
    {
      headers: { 'Content-Type': 'application/json' },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to get brands for salt: ${response.statusText}`);
  }

  return response.json();
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

  const response = await fetch(
    `${API_BASE_URL}/api/v1/brands?${queryParams}`,
    {
      headers: { 'Content-Type': 'application/json' },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to list brands: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get brand details by ID
 */
export async function getBrand(brandId: string): Promise<Brand> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/brands/${brandId}`,
    {
      headers: { 'Content-Type': 'application/json' },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to get brand: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get alternative brands with same composition
 */
export async function getBrandAlternatives(brandId: string): Promise<Brand[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/brands/${brandId}/alternatives`,
    {
      headers: { 'Content-Type': 'application/json' },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to get brand alternatives: ${response.statusText}`);
  }

  return response.json();
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

  const response = await fetch(
    `${API_BASE_URL}/api/v1/manufacturers?${params}`,
    {
      headers: { 'Content-Type': 'application/json' },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to list manufacturers: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get manufacturer by ID
 */
export async function getManufacturer(manufacturerId: string): Promise<Manufacturer> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/manufacturers/${manufacturerId}`,
    {
      headers: { 'Content-Type': 'application/json' },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to get manufacturer: ${response.statusText}`);
  }

  return response.json();
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
  token: string
): Promise<BrandResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/admin/brands`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to create brand: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Update a brand (Admin only)
 */
export async function updateBrand(
  brandId: string,
  data: UpdateBrandRequest,
  token: string
): Promise<BrandResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/admin/brands/${brandId}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to update brand: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Delete a brand (Admin only)
 */
export async function deleteBrand(brandId: string, token: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/v1/admin/brands/${brandId}`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to delete brand: ${response.statusText}`);
  }
}
