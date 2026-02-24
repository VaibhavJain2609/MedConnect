"""Tests for admin brand management endpoints."""

import pytest
from datetime import date
from uuid import uuid4

from app.models.medicine.commercial import Brand, Manufacturer, BrandComposition
from app.models.medicine.salts import Salt, SaltStrength
from app.models.medicine.classifications import TherapeuticClass


pytestmark = pytest.mark.asyncio


class TestCreateBrand:
    """Test POST /api/v1/admin/brands endpoint."""

    async def test_create_brand_success(
        self, admin_client, medicine_db, admin_user, sample_manufacturer, sample_salt_strength
    ):
        """Should create a brand with valid data."""
        request_data = {
            "brand_name": "Crocin 500",
            "manufacturer_id": str(sample_manufacturer.manufacturer_id),
            "is_discontinued": False,
            "drug_type": "allopathy",
            "launch_date": "2020-01-01",
            "compositions": [
                {
                    "salt_strength_id": str(sample_salt_strength.salt_strength_id),
                    "sequence": 1
                }
            ]
        }

        response = await admin_client.post("/api/v1/admin/brands", json=request_data)

        assert response.status_code == 201
        data = response.json()
        assert data["brand_name"] == "Crocin 500"
        assert data["manufacturer_name"] == sample_manufacturer.manufacturer_name
        assert data["is_discontinued"] is False
        assert "salt_composition" in data

    async def test_create_brand_combination_drug(
        self, admin_client, medicine_db, sample_manufacturer, sample_salt_strength
    ):
        """Should create a combination drug with multiple salts."""
        # Create second salt and strength
        salt2 = Salt(salt_name="Caffeine", chemical_formula="C8H10N4O2")
        medicine_db.add(salt2)
        await medicine_db.flush()

        strength2 = SaltStrength(
            salt_id=salt2.salt_id,
            strength_value=65,
            strength_unit="mg"
        )
        medicine_db.add(strength2)
        await medicine_db.commit()

        request_data = {
            "brand_name": "Saridon",
            "manufacturer_id": str(sample_manufacturer.manufacturer_id),
            "compositions": [
                {
                    "salt_strength_id": str(sample_salt_strength.salt_strength_id),
                    "sequence": 1
                },
                {
                    "salt_strength_id": str(strength2.salt_strength_id),
                    "sequence": 2
                }
            ]
        }

        response = await admin_client.post("/api/v1/admin/brands", json=request_data)

        assert response.status_code == 201
        data = response.json()
        assert data["brand_name"] == "Saridon"
        assert "+" in data["salt_composition"]  # Combination drug indicator

    async def test_create_brand_nonexistent_manufacturer(
        self, admin_client, sample_salt_strength
    ):
        """Should return 404 if manufacturer doesn't exist."""
        request_data = {
            "brand_name": "Test Brand",
            "manufacturer_id": str(uuid4()),
            "compositions": [
                {
                    "salt_strength_id": str(sample_salt_strength.salt_strength_id),
                    "sequence": 1
                }
            ]
        }

        response = await admin_client.post("/api/v1/admin/brands", json=request_data)

        assert response.status_code == 404
        assert "Manufacturer" in response.json()["detail"]

    async def test_create_brand_nonexistent_salt_strength(
        self, admin_client, sample_manufacturer
    ):
        """Should return 404 if salt_strength doesn't exist."""
        request_data = {
            "brand_name": "Test Brand",
            "manufacturer_id": str(sample_manufacturer.manufacturer_id),
            "compositions": [
                {
                    "salt_strength_id": str(uuid4()),
                    "sequence": 1
                }
            ]
        }

        response = await admin_client.post("/api/v1/admin/brands", json=request_data)

        assert response.status_code == 404
        assert "Salt strengths not found" in response.json()["detail"]

    async def test_create_brand_duplicate(
        self, admin_client, sample_brand, sample_manufacturer, sample_salt_strength
    ):
        """Should return 409 if brand+manufacturer already exists."""
        request_data = {
            "brand_name": sample_brand.brand_name,
            "manufacturer_id": str(sample_brand.manufacturer_id),
            "compositions": [
                {
                    "salt_strength_id": str(sample_salt_strength.salt_strength_id),
                    "sequence": 1
                }
            ]
        }

        response = await admin_client.post("/api/v1/admin/brands", json=request_data)

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    async def test_create_brand_unauthorized(
        self, client, sample_manufacturer, sample_salt_strength
    ):
        """Should return 401 without authentication."""
        request_data = {
            "brand_name": "Test Brand",
            "manufacturer_id": str(sample_manufacturer.manufacturer_id),
            "compositions": [
                {
                    "salt_strength_id": str(sample_salt_strength.salt_strength_id),
                    "sequence": 1
                }
            ]
        }

        response = await client.post("/api/v1/admin/brands", json=request_data)

        assert response.status_code == 401

    async def test_create_brand_forbidden_non_admin(
        self, patient_client, sample_manufacturer, sample_salt_strength
    ):
        """Should return 403 for non-admin users."""
        request_data = {
            "brand_name": "Test Brand",
            "manufacturer_id": str(sample_manufacturer.manufacturer_id),
            "compositions": [
                {
                    "salt_strength_id": str(sample_salt_strength.salt_strength_id),
                    "sequence": 1
                }
            ]
        }

        response = await patient_client.post("/api/v1/admin/brands", json=request_data)

        assert response.status_code == 403

    async def test_create_brand_empty_compositions(
        self, admin_client, sample_manufacturer
    ):
        """Should return 422 if compositions list is empty."""
        request_data = {
            "brand_name": "Test Brand",
            "manufacturer_id": str(sample_manufacturer.manufacturer_id),
            "compositions": []
        }

        response = await admin_client.post("/api/v1/admin/brands", json=request_data)

        assert response.status_code == 422


class TestUpdateBrand:
    """Test PUT /api/v1/admin/brands/{brand_id} endpoint."""

    async def test_update_brand_name(
        self, admin_client, medicine_db, sample_brand
    ):
        """Should update brand name."""
        request_data = {
            "brand_name": "Crocin Advanced"
        }

        response = await admin_client.put(
            f"/api/v1/admin/brands/{sample_brand.brand_id}",
            json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["brand_name"] == "Crocin Advanced"

    async def test_update_brand_discontinued_status(
        self, admin_client, sample_brand
    ):
        """Should update discontinued status."""
        request_data = {
            "is_discontinued": True,
            "discontinuation_date": "2024-12-31"
        }

        response = await admin_client.put(
            f"/api/v1/admin/brands/{sample_brand.brand_id}",
            json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_discontinued"] is True
        assert data["discontinuation_date"] == "2024-12-31"

    async def test_update_brand_compositions(
        self, admin_client, medicine_db, sample_brand
    ):
        """Should replace brand compositions."""
        # Create new salt and strength
        new_salt = Salt(salt_name="Ibuprofen")
        medicine_db.add(new_salt)
        await medicine_db.flush()

        new_strength = SaltStrength(
            salt_id=new_salt.salt_id,
            strength_value=400,
            strength_unit="mg"
        )
        medicine_db.add(new_strength)
        await medicine_db.commit()

        request_data = {
            "compositions": [
                {
                    "salt_strength_id": str(new_strength.salt_strength_id),
                    "sequence": 1
                }
            ]
        }

        response = await admin_client.put(
            f"/api/v1/admin/brands/{sample_brand.brand_id}",
            json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert "Ibuprofen" in data["salt_composition"]

    async def test_update_brand_not_found(self, admin_client):
        """Should return 404 if brand doesn't exist."""
        request_data = {
            "brand_name": "Updated Name"
        }

        response = await admin_client.put(
            f"/api/v1/admin/brands/{uuid4()}",
            json=request_data
        )

        assert response.status_code == 404

    async def test_update_brand_duplicate_name(
        self, admin_client, medicine_db, sample_brand, sample_manufacturer
    ):
        """Should return 409 if updated name conflicts with existing brand."""
        # Create another brand
        other_brand = Brand(
            brand_name="Other Brand",
            manufacturer_id=sample_manufacturer.manufacturer_id
        )
        medicine_db.add(other_brand)
        await medicine_db.commit()

        request_data = {
            "brand_name": "Other Brand"
        }

        response = await admin_client.put(
            f"/api/v1/admin/brands/{sample_brand.brand_id}",
            json=request_data
        )

        assert response.status_code == 409

    async def test_update_brand_unauthorized(self, client, sample_brand):
        """Should return 401 without authentication."""
        request_data = {"brand_name": "Updated"}

        response = await client.put(
            f"/api/v1/admin/brands/{sample_brand.brand_id}",
            json=request_data
        )

        assert response.status_code == 401


class TestDeleteBrand:
    """Test DELETE /api/v1/admin/brands/{brand_id} endpoint."""

    async def test_delete_brand_success(
        self, admin_client, medicine_db, sample_brand
    ):
        """Should delete a brand."""
        brand_id = sample_brand.brand_id

        response = await admin_client.delete(f"/api/v1/admin/brands/{brand_id}")

        assert response.status_code == 204

        # Verify deletion
        from sqlalchemy import select
        result = await medicine_db.execute(
            select(Brand).where(Brand.brand_id == brand_id)
        )
        assert result.scalar_one_or_none() is None

    async def test_delete_brand_cascades_compositions(
        self, admin_client, medicine_db, sample_brand
    ):
        """Should cascade delete brand compositions."""
        brand_id = sample_brand.brand_id

        # Verify compositions exist
        from sqlalchemy import select
        result = await medicine_db.execute(
            select(BrandComposition).where(BrandComposition.brand_id == brand_id)
        )
        assert len(result.scalars().all()) > 0

        # Delete brand
        response = await admin_client.delete(f"/api/v1/admin/brands/{brand_id}")
        assert response.status_code == 204

        # Verify compositions deleted
        result = await medicine_db.execute(
            select(BrandComposition).where(BrandComposition.brand_id == brand_id)
        )
        assert len(result.scalars().all()) == 0

    async def test_delete_brand_not_found(self, admin_client):
        """Should return 404 if brand doesn't exist."""
        response = await admin_client.delete(f"/api/v1/admin/brands/{uuid4()}")

        assert response.status_code == 404

    async def test_delete_brand_unauthorized(self, client, sample_brand):
        """Should return 401 without authentication."""
        response = await client.delete(f"/api/v1/admin/brands/{sample_brand.brand_id}")

        assert response.status_code == 401
