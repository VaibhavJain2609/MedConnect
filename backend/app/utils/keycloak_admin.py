import httpx
from fastapi import HTTPException, status

from app.config import settings


async def assign_realm_role(keycloak_user_id: str, role_name: str) -> None:
    """Assign a realm role to a Keycloak user via Admin REST API."""
    base = settings.KEYCLOAK_URL
    realm = settings.KEYCLOAK_REALM

    async with httpx.AsyncClient() as client:
        # 1. Get admin token from master realm
        token_resp = await client.post(
            f"{base}/realms/master/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": settings.KEYCLOAK_ADMIN_USER,
                "password": settings.KEYCLOAK_ADMIN_PASSWORD,
            },
        )
        if token_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"error": {"code": "KEYCLOAK_ADMIN_AUTH_FAILED", "message": "Failed to authenticate with Keycloak admin"}},
            )
        admin_token = token_resp.json()["access_token"]

        headers = {"Authorization": f"Bearer {admin_token}"}

        # 2. Get role representation
        role_resp = await client.get(
            f"{base}/admin/realms/{realm}/roles/{role_name}",
            headers=headers,
        )
        if role_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"error": {"code": "KEYCLOAK_ROLE_NOT_FOUND", "message": f"Role '{role_name}' not found in Keycloak"}},
            )
        role = role_resp.json()

        # 3. Assign role to user
        assign_resp = await client.post(
            f"{base}/admin/realms/{realm}/users/{keycloak_user_id}/role-mappings/realm",
            headers=headers,
            json=[role],
        )
        if assign_resp.status_code not in (200, 204):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"error": {"code": "KEYCLOAK_ROLE_ASSIGN_FAILED", "message": "Failed to assign role in Keycloak"}},
            )
