"""Validate the frozen `data/kaduna_leads.csv` before the app uses it.

Run after any import::

    python scripts/validate_leads.py

Exits non-zero if any hard check fails. Prints a summary of soft checks.
"""

import csv
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

LEADS_CSV = DATA_DIR / "kaduna_leads.csv"
PROVENANCE_CSV = DATA_DIR / "kaduna_leads_provenance.csv"
MANIFEST_JSON = DATA_DIR / "import_manifest.json"

REQUIRED_COLUMNS = ["id", "name", "address", "phone", "category", "description", "lat", "lng"]
EXPECTED_ROWS = 50
KADUNA_BBOX = (10.40, 7.30, 10.65, 7.55)  # south, west, north, east


def fail(msg):
    print(f"[FAIL] {msg}")
    return False


def load_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main():
    ok = True

    if not LEADS_CSV.exists():
        print(f"[FAIL] Missing {LEADS_CSV}")
        return 1

    rows = load_csv(LEADS_CSV)

    # 1. Schema
    header = rows[0].keys() if rows else []
    if list(header) != REQUIRED_COLUMNS:
        ok = fail(f"Schema mismatch: expected {REQUIRED_COLUMNS}, got {list(header)}")

    # 2. Row count
    if len(rows) != EXPECTED_ROWS:
        ok = fail(f"Expected {EXPECTED_ROWS} rows, found {len(rows)}")

    # 3. Unique ids
    ids = [r["id"] for r in rows]
    if len(set(ids)) != len(ids):
        ok = fail("Duplicate id values found")

    # 4. Duplicate names
    names = [r["name"].strip().lower() for r in rows]
    if len(set(names)) != len(names):
        ok = fail("Duplicate business names found")

    # 5. Coordinates
    bad_coords = [
        r["name"] for r in rows
        if not r["lat"] or not r["lng"] or float(r["lat"]) < KADUNA_BBOX[0] or float(r["lat"]) > KADUNA_BBOX[2]
        or float(r["lng"]) < KADUNA_BBOX[1] or float(r["lng"]) > KADUNA_BBOX[3]
    ]
    if bad_coords:
        ok = fail(f"Coordinates out of Kaduna bounds: {bad_coords[:5]}")

    # 6. Phone normalisation (soft)
    phones = [r["phone"] for r in rows if r["phone"].strip()]
    bad_phones = [p for p in phones if not p.startswith("234") or len(p) < 10]
    if bad_phones:
        ok = fail(f"Non-normalised phone numbers: {bad_phones[:5]}")

    # 7. Provenance integrity (soft)
    prov = load_csv(PROVENANCE_CSV)
    prov_ids = {r["id"] for r in prov}
    missing_prov = [i for i in ids if i not in prov_ids]
    if missing_prov:
        ok = fail(f"Rows missing provenance entries: {missing_prov[:5]}")

    # 8. Manifest (soft)
    import json
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8")) if MANIFEST_JSON.exists() else {}
    real = sum(1 for r in prov if r["source_type"] == "osm") if prov else 0
    fallback = len(rows) - real

    print(f"  rows: {len(rows)} | real OSM: {real} | demo fallback: {fallback}")
    print(f"  null phones: {sum(1 for r in rows if not r['phone'].strip())}")
    print(f"  generic addresses: {sum(1 for r in rows if r['address'].strip() == 'Kaduna')}")
    print(f"  import date: {manifest.get('imported_at', 'n/a')}")

    if ok:
        print("\nAll hard checks passed. Dataset is safe to load.")
        return 0
    print("\nDataset FAILED validation.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
