import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import create_test_token


@pytest.mark.asyncio
async def test_me_auto_provisions_patient(client: AsyncClient):
    """First request with a valid Keycloak token auto-provisions the user."""
    sub = str(uuid.uuid4())
    token = create_test_token(sub=sub, email="patient@test.com", name="Test Patient", roles=["patient"])

    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Test Patient"
    assert data["email"] == "patient@test.com"
    assert data["role"] == "patient"


@pytest.mark.asyncio
async def test_me_auto_provisions_doctor(client: AsyncClient):
    """Doctor role in token creates both User and Doctor profile."""
    sub = str(uuid.uuid4())
    token = create_test_token(sub=sub, email="doctor@test.com", name="Dr. Test", roles=["doctor"])

    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "doctor"
    assert data["full_name"] == "Dr. Test"


@pytest.mark.asyncio
async def test_me_returns_existing_user(client: AsyncClient):
    """Second request with same sub returns the same user."""
    sub = str(uuid.uuid4())
    token = create_test_token(sub=sub, email="existing@test.com", name="Existing User", roles=["patient"])

    # First call provisions
    resp1 = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp1.status_code == 200
    user_id = resp1.json()["id"]

    # Second call returns same user
    resp2 = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp2.status_code == 200
    assert resp2.json()["id"] == user_id


@pytest.mark.asyncio
async def test_me_syncs_updated_claims(client: AsyncClient):
    """If token claims change (e.g. name), local DB is synced."""
    sub = str(uuid.uuid4())
    token1 = create_test_token(sub=sub, email="sync@test.com", name="Old Name", roles=["patient"])

    resp1 = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token1}"})
    assert resp1.json()["full_name"] == "Old Name"

    token2 = create_test_token(sub=sub, email="sync@test.com", name="New Name", roles=["patient"])
    resp2 = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token2}"})
    assert resp2.json()["full_name"] == "New Name"


@pytest.mark.asyncio
async def test_invalid_token_returns_401(client: AsyncClient):
    """A garbage token should be rejected."""
    response = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_signup_endpoint_removed(client: AsyncClient):
    """POST /signup should no longer exist."""
    response = await client.post("/api/v1/auth/signup", json={
        "email": "test@test.com",
        "password": "testpass123",
        "full_name": "Test",
        "role": "patient",
    })
    assert response.status_code == 405 or response.status_code == 404


@pytest.mark.asyncio
async def test_login_endpoint_removed(client: AsyncClient):
    """POST /login should no longer exist."""
    response = await client.post("/api/v1/auth/login", json={
        "email": "test@test.com",
        "password": "testpass123",
    })
    assert response.status_code == 405 or response.status_code == 404
