"""Clinical safety gate for prescription creation.

Runs server-side before a prescription is persisted:

  1. Resolve each prescribed item -> Brand -> Salts (via BrandComposition).
  2. Checks:
     a. pairwise ``DrugInteraction`` across all resolved salts
        (via ``InteractionService.check_interactions``)
     b. patient allergy match — ``User.allergies`` vs salt/brand names
     c. duplicate therapy — same salt/brand already in another active
        prescription for the patient (not deleted, ``valid_until >= today``
        or no expiry)
     d. ``SaltContraindication``/``Contraindication`` rows matching the
        patient's ``chronic_conditions``
  3. Enforcement is applied by the caller (see routers/doctors.py):
       contraindicated -> block creation (409)
       major           -> require ``safety_override_reason`` on the request
       moderate/minor  -> warn-only, returned in the response ``safety`` block
  4. ``PrescriptionAudit`` rows (medicine DB) are written for every outcome —
     including blocked attempts. For blocked attempts there is no real
     prescription row, so ``prescription_id`` holds a generated attempt UUID
     and each stored alert carries ``outcome="blocked"``.

Severity vocabulary is normalized to the DrugInteraction scale
(minor | moderate | major | contraindicated). Contraindication rows use the
"absolute"/"relative" vocabulary — mapped to "contraindicated"/"major".
"""

import re
import uuid
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.medicine.audit import PrescriptionAudit
from app.models.medicine.clinical_safety import Contraindication, SaltContraindication
from app.models.medicine.commercial import Brand, BrandComposition
from app.models.medicine.salts import Salt, SaltStrength
from app.models.prescription import Prescription
from app.models.user import User
from app.services.interaction_service import InteractionService

SEVERITY_RANK = {"minor": 1, "moderate": 2, "major": 3, "contraindicated": 4}

# Non-DrugInteraction severities: allergies require an explicit override
# (name matching can produce false positives, so they are overridable),
# duplicate therapy is warn-only.
ALLERGY_SEVERITY = "major"
DUPLICATE_SEVERITY = "moderate"
DEFAULT_CONTRAINDICATION_SEVERITY = "major"


def _norm(text) -> str:
    """Lowercase, trim, collapse whitespace."""
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _names_match(a: str, b: str) -> bool:
    """Normalized equality or containment (min 3 chars to avoid noise)."""
    a, b = _norm(a), _norm(b)
    if not a or not b or len(a) < 3 or len(b) < 3:
        return False
    return a == b or a in b or b in a


def _patient_terms(raw) -> list[str]:
    """Extract matchable terms from a JSONB list (allergies / chronic_conditions).

    Entries are usually plain strings; dict entries contribute the value of
    the first recognized name-ish key.
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


def _map_severity(raw: str | None, default: str = DEFAULT_CONTRAINDICATION_SEVERITY) -> str:
    """Normalize any severity vocabulary onto the interaction scale."""
    r = _norm(raw)
    if r in ("contraindicated", "absolute"):
        return "contraindicated"
    if r in ("major", "relative", "severe", "high"):
        return "major"
    if r == "moderate":
        return "moderate"
    if r in ("minor", "mild", "low"):
        return "minor"
    return default


@dataclass
class ResolvedItem:
    """One prescribed medicine line with its catalog resolution."""

    item: dict
    brand: Brand | None = None
    salts: list[Salt] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        return self.item.get("brand_name") or self.item.get("name") or "unknown"


@dataclass
class SafetyGateResult:
    alerts: list[dict]
    resolved: list[ResolvedItem]
    salt_ids: list[UUID]


async def _resolve_brand(medicine_db: AsyncSession, item: dict) -> Brand | None:
    """Resolve a medicine item to a catalog Brand via brand_id or brand_name."""
    brand_id = item.get("brand_id")
    if brand_id:
        try:
            brand = await medicine_db.get(Brand, uuid.UUID(str(brand_id)))
        except (ValueError, TypeError):
            brand = None
        if brand is not None:
            return brand

    brand_name = item.get("brand_name") or item.get("name")
    if not brand_name:
        return None

    # Exact case-insensitive match first
    result = await medicine_db.execute(
        select(Brand).where(func.lower(Brand.brand_name) == _norm(brand_name)).limit(1)
    )
    brand = result.scalar_one_or_none()
    if brand is not None:
        return brand

    # Fallback: prefix match ("Crocin" -> "Crocin 500mg"), shortest name wins
    result = await medicine_db.execute(
        select(Brand)
        .where(Brand.brand_name.ilike(f"{brand_name}%"))
        .order_by(func.length(Brand.brand_name))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _brand_salts(medicine_db: AsyncSession, brand_id: UUID) -> list[Salt]:
    stmt = (
        select(Salt)
        .join(SaltStrength, Salt.salt_id == SaltStrength.salt_id)
        .join(BrandComposition, BrandComposition.salt_strength_id == SaltStrength.salt_strength_id)
        .where(BrandComposition.brand_id == brand_id)
        .order_by(BrandComposition.sequence)
    )
    result = await medicine_db.execute(stmt)
    return list(result.scalars().all())


async def resolve_items(medicine_db: AsyncSession, medicines: list[dict]) -> list[ResolvedItem]:
    """Resolve each prescribed item -> brand -> salt list."""
    resolved: list[ResolvedItem] = []
    for item in medicines:
        brand = await _resolve_brand(medicine_db, item)
        salts: list[Salt] = []
        if brand is not None:
            salts = await _brand_salts(medicine_db, brand.brand_id)

        # An explicit salt_id on the item is additive (covers cases where the
        # brand is absent from the catalog but the salt is known).
        raw_salt_id = item.get("salt_id")
        if raw_salt_id:
            try:
                salt = await medicine_db.get(Salt, uuid.UUID(str(raw_salt_id)))
            except (ValueError, TypeError):
                salt = None
            if salt is not None and all(s.salt_id != salt.salt_id for s in salts):
                salts.append(salt)

        resolved.append(ResolvedItem(item=item, brand=brand, salts=salts))
    return resolved


async def _active_therapy(
    db: AsyncSession,
    medicine_db: AsyncSession,
    patient_id: UUID,
) -> tuple[set[UUID], set[str]]:
    """Collect (salt_ids, normalized brand names) from the patient's active prescriptions."""
    stmt = select(Prescription.medicines).where(
        Prescription.patient_id == patient_id,
        Prescription.deleted_at.is_(None),
        or_(
            Prescription.valid_until.is_(None),
            Prescription.valid_until >= date.today(),
        ),
    )
    result = await db.execute(stmt)

    salt_ids: set[UUID] = set()
    brand_names: set[str] = set()
    brand_ids: set[UUID] = set()
    for (medicines,) in result.all():
        for med in medicines or []:
            if not isinstance(med, dict):
                continue
            if med.get("salt_id"):
                try:
                    salt_ids.add(uuid.UUID(str(med["salt_id"])))
                except (ValueError, TypeError):
                    pass
            if med.get("brand_id"):
                try:
                    brand_ids.add(uuid.UUID(str(med["brand_id"])))
                except (ValueError, TypeError):
                    pass
            name = med.get("brand_name") or med.get("name")
            if name:
                brand_names.add(_norm(name))

    # Resolve stored brand names (exact normalized match) to brand ids
    if brand_names:
        rows = await medicine_db.execute(
            select(Brand.brand_id).where(func.lower(Brand.brand_name).in_(brand_names))
        )
        brand_ids.update(row[0] for row in rows.all())

    # Resolve brand ids -> salts via composition
    if brand_ids:
        rows = await medicine_db.execute(
            select(Salt.salt_id)
            .join(SaltStrength, Salt.salt_id == SaltStrength.salt_id)
            .join(BrandComposition, BrandComposition.salt_strength_id == SaltStrength.salt_strength_id)
            .where(BrandComposition.brand_id.in_(brand_ids))
        )
        salt_ids.update(row[0] for row in rows.all())

    return salt_ids, brand_names


async def run_safety_gate(
    db: AsyncSession,
    medicine_db: AsyncSession,
    patient_id: UUID,
    medicines: list[dict],
) -> SafetyGateResult:
    """Run all clinical safety checks for a proposed prescription.

    Returns alerts (JSON-serializable dicts) sorted most-severe first, plus
    the resolved items/salts for audit persistence. Enforcement decisions
    (block / require override) are left to the caller.
    """
    resolved = await resolve_items(medicine_db, medicines)
    salt_ids = list({s.salt_id for item in resolved for s in item.salts})

    alerts: list[dict] = []

    # (a) Pairwise drug-drug interactions across all resolved salts
    interactions = await InteractionService.check_interactions(medicine_db, salt_ids)
    for ix in interactions:
        alerts.append(
            {
                "severity": _map_severity(ix["severity"], default="moderate"),
                "kind": "interaction",
                "detail": (
                    f"{ix['salt_1']['name']} + {ix['salt_2']['name']}: {ix['effect']}"
                    + (f" Management: {ix['management']}" if ix.get("management") else "")
                ),
                "salts": [ix["salt_1"]["name"], ix["salt_2"]["name"]],
                "salt_ids": [ix["salt_1"]["id"], ix["salt_2"]["id"]],
                "interaction_id": ix["interaction_id"],
                "evidence_level": ix.get("evidence_level"),
            }
        )

    patient = await db.get(User, patient_id)
    allergy_terms = _patient_terms(patient.allergies if patient else None)
    condition_terms = _patient_terms(patient.chronic_conditions if patient else None)

    # (b) Allergy match — allergies vs salt names / brand names / item name
    if allergy_terms:
        seen: set[tuple[str, str]] = set()
        for item in resolved:
            candidate_names = [item.display_name]
            if item.brand is not None:
                candidate_names.append(item.brand.brand_name)
            candidate_names.extend(s.salt_name for s in item.salts)
            item_salt_ids = [str(s.salt_id) for s in item.salts]
            item_salt_names = [s.salt_name for s in item.salts]
            for allergy in allergy_terms:
                for name in candidate_names:
                    if _names_match(allergy, name) and (_norm(allergy), _norm(name)) not in seen:
                        seen.add((_norm(allergy), _norm(name)))
                        alerts.append(
                            {
                                "severity": ALLERGY_SEVERITY,
                                "kind": "allergy",
                                "detail": (
                                    f"Patient allergy '{allergy}' matches "
                                    f"'{name}' in prescribed item '{item.display_name}'"
                                ),
                                "salts": item_salt_names or None,
                                "salt_ids": item_salt_ids,
                                "medicine": item.display_name,
                            }
                        )

    # (c) Duplicate therapy — same salt/brand in another active prescription
    active_salt_ids, active_brand_names = await _active_therapy(db, medicine_db, patient_id)
    for item in resolved:
        for salt in item.salts:
            if salt.salt_id in active_salt_ids:
                alerts.append(
                    {
                        "severity": DUPLICATE_SEVERITY,
                        "kind": "duplicate_therapy",
                        "detail": (
                            f"'{salt.salt_name}' is already present in an active "
                            f"prescription for this patient"
                        ),
                        "salts": [salt.salt_name],
                        "salt_ids": [str(salt.salt_id)],
                        "medicine": item.display_name,
                    }
                )
        if not item.salts and _norm(item.display_name) in active_brand_names:
            alerts.append(
                {
                    "severity": DUPLICATE_SEVERITY,
                    "kind": "duplicate_therapy",
                    "detail": (
                        f"'{item.display_name}' is already prescribed in an active "
                        f"prescription for this patient"
                    ),
                    "salts": None,
                    "salt_ids": [],
                    "medicine": item.display_name,
                }
            )

    # (d) Contraindications — salt contraindication rows vs chronic conditions
    if salt_ids and condition_terms:
        stmt = (
            select(SaltContraindication, Contraindication, Salt)
            .join(Contraindication, Contraindication.contraindication_id == SaltContraindication.contraindication_id)
            .join(Salt, Salt.salt_id == SaltContraindication.salt_id)
            .where(SaltContraindication.salt_id.in_(salt_ids))
        )
        result = await medicine_db.execute(stmt)
        for sc, contra, salt in result.all():
            for condition in condition_terms:
                if _names_match(condition, contra.contraindication_name):
                    severity = _map_severity(sc.severity or contra.severity)
                    alerts.append(
                        {
                            "severity": severity,
                            "kind": "contraindication",
                            "detail": (
                                f"'{salt.salt_name}' is contraindicated with patient "
                                f"condition '{condition}' ({contra.contraindication_name})"
                                + (f". {sc.notes}" if sc.notes else "")
                            ),
                            "salts": [salt.salt_name],
                            "salt_ids": [str(salt.salt_id)],
                            "contraindication": contra.contraindication_name,
                        }
                    )
                    break  # one alert per (salt, contraindication) row is enough

    alerts.sort(key=lambda a: -SEVERITY_RANK.get(a["severity"], 0))
    return SafetyGateResult(alerts=alerts, resolved=resolved, salt_ids=salt_ids)


def _relevant(alerts: list[dict], kinds: set[str], salt_id: UUID | None, medicine: str) -> list[dict]:
    """Alerts of the given kinds relevant to one (item, salt) audit row."""
    out = []
    for a in alerts:
        if a["kind"] not in kinds:
            continue
        if salt_id is not None and str(salt_id) in (a.get("salt_ids") or []):
            out.append(a)
        elif a.get("medicine") and _norm(a["medicine"]) == _norm(medicine):
            out.append(a)
    return out


def _payload(alert: dict, blocked: bool, override_reason: str | None) -> dict:
    """JSONB-safe copy of an alert annotated with outcome/override metadata."""
    entry = {k: v for k, v in alert.items() if v is not None}
    entry["outcome"] = "blocked" if blocked else "created"
    entry["overridden"] = bool(override_reason) and alert["severity"] == "major"
    if override_reason:
        entry["override_reason"] = override_reason
    return entry


async def write_prescription_audit(
    medicine_db: AsyncSession,
    prescription_id: UUID,
    doctor_id: UUID,
    patient_id: UUID,
    resolved: list[ResolvedItem],
    alerts: list[dict],
    override_reason: str | None = None,
    blocked: bool = False,
) -> None:
    """Persist one PrescriptionAudit row per (item, salt) pair in the medicine DB.

    ``blocked`` marks attempts rejected by the safety gate; in that case
    ``prescription_id`` is a generated attempt id (no prescription row exists).
    Caller is responsible for flush/commit.
    """
    for item in resolved:
        salts = item.salts or [None]
        for salt in salts:
            salt_id = salt.salt_id if salt is not None else None
            audit = PrescriptionAudit(
                prescription_id=prescription_id,
                doctor_id=doctor_id,
                patient_id=patient_id,
                brand_id=item.brand.brand_id if item.brand is not None else None,
                salt_id=salt_id,
                dosage=item.item.get("dose") or item.item.get("dosage"),
                duration=item.item.get("duration"),
                interaction_alerts=[
                    _payload(a, blocked, override_reason)
                    for a in _relevant(alerts, {"interaction", "duplicate_therapy"}, salt_id, item.display_name)
                ] or None,
                contraindication_alerts=[
                    _payload(a, blocked, override_reason)
                    for a in _relevant(alerts, {"contraindication"}, salt_id, item.display_name)
                ] or None,
                allergy_alerts=[
                    _payload(a, blocked, override_reason)
                    for a in _relevant(alerts, {"allergy"}, salt_id, item.display_name)
                ] or None,
            )
            medicine_db.add(audit)
    await medicine_db.flush()
