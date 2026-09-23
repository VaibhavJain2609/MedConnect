"""``Idempotency-Key`` support for double-submit protection on POST endpoints.

Design (deliberately small — table + dependency + route class):

- A route opts in via ``dependencies=[Depends(idempotent("<endpoint>"))]``
  plus ``IdempotentRoute`` as the router's ``route_class`` (needed to persist
  the response after the handler runs — a plain dependency cannot see it).
- When the ``Idempotency-Key`` header is absent the request passes straight
  through — zero behaviour change.
- When present, the dependency claims ``(key, user_id, endpoint)`` by
  inserting a row and committing it *before* the handler runs:

  - existing fresh row with a stored response → replay it
    (``IdempotentReplay`` → stored status/body + ``Idempotent-Replay: true``);
  - existing fresh row with NULL response / lost insert race →
    409 ``IDEMPOTENCY_IN_PROGRESS`` — the original request is still running;
  - existing fresh row with a different request body →
    409 ``IDEMPOTENCY_MISMATCH``;
  - expired row (>24h) → deleted on read, request re-processes normally.

- ``IdempotentRoute`` writes the rendered response body/status onto the
  claim row after a successful handler run; on any exception (or a
  non-JSON / 5xx response) the claim is deleted so a later retry with the
  same key re-processes instead of being stuck on a poisoned key.

Bookkeeping uses ``request.app.dependency_overrides`` to resolve ``get_db``
so tests (single shared session override) and production (fresh session per
resolution) both work without touching handler signatures.
"""
import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.routing import APIRoute
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from app.database import get_db
from app.dependencies import get_current_user
from app.models.idempotency import IdempotencyKey
from app.models.user import User

logger = logging.getLogger(__name__)

# Replay window — keys older than this are ignored (and lazily deleted).
IDEMPOTENCY_TTL = timedelta(hours=24)

# request.state attribute carrying the claim for IdempotentRoute to fulfil.
_STATE_ATTR = "idempotency_claim"


class IdempotentReplay(Exception):
    """A fresh stored response exists for this key — replay it verbatim.

    Raised inside the ``idempotent`` dependency; converted to a real
    response by the exception handler registered in ``app.main``.
    """

    def __init__(self, response_json: Any, status_code: int | None):
        super().__init__("idempotent replay")
        self.response_json = response_json
        self.status_code = status_code or status.HTTP_200_OK


def _http_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message}},
    )


def _is_expired(row: IdempotencyKey) -> bool:
    created = row.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return created < datetime.now(timezone.utc) - IDEMPOTENCY_TTL


async def _fetch_key(
    db: AsyncSession, key: str, user_id: uuid.UUID, endpoint: str
) -> IdempotencyKey | None:
    result = await db.execute(
        select(IdempotencyKey).where(
            IdempotencyKey.key == key,
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.endpoint == endpoint,
        )
    )
    return result.scalar_one_or_none()


async def _resolve_session(request: Request):
    """Open a session via the request's (possibly overridden) ``get_db``.

    Returns ``(session, agen)`` — caller must ``await agen.aclose()`` so the
    generator's own teardown (session close in prod, no-op in tests) runs.
    """
    provider = request.app.dependency_overrides.get(get_db, get_db)
    agen = provider()
    session = await agen.__anext__()
    return session, agen


async def _discard_claim(request: Request, claim: dict) -> None:
    """Best-effort delete of a claim row (handler raised / bad response)."""
    try:
        session, agen = await _resolve_session(request)
        try:
            await session.execute(
                delete(IdempotencyKey).where(
                    IdempotencyKey.key == claim["key"],
                    IdempotencyKey.user_id == claim["user_id"],
                    IdempotencyKey.endpoint == claim["endpoint"],
                )
            )
            await session.commit()
        finally:
            await agen.aclose()
    except Exception:
        logger.warning("idempotency claim discard failed", exc_info=True)


async def _store_response(request: Request, claim: dict, response: Response) -> None:
    """Persist the rendered response onto the claim row. Never raises —
    a bookkeeping failure must not mask a completed request."""
    body = getattr(response, "body", None)
    payload: Any = None
    store = (
        body is not None
        and response.status_code is not None
        and response.status_code < 500
    )
    if store:
        try:
            payload = json.loads(body)
        except (TypeError, ValueError):
            store = False  # non-JSON body (streaming/file) — nothing to replay

    try:
        session, agen = await _resolve_session(request)
        try:
            if store:
                await session.execute(
                    update(IdempotencyKey)
                    .where(
                        IdempotencyKey.key == claim["key"],
                        IdempotencyKey.user_id == claim["user_id"],
                        IdempotencyKey.endpoint == claim["endpoint"],
                    )
                    .values(
                        response_json=payload,
                        status_code=response.status_code,
                    )
                )
            else:
                # Unreplayable / server-error response — release the key so a
                # real retry re-processes instead of hitting a stuck claim.
                await session.execute(
                    delete(IdempotencyKey).where(
                        IdempotencyKey.key == claim["key"],
                        IdempotencyKey.user_id == claim["user_id"],
                        IdempotencyKey.endpoint == claim["endpoint"],
                    )
                )
            await session.commit()
        finally:
            await agen.aclose()
    except Exception:
        logger.warning("idempotency response store failed", exc_info=True)


def idempotent(endpoint: str):
    """Dependency factory — claim an Idempotency-Key for ``endpoint``.

    Add to a route via ``dependencies=[Depends(idempotent("..."))]``; the
    router must use ``IdempotentRoute`` so the response is stored.
    """

    async def _idempotent_dep(
        request: Request,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> None:
        key = request.headers.get("idempotency-key")
        if key is None:
            return  # header absent → pass through unchanged
        key = key.strip()
        if not key or len(key) > 255:
            raise _http_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_IDEMPOTENCY_KEY",
                "Idempotency-Key must be 1-255 characters",
            )

        request_hash = hashlib.sha256(await request.body()).hexdigest()

        row = await _fetch_key(db, key, user.id, endpoint)
        if row is not None and _is_expired(row):
            # Lazy retention: drop the stale row and treat the key as new.
            await db.execute(
                delete(IdempotencyKey).where(
                    IdempotencyKey.key == row.key,
                    IdempotencyKey.user_id == row.user_id,
                    IdempotencyKey.endpoint == row.endpoint,
                )
            )
            row = None

        if row is not None:
            if row.response_json is None:
                # Claim exists but no stored response yet — the original
                # request is still running (or crashed before storing).
                raise _http_error(
                    status.HTTP_409_CONFLICT,
                    "IDEMPOTENCY_IN_PROGRESS",
                    "A request with this Idempotency-Key is still being processed",
                )
            if row.request_hash != request_hash:
                raise _http_error(
                    status.HTTP_409_CONFLICT,
                    "IDEMPOTENCY_MISMATCH",
                    "Idempotency-Key was already used with a different request body",
                )
            raise IdempotentReplay(row.response_json, row.status_code)

        db.add(
            IdempotencyKey(
                key=key,
                user_id=user.id,
                endpoint=endpoint,
                request_hash=request_hash,
            )
        )
        try:
            # Commit immediately: the claim must be visible to concurrent
            # duplicates *before* the handler finishes, and durable enough
            # that the post-handler UPDATE on a separate session finds it.
            await db.commit()
        except IntegrityError:
            await db.rollback()
            # Lost the check-then-insert race — the other request's claim is
            # now committed; replay it if it already has a response.
            row = await _fetch_key(db, key, user.id, endpoint)
            if (
                row is not None
                and not _is_expired(row)
                and row.request_hash == request_hash
                and row.response_json is not None
            ):
                raise IdempotentReplay(row.response_json, row.status_code)
            raise _http_error(
                status.HTTP_409_CONFLICT,
                "IDEMPOTENCY_IN_PROGRESS",
                "A request with this Idempotency-Key is still being processed",
            )

        # Marker for IdempotentRoute: persist the response on this claim
        # once the handler has run (or discard it if the handler raises).
        request.state.idempotency_claim = {
            "key": key,
            "user_id": user.id,
            "endpoint": endpoint,
        }

    return _idempotent_dep


class IdempotentRoute(APIRoute):
    """Route class that fulfils/discards the claim set by ``idempotent()``.

    Wraps the matched route's handler: after it returns a Response, the
    rendered body is stored on the claim row; if it raises, the claim is
    discarded so the key isn't poisoned. Routes without the ``idempotent``
    dependency (no claim on ``request.state``) pass straight through.
    """

    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                response = await original(request)
            except Exception:
                claim = getattr(request.state, _STATE_ATTR, None)
                if claim is not None:
                    await _discard_claim(request, claim)
                raise
            claim = getattr(request.state, _STATE_ATTR, None)
            if claim is not None:
                await _store_response(request, claim, response)
            return response

        return handler
