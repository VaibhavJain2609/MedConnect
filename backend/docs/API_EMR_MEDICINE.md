# EMR Medicine API Documentation

## Overview

The EMR Medicine API provides access to a normalized pharmaceutical database with 250K+ brands, 1,500+ salts (APIs), and comprehensive clinical data.

## Base URL
```
http://localhost:8000/api/v1
```

---

## Endpoints

### 1. Unified Search

**Search medicines (salts and brands)**

```http
GET /medicines/search?q={query}&limit={limit}
```

**Parameters:**
- `q` (required): Search query (min 1 character)
- `limit` (optional): Results per category (1-100, default: 50)

**Response:**
```json
{
  "salts": [
    {
      "id": "uuid",
      "name": "Paracetamol",
      "type": "salt",
      "chemical_class": "string | null",
      "therapeutic_class": "PAIN ANALGESICS",
      "strengths": [
        {
          "id": "uuid",
          "value": "500.000",
          "unit": "mg",
          "display": "500.000mg"
        }
      ]
    }
  ],
  "brands": [
    {
      "id": "uuid",
      "name": "Crocin 500mg Tablet",
      "type": "brand",
      "manufacturer": "GlaxoSmithKline",
      "composition": "Paracetamol (500mg)",
      "is_discontinued": false
    }
  ],
  "total_salts": 2,
  "total_brands": 35
}
```

**Use Case:** Initial search bar, autocomplete

**Example:**
```bash
curl "http://localhost:8000/api/v1/medicines/search?q=paracetamol&limit=10"
```

---

### 2. Salts (Active Pharmaceutical Ingredients)

#### List Salts

```http
GET /salts?search={query}&page={page}&limit={limit}
```

**Parameters:**
- `search` (optional): Search query
- `chemical_class_id` (optional): Filter by chemical class
- `therapeutic_class_id` (optional): Filter by therapeutic class
- `page` (optional): Page number (default: 1)
- `limit` (optional): Results per page (1-100, default: 50)

**Response:**
```json
{
  "salts": [...],
  "total": 1532,
  "page": 1,
  "pages": 31
}
```

#### Get Salt Details

```http
GET /salts/{salt_id}
```

**Response:**
```json
{
  "salt_id": "uuid",
  "salt_name": "Paracetamol",
  "description": "Analgesic and antipyretic",
  "chemical_formula": "C8H9NO2",
  "habit_forming": false,
  "prescription_required": true,
  "schedule": null,
  "pregnancy_category": "B",
  "lactation_safe": true,
  "chemical_class": {...},
  "therapeutic_class": {...},
  "action_class": {...},
  "strengths": [...],
  "created_at": "timestamp",
  "updated_at": "timestamp"
}
```

**Use Case:** Display full salt information, safety data

#### Get Salt Strengths

```http
GET /salts/{salt_id}/strengths
```

**Response:**
```json
[
  {
    "salt_strength_id": "uuid",
    "salt_id": "uuid",
    "strength_value": "500.000",
    "strength_unit": "mg",
    "display_strength": "500.000mg",
    "is_standard_strength": true,
    "pediatric_approved": false
  }
]
```

**Use Case:** Doctor selects salt → show available strengths

#### Get Brands for Salt

```http
GET /salts/{salt_id}/brands?strength_value={value}&strength_unit={unit}&limit={limit}
```

**Parameters:**
- `strength_value` (optional): Filter by specific strength
- `strength_unit` (optional): Unit (mg, mcg, etc.)
- `limit` (optional): Max results (default: 50)

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "Crocin 500mg Tablet",
    "manufacturer": "GlaxoSmithKline",
    "composition": "Paracetamol (500mg)",
    "is_discontinued": false
  }
]
```

**Use Case:** Doctor selects strength → show available brands

---

### 3. Brands (Commercial Medicines)

#### List Brands

```http
GET /brands?search={query}&salt_id={id}&manufacturer_id={id}&include_discontinued={bool}&page={page}&limit={limit}
```

**Parameters:**
- `search` (optional): Search by brand name
- `salt_id` (optional): Filter by salt
- `manufacturer_id` (optional): Filter by manufacturer
- `include_discontinued` (optional): Include discontinued (default: false)
- `page` (optional): Page number
- `limit` (optional): Results per page

**Response:**
```json
{
  "brands": [
    {
      "brand_id": "uuid",
      "brand_name": "Crocin 500mg Tablet",
      "manufacturer": {
        "manufacturer_id": "uuid",
        "manufacturer_name": "GlaxoSmithKline",
        "country": null,
        "is_active": true
      },
      "compositions": [
        {
          "composition_id": "uuid",
          "salt_name": "Paracetamol",
          "strength_value": "500.000",
          "strength_unit": "mg",
          "display_strength": "500.000mg",
          "sequence": 1
        }
      ],
      "salt_composition": "Paracetamol (500mg)",
      "is_discontinued": false,
      "drug_type": "allopathy",
      "launch_date": null,
      "discontinuation_date": null
    }
  ],
  "total": 250797,
  "page": 1,
  "pages": 5016
}
```

#### Get Brand Details

```http
GET /brands/{brand_id}
```

**Use Case:** View complete brand information

#### Get Brand Alternatives

```http
GET /brands/{brand_id}/alternatives
```

**Response:** List of brands with same salt composition

**Use Case:** Patient views alternatives (same composition, different brands)

---

### 4. Manufacturers

#### List Manufacturers

```http
GET /manufacturers?search={query}&is_active={bool}&limit={limit}&offset={offset}
```

**Response:**
```json
[
  {
    "manufacturer_id": "uuid",
    "manufacturer_name": "GlaxoSmithKline Pharmaceuticals Ltd",
    "country": null,
    "license_number": null,
    "is_active": true,
    "created_at": "timestamp",
    "updated_at": "timestamp"
  }
]
```

#### Get Manufacturer Details

```http
GET /manufacturers/{manufacturer_id}
```

---

## Doctor Workflow Example

### Scenario: Prescribe paracetamol for fever

**Step 1: Search for medicine**
```bash
GET /medicines/search?q=paracetamol
# Returns both salt and brand results
```

**Step 2: Doctor selects "Paracetamol" (salt)**
```bash
GET /salts/{salt_id}/strengths
# Returns: 500mg, 650mg, 1000mg, etc.
```

**Step 3: Doctor selects strength (500mg)**
```bash
GET /salts/{salt_id}/brands?strength_value=500&strength_unit=mg
# Returns: Crocin, Dolo, Calpol, etc.
```

**Step 4: Doctor selects brand (Crocin 500mg)**
```bash
GET /brands/{brand_id}
# Full details for prescription
```

---

## Patient Workflow Example

### Scenario: View prescription medicine details

**Step 1: Patient views prescribed brand**
```bash
GET /brands/{brand_id}
# Shows: Name, composition, manufacturer
```

**Step 2: View alternatives**
```bash
GET /brands/{brand_id}/alternatives
# Shows: Other brands with same composition
```

---

## Database Statistics

- **Salts:** 1,532 unique APIs
- **Salt Strengths:** 5,984 available strengths
- **Brands:** 250,797 commercial products
- **Manufacturers:** 7,648 companies
- **Brand Compositions:** 331,442 relationships
- **Therapeutic Classes:** 22
- **Chemical Classes:** 871
- **Action Classes:** 431

---

## Error Responses

### 404 Not Found
```json
{
  "detail": "Salt not found"
}
```

### 422 Validation Error
```json
{
  "detail": [
    {
      "loc": ["query", "q"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## Testing

Interactive API docs available at:
```
http://localhost:8000/docs
```

Redoc documentation:
```
http://localhost:8000/redoc
```

---

## Notes

- All IDs are UUIDs
- Decimal values (strengths) returned as strings to preserve precision
- Timestamps in ISO 8601 format
- Pagination uses 1-based indexing
- Default sorting: alphabetical by name
