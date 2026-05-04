#!/usr/bin/env python3
"""
Populate salt_side_effects from the source CSV.

The dataset has per-brand side effects in `Consolidated_Side_Effects` and the
brand's salts in `short_composition1` / `short_composition2`. Side effects in
this domain are conceptually salt-level, so we project: for every brand row,
each of its salts inherits each of that row's side effects. Pairs are
deduplicated across the full dataset.

Usage (inside the backend container):
    docker-compose exec backend python scripts/populate_salt_side_effects.py
"""

from __future__ import annotations

import csv
import os
import re
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

SALT_NAME_RE = re.compile(r"^([^(]+)")


def find_csv() -> str:
    for p in CSV_CANDIDATES:
        if os.path.exists(p):
            return p
    sys.exit(f"CSV not found. Tried: {CSV_CANDIDATES}")


def clean_salt(raw: str) -> str | None:
    m = SALT_NAME_RE.match(raw.strip())
    if not m:
        return None
    name = m.group(1).strip()
    return name or None


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

    cur.execute("SELECT salt_id, salt_name FROM salts")
    salts: dict[str, uuid.UUID] = {n.strip().lower(): sid for sid, n in cur.fetchall()}
    print(f"Loaded {len(salts)} salts")

    cur.execute("SELECT side_effect_id, side_effect_name FROM side_effects")
    se_map: dict[str, uuid.UUID] = {n.strip().lower(): sid for sid, n in cur.fetchall()}
    print(f"Loaded {len(se_map)} existing side effects")

    # First pass: salt_name_lower -> { (se_name_original_case, se_name_lower) }
    salt_to_ses: dict[str, set[tuple[str, str]]] = defaultdict(set)
    salt_misses: dict[str, int] = defaultdict(int)
    rows_with_ses = 0

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_ses = (row.get("Consolidated_Side_Effects") or "").strip()
            if not raw_ses:
                continue
            rows_with_ses += 1
            ses = split_side_effects(raw_ses)
            for col in ("short_composition1", "short_composition2"):
                comp = (row.get(col) or "").strip()
                if not comp:
                    continue
                salt_name = clean_salt(comp)
                if not salt_name:
                    continue
                key = salt_name.lower()
                if key not in salts:
                    salt_misses[key] += 1
                    continue
                for se in ses:
                    salt_to_ses[key].add((se, se.lower()))

    print(f"Rows with side effects: {rows_with_ses}")
    print(f"Distinct salts matched: {len(salt_to_ses)}")
    if salt_misses:
        # Show top 5 unmatched salts so the user can see the gap.
        top = sorted(salt_misses.items(), key=lambda kv: -kv[1])[:5]
        print(f"Unmatched salt names (top 5 of {len(salt_misses)}):")
        for name, cnt in top:
            print(f"  - {name!r}: {cnt} occurrences")

    # Insert any side-effect names not already in the catalog.
    new_se_names = {
        original
        for pairs in salt_to_ses.values()
        for original, lower in pairs
        if lower not in se_map
    }
    if new_se_names:
        print(f"Inserting {len(new_se_names)} new side effect names")
        rows_to_insert = [(str(uuid.uuid4()), n) for n in sorted(new_se_names)]
        execute_values(
            cur,
            """
            INSERT INTO side_effects (side_effect_id, side_effect_name)
            VALUES %s
            ON CONFLICT (side_effect_name) DO NOTHING
            """,
            rows_to_insert,
        )
        # Reload
        cur.execute("SELECT side_effect_id, side_effect_name FROM side_effects")
        se_map = {n.strip().lower(): sid for sid, n in cur.fetchall()}

    # Build deduplicated salt_side_effects pairs
    pairs: set[tuple[uuid.UUID, uuid.UUID]] = set()
    for salt_key, ses in salt_to_ses.items():
        sid = salts[salt_key]
        for _, se_lower in ses:
            seid = se_map.get(se_lower)
            if seid:
                pairs.add((sid, seid))

    print(f"Distinct (salt, side_effect) pairs to upsert: {len(pairs)}")

    if pairs:
        # Insert in chunks of 5k to keep the statement small.
        rows = [(str(s), str(e)) for s, e in pairs]
        chunk = 5000
        inserted = 0
        for i in range(0, len(rows), chunk):
            execute_values(
                cur,
                """
                INSERT INTO salt_side_effects (salt_id, side_effect_id)
                VALUES %s
                ON CONFLICT (salt_id, side_effect_id) DO NOTHING
                """,
                rows[i : i + chunk],
            )
            inserted += cur.rowcount if cur.rowcount > 0 else 0
        print(f"Inserted (or already present) — affected rows reported by driver: {inserted}")

    conn.commit()
    cur.execute("SELECT COUNT(*) FROM salt_side_effects")
    total = cur.fetchone()[0]
    print(f"salt_side_effects total now: {total}")

    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
