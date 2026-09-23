"""Admin bulk CSV import for the medicine catalog (brands + pack rows).

``POST /api/v1/admin/catalog/import`` accepts a multipart CSV upload with one
row per brand pack:

    brand_name,manufacturer_name,salt_name,strength_value,strength_unit,
    pack_form_name,pack_type,quantity,barcode,mrp_paise

Real mode upserts — manufacturer by name, salt by name, brand by
(name + manufacturer), packaging by (brand + pack_form + quantity) — so
re-importing the same file is idempotent. ``?dry_run=true`` runs the same
validation and lookups but writes nothing, returning a per-row preview of
what a real import would do.

Each row's writes run inside a SAVEPOINT (``db.begin_nested()``) so a bad row
rolls back without killing the batch — see the expiry-worker lesson: a full
rollback expires cached ORM objects and drops pending inserts.
"""

import csv
import io
import uuid
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_medicine_db
from app.dependencies import require_admin
from app.models.medicine.commercial import Brand, BrandComposition, Manufacturer
from app.models.medicine.packaging import BrandPackaging, PackForm
from app.models.medicine.salts import Salt, SaltStrength
from app.models.user import User
from app.services import medicine_cache
from app.utils.barcode import is_valid_barcode, normalize_barcode

MAX_FILE_BYTES = 2 * 1024 * 1024  # 2 MB
MAX_ROWS = 1000

REQUIRED_COLUMNS = {
    "brand_name",
    "manufacturer_name",
    "salt_name",
    "strength_value",
    "strength_unit",
    "pack_form_name",
    "quantity",
}
ALLOWED_COLUMNS = REQUIRED_COLUMNS | {"pack_type", "barcode", "mrp_paise"}


class ImportRowResult(BaseModel):
    """Outcome for one CSV data row (2-based row number, header = row 1)."""

    row: int
    brand_name: Optional[str] = None
    status: str  # "created" | "updated" | "skipped" | "error"
    message: Optional[str] = None


class CatalogImportResponse(BaseModel):
    """Import report: counts per status + per-row detail."""

    dry_run: bool
    total: int
    created: int
    updated: int
    skipped: int
    errors: list[ImportRowResult]
    rows: list[ImportRowResult]


class _RowError(ValueError):
    """Domain validation failure for a single CSV row."""


class _ParsedRow(BaseModel):
    brand_name: str
    manufacturer_name: str
    salt_name: str
    strength_value: Decimal
    strength_unit: str
    pack_form_name: str
    pack_type: Optional[str]
    quantity: int
    barcode: Optional[str]
    mrp_paise: Optional[int]


def _parse_row(raw: dict[str, str]) -> _ParsedRow:
    """Validate/coerce one CSV record; raises _RowError with the field problem."""

    def req(field: str) -> str:
        value = (raw.get(field) or "").strip()
        if not value:
            raise _RowError(f"{field} is required")
        return value

    brand_name = req("brand_name")
    if len(brand_name) > 255:
        raise _RowError("brand_name exceeds 255 characters")

    manufacturer_name = req("manufacturer_name")
    salt_name = req("salt_name")

    strength_raw = req("strength_value")
    try:
        strength_value = Decimal(strength_raw)
    except InvalidOperation:
        raise _RowError(f"strength_value '{strength_raw}' is not a number")
    if strength_value <= 0 or strength_value >= Decimal("10000000"):
        raise _RowError("strength_value must be > 0 and < 10,000,000")

    strength_unit = req("strength_unit")
    if len(strength_unit) > 20:
        raise _RowError("strength_unit exceeds 20 characters")

    pack_form_name = req("pack_form_name")

    quantity_raw = req("quantity")
    try:
        quantity = int(quantity_raw)
    except ValueError:
        raise _RowError(f"quantity '{quantity_raw}' is not an integer")
    if quantity < 1:
        raise _RowError("quantity must be >= 1")

    pack_type = (raw.get("pack_type") or "").strip() or None
    if pack_type and len(pack_type) > 100:
        raise _RowError("pack_type exceeds 100 characters")

    barcode = normalize_barcode(raw.get("barcode"))
    if barcode is not None and not is_valid_barcode(barcode):
        raise _RowError("barcode must be digits only, 8-14 characters (GTIN/EAN)")

    mrp_raw = (raw.get("mrp_paise") or "").strip()
    mrp_paise: Optional[int] = None
    if mrp_raw:
        try:
            mrp_paise = int(mrp_raw)
        except ValueError:
            raise _RowError(f"mrp_paise '{mrp_raw}' is not an integer")
        if mrp_paise < 0:
            raise _RowError("mrp_paise must be >= 0")

    return _ParsedRow(
        brand_name=brand_name,
        manufacturer_name=manufacturer_name,
        salt_name=salt_name,
        strength_value=strength_value,
        strength_unit=strength_unit,
        pack_form_name=pack_form_name,
        pack_type=pack_type,
        quantity=quantity,
        barcode=barcode,
        mrp_paise=mrp_paise,
    )


class _Caches:
    """Request-scoped find-or-create caches (CSV rows repeat the same entities).

    Cleared after any failed savepoint: the rollback drops objects flushed
    inside it, so a cached entry could point at a rolled-back insert.
    """

    def __init__(self) -> None:
        self.mfr_by_name: dict[str, Manufacturer] = {}
        self.salt_by_name: dict[str, Salt] = {}
        self.strength_by_key: dict[tuple, SaltStrength] = {}
        self.pack_form_by_name: dict[str, PackForm] = {}
        self.brand_by_key: dict[tuple[str, uuid.UUID], Brand] = {}
        self.composition_keys: set[tuple[uuid.UUID, uuid.UUID]] = set()
        self.composition_count: dict[uuid.UUID, int] = {}
        self.packaging_by_key: dict[tuple, BrandPackaging] = {}

    def clear(self) -> None:
        self.__init__()


async def _find_manufacturer(
    db: AsyncSession, caches: _Caches, name: str
) -> Optional[Manufacturer]:
    key = name.lower()
    if key not in caches.mfr_by_name:
        result = await db.execute(
            select(Manufacturer).where(func.lower(Manufacturer.manufacturer_name) == key)
        )
        mfr = result.scalar_one_or_none()
        if mfr is not None:
            caches.mfr_by_name[key] = mfr
    return caches.mfr_by_name.get(key)


async def _find_salt(db: AsyncSession, caches: _Caches, name: str) -> Optional[Salt]:
    key = name.lower()
    if key not in caches.salt_by_name:
        result = await db.execute(
            select(Salt).where(func.lower(Salt.salt_name) == key)
        )
        salt = result.scalar_one_or_none()
        if salt is not None:
            caches.salt_by_name[key] = salt
    return caches.salt_by_name.get(key)


async def _find_strength(
    db: AsyncSession, caches: _Caches, salt_id: uuid.UUID, value: Decimal, unit: str
) -> Optional[SaltStrength]:
    key = (salt_id, value.normalize(), unit)
    if key not in caches.strength_by_key:
        result = await db.execute(
            select(SaltStrength).where(
                SaltStrength.salt_id == salt_id,
                SaltStrength.strength_value == value,
                SaltStrength.strength_unit == unit,
            )
        )
        strength = result.scalar_one_or_none()
        if strength is not None:
            caches.strength_by_key[key] = strength
    return caches.strength_by_key.get(key)


async def _find_pack_form(
    db: AsyncSession, caches: _Caches, name: str
) -> Optional[PackForm]:
    key = name.lower()
    if key not in caches.pack_form_by_name:
        result = await db.execute(
            select(PackForm).where(func.lower(PackForm.form_name) == key)
        )
        pack_form = result.scalar_one_or_none()
        if pack_form is not None:
            caches.pack_form_by_name[key] = pack_form
    return caches.pack_form_by_name.get(key)


async def _find_brand(
    db: AsyncSession, caches: _Caches, name: str, manufacturer_id: uuid.UUID
) -> Optional[Brand]:
    key = (name.lower(), manufacturer_id)
    if key not in caches.brand_by_key:
        result = await db.execute(
            select(Brand).where(
                func.lower(Brand.brand_name) == name.lower(),
                Brand.manufacturer_id == manufacturer_id,
            )
        )
        brand = result.scalar_one_or_none()
        if brand is not None:
            caches.brand_by_key[key] = brand
    return caches.brand_by_key.get(key)


async def _composition_exists(
    db: AsyncSession, caches: _Caches, brand_id: uuid.UUID, strength_id: uuid.UUID
) -> bool:
    key = (brand_id, strength_id)
    if key in caches.composition_keys:
        return True
    result = await db.execute(
        select(BrandComposition.composition_id).where(
            BrandComposition.brand_id == brand_id,
            BrandComposition.salt_strength_id == strength_id,
        )
    )
    exists = result.scalar_one_or_none() is not None
    if exists:
        caches.composition_keys.add(key)
    return exists


async def _composition_count(
    db: AsyncSession, caches: _Caches, brand_id: uuid.UUID
) -> int:
    if brand_id not in caches.composition_count:
        result = await db.execute(
            select(func.count())
            .select_from(BrandComposition)
            .where(BrandComposition.brand_id == brand_id)
        )
        caches.composition_count[brand_id] = result.scalar_one()
    return caches.composition_count[brand_id]


async def _find_packaging(
    db: AsyncSession,
    caches: _Caches,
    brand_id: uuid.UUID,
    pack_form_id: uuid.UUID,
    quantity: int,
) -> Optional[BrandPackaging]:
    key = (brand_id, pack_form_id, quantity)
    if key not in caches.packaging_by_key:
        result = await db.execute(
            select(BrandPackaging).where(
                BrandPackaging.brand_id == brand_id,
                BrandPackaging.pack_form_id == pack_form_id,
                BrandPackaging.quantity == quantity,
            )
        )
        pack = result.scalar_one_or_none()
        if pack is not None:
            caches.packaging_by_key[key] = pack
    return caches.packaging_by_key.get(key)


def _pack_differs(pack: BrandPackaging, row: _ParsedRow) -> bool:
    """True when the CSV supplies non-empty pack fields that differ — empty CSV
    cells never clear existing values (upsert semantics)."""
    if row.pack_type is not None and pack.pack_type != row.pack_type:
        return True
    if row.barcode is not None and pack.barcode != row.barcode:
        return True
    if row.mrp_paise is not None and pack.mrp_paise != row.mrp_paise:
        return True
    return False


async def _preview_row(
    db: AsyncSession, caches: _Caches, row: _ParsedRow
) -> tuple[str, str]:
    """Dry-run: same lookups as a real import, no writes. Reports what a real
    import would do against current DB state (it does not simulate earlier
    rows in the same file)."""
    pack_form = await _find_pack_form(db, caches, row.pack_form_name)
    if pack_form is None:
        raise _RowError(f"unknown pack_form_name '{row.pack_form_name}'")

    manufacturer = await _find_manufacturer(db, caches, row.manufacturer_name)
    brand: Optional[Brand] = None
    if manufacturer is not None:
        brand = await _find_brand(db, caches, row.brand_name, manufacturer.manufacturer_id)

    if brand is None:
        return "created", "would create brand + composition + pack"

    pack = await _find_packaging(
        db, caches, brand.brand_id, pack_form.pack_form_id, row.quantity
    )
    if pack is None:
        return "created", "would create pack for existing brand"

    # Existing pack — would the row change anything?
    salt = await _find_salt(db, caches, row.salt_name)
    composition_missing = True
    if salt is not None:
        strength = await _find_strength(
            db, caches, salt.salt_id, row.strength_value, row.strength_unit
        )
        if strength is not None:
            composition_missing = not await _composition_exists(
                db, caches, brand.brand_id, strength.salt_strength_id
            )
    if composition_missing or _pack_differs(pack, row):
        return "updated", "would update existing brand/pack"
    return "skipped", "no changes"


async def _import_row(
    db: AsyncSession, caches: _Caches, row: _ParsedRow
) -> tuple[str, str]:
    """Real import for one row. Caller wraps in a SAVEPOINT."""
    pack_form = await _find_pack_form(db, caches, row.pack_form_name)
    if pack_form is None:
        raise _RowError(f"unknown pack_form_name '{row.pack_form_name}'")

    # --- manufacturer (find-or-create by name) ---
    manufacturer = await _find_manufacturer(db, caches, row.manufacturer_name)
    if manufacturer is None:
        manufacturer = Manufacturer(manufacturer_name=row.manufacturer_name, is_active=True)
        db.add(manufacturer)
        await db.flush()
        caches.mfr_by_name[row.manufacturer_name.lower()] = manufacturer

    # --- salt + strength (find-or-create) ---
    salt = await _find_salt(db, caches, row.salt_name)
    if salt is None:
        salt = Salt(salt_name=row.salt_name, prescription_required=True)
        db.add(salt)
        await db.flush()
        caches.salt_by_name[row.salt_name.lower()] = salt

    strength = await _find_strength(
        db, caches, salt.salt_id, row.strength_value, row.strength_unit
    )
    if strength is None:
        strength = SaltStrength(
            salt_id=salt.salt_id,
            strength_value=row.strength_value,
            strength_unit=row.strength_unit,
        )
        db.add(strength)
        await db.flush()
        caches.strength_by_key[
            (salt.salt_id, row.strength_value.normalize(), row.strength_unit)
        ] = strength

    # --- brand (find-or-create by name + manufacturer) ---
    brand = await _find_brand(db, caches, row.brand_name, manufacturer.manufacturer_id)
    brand_created = brand is None
    if brand_created:
        brand = Brand(
            brand_name=row.brand_name,
            manufacturer_id=manufacturer.manufacturer_id,
            drug_type="allopathy",
        )
        db.add(brand)
        await db.flush()
        caches.brand_by_key[(row.brand_name.lower(), manufacturer.manufacturer_id)] = brand
        caches.composition_count[brand.brand_id] = 0
    assert brand is not None

    # --- composition (link strength to brand if missing) ---
    composition_added = False
    if not await _composition_exists(db, caches, brand.brand_id, strength.salt_strength_id):
        seq = await _composition_count(db, caches, brand.brand_id) + 1
        db.add(
            BrandComposition(
                brand_id=brand.brand_id,
                salt_strength_id=strength.salt_strength_id,
                sequence=seq,
            )
        )
        caches.composition_keys.add((brand.brand_id, strength.salt_strength_id))
        caches.composition_count[brand.brand_id] = seq
        composition_added = True

    # --- packaging (upsert by brand + pack_form + quantity) ---
    pack = await _find_packaging(
        db, caches, brand.brand_id, pack_form.pack_form_id, row.quantity
    )
    pack_created = pack is None
    pack_updated = False
    if pack_created:
        pack = BrandPackaging(
            brand_id=brand.brand_id,
            pack_form_id=pack_form.pack_form_id,
            quantity=row.quantity,
            pack_type=row.pack_type,
            barcode=row.barcode,
            mrp_paise=row.mrp_paise,
            is_primary_pack=True,
        )
        db.add(pack)
        await db.flush()
        caches.packaging_by_key[(brand.brand_id, pack_form.pack_form_id, row.quantity)] = pack
    elif _pack_differs(pack, row):
        if row.pack_type is not None:
            pack.pack_type = row.pack_type
        if row.barcode is not None:
            pack.barcode = row.barcode
        if row.mrp_paise is not None:
            pack.mrp_paise = row.mrp_paise
        pack_updated = True

    if brand_created or pack_created:
        parts = []
        if brand_created:
            parts.append("brand")
        if pack_created:
            parts.append("pack")
        return "created", f"created {' + '.join(parts)}"
    if composition_added or pack_updated:
        return "updated", "updated existing brand/pack"
    return "skipped", "no changes"


router = APIRouter(
    prefix="/admin/catalog",
    tags=["admin-catalog"],
    dependencies=[Depends(require_admin)],
)


@router.post("/import", response_model=CatalogImportResponse)
async def import_catalog_csv(
    file: UploadFile = File(...),
    dry_run: bool = Query(False),
    db: AsyncSession = Depends(get_medicine_db),
    admin: User = Depends(require_admin),
):
    """Bulk-import brands + packaging rows from a CSV file — Admin only.

    - ``?dry_run=true`` validates and reports per-row outcomes without writing.
    - Real mode upserts per row inside a SAVEPOINT; one bad row does not
      kill the batch.
    - Rejects non-CSV files, files > 2 MB, and files with > 1000 data rows.
    """
    filename = (file.filename or "").lower()
    if not filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "NOT_CSV", "message": "Only .csv files are accepted"}},
        )

    raw = await file.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail={"error": {"code": "FILE_TOO_LARGE", "message": "CSV file exceeds 2 MB"}},
        )

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_CSV", "message": "File is not valid UTF-8"}},
        )

    records = [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
    if len(records) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {"code": "INVALID_CSV", "message": "CSV must have a header row and at least one data row"}
            },
        )

    headers = [h.strip() for h in records[0]]
    missing_columns = REQUIRED_COLUMNS - set(headers)
    if missing_columns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_CSV",
                    "message": f"Missing required columns: {', '.join(sorted(missing_columns))}",
                }
            },
        )

    data_records = records[1:]
    if len(data_records) > MAX_ROWS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {"code": "TOO_MANY_ROWS", "message": f"CSV exceeds {MAX_ROWS} data rows"}
            },
        )

    caches = _Caches()
    results: list[ImportRowResult] = []
    counts = {"created": 0, "updated": 0, "skipped": 0, "error": 0}

    for offset, record in enumerate(data_records):
        row_no = offset + 2  # header is row 1
        raw_row = {
            header: (record[i].strip() if i < len(record) else "")
            for i, header in enumerate(headers)
        }
        try:
            parsed = _parse_row(raw_row)
        except _RowError as exc:
            results.append(
                ImportRowResult(
                    row=row_no,
                    brand_name=(raw_row.get("brand_name") or None),
                    status="error",
                    message=str(exc),
                )
            )
            counts["error"] += 1
            continue

        try:
            if dry_run:
                row_status, message = await _preview_row(db, caches, parsed)
            else:
                # Per-row SAVEPOINT: a failure rolls back only this row's
                # writes, keeping the outer transaction (and earlier rows).
                async with db.begin_nested():
                    row_status, message = await _import_row(db, caches, parsed)
        except Exception as exc:  # noqa: BLE001 — batch must survive bad rows
            # The nested transaction already rolled back this row's writes.
            # Cached objects may point at rolled-back inserts — drop them so
            # the next row re-queries fresh state.
            caches.clear()
            results.append(
                ImportRowResult(
                    row=row_no,
                    brand_name=parsed.brand_name,
                    status="error",
                    message=str(exc),
                )
            )
            counts["error"] += 1
            continue

        results.append(
            ImportRowResult(
                row=row_no,
                brand_name=parsed.brand_name,
                status=row_status,
                message=message,
            )
        )
        counts[row_status] += 1

    if not dry_run and (counts["created"] or counts["updated"]):
        await db.commit()
        await medicine_cache.invalidate_catalog()

    errors = [r for r in results if r.status == "error"]
    return CatalogImportResponse(
        dry_run=dry_run,
        total=len(data_records),
        created=counts["created"],
        updated=counts["updated"],
        skipped=counts["skipped"],
        errors=errors,
        rows=results,
    )
