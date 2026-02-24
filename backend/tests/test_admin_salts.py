"""Tests for admin salt management endpoints."""

import pytest
from uuid import uuid4

from app.models.medicine.salts import Salt, SaltStrength

pytestmark = pytest.mark.asyncio


class TestCreateSalt:
    """Test POST /api/v1/admin/salts endpoint."""

    async def test_create_salt_success(self, admin_client, medicine_db):
        """Should create salt with valid data."""
        request_data = {
            "salt_name": "Paracetamol",
            "description": "Analgesic and antipyretic",
            "chemical_formula": "C8H9NO2",
            "habit_forming": False,
            "prescription_required": False,
            "schedule": None,
            "pregnancy_category": "B",
            "lactation_safe": True
        }

        response = await admin_client.post("/api/v1/admin/salts", json=request_data)

        assert response.status_code == 201
        data = response.json()
        assert data["salt_name"] == "Paracetamol"
        assert data["description"] == "Analgesic and antipyretic"
        assert data["chemical_formula"] == "C8H9NO2"
        assert data["habit_forming"] is False
        assert "salt_id" in data

    async def test_create_salt_minimal(self, admin_client, medicine_db):
        """Should create salt with only required field."""
        request_data = {
            "salt_name": "Ibuprofen"
        }

        response = await admin_client.post("/api/v1/admin/salts", json=request_data)

        assert response.status_code == 201
        data = response.json()
        assert data["salt_name"] == "Ibuprofen"
        assert data["prescription_required"] is True  # Default value
        assert data["habit_forming"] is False  # Default value

    async def test_create_salt_duplicate_name(self, admin_client, medicine_db):
        """Should return 409 for duplicate salt name (case-insensitive)."""
        request_data = {
            "salt_name": "Aspirin"
        }
        response = await admin_client.post("/api/v1/admin/salts", json=request_data)
        assert response.status_code == 201

        # Exact duplicate
        response = await admin_client.post("/api/v1/admin/salts", json=request_data)
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

        # Case-insensitive duplicate
        request_data["salt_name"] = "ASPIRIN"
        response = await admin_client.post("/api/v1/admin/salts", json=request_data)
        assert response.status_code == 409

    async def test_create_salt_with_strengths(self, admin_client, medicine_db):
        """Should create salt with initial strengths."""
        request_data = {
            "salt_name": "Amoxicillin",
            "prescription_required": True,
            "strengths": [
                {"strength_value": 250, "strength_unit": "mg"},
                {"strength_value": 500, "strength_unit": "mg"}
            ]
        }

        response = await admin_client.post("/api/v1/admin/salts", json=request_data)

        assert response.status_code == 201
        data = response.json()
        assert data["salt_name"] == "Amoxicillin"
        assert len(data["strengths"]) == 2
        assert data["strengths"][0]["strength_value"] == 250
        assert data["strengths"][1]["strength_value"] == 500


class TestUpdateSalt:
    """Test PUT /api/v1/admin/salts/{id} endpoint."""

    async def test_update_salt_success(self, admin_client, medicine_db):
        """Should update salt with valid data."""
        # Create salt first
        salt = Salt(
            salt_name="Test Salt",
            description="Old description",
            habit_forming=False
        )
        medicine_db.add(salt)
        await medicine_db.commit()
        await medicine_db.refresh(salt)

        # Update it
        request_data = {
            "description": "New description",
            "prescription_required": True
        }

        response = await admin_client.put(
            f"/api/v1/admin/salts/{salt.salt_id}",
            json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["salt_name"] == "Test Salt"  # Unchanged
        assert data["description"] == "New description"  # Updated
        assert data["prescription_required"] is True  # Updated

    async def test_update_salt_partial(self, admin_client, medicine_db):
        """Should update only specified fields."""
        salt = Salt(
            salt_name="Partial Update Test",
            description="Original",
            habit_forming=False
        )
        medicine_db.add(salt)
        await medicine_db.commit()
        await medicine_db.refresh(salt)

        # Update only salt_name
        request_data = {
            "salt_name": "Updated Name"
        }

        response = await admin_client.put(
            f"/api/v1/admin/salts/{salt.salt_id}",
            json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["salt_name"] == "Updated Name"
        assert data["description"] == "Original"  # Unchanged

    async def test_update_salt_duplicate_name(self, admin_client, medicine_db):
        """Should return 409 when updating to duplicate name."""
        salt1 = Salt(salt_name="Salt One")
        salt2 = Salt(salt_name="Salt Two")
        medicine_db.add_all([salt1, salt2])
        await medicine_db.commit()
        await medicine_db.refresh(salt1)
        await medicine_db.refresh(salt2)

        # Try to rename salt2 to salt1's name
        request_data = {
            "salt_name": "Salt One"
        }

        response = await admin_client.put(
            f"/api/v1/admin/salts/{salt2.salt_id}",
            json=request_data
        )

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    async def test_update_salt_not_found(self, admin_client, medicine_db):
        """Should return 404 for non-existent salt."""
        fake_id = uuid4()
        request_data = {
            "description": "New description"
        }

        response = await admin_client.put(
            f"/api/v1/admin/salts/{fake_id}",
            json=request_data
        )

        assert response.status_code == 404


class TestDeleteSalt:
    """Test DELETE /api/v1/admin/salts/{id} endpoint."""

    async def test_delete_salt_success(self, admin_client, medicine_db):
        """Should delete salt without strengths or brand usage."""
        salt = Salt(salt_name="Delete Test")
        medicine_db.add(salt)
        await medicine_db.commit()
        await medicine_db.refresh(salt)

        response = await admin_client.delete(
            f"/api/v1/admin/salts/{salt.salt_id}"
        )

        assert response.status_code == 204

        # Verify deleted
        from sqlalchemy import select
        result = await medicine_db.execute(
            select(Salt).where(Salt.salt_id == salt.salt_id)
        )
        assert result.scalar_one_or_none() is None

    async def test_delete_salt_with_strengths(self, admin_client, medicine_db):
        """Should return 409 if salt has strengths."""
        salt = Salt(salt_name="Has Strengths")
        medicine_db.add(salt)
        await medicine_db.flush()

        strength = SaltStrength(
            salt_id=salt.salt_id,
            strength_value=500,
            strength_unit="mg"
        )
        medicine_db.add(strength)
        await medicine_db.commit()

        response = await admin_client.delete(
            f"/api/v1/admin/salts/{salt.salt_id}"
        )

        assert response.status_code == 409
        assert "strength" in response.json()["detail"].lower()

    async def test_delete_salt_not_found(self, admin_client, medicine_db):
        """Should return 404 for non-existent salt."""
        fake_id = uuid4()

        response = await admin_client.delete(
            f"/api/v1/admin/salts/{fake_id}"
        )

        assert response.status_code == 404
