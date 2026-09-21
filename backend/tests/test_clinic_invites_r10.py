"""Round-10 coverage for the clinic invite / join-request router.

Covers:
- POST   /api/v1/clinics/{id}/invites — owner/admin-only create, role
  whitelist (doctor|receptionist), email invites, max_uses.
- GET    /api/v1/clinics/{id}/invites — list, revoked excluded.
- DELETE /api/v1/clinics/{id}/invites/{iid} — revoke (soft delete).
- POST   /api/v1/invites/redeem — happy path, role gating (doctor invites
  need the doctor account role; receptionist invites are open), uniform
  403 anti-probing for non-doctors, expired/exhausted/already-member.
- GET    /api/v1/clinics/search — name search, min-length, inactive hidden.
- POST   /api/v1/clinics/{id}/join-request + review lifecycle.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinic import Clinic, ClinicMembership
from app.models.clinic_invite import ClinicInvite, ClinicJoinRequest
from app.models.notification import Notification
from app.models.user import User
from tests.conftest import make_auth_header

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def clinic(db: AsyncSession, doctor_user: User) -> Clinic:
    c = Clinic(id=uuid.uuid4(), name="Invite Clinic", city="Pune", created_by=doctor_user.id)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def _membership(
    db: AsyncSession, clinic_id, user_id, role: str, is_active: bool = True
) -> ClinicMembership:
    m = ClinicMembership(
        id=uuid.uuid4(), clinic_id=clinic_id, user_id=user_id, role=role,
        is_active=is_active,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


@pytest_asyncio.fixture
async def owner_membership(db: AsyncSession, clinic: Clinic, doctor_user: User):
    return await _membership(db, clinic.id, doctor_user.id, "owner")


async def _make_user(
    db: AsyncSession, role: str = "doctor", name: str = "Staff User"
) -> tuple[User, dict]:
    user = User(
        keycloak_sub=f"{role}-{uuid.uuid4()}",
        email=f"{uuid.uuid4().hex[:8]}@test.com",
        full_name=name,
        role=role,
    )
    db.add(user)
    await db.commit()
    return user, make_auth_header(user, roles=[role])


async def _make_invite(
    db: AsyncSession,
    clinic_id,
    creator_id,
    *,
    code: str = "INVITE1",
    role: str = "doctor",
    invite_type: str = "code",
    expires_at: datetime | None = None,
    max_uses: int | None = None,
    use_count: int = 0,
    deleted: bool = False,
) -> ClinicInvite:
    invite = ClinicInvite(
        id=uuid.uuid4(),
        clinic_id=clinic_id,
        invite_type=invite_type,
        code=code,
        role=role,
        expires_at=expires_at
        if expires_at is not None
        else datetime.now(timezone.utc) + timedelta(days=7),
        max_uses=max_uses,
        use_count=use_count,
        created_by=creator_id,
        deleted_at=datetime.now(timezone.utc) if deleted else None,
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return invite


# ---------------------------------------------------------------------------
# POST /clinics/{id}/invites — create
# ---------------------------------------------------------------------------


class TestCreateInvite:
    async def test_owner_creates_code_invite(
        self, doctor_client, clinic, owner_membership
    ):
        resp = await doctor_client.post(
            f"/api/v1/clinics/{clinic.id}/invites", json={}
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert len(body["code"]) == 16
        assert body["role"] == "doctor"
        assert body["invite_type"] == "code"
        assert datetime.fromisoformat(body["expires_at"]) > datetime.now(timezone.utc)

    async def test_admin_member_creates_invite(
        self, doctor_client, db, clinic, doctor_user
    ):
        await _membership(db, clinic.id, doctor_user.id, "admin")
        resp = await doctor_client.post(
            f"/api/v1/clinics/{clinic.id}/invites",
            json={"role": "receptionist", "expires_days": 3, "max_uses": 5},
        )
        assert resp.status_code == 201
        assert resp.json()["role"] == "receptionist"

    async def test_email_invite(
        self, doctor_client, db, clinic, owner_membership
    ):
        resp = await doctor_client.post(
            f"/api/v1/clinics/{clinic.id}/invites",
            json={"invite_type": "email", "email": "newdoc@test.com"},
        )
        assert resp.status_code == 201
        invite = await db.scalar(
            select(ClinicInvite).where(ClinicInvite.code == resp.json()["code"])
        )
        assert invite.invite_type == "email"
        assert invite.email == "newdoc@test.com"

    async def test_plain_doctor_member_forbidden(
        self, doctor_client, db, clinic, doctor_user
    ):
        """A 'doctor' membership is not administrative — cannot mint invites."""
        await _membership(db, clinic.id, doctor_user.id, "doctor")
        resp = await doctor_client.post(
            f"/api/v1/clinics/{clinic.id}/invites", json={}
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    async def test_receptionist_member_forbidden(
        self, doctor_client, db, clinic, doctor_user
    ):
        await _membership(db, clinic.id, doctor_user.id, "receptionist")
        resp = await doctor_client.post(
            f"/api/v1/clinics/{clinic.id}/invites", json={}
        )
        assert resp.status_code == 403

    async def test_non_member_forbidden(self, client, db, clinic):
        _, outsider_auth = await _make_user(db, "doctor")
        resp = await client.post(
            f"/api/v1/clinics/{clinic.id}/invites", json={}, headers=outsider_auth
        )
        assert resp.status_code == 403

    async def test_platform_admin_without_membership_forbidden(
        self, admin_client, clinic
    ):
        """Invite authz is membership-based — a global admin who is not a
        clinic member cannot create invites."""
        resp = await admin_client.post(f"/api/v1/clinics/{clinic.id}/invites", json={})
        assert resp.status_code == 403

    async def test_invalid_clinic_id_422(self, doctor_client):
        resp = await doctor_client.post("/api/v1/clinics/nope/invites", json={})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "INVALID_ID"

    async def test_privileged_role_rejected(
        self, doctor_client, clinic, owner_membership
    ):
        """role is Literal['doctor','receptionist'] — 'owner' must never be
        mintable via invite."""
        resp = await doctor_client.post(
            f"/api/v1/clinics/{clinic.id}/invites", json={"role": "owner"}
        )
        assert resp.status_code == 422

    async def test_unauthenticated_401(self, client, clinic):
        resp = await client.post(f"/api/v1/clinics/{clinic.id}/invites", json={})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /clinics/{id}/invites — list
# ---------------------------------------------------------------------------


class TestListInvites:
    async def test_lists_active_invites(
        self, doctor_client, db, clinic, owner_membership, doctor_user
    ):
        invite = await _make_invite(
            db, clinic.id, doctor_user.id, code="LISTME1", max_uses=3
        )
        resp = await doctor_client.get(f"/api/v1/clinics/{clinic.id}/invites")
        assert resp.status_code == 200, resp.text
        rows = resp.json()["data"]
        assert len(rows) == 1
        assert rows[0]["id"] == str(invite.id)
        assert rows[0]["code"] == "LISTME1"
        assert rows[0]["max_uses"] == 3
        assert rows[0]["use_count"] == 0

    async def test_revoked_invite_excluded(
        self, doctor_client, db, clinic, owner_membership, doctor_user
    ):
        await _make_invite(db, clinic.id, doctor_user.id, code="DEADBEEF", deleted=True)
        resp = await doctor_client.get(f"/api/v1/clinics/{clinic.id}/invites")
        assert resp.json()["data"] == []

    async def test_non_admin_member_forbidden(
        self, doctor_client, db, clinic, doctor_user
    ):
        await _membership(db, clinic.id, doctor_user.id, "doctor")
        resp = await doctor_client.get(f"/api/v1/clinics/{clinic.id}/invites")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# DELETE /clinics/{id}/invites/{iid} — revoke
# ---------------------------------------------------------------------------


class TestRevokeInvite:
    async def test_revoke_soft_deletes_and_blocks_redeem(
        self, client, db, clinic, owner_membership, doctor_user
    ):
        invite = await _make_invite(db, clinic.id, doctor_user.id, code="REVOKE1")
        owner_auth = make_auth_header(doctor_user, roles=["doctor"])

        resp = await client.delete(
            f"/api/v1/clinics/{clinic.id}/invites/{invite.id}", headers=owner_auth
        )
        assert resp.status_code == 204

        await db.refresh(invite)
        assert invite.deleted_at is not None

        redeemer, redeemer_auth = await _make_user(db, "doctor")
        redeem = await client.post(
            "/api/v1/invites/redeem", json={"code": "REVOKE1"}, headers=redeemer_auth
        )
        assert redeem.status_code == 404
        assert redeem.json()["error"]["code"] == "INVALID_CODE"

    async def test_revoke_unknown_404(
        self, doctor_client, clinic, owner_membership
    ):
        resp = await doctor_client.delete(
            f"/api/v1/clinics/{clinic.id}/invites/{uuid.uuid4()}"
        )
        assert resp.status_code == 404

    async def test_revoke_other_clinics_invite_404(
        self, doctor_client, db, clinic, owner_membership, doctor_user
    ):
        other = Clinic(id=uuid.uuid4(), name="Other", created_by=doctor_user.id)
        db.add(other)
        await db.commit()
        invite = await _make_invite(db, other.id, doctor_user.id, code="OTHERCL1")

        resp = await doctor_client.delete(
            f"/api/v1/clinics/{clinic.id}/invites/{invite.id}"
        )
        assert resp.status_code == 404
        await db.refresh(invite)
        assert invite.deleted_at is None

    async def test_revoke_non_admin_member_403(
        self, doctor_client, db, clinic, doctor_user
    ):
        await _membership(db, clinic.id, doctor_user.id, "doctor")
        invite = await _make_invite(db, clinic.id, doctor_user.id, code="KEEPME1")
        resp = await doctor_client.delete(
            f"/api/v1/clinics/{clinic.id}/invites/{invite.id}"
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /invites/redeem
# ---------------------------------------------------------------------------


class TestRedeemInvite:
    async def test_doctor_redeems_doctor_invite(
        self, client, db, clinic, owner_membership, doctor_user
    ):
        invite = await _make_invite(db, clinic.id, doctor_user.id, code="REDEEM1")
        redeemer, auth = await _make_user(db, "doctor", name="Joining Doc")

        resp = await client.post(
            "/api/v1/invites/redeem", json={"code": "redeem1"}, headers=auth
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["clinic_id"] == str(clinic.id)
        assert body["role"] == "doctor"

        membership = await db.scalar(
            select(ClinicMembership).where(
                ClinicMembership.user_id == redeemer.id,
                ClinicMembership.clinic_id == clinic.id,
            )
        )
        assert membership is not None
        assert membership.role == "doctor"
        assert membership.is_active is True

        await db.refresh(invite)
        assert invite.use_count == 1

    async def test_patient_redeems_receptionist_invite(
        self, client, db, clinic, owner_membership, doctor_user, patient_user
    ):
        """Receptionist invites are open to any authenticated user — the
        membership role (not the account role) scopes access."""
        await _make_invite(
            db, clinic.id, doctor_user.id, code="FRONTDESK", role="receptionist"
        )
        resp = await client.post(
            "/api/v1/invites/redeem",
            json={"code": "FRONTDESK"},
            headers=make_auth_header(patient_user),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["role"] == "receptionist"

        membership = await db.scalar(
            select(ClinicMembership).where(
                ClinicMembership.user_id == patient_user.id,
                ClinicMembership.clinic_id == clinic.id,
            )
        )
        assert membership.role == "receptionist"

    async def test_patient_cannot_redeem_doctor_invite(
        self, client, db, clinic, owner_membership, doctor_user, patient_user
    ):
        await _make_invite(db, clinic.id, doctor_user.id, code="DOCONLY1")
        resp = await client.post(
            "/api/v1/invites/redeem",
            json={"code": "DOCONLY1"},
            headers=make_auth_header(patient_user),
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    async def test_doctor_unknown_code_404(self, client, db, clinic, doctor_user):
        _, auth = await _make_user(db, "doctor")
        resp = await client.post(
            "/api/v1/invites/redeem", json={"code": "NOSUCHCODE"}, headers=auth
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "INVALID_CODE"

    async def test_non_doctor_unknown_code_403(
        self, client, db, patient_user
    ):
        """Uniform 403 for missing/doctor invites — non-doctors cannot probe
        code validity."""
        resp = await client.post(
            "/api/v1/invites/redeem",
            json={"code": "WHATEVER1"},
            headers=make_auth_header(patient_user),
        )
        assert resp.status_code == 403

    async def test_expired_invite_400(
        self, client, db, clinic, owner_membership, doctor_user
    ):
        await _make_invite(
            db, clinic.id, doctor_user.id, code="EXPIRED1",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        _, auth = await _make_user(db, "doctor")
        resp = await client.post(
            "/api/v1/invites/redeem", json={"code": "EXPIRED1"}, headers=auth
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "EXPIRED_CODE"

    async def test_exhausted_invite_400(
        self, client, db, clinic, owner_membership, doctor_user
    ):
        invite = await _make_invite(
            db, clinic.id, doctor_user.id, code="ONEUSE1", max_uses=1
        )
        first, first_auth = await _make_user(db, "doctor", name="First Doc")
        resp1 = await client.post(
            "/api/v1/invites/redeem", json={"code": "ONEUSE1"}, headers=first_auth
        )
        assert resp1.status_code == 200

        _, second_auth = await _make_user(db, "doctor", name="Second Doc")
        resp2 = await client.post(
            "/api/v1/invites/redeem", json={"code": "ONEUSE1"}, headers=second_auth
        )
        assert resp2.status_code == 400
        assert resp2.json()["error"]["code"] == "CODE_EXHAUSTED"

        await db.refresh(invite)
        assert invite.use_count == 1

    async def test_already_member_409(
        self, client, db, clinic, owner_membership, doctor_user
    ):
        await _make_invite(db, clinic.id, doctor_user.id, code="MEMBER1")
        resp = await client.post(
            "/api/v1/invites/redeem",
            json={"code": "MEMBER1"},
            headers=make_auth_header(doctor_user, roles=["doctor"]),
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "ALREADY_MEMBER"

    async def test_redeem_unauthenticated_401(self, client):
        resp = await client.post("/api/v1/invites/redeem", json={"code": "X"})
        assert resp.status_code == 401

    async def test_rejoin_after_membership_deactivated(
        self, client, db, clinic, owner_membership, doctor_user
    ):
        """A user whose membership was deactivated (is_active=False, not
        soft-deleted) should be able to rejoin via a fresh invite — or at
        worst get a clean 4xx, never a 500."""
        former, former_auth = await _make_user(db, "doctor", name="Former Member")
        await _membership(db, clinic.id, former.id, "doctor", is_active=False)
        await _make_invite(db, clinic.id, doctor_user.id, code="REJOIN1")

        resp = await client.post(
            "/api/v1/invites/redeem", json={"code": "REJOIN1"}, headers=former_auth
        )
        assert resp.status_code == 200
        active = await db.scalar(
            select(func.count()).select_from(ClinicMembership).where(
                ClinicMembership.user_id == former.id,
                ClinicMembership.clinic_id == clinic.id,
                ClinicMembership.is_active.is_(True),
                ClinicMembership.deleted_at.is_(None),
            )
        )
        assert active == 1


# ---------------------------------------------------------------------------
# GET /clinics/search
# ---------------------------------------------------------------------------


class TestClinicSearch:
    async def test_search_by_name(self, doctor_client, clinic):
        resp = await doctor_client.get("/api/v1/clinics/search", params={"q": "Invite"})
        assert resp.status_code == 200, resp.text
        rows = resp.json()["data"]
        assert len(rows) == 1
        assert rows[0]["id"] == str(clinic.id)
        assert rows[0]["city"] == "Pune"

    async def test_search_min_length(self, doctor_client):
        resp = await doctor_client.get("/api/v1/clinics/search", params={"q": "x"})
        assert resp.status_code == 422

    async def test_search_excludes_inactive(self, doctor_client, db, clinic):
        clinic.is_active = False
        await db.commit()
        resp = await doctor_client.get("/api/v1/clinics/search", params={"q": "Invite"})
        assert resp.json()["data"] == []

    async def test_search_requires_auth(self, client):
        resp = await client.get("/api/v1/clinics/search", params={"q": "ab"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Join requests
# ---------------------------------------------------------------------------


class TestJoinRequests:
    async def test_create_join_request(
        self, client, db, clinic, doctor_user
    ):
        _, auth = await _make_user(db, "doctor", name="Applicant")
        resp = await client.post(
            f"/api/v1/clinics/{clinic.id}/join-request",
            json={"message": "please add me"},
            headers=auth,
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["status"] == "pending"

    async def test_duplicate_pending_request_409(
        self, client, db, clinic
    ):
        _, auth = await _make_user(db, "doctor")
        first = await client.post(
            f"/api/v1/clinics/{clinic.id}/join-request", json={}, headers=auth
        )
        assert first.status_code == 201
        second = await client.post(
            f"/api/v1/clinics/{clinic.id}/join-request", json={}, headers=auth
        )
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "REQUEST_EXISTS"

    async def test_existing_member_cannot_request(
        self, client, db, clinic, doctor_user
    ):
        await _membership(db, clinic.id, doctor_user.id, "doctor")
        resp = await client.post(
            f"/api/v1/clinics/{clinic.id}/join-request",
            json={},
            headers=make_auth_header(doctor_user, roles=["doctor"]),
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "ALREADY_MEMBER"

    async def test_join_request_nonexistent_clinic(
        self, client, db
    ):
        """Joining a clinic that does not exist should be a clean 404, not a
        FK violation / 500."""
        _, auth = await _make_user(db, "doctor")
        resp = await client.post(
            f"/api/v1/clinics/{uuid.uuid4()}/join-request", json={}, headers=auth
        )
        assert resp.status_code == 404

    async def test_list_join_requests_admin(
        self, doctor_client, db, clinic, owner_membership
    ):
        requester, auth = await _make_user(db, "doctor", name="Applicant Doc")
        await doctor_client.post(
            f"/api/v1/clinics/{clinic.id}/join-request",
            json={"message": "hi"},
            headers=auth,
        )
        resp = await doctor_client.get(f"/api/v1/clinics/{clinic.id}/join-requests")
        assert resp.status_code == 200, resp.text
        rows = resp.json()["data"]
        assert len(rows) == 1
        assert rows[0]["user_id"] == str(requester.id)
        assert rows[0]["full_name"] == "Applicant Doc"
        assert rows[0]["status"] == "pending"

    async def test_list_join_requests_status_filter(
        self, doctor_client, db, clinic, owner_membership
    ):
        requester, auth = await _make_user(db, "doctor")
        created = await doctor_client.post(
            f"/api/v1/clinics/{clinic.id}/join-request", json={}, headers=auth
        )
        rid = created.json()["id"]
        await doctor_client.put(
            f"/api/v1/clinics/{clinic.id}/join-requests/{rid}",
            json={"action": "rejected"},
        )
        pending = await doctor_client.get(f"/api/v1/clinics/{clinic.id}/join-requests")
        assert pending.json()["data"] == []
        all_rows = await doctor_client.get(
            f"/api/v1/clinics/{clinic.id}/join-requests", params={"status": "all"}
        )
        assert len(all_rows.json()["data"]) == 1

    async def test_list_join_requests_non_admin_403(
        self, doctor_client, db, clinic, doctor_user
    ):
        await _membership(db, clinic.id, doctor_user.id, "doctor")
        resp = await doctor_client.get(f"/api/v1/clinics/{clinic.id}/join-requests")
        assert resp.status_code == 403

    async def test_approve_creates_membership_and_notifies(
        self, doctor_client, db, clinic, owner_membership
    ):
        requester, auth = await _make_user(db, "doctor", name="Approve Me")
        created = await doctor_client.post(
            f"/api/v1/clinics/{clinic.id}/join-request",
            json={"message": "please"},
            headers=auth,
        )
        rid = created.json()["id"]

        resp = await doctor_client.put(
            f"/api/v1/clinics/{clinic.id}/join-requests/{rid}",
            json={"action": "approved", "role": "doctor"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "approved"

        membership = await db.scalar(
            select(ClinicMembership).where(
                ClinicMembership.user_id == requester.id,
                ClinicMembership.clinic_id == clinic.id,
            )
        )
        assert membership is not None
        assert membership.role == "doctor"

        notif = await db.scalar(
            select(Notification).where(Notification.user_id == requester.id)
        )
        assert notif is not None
        assert "approved" in notif.title

    async def test_reject_creates_no_membership(
        self, doctor_client, db, clinic, owner_membership
    ):
        requester, auth = await _make_user(db, "doctor")
        created = await doctor_client.post(
            f"/api/v1/clinics/{clinic.id}/join-request", json={}, headers=auth
        )
        rid = created.json()["id"]

        resp = await doctor_client.put(
            f"/api/v1/clinics/{clinic.id}/join-requests/{rid}",
            json={"action": "rejected"},
        )
        assert resp.status_code == 200
        membership = await db.scalar(
            select(ClinicMembership).where(
                ClinicMembership.user_id == requester.id,
                ClinicMembership.clinic_id == clinic.id,
            )
        )
        assert membership is None

    async def test_review_invalid_action_400(
        self, doctor_client, db, clinic, owner_membership
    ):
        _, auth = await _make_user(db, "doctor")
        created = await doctor_client.post(
            f"/api/v1/clinics/{clinic.id}/join-request", json={}, headers=auth
        )
        resp = await doctor_client.put(
            f"/api/v1/clinics/{clinic.id}/join-requests/{created.json()['id']}",
            json={"action": "maybe"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_ACTION"

    async def test_review_nonpending_404(
        self, doctor_client, db, clinic, owner_membership
    ):
        """Re-reviewing a decided request must 404, not double-approve."""
        _, auth = await _make_user(db, "doctor")
        created = await doctor_client.post(
            f"/api/v1/clinics/{clinic.id}/join-request", json={}, headers=auth
        )
        rid = created.json()["id"]
        await doctor_client.put(
            f"/api/v1/clinics/{clinic.id}/join-requests/{rid}",
            json={"action": "rejected"},
        )
        again = await doctor_client.put(
            f"/api/v1/clinics/{clinic.id}/join-requests/{rid}",
            json={"action": "approved"},
        )
        assert again.status_code == 404

    async def test_approve_after_requester_became_member(
        self, doctor_client, db, clinic, owner_membership, doctor_user
    ):
        """Race: requester redeems an invite while their join request is
        still pending; approving afterwards must not 500 or duplicate the
        membership."""
        requester, auth = await _make_user(db, "doctor")
        created = await doctor_client.post(
            f"/api/v1/clinics/{clinic.id}/join-request", json={}, headers=auth
        )
        rid = created.json()["id"]

        await _make_invite(db, clinic.id, doctor_user.id, code="PARALLEL1")
        redeem = await doctor_client.post(
            "/api/v1/invites/redeem", json={"code": "PARALLEL1"}, headers=auth
        )
        assert redeem.status_code == 200

        resp = await doctor_client.put(
            f"/api/v1/clinics/{clinic.id}/join-requests/{rid}",
            json={"action": "approved"},
        )
        assert resp.status_code == 200
        count = await db.scalar(
            select(func.count()).select_from(ClinicMembership).where(
                ClinicMembership.user_id == requester.id,
                ClinicMembership.clinic_id == clinic.id,
                ClinicMembership.deleted_at.is_(None),
            )
        )
        assert count == 1

    async def test_review_non_admin_403(
        self, client, db, clinic, owner_membership, doctor_user
    ):
        requester, auth = await _make_user(db, "doctor")
        created = await client.post(
            f"/api/v1/clinics/{clinic.id}/join-request", json={}, headers=auth
        )
        plain_member, member_auth = await _make_user(db, "doctor")
        await _membership(db, clinic.id, plain_member.id, "doctor")
        resp = await client.put(
            f"/api/v1/clinics/{clinic.id}/join-requests/{created.json()['id']}",
            json={"action": "approved"},
            headers=member_auth,
        )
        assert resp.status_code == 403
