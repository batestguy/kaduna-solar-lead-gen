"""One-time OSM/Overpass import for Kaduna business leads.

Run ONCE before the app is used::

    python scripts/import_osm_leads.py

This script queries the public Overpass API, normalises and de-duplicates the
results, then writes the frozen `data/kaduna_leads.csv` used by the app.

Rules:
- The Streamlit app NEVER calls this script or any network endpoint.
- If fewer than 50 verified OSM businesses are found, the remainder are padded
  from `data/kaduna_leads_demo.csv` and clearly flagged `demo_fallback` in the
  provenance file.
- No fabricated phone numbers, addresses, or coordinates are ever generated.
"""

import csv
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"

DEMO_CSV = DATA_DIR / "kaduna_leads_demo.csv"
OUT_CSV = DATA_DIR / "kaduna_leads.csv"
PROVENANCE_CSV = DATA_DIR / "kaduna_leads_provenance.csv"
MANIFEST_JSON = DATA_DIR / "import_manifest.json"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "SolSearching-LeadGen/1.0 (one-time import; cached; attributted ODbL)"

KADUNA_BBOX = (10.40, 7.30, 10.65, 7.55)  # south, west, north, east
TARGET_ROWS = 50

REQUIRED_COLUMNS = ["id", "name", "address", "phone", "category", "description", "lat", "lng"]

OVERPASS_QUERY = """
[out:json][timeout:120];
(
  nwr["shop"]({bbox});
  nwr["amenity"~"restaurant|fast_food|cafe|pharmacy|school|hospital|clinic|hotel|guest_house|fuel|bank|marketplace|workshop"]({bbox});
  nwr["office"]({bbox});
  nwr["craft"]({bbox});
  nwr["tourism"="hotel"]({bbox});
  nwr["building"="industrial"]({bbox});
);
out center tags;
""".format(bbox=",".join(str(v) for v in KADUNA_BBOX))

CATEGORY_RANK = ["shop", "craft", "amenity", "tourism", "office", "building"]

AMENITY_LABEL = {
    "restaurant": "Restaurant",
    "fast_food": "Restaurant",
    "cafe": "Restaurant",
    "pharmacy": "Pharmacy",
    "school": "School",
    "hospital": "Hospital",
    "clinic": "Clinic",
    "hotel": "Hotel",
    "guest_house": "Guest House",
    "fuel": "Fuel Station",
    "bank": "Bank",
    "marketplace": "Market",
    "workshop": "Workshop",
}

SHOP_LABEL = {
    "supermarket": "Supermarket",
    "bakery": "Bakery",
    "clothes": "Clothing Store",
    "electronics": "Electronics",
    "furniture": "Furniture",
    "hardware": "Hardware",
    "books": "Bookstore",
    "car": "Car Dealership",
    "car_repair": "Auto Repair",
    "greengrocer": "Greengrocer",
    "butcher": "Butcher",
    "mall": "Shopping Mall",
    "department_store": "Department Store",
}

CRAFT_LABEL = {
    "metal_construction": "Metal Fabrication",
    "carpenter": "Carpentry",
    "electrician": "Electrical Services",
    "plumber": "Plumbing",
    "blacksmith": "Blacksmith",
    "tailor": "Tailoring",
}


def _has_coords(el):
    if "lat" in el and "lon" in el:
        return True
    if "center" in el and "lat" in el["center"] and "lon" in el["center"]:
        return True
    return False


def _coords(el):
    if "lat" in el and "lon" in el:
        return float(el["lat"]), float(el["lon"])
    c = el["center"]
    return float(c["lat"]), float(c["lon"])


def _primary_tag(tags):
    for key in CATEGORY_RANK:
        if tags.get(key):
            return key, tags[key]
    return None, None


def _category_label(tags):
    key, value = _primary_tag(tags)
    if not key or not value:
        return "Business"
    if key == "shop":
        return SHOP_LABEL.get(str(value), "Shop")
    if key == "amenity":
        return AMENITY_LABEL.get(str(value), "Amenity")
    if key == "craft":
        return CRAFT_LABEL.get(str(value), "Craft")
    if key == "tourism" and str(value) == "hotel":
        return "Hotel"
    if key == "office":
        return "Office"
    if key == "building":
        return "Industrial"
    return "Business"


def _phone(tags):
    raw = tags.get("phone") or tags.get("contact:phone") or tags.get("contact:mobile")
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits.startswith("0"):
        digits = "234" + digits[1:]
    elif len(digits) == 10 and digits.startswith("7"):
        digits = "234" + digits
    elif len(digits) == 8:
        digits = "234" + digits
    return digits if len(digits) >= 10 and digits.startswith("234") else None


def _address(tags):
    street = tags.get("addr:street")
    number = tags.get("addr:housenumber")
    area = tags.get("addr:district") or tags.get("addr:suburb") or tags.get("addr:city")
    parts = []
    if number:
        parts.append(str(number))
    if street:
        parts.append(street)
    if area:
        parts.append(area)
    if parts:
        return ", ".join(parts) + ", Kaduna"
    return "Kaduna"


CATEGORY_NOTE = {
    "Bank": "Bank branch with ATM and power-dependent operations.",
    "Hotel": "Hotel with air conditioning, water pumps and 24-hour reception load.",
    "Fuel Station": "Fuel station running pumps, lighting and compressors.",
    "Restaurant": "Restaurant with refrigeration, cooking and cooling load.",
    "Hospital": "Hospital with round-the-clock, power-critical equipment.",
    "Clinic": "Clinic with lighting, fridges and diagnostic equipment.",
    "School": "School with computer lab, fans and lighting.",
    "Supermarket": "Supermarket with freezers, cold display and air conditioning.",
    "Pharmacy": "Pharmacy with cold-chain medicine storage.",
    "Bakery": "Bakery with ovens and mixing equipment.",
    "Car Dealership": "Showroom with lighting and workshop demand.",
    "Auto Repair": "Workshop running power tools and compressors.",
    "Bookstore": "Retail store with lighting and fans.",
    "Shop": "Retail business with lighting and cooling demand.",
    "Office": "Office with IT, lighting and air conditioning load.",
    "Market": "Market trading area with commercial electricity demand.",
    "Guest House": "Guest house with room AC and kitchen load.",
    "Industrial": "Industrial facility with heavy machinery demand.",
    "Metal Fabrication": "Fabrication workshop running heavy machines.",
    "Carpentry": "Carpentry workshop with power tools.",
    "Electrical Services": "Service business with equipment and lighting load.",
    "Plumbing": "Service workshop with pumps and tools.",
    "Blacksmith": "Blacksmith forge with heating and tools.",
    "Tailoring": "Tailoring shop with electric irons and machines.",
    "Clothing Store": "Retail clothing store with lighting and AC.",
    "Electronics": "Electronics store with testing equipment.",
    "Furniture": "Furniture store with workshop and display lighting.",
    "Hardware": "Hardware store with lighting and inventory.",
    "Greengrocer": "Fresh produce store with cold storage needs.",
    "Butcher": "Butcher shop with cold storage for meat.",
    "Shopping Mall": "Mall with common-area cooling and lighting.",
    "Department Store": "Department store with high lighting and cooling load.",
    "Amenity": "Business with daily commercial power needs.",
    "Craft": "Craft workshop with tools and lighting.",
    "Business": "Business with commercial electricity demand.",
}


def _description(tags):
    label = _category_label(tags)
    bits = [CATEGORY_NOTE.get(label, "Business with commercial power needs.")]
    if tags.get("brand"):
        bits.append(f"Brand: {tags['brand']}.")
    if tags.get("website"):
        bits.append(f"Web: {tags['website']}.")
    bits.append(f"Source: OpenStreetMap.")
    return " ".join(bits)


def _normalize_name(name):
    return re.sub(r"\s+", " ", name).strip().title()


def fetch_osm():
    print("Querying Overpass API for Kaduna businesses…")
    resp = requests.post(
        OVERPASS_URL,
        data={"data": OVERPASS_QUERY},
        timeout=120,
        headers={"User-Agent": USER_AGENT},
    )
    resp.raise_for_status()
    return resp.json()


def parse_elements(data):
    rows = []
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name or not _has_coords(el):
            continue
        lat, lng = _coords(el)
        rows.append(
            {
                "osm_id": f"{el['type']}/{el['id']}",
                "name": _normalize_name(name),
                "address": _address(tags),
                "phone": _phone(tags),
                "category": _category_label(tags),
                "description": _description(tags),
                "lat": round(lat, 6),
                "lng": round(lng, 6),
                "osm_category": _primary_tag(tags)[1] if _primary_tag(tags)[0] else None,
            }
        )
    return rows


def dedupe(rows):
    seen = set()
    unique = []
    for row in rows:
        key = row["name"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique


def load_demo():
    rows = []
    with open(DEMO_CSV, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append(
                {
                    "osm_id": None,
                    "name": r["name"],
                    "address": r["address"],
                    "phone": r["phone"] or None,
                    "category": r["category"],
                    "description": r["description"],
                    "lat": float(r["lat"]),
                    "lng": float(r["lng"]),
                    "osm_category": None,
                }
            )
    return rows


def select_rows(rows):
    """Pick the best TARGET_ROWS: phones first, then addresses, then category diversity."""
    rows = sorted(
        rows,
        key=lambda r: (
            1 if r["phone"] else 0,
            1 if r["address"] and r["address"] != "Kaduna" else 0,
        ),
        reverse=True,
    )
    picked = []
    seen_categories = {}
    for row in rows:
        if len(picked) >= TARGET_ROWS:
            break
        picked.append(row)
        seen_categories[row["category"]] = seen_categories.get(row["category"], 0) + 1
    return picked


def write_outputs(real_rows, imported_at):
    demo_rows = load_demo()
    real_rows = select_rows(real_rows)
    pad_count = TARGET_ROWS - len(real_rows)
    fallback = demo_rows[: max(pad_count, 0)] if pad_count > 0 else []

    final = real_rows + fallback

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(REQUIRED_COLUMNS)
        for i, row in enumerate(final[:TARGET_ROWS], start=1):
            writer.writerow(
                [i, row["name"], row["address"], row["phone"] or "", row["category"], row["description"], row["lat"], row["lng"]]
            )

    with open(PROVENANCE_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["id", "name", "osm_id", "source_type", "osm_category", "imported_at"])
        for i, row in enumerate(final[:TARGET_ROWS], start=1):
            source = "osm" if row["osm_id"] else "demo_fallback"
            writer.writerow([i, row["name"], row["osm_id"] or "", source, row["osm_category"] or "", imported_at])

    manifest = {
        "target_rows": TARGET_ROWS,
        "real_osm_rows": len(real_rows),
        "demo_fallback_rows": len(fallback),
        "imported_at": imported_at,
        "source": "OpenStreetMap / Overpass API",
        "license": "ODbL",
        "attribution": "OpenStreetMap contributors",
        "bbox": list(KADUNA_BBOX),
        "schema": REQUIRED_COLUMNS,
        "note": "Streamlit app never scrapes at runtime; this file is frozen input.",
    }
    with open(MANIFEST_JSON, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    RAW_DIR.mkdir(exist_ok=True)
    return manifest


def main():
    RAW_DIR.mkdir(exist_ok=True)
    data = fetch_osm()

    raw_path = RAW_DIR / "osm_kaduna_businesses.json"
    with open(raw_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    print(f"Saved raw OSM response -> {raw_path.name}")

    rows = parse_elements(data)
    print(f"Parsed {len(rows)} named businesses")
    rows = dedupe(rows)
    print(f"After de-duplication: {len(rows)}")

    imported_at = datetime.now(timezone.utc).isoformat()
    manifest = write_outputs(rows, imported_at)

    print(f"Wrote {OUT_CSV.name}: {manifest['real_osm_rows']} real + {manifest['demo_fallback_rows']} fallback = {manifest['target_rows']}")
    print(f"Provenance: {PROVENANCE_CSV.name}")
    print(f"Manifest: {MANIFEST_JSON.name}")


if __name__ == "__main__":
    sys.exit(main())
