#!/usr/bin/env python3
"""
Populate brand_side_effects from the source CSV.

Each row in the dataset describes a single brand and lists that brand's
own side effects in `Consolidated_Side_Effects`. Brands are matched by
(brand_name, manufacturer_name) — the same UNIQUE key the brands table
uses on (brand_name, manufacturer_id).

Re-runnable: existing pairs are skipped via ON CONFLICT DO NOTHING.

Usage (inside the backend container):
    docker-compose exec backend python scripts/populate_brand_side_effects.py
"""

from __future__ import annotations

import csv
import os
import sys
import uuid
from collections import defaultdict
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

CSV_CANDIDATES = [
    "/app/Dataset/Extensive_A_Z_medicines_dataset_of_India.csv",
    str(Path(__file__).resolve().parents[2] / "Dataset" / "Extensive_A_Z_medicines_dataset_of_India.csv"),
]


def find_csv() -> str:
    for p in CSV_CANDIDATES:
        if os.path.exists(p):
            return p
    sys.exit(f"CSV not found. Tried: {CSV_CANDIDATES}")


def split_side_effects(raw: str) -> list[str]:
    return [s.strip() for s in raw.split(",") if s.strip()]


def main() -> int:
    dsn = os.environ.get("MEDICINE_DB_URL_SYNC")
    if not dsn:
        sys.exit("MEDICINE_DB_URL_SYNC not set")

    csv_path = find_csv()
    print(f"Reading {csv_path}")

    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    cur = conn.cursor()

    # Manufacturer name -> id (lowercased, stripped)
    cur.execute("SELECT manufacturer_id, manufacturer_name FROM manufacturers")
    manufacturers: dict[str, uuid.UUID] = {
        n.strip().lower(): mid for mid, n in cur.fetchall()
    }
    print(f"Loaded {len(manufacturers)} manufacturers")

    # (brand_name_lower, manufacturer_id) -> brand_id
    cur.execute("SELECT brand_id, brand_name, manufacturer_id FROM brands")
    brands_by_key: dict[tuple[str, uuid.UUID], uuid.UUID] = {}
    for bid, bname, mid in cur.fetchall():
        brands_by_key[(bname.strip().lower(), mid)] = bid
    print(f"Loaded {len(brands_by_key)} brands")

    cur.execute("SELECT side_effect_id, side_effect_name FROM side_effects")
    se_map: dict[str, uuid.UUID] = {n.strip().lower(): sid for sid, n in cur.fetchall()}
    print(f"Loaded {len(se_map)} existing side effects")

    # Pass 1: collect (brand_id, set[side_effect_name]) and any new effect names
    brand_to_ses: dict[uuid.UUID, set[str]] = defaultdict(set)
    new_se_originals: dict[str, str] = {}  # lower -> original-case for new
    rows_with_ses = 0
    matched_rows = 0
    unmatched_brand = 0
    unmatched_manufacturer = 0

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_ses = (row.get("Consolidated_Side_Effects") or "").strip()
            if not raw_ses:
                continue
            rows_with_ses += 1

            brand_name = (row.get("name") or "").strip()
            mfr_name = (row.get("manufacturer_name") or "").strip()
            if not brand_name or not mfr_name:
                continue

            mid = manufacturers.get(mfr_name.lower())
            if not mid:
                unmatched_manufacturer += 1
                continue
            brand_id = brands_by_key.get((brand_name.lower(), mid))
            if not brand_id:
                unmatched_brand += 1
                continue
            matched_rows += 1

            for se in split_side_effects(raw_ses):
                key = se.lower()
                brand_to_ses[brand_id].add(key)
                if key not in se_map:
                    new_se_originals.setdefault(key, se)

    print(
        f"Rows with side effects: {rows_with_ses}, matched: {matched_rows}, "
        f"unmatched brand: {unmatched_brand}, unmatched manufacturer: {unmatched_manufacturer}"
    )

    # Insert new side effect catalog entries
    if new_se_originals:
        print(f"Inserting {len(new_se_originals)} new side effect names")
        rows_to_insert = [(str(uuid.uuid4()), n) for n in new_se_originals.values()]
        execute_values(
            cur,
            """
            INSERT INTO side_effects (side_effect_id, side_effect_name)
            VALUES %s
            ON CONFLICT (side_effect_name) DO NOTHING
            """,
            rows_to_insert,
        )
        cur.execute("SELECT side_effect_id, side_effect_name FROM side_effects")
        se_map = {n.strip().lower(): sid for sid, n in cur.fetchall()}

    # Build (brand_id, side_effect_id) pairs
    pairs: list[tuple[str, str]] = []
    for brand_id, se_keys in brand_to_ses.items():
        for k in se_keys:
            seid = se_map.get(k)
            if seid:
                pairs.append((str(brand_id), str(seid)))

    print(f"Pairs to upsert: {len(pairs)}")

    chunk = 10000
    for i in range(0, len(pairs), chunk):
        execute_values(
            cur,
            """
            INSERT INTO brand_side_effects (brand_id, side_effect_id)
            VALUES %s
            ON CONFLICT (brand_id, side_effect_id) DO NOTHING
            """,
            pairs[i : i + chunk],
        )

    conn.commit()
    cur.execute("SELECT COUNT(*) FROM brand_side_effects")
    print(f"brand_side_effects total now: {cur.fetchone()[0]}")
    cur.execute(
        "SELECT COUNT(DISTINCT brand_id), COUNT(DISTINCT side_effect_id) FROM brand_side_effects"
    )
    db, ds = cur.fetchone()
    print(f"distinct brands: {db}, distinct side effects: {ds}")

    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
