"""Tests for POST /api/v1/admin/catalog/import (CSV bulk import)."""

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app.models.medicine.commercial import Brand, BrandComposition, Manufacturer
from app.models.medicine.packaging import BrandPackaging, PackForm
from app.models.medicine.salts import Salt, SaltStrength

pytestmark = pytest.mark.asyncio

CSV_HEADER = (
    "brand_name,manufacturer_name,salt_name,strength_value,strength_unit,"
    "pack_form_name,pack_type,quantity,barcode,mrp_paise"
)

VALID_ROW_1 = "Crocin 500,GSK,Paracetamol,500,mg,Tablet,strip of 10,10,8901234567890,12500"
VALID_ROW_2 = "Brufen 400,Abbott,Ibuprofen,400,mg,Tablet,strip of 15,15,,8750"


def _csv(*rows: str) -> bytes:
    return (CSV_HEADER + "\n" + "\n".join(rows) + "\n").encode()


def _upload(content: bytes, filename: str = "catalog.csv"):
    return {"file": (filename, content, "text/csv")}


@pytest_asyncio.fixture
async def sample_pack_form(medicine_db):
    """Seed the pack form the CSV rows reference."""
    pack_form = PackForm(form_name="Tablet", route_of_administration="Oral", is_solid=True)
    medicine_db.add(pack_form)
    await medicine_db.commit()
    await medicine_db.refresh(pack_form)
    return pack_form


async def _count(medicine_db, model) -> int:
    result = await medicine_db.execute(select(func.count()).select_from(model))
    return result.scalar_one()


class TestCatalogImport:
    async def test_happy_path_import(
        self, admin_client, medicine_db, sample_pack_form
    ):
        """Two valid rows create mfr/salt/strength/brand/composition/packaging."""
        response = await admin_client.post(
            "/api/v1/admin/catalog/import",
            files=_upload(_csv(VALID_ROW_1, VALID_ROW_2)),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["dry_run"] is False
        assert data["total"] == 2
        assert data["created"] == 2
        assert data["updated"] == 0
        assert data["skipped"] == 0
        assert data["errors"] == []
        assert len(data["rows"]) == 2
        assert all(r["status"] == "created" for r in data["rows"])

        assert await _count(medicine_db, Manufacturer) == 2
        assert await _count(medicine_db, Salt) == 2
        assert await _count(medicine_db, SaltStrength) == 2
        assert await _count(medicine_db, Brand) == 2
        assert await _count(medicine_db, BrandComposition) == 2
        assert await _count(medicine_db, BrandPackaging) == 2

        # Pack row carries the CSV fields (barcode normalized, mrp stored).
        pack = (
            await medicine_db.execute(
                select(BrandPackaging).where(BrandPackaging.barcode == "8901234567890")
            )
        ).scalar_one()
        assert pack.pack_type == "strip of 10"
        assert pack.mrp_paise == 12500
        assert pack.is_primary_pack is True

    async def test_dry_run_writes_nothing(
        self, admin_client, medicine_db, sample_pack_form
    ):
        """?dry_run=true reports would-be outcomes and persists nothing."""
        response = await admin_client.post(
            "/api/v1/admin/catalog/import?dry_run=true",
            files=_upload(_csv(VALID_ROW_1)),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["dry_run"] is True
        assert data["created"] == 1
        assert data["rows"][0]["status"] == "created"

        assert await _count(medicine_db, Manufacturer) == 0
        assert await _count(medicine_db, Brand) == 0
        assert await _count(medicine_db, BrandPackaging) == 0

    async def test_idempotent_reimport(
        self, admin_client, medicine_db, sample_pack_form
    ):
        """Re-importing the same file skips every row — no duplicates."""
        first = await admin_client.post(
            "/api/v1/admin/catalog/import", files=_upload(_csv(VALID_ROW_1))
        )
        assert first.json()["created"] == 1

        second = await admin_client.post(
            "/api/v1/admin/catalog/import", files=_upload(_csv(VALID_ROW_1))
        )
        data = second.json()
        assert data["created"] == 0
        assert data["updated"] == 0
        assert data["skipped"] == 1
        assert data["rows"][0]["status"] == "skipped"

        assert await _count(medicine_db, Brand) == 1
        assert await _count(medicine_db, BrandPackaging) == 1
        assert await _count(medicine_db, BrandComposition) == 1

    async def test_reimport_updates_changed_pack_fields(
        self, admin_client, medicine_db, sample_pack_form
    ):
        """A re-import with different barcode/mrp updates the existing pack."""
        await admin_client.post(
            "/api/v1/admin/catalog/import", files=_upload(_csv(VALID_ROW_1))
        )

        changed = "Crocin 500,GSK,Paracetamol,500,mg,Tablet,strip of 10,10,8909999999999,15000"
        response = await admin_client.post(
            "/api/v1/admin/catalog/import", files=_upload(_csv(changed))
        )
        data = response.json()
        assert data["updated"] == 1
        assert data["created"] == 0

        pack = (
            await medicine_db.execute(select(BrandPackaging))
        ).scalar_one()
        assert pack.barcode == "8909999999999"
        assert pack.mrp_paise == 15000

    async def test_bad_rows_isolated(
        self, admin_client, medicine_db, sample_pack_form
    ):
        """One bad row doesn't kill the batch — good rows still commit."""
        bad_quantity = "Bad Qty,Acme,Paracetamol,500,mg,Tablet,,zero,,"
        unknown_form = "Bad Form,Acme,Paracetamol,500,mg,Nebulizer,,5,,"

        response = await admin_client.post(
            "/api/v1/admin/catalog/import",
            files=_upload(_csv(VALID_ROW_1, bad_quantity, unknown_form, VALID_ROW_2)),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 4
        assert data["created"] == 2
        assert len(data["errors"]) == 2
        assert {e["row"] for e in data["errors"]} == {3, 4}
        assert "quantity" in data["errors"][0]["message"]
        assert "pack_form_name" in data["errors"][1]["message"]

        assert await _count(medicine_db, Brand) == 2
        assert await _count(medicine_db, BrandPackaging) == 2

    async def test_same_brand_multiple_packs(
        self, admin_client, medicine_db, sample_pack_form
    ):
        """Two pack sizes for one brand → one brand, two packaging rows."""
        row_10 = "Crocin 500,GSK,Paracetamol,500,mg,Tablet,strip of 10,10,,12500"
        row_20 = "Crocin 500,GSK,Paracetamol,500,mg,Tablet,strip of 20,20,,23000"

        response = await admin_client.post(
            "/api/v1/admin/catalog/import", files=_upload(_csv(row_10, row_20))
        )
        data = response.json()
        assert data["created"] == 2
        assert data["errors"] == []

        assert await _count(medicine_db, Brand) == 1
        assert await _count(medicine_db, BrandPackaging) == 2
        # One composition, not duplicated on the second row.
        assert await _count(medicine_db, BrandComposition) == 1

    async def test_invalid_barcode_rejected(
        self, admin_client, medicine_db, sample_pack_form
    ):
        row = "Crocin 500,GSK,Paracetamol,500,mg,Tablet,,10,ABC123,12500"
        response = await admin_client.post(
            "/api/v1/admin/catalog/import", files=_upload(_csv(row))
        )
        data = response.json()
        assert data["created"] == 0
        assert len(data["errors"]) == 1
        assert "barcode" in data["errors"][0]["message"]
        assert await _count(medicine_db, Brand) == 0

    async def test_rejects_non_csv(self, admin_client, sample_pack_form):
        response = await admin_client.post(
            "/api/v1/admin/catalog/import",
            files=_upload(b"name\n", filename="catalog.xlsx"),
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "NOT_CSV"

    async def test_rejects_missing_columns(self, admin_client, sample_pack_form):
        response = await admin_client.post(
            "/api/v1/admin/catalog/import",
            files=_upload(b"brand_name,manufacturer_name\nX,Y\n"),
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_CSV"

    async def test_rejects_over_1000_rows(self, admin_client, sample_pack_form):
        rows = "\n".join(f"Brand{i},Mfr,Salt,500,mg,Tablet,,1,," for i in range(1001))
        response = await admin_client.post(
            "/api/v1/admin/catalog/import",
            files=_upload((CSV_HEADER + "\n" + rows).encode()),
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "TOO_MANY_ROWS"

    async def test_rejects_oversized_file(self, admin_client, sample_pack_form):
        response = await admin_client.post(
            "/api/v1/admin/catalog/import",
            files=_upload(b"x" * (2 * 1024 * 1024 + 1)),
        )
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "FILE_TOO_LARGE"

    async def test_non_admin_forbidden(self, patient_client, sample_pack_form):
        response = await patient_client.post(
            "/api/v1/admin/catalog/import",
            files=_upload(_csv(VALID_ROW_1)),
        )
        assert response.status_code == 403

    async def test_unauthenticated_unauthorized(self, client, sample_pack_form):
        response = await client.post(
            "/api/v1/admin/catalog/import",
            files=_upload(_csv(VALID_ROW_1)),
        )
        assert response.status_code in (401, 403)
