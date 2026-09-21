"""Tests for barcode (GTIN/EAN) support in the medicine catalog.

Barcodes are stored per-pack on ``brand_packaging.barcode`` (Indian packs
carry one barcode per pack size). Covered here:

- GET /api/v1/medicines/by-barcode/{code} — hit / miss / invalid format
- Text search matching barcode input (pure digit strings, len 8-14)
- Admin write path: packaging on brand create/update + format validation
- Non-unique behaviour: duplicate barcodes still resolve
"""

import pytest
import pytest_asyncio
from uuid import uuid4

from sqlalchemy import select

from app.models.medicine.commercial import Brand, BrandComposition
from app.models.medicine.packaging import BrandPackaging, PackForm

pytestmark = pytest.mark.asyncio

BARCODE = "8901234567890"  # 13 digits — EAN-13 shaped


@pytest_asyncio.fixture(scope="function")
async def sample_pack_form(medicine_db):
    """A pack form (dosage form) for packaging rows."""
    form = PackForm(
        form_name="Tablet",
        route_of_administration="Oral",
        is_solid=True,
        is_liquid=False,
    )
    medicine_db.add(form)
    await medicine_db.commit()
    await medicine_db.refresh(form)
    return form


@pytest_asyncio.fixture(scope="function")
async def sample_pack(medicine_db, sample_brand, sample_pack_form):
    """A packaging row with a barcode on sample_brand."""
    pack = BrandPackaging(
        brand_id=sample_brand.brand_id,
        pack_form_id=sample_pack_form.pack_form_id,
        quantity=10,
        pack_type="strip of 10 tablets",
        barcode=BARCODE,
        is_primary_pack=True,
    )
    medicine_db.add(pack)
    await medicine_db.commit()
    await medicine_db.refresh(pack)
    return pack


class TestBarcodeLookup:
    """GET /api/v1/medicines/by-barcode/{code}"""

    async def test_lookup_hit(
        self, patient_client, sample_pack, sample_brand
    ):
        """Known barcode resolves to the brand with composition + pack info."""
        response = await patient_client.get(
            f"/api/v1/medicines/by-barcode/{BARCODE}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["brand_id"] == str(sample_brand.brand_id)
        assert data["brand_name"] == sample_brand.brand_name
        assert "Paracetamol" in data["salt_composition"]
        # Pack info present, barcode round-trips
        assert len(data["packaging"]) == 1
        pack = data["packaging"][0]
        assert pack["barcode"] == BARCODE
        assert pack["pack_form_name"] == "Tablet"
        assert pack["quantity"] == 10

    async def test_lookup_hit_with_spaces(self, patient_client, sample_pack):
        """Whitespace in the scanned input is stripped before lookup."""
        response = await patient_client.get(
            "/api/v1/medicines/by-barcode/8901 2345 67890"
        )
        assert response.status_code == 200
        assert response.json()["packaging"][0]["barcode"] == BARCODE

    async def test_lookup_miss(self, patient_client, sample_pack):
        """Unknown barcode returns 404."""
        response = await patient_client.get(
            "/api/v1/medicines/by-barcode/8909999999999"
        )
        assert response.status_code == 404

    async def test_lookup_invalid_format_short(self, patient_client):
        """Fewer than 8 digits is not a valid GTIN/EAN — 422."""
        response = await patient_client.get("/api/v1/medicines/by-barcode/12345")
        assert response.status_code == 422

    async def test_lookup_invalid_format_nondigits(self, patient_client):
        """Non-digit characters — 422."""
        response = await patient_client.get(
            "/api/v1/medicines/by-barcode/890123ABC789"
        )
        assert response.status_code == 422

    async def test_lookup_invalid_format_too_long(self, patient_client):
        """More than 14 digits — 422."""
        response = await patient_client.get(
            "/api/v1/medicines/by-barcode/123456789012345"
        )
        assert response.status_code == 422

    async def test_lookup_unauthenticated(self, client, sample_pack):
        """Requires authentication."""
        response = await client.get(f"/api/v1/medicines/by-barcode/{BARCODE}")
        assert response.status_code == 401

    async def test_lookup_duplicate_barcodes_nonunique(
        self, medicine_db, patient_client, sample_pack, sample_manufacturer
    ):
        """Barcode index is non-unique: two packs sharing a barcode still resolve."""
        other_brand = Brand(
            brand_name="Other Brand",
            manufacturer_id=sample_manufacturer.manufacturer_id,
        )
        medicine_db.add(other_brand)
        await medicine_db.flush()
        other_pack = BrandPackaging(
            brand_id=other_brand.brand_id,
            pack_form_id=sample_pack.pack_form_id,
            quantity=20,
            barcode=BARCODE,
        )
        medicine_db.add(other_pack)
        await medicine_db.commit()

        response = await patient_client.get(
            f"/api/v1/medicines/by-barcode/{BARCODE}"
        )
        assert response.status_code == 200
        assert response.json()["brand_name"] in {"Crocin", "Other Brand"}


class TestBarcodeSearch:
    """Text search matches barcode input (pure digit string, len 8-14)."""

    async def test_unified_search_by_barcode(
        self, patient_client, sample_pack, sample_brand
    ):
        """GET /medicines/search?q=<barcode> returns the brand."""
        response = await patient_client.get(
            f"/api/v1/medicines/search?q={BARCODE}"
        )
        assert response.status_code == 200
        data = response.json()
        brand_ids = [b["id"] for b in data["brands"]]
        assert str(sample_brand.brand_id) in brand_ids

    async def test_brand_list_search_by_barcode(
        self, patient_client, sample_pack, sample_brand
    ):
        """GET /brands?search=<barcode> returns the brand."""
        response = await patient_client.get(
            f"/api/v1/brands?search={BARCODE}"
        )
        assert response.status_code == 200
        data = response.json()
        brand_ids = [b["brand_id"] for b in data["brands"]]
        assert str(sample_brand.brand_id) in brand_ids

    async def test_search_short_digit_string_not_barcode(
        self, patient_client, sample_pack
    ):
        """Digit strings shorter than 8 chars are treated as plain text."""
        response = await patient_client.get("/api/v1/medicines/search?q=1234")
        assert response.status_code == 200
        # No false barcode hit — brand has no "1234" in its name either
        assert response.json()["total_brands"] == 0

    async def test_search_barcode_no_match(
        self, patient_client, sample_pack
    ):
        """A well-formed barcode with no pack match returns empty results."""
        response = await patient_client.get(
            "/api/v1/medicines/search?q=8909999999999"
        )
        assert response.status_code == 200
        assert response.json()["total_brands"] == 0


class TestPackForms:
    """GET /api/v1/pack-forms — dropdown source for pack management UIs."""

    async def test_list_pack_forms(self, patient_client, sample_pack_form):
        response = await patient_client.get("/api/v1/pack-forms")
        assert response.status_code == 200
        names = [pf["form_name"] for pf in response.json()]
        assert "Tablet" in names

    async def test_list_pack_forms_unauthenticated(self, client):
        response = await client.get("/api/v1/pack-forms")
        assert response.status_code == 401


class TestAdminBrandPackaging:
    """Admin write path: packaging (with barcode) on brand create/update."""

    def _brand_payload(self, manufacturer_id, salt_strength_id, **extra):
        payload = {
            "brand_name": "BarcodeBrand",
            "manufacturer_id": str(manufacturer_id),
            "compositions": [
                {"salt_strength_id": str(salt_strength_id), "sequence": 1}
            ],
        }
        payload.update(extra)
        return payload

    async def test_create_brand_with_barcode(
        self,
        admin_client,
        sample_manufacturer,
        sample_salt_strength,
        sample_pack_form,
    ):
        """Create a brand with a pack carrying a barcode — 201."""
        payload = self._brand_payload(
            sample_manufacturer.manufacturer_id,
            sample_salt_strength.salt_strength_id,
            packaging=[
                {
                    "pack_form_id": str(sample_pack_form.pack_form_id),
                    "quantity": 10,
                    "pack_type": "strip of 10 tablets",
                    "barcode": BARCODE,
                }
            ],
        )
        response = await admin_client.post("/api/v1/admin/brands", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert len(data["packaging"]) == 1
        assert data["packaging"][0]["barcode"] == BARCODE
        assert data["packaging"][0]["pack_form_name"] == "Tablet"

    async def test_create_brand_barcode_normalized(
        self,
        admin_client,
        sample_manufacturer,
        sample_salt_strength,
        sample_pack_form,
    ):
        """Barcodes with embedded spaces are stored stripped."""
        payload = self._brand_payload(
            sample_manufacturer.manufacturer_id,
            sample_salt_strength.salt_strength_id,
            packaging=[
                {
                    "pack_form_id": str(sample_pack_form.pack_form_id),
                    "quantity": 10,
                    "barcode": "8901 2345 67890",
                }
            ],
        )
        response = await admin_client.post("/api/v1/admin/brands", json=payload)

        assert response.status_code == 201
        assert response.json()["packaging"][0]["barcode"] == BARCODE

    async def test_create_brand_invalid_barcode_422(
        self,
        admin_client,
        sample_manufacturer,
        sample_salt_strength,
        sample_pack_form,
    ):
        """Non-digit / wrong-length barcode on write — 422."""
        for bad in ("1234", "8901234567890123456", "8901234ABC890"):
            payload = self._brand_payload(
                sample_manufacturer.manufacturer_id,
                sample_salt_strength.salt_strength_id,
                packaging=[
                    {
                        "pack_form_id": str(sample_pack_form.pack_form_id),
                        "quantity": 10,
                        "barcode": bad,
                    }
                ],
            )
            response = await admin_client.post(
                "/api/v1/admin/brands", json=payload
            )
            assert response.status_code == 422, f"expected 422 for {bad!r}"

    async def test_create_brand_unknown_pack_form_404(
        self, admin_client, sample_manufacturer, sample_salt_strength
    ):
        """Unknown pack_form_id — 404."""
        payload = self._brand_payload(
            sample_manufacturer.manufacturer_id,
            sample_salt_strength.salt_strength_id,
            packaging=[
                {
                    "pack_form_id": str(uuid4()),
                    "quantity": 10,
                    "barcode": BARCODE,
                }
            ],
        )
        response = await admin_client.post("/api/v1/admin/brands", json=payload)
        assert response.status_code == 404

    async def test_update_brand_packaging(
        self,
        admin_client,
        medicine_db,
        sample_brand,
        sample_pack,
        sample_pack_form,
    ):
        """PUT packaging replaces existing packs (replace-all semantics)."""
        new_barcode = "8901111122223"
        payload = {
            "packaging": [
                {
                    "pack_form_id": str(sample_pack_form.pack_form_id),
                    "quantity": 30,
                    "pack_type": "strip of 30 tablets",
                    "barcode": new_barcode,
                }
            ]
        }
        response = await admin_client.put(
            f"/api/v1/admin/brands/{sample_brand.brand_id}", json=payload
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["packaging"]) == 1
        assert data["packaging"][0]["barcode"] == new_barcode

        # Old barcode no longer resolves; new one does
        miss = await admin_client.get(f"/api/v1/medicines/by-barcode/{BARCODE}")
        assert miss.status_code == 404
        hit = await admin_client.get(
            f"/api/v1/medicines/by-barcode/{new_barcode}"
        )
        assert hit.status_code == 200

    async def test_update_brand_invalid_barcode_422(
        self, admin_client, sample_brand, sample_pack_form
    ):
        """Invalid barcode on update — 422."""
        payload = {
            "packaging": [
                {
                    "pack_form_id": str(sample_pack_form.pack_form_id),
                    "quantity": 10,
                    "barcode": "not-a-barcode",
                }
            ]
        }
        response = await admin_client.put(
            f"/api/v1/admin/brands/{sample_brand.brand_id}", json=payload
        )
        assert response.status_code == 422
