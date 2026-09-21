"""Barcode (GTIN/EAN) helpers for the medicine catalog.

Indian medicine packs carry GTIN-8/12/13/14 or EAN barcodes printed per
pack size. They are stored on ``BrandPackaging.barcode`` — digits only,
8-14 characters, with whitespace stripped on write.
"""

import re

# Digits only, 8-14 characters (covers GTIN-8/12/13/14 and EAN-8/13).
BARCODE_PATTERN = re.compile(r"^\d{8,14}$")


def normalize_barcode(raw: str | None) -> str | None:
    """Strip all whitespace from a barcode.

    Returns ``None`` when the input is ``None`` or whitespace-only.
    """
    if raw is None:
        return None
    code = re.sub(r"\s+", "", raw)
    return code or None


def is_valid_barcode(code: str) -> bool:
    """True when ``code`` is a syntactically valid GTIN/EAN barcode."""
    return bool(BARCODE_PATTERN.fullmatch(code))


def is_barcode_query(query: str | None) -> bool:
    """True when a free-text search query looks like a scannable barcode."""
    normalized = normalize_barcode(query)
    return normalized is not None and is_valid_barcode(normalized)
