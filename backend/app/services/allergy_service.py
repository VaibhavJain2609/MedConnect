"""Patient allergy → salt matching service.

Turns free-text ``User.allergies`` entries into structured checks against
catalog ``Salt`` rows. Backs ``POST /api/v1/interactions/check-allergies``
so the Rx UI can call the backend instead of doing fuzzy substring matching
client-side.

Matching rules (the ``Salt`` model has no synonyms column — matching is
name-only):

  - ``"exact"``   — normalized allergy term equals normalized ``salt_name``
  - ``"partial"`` — containment in either direction, only when both sides are
                    >= ``MIN_PARTIAL_LEN`` chars after normalization (e.g.
                    "paracet" vs "Paracetamol"). Reported as a weaker match
                    so the UI can phrase it as "possible" rather than exact.

Terms shorter than 4 characters never partial-match, which avoids false
positives like allergy "pen" matching "Penicillin" or "Openacid".
"""

import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.medicine.salts import Salt
from app.services import medicine_cache

MIN_PARTIAL_LEN = 4


def _norm(text) -> str:
    """Lowercase, trim, collapse whitespace."""
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def allergy_terms(raw) -> list[str]:
    """Extract matchable terms from a JSONB list (User.allergies).

    Entries are usually plain strings; dict entries contribute the value of
    the first recognized name-ish key. Same semantics as
    ``clinical_safety_service._patient_terms``.
    """
    terms: list[str] = []
    for entry in raw or []:
        if isinstance(entry, str):
            terms.append(entry)
        elif isinstance(entry, dict):
            for key in ("name", "substance", "allergen", "drug", "condition", "value"):
                if isinstance(entry.get(key), str):
                    terms.append(entry[key])
                    break
    return [t for t in terms if t and t.strip()]


async def _load_salt_names(
    medicine_db: AsyncSession, salt_ids: list[UUID]
) -> dict[UUID, str]:
    """salt_id -> salt_name, with a read-through medcat cache.

    Cache key ``medcat:salt:name:{salt_id}`` -> salt_name. The catalog is
    effectively static (admin mutations flush ``medcat:*``), so names cache
    under DETAIL_TTL. Cache failures degrade to a plain DB read.
    """
    names: dict[UUID, str] = {}
    missing: list[UUID] = []
    for salt_id in dict.fromkeys(salt_ids or []):  # dedupe, keep order
        cached = await medicine_cache.get_cached(
            medicine_cache.make_key("salt:name", salt_id)
        )
        if isinstance(cached, str) and cached:
            names[salt_id] = cached
        else:
            missing.append(salt_id)

    if missing:
        result = await medicine_db.execute(
            select(Salt.salt_id, Salt.salt_name).where(Salt.salt_id.in_(missing))
        )
        for salt_id, salt_name in result.all():
            names[salt_id] = salt_name
            await medicine_cache.set_cached(
                medicine_cache.make_key("salt:name", salt_id),
                salt_name,
                ttl=medicine_cache.DETAIL_TTL_SECONDS,
            )
    return names


def _match_kind(allergy_norm: str, salt_norm: str) -> str | None:
    """Classify a (allergy term, salt name) pair, or None if no match."""
    if not allergy_norm or not salt_norm:
        return None
    if allergy_norm == salt_norm:
        return "exact"
    if (
        len(allergy_norm) >= MIN_PARTIAL_LEN
        and len(salt_norm) >= MIN_PARTIAL_LEN
        and (allergy_norm in salt_norm or salt_norm in allergy_norm)
    ):
        return "partial"
    return None


async def check_allergies(
    medicine_db: AsyncSession,
    allergies_raw,
    salt_ids: list[UUID],
) -> dict:
    """Match a patient's allergy terms against the given catalog salts.

    Returns::

        {
            "conflicts": [
                {"salt_id": str, "salt_name": str, "allergy": str,
                 "match": "exact" | "partial"},
                ...
            ],
            "checked_allergies": [str, ...],  # terms that produced NO match
        }
    """
    terms = allergy_terms(allergies_raw)
    salt_names = await _load_salt_names(medicine_db, salt_ids)

    conflicts: list[dict] = []
    matched_norms: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()

    for term in terms:
        term_norm = _norm(term)
        if not term_norm:
            continue
        for salt_id, salt_name in salt_names.items():
            kind = _match_kind(term_norm, _norm(salt_name))
            if kind is None:
                continue
            pair = (str(salt_id), term_norm)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            matched_norms.add(term_norm)
            conflicts.append(
                {
                    "salt_id": str(salt_id),
                    "salt_name": salt_name,
                    "allergy": term,
                    "match": kind,
                }
            )

    checked = [t for t in terms if _norm(t) not in matched_norms]
    return {"conflicts": conflicts, "checked_allergies": checked}
