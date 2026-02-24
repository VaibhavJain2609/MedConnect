"""Tests for admin manufacturer management endpoints."""

import pytest
from uuid import uuid4

from app.models.medicine.commercial import Manufacturer, Brand

pytestmark = pytest.mark.asyncio


class TestCreateManufacturer:
    """Test POST /api/v1/admin/manufacturers endpoint."""

    async def test_create_manufacturer_success(self, admin_client, medicine_db):
        """Should create manufacturer with valid data."""
        request_data = {
            "manufacturer_name": "Dr. Reddy's Laboratories",
            "country": "India",
            "license_number": "MFG-789012",
            "is_active": True
        }

        response = await admin_client.post("/api/v1/admin/manufacturers", json=request_data)

        assert response.status_code == 201
        data = response.json()
        assert data["manufacturer_name"] == "Dr. Reddy's Laboratories"
        assert data["country"] == "India"
        assert data["license_number"] == "MFG-789012"
        assert data["is_active"] is True
        assert "manufacturer_id" in data

    async def test_create_manufacturer_minimal(self, admin_client, medicine_db):
        """Should create manufacturer with only required field."""
        request_data = {
            "manufacturer_name": "Cipla Ltd"
        }

        response = await admin_client.post("/api/v1/admin/manufacturers", json=request_data)

        assert response.status_code == 201
        data = response.json()
        assert data["manufacturer_name"] == "Cipla Ltd"
        assert data["is_active"] is True  # Default value
        assert data["country"] is None
        assert data["license_number"] is None

    async def test_create_manufacturer_duplicate_name(self, admin_client, medicine_db):
        """Should return 409 for duplicate manufacturer name (case-insensitive)."""
        # Create first manufacturer
        request_data = {
            "manufacturer_name": "GSK Pharmaceuticals"
        }
        response = await admin_client.post("/api/v1/admin/manufacturers", json=request_data)
        assert response.status_code == 201

        # Try exact duplicate
        response = await admin_client.post("/api/v1/admin/manufacturers", json=request_data)
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

        # Try case-insensitive duplicate
        request_data["manufacturer_name"] = "gsk pharmaceuticals"
        response = await admin_client.post("/api/v1/admin/manufacturers", json=request_data)
        assert response.status_code == 409


class TestUpdateManufacturer:
    """Test PUT /api/v1/admin/manufacturers/{id} endpoint."""

    async def test_update_manufacturer_success(self, admin_client, medicine_db):
        """Should update manufacturer with valid data."""
        # Create manufacturer first
        manufacturer = Manufacturer(
            manufacturer_name="Test Pharma",
            country="India",
            license_number="OLD-123"
        )
        medicine_db.add(manufacturer)
        await medicine_db.commit()
        await medicine_db.refresh(manufacturer)

        # Update it
        request_data = {
            "country": "USA",
            "license_number": "US-123456"
        }

        response = await admin_client.put(
            f"/api/v1/admin/manufacturers/{manufacturer.manufacturer_id}",
            json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["manufacturer_name"] == "Test Pharma"  # Unchanged
        assert data["country"] == "USA"  # Updated
        assert data["license_number"] == "US-123456"  # Updated

    async def test_update_manufacturer_partial(self, admin_client, medicine_db):
        """Should update only specified fields."""
        manufacturer = Manufacturer(
            manufacturer_name="Partial Update Test",
            country="India",
            is_active=True
        )
        medicine_db.add(manufacturer)
        await medicine_db.commit()
        await medicine_db.refresh(manufacturer)

        # Update only name
        request_data = {
            "manufacturer_name": "Updated Name"
        }

        response = await admin_client.put(
            f"/api/v1/admin/manufacturers/{manufacturer.manufacturer_id}",
            json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["manufacturer_name"] == "Updated Name"
        assert data["country"] == "India"  # Unchanged
        assert data["is_active"] is True  # Unchanged

    async def test_update_manufacturer_duplicate_name(self, admin_client, medicine_db):
        """Should return 409 when updating to duplicate name."""
        # Create two manufacturers
        mfr1 = Manufacturer(manufacturer_name="Manufacturer One")
        mfr2 = Manufacturer(manufacturer_name="Manufacturer Two")
        medicine_db.add_all([mfr1, mfr2])
        await medicine_db.commit()
        await medicine_db.refresh(mfr1)
        await medicine_db.refresh(mfr2)

        # Try to rename mfr2 to mfr1's name
        request_data = {
            "manufacturer_name": "Manufacturer One"
        }

        response = await admin_client.put(
            f"/api/v1/admin/manufacturers/{mfr2.manufacturer_id}",
            json=request_data
        )

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    async def test_update_manufacturer_not_found(self, admin_client, medicine_db):
        """Should return 404 for non-existent manufacturer."""
        fake_id = uuid4()
        request_data = {
            "country": "USA"
        }

        response = await admin_client.put(
            f"/api/v1/admin/manufacturers/{fake_id}",
            json=request_data
        )

        assert response.status_code == 404

    async def test_update_manufacturer_toggle_active(self, admin_client, medicine_db):
        """Should toggle is_active flag."""
        manufacturer = Manufacturer(
            manufacturer_name="Toggle Test",
            is_active=True
        )
        medicine_db.add(manufacturer)
        await medicine_db.commit()
        await medicine_db.refresh(manufacturer)

        # Deactivate
        request_data = {
            "is_active": False
        }

        response = await admin_client.put(
            f"/api/v1/admin/manufacturers/{manufacturer.manufacturer_id}",
            json=request_data
        )

        assert response.status_code == 200
        assert response.json()["is_active"] is False


class TestDeleteManufacturer:
    """Test DELETE /api/v1/admin/manufacturers/{id} endpoint."""

    async def test_delete_manufacturer_success(self, admin_client, medicine_db):
        """Should delete manufacturer without brands."""
        manufacturer = Manufacturer(manufacturer_name="Delete Test")
        medicine_db.add(manufacturer)
        await medicine_db.commit()
        await medicine_db.refresh(manufacturer)

        response = await admin_client.delete(
            f"/api/v1/admin/manufacturers/{manufacturer.manufacturer_id}"
        )

        assert response.status_code == 204

        # Verify deleted
        from sqlalchemy import select
        result = await medicine_db.execute(
            select(Manufacturer).where(
                Manufacturer.manufacturer_id == manufacturer.manufacturer_id
            )
        )
        assert result.scalar_one_or_none() is None

    async def test_delete_manufacturer_with_brands(
        self, admin_client, medicine_db, sample_salt_strength
    ):
        """Should return 409 if manufacturer has brands."""
        # Create manufacturer with brand
        manufacturer = Manufacturer(manufacturer_name="Has Brands")
        medicine_db.add(manufacturer)
        await medicine_db.flush()

        from app.models.medicine.commercial import Brand, BrandComposition
        brand = Brand(
            brand_name="Test Brand",
            manufacturer_id=manufacturer.manufacturer_id,
            is_discontinued=False
        )
        medicine_db.add(brand)
        await medicine_db.flush()

        # Add composition
        composition = BrandComposition(
            brand_id=brand.brand_id,
            salt_strength_id=sample_salt_strength.salt_strength_id,
            sequence=1
        )
        medicine_db.add(composition)
        await medicine_db.commit()

        # Try to delete manufacturer
        response = await admin_client.delete(
            f"/api/v1/admin/manufacturers/{manufacturer.manufacturer_id}"
        )

        assert response.status_code == 409
        assert "brand" in response.json()["detail"].lower()

    async def test_delete_manufacturer_not_found(self, admin_client, medicine_db):
        """Should return 404 for non-existent manufacturer."""
        fake_id = uuid4()

        response = await admin_client.delete(
            f"/api/v1/admin/manufacturers/{fake_id}"
        )

        assert response.status_code == 404
