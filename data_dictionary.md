# Data Dictionary — Kaduna Solar Lead Gen

Brand: **Sol Searching** · Dataset: **OpenStreetMap (real data, one-time import)**
Runtime source: `data/kaduna_leads.csv` (frozen, exactly 50 rows). The app never
scrapes; it only loads this file.

## Source columns (`data/kaduna_leads.csv`)

| Column | Type | Description |
|---|---|---|
| `id` | int | Unique lead identifier (1–50). |
| `name` | str | Business name, normalised (title case). |
| `address` | str | Address assembled from OSM `addr:*` tags; falls back to `"Kaduna"` if none exist. Never invented. |
| `phone` | str (nullable) | Normalised to E.164 (`234…`). Null → email pitch path. |
| `category` | str | Normalised business vertical (Bank, Hotel, Hospital, Restaurant, School, …). |
| `description` | str | Category-specific one-liner + brand/website hints + OSM source note. |
| `lat` | float | Latitude within Kaduna metro bbox. |
| `lng` | float | Longitude within Kaduna metro bbox. |

## Engineered columns (computed in memory, never written back to CSV)

| Column | Type | Description |
|---|---|---|
| `assigned_band` | str (`A`/`B`/`D`) | Keyword logic over `category` + `description`. A heavy (10 h/day), B medium (6 h/day), D light (2 h/day). |
| `est_monthly_fuel` | int | Hardcoded diesel cost per band: `A` → ₦450,000 · `B` → ₦200,000 · `D` → ₦50,000. |
| `generated_pitch` | str (nullable) | Null until Finance Hub. Populated by Gemini Flash (or simulated fallback) and cached in session state. |
| `selected` | bool | UI checkbox column used on the Map page; persisted in session state. |

### Keyword → band mapping

- **Band A**: factory, manufacturing, processing, cold chain, cold storage, cold room, freezer, hotel, hospital, bottling, plant, block makers, blast freezer
- **Band B**: restaurant, eatery, grill, pharmacy, school, salon, auto repair, supermarket, bakery, laundry, printing, guest house
- **Band D**: kiosk, boutique, phone repair, barber, bookstore, tailoring, fashion, accessories
- Unmatched → defaults to `B`.

## Risk / reward model (illustrative assumptions)

Grid-supply hours are assumptions to explain the pitch — **not** measured outage
data. Replace when real data arrives.

| Band | Diesel use (h/day) | Grid supply (h/day) | Diesel /month |
|---|---|---|---|
| A | 10 | 8 | ₦450,000 |
| B | 6 | 5 | ₦200,000 |
| D | 2 | 3 | ₦50,000 |

- `grid_gap = max(diesel_hours - grid_hours, 0)` — daily hours the business runs on its own generation.
- `grid_risk = 24 - grid_hours` — daily hours of grid dependency exposure.
- `monthly_saving = est_monthly_fuel - SOLAR_INSTALLMENT`
- `payback_months = 3,000,000 / monthly_saving`
- Advisory: 🟢 Immediate ROI (`>₦300k`) · 🟡 Strong Candidate (`>₦100k`) · 🔴 Educate First (`≤₦100k`)

## Constants

| Constant | Value | Where |
|---|---|---|
| `SOLAR_INSTALLMENT` | ₦85,000/month (₦3M / 36 months) | Finance Hub chart |
| `SYSTEM_COST` | ₦3,000,000 | payback calc |
| Chart cap | Top 10 by `est_monthly_fuel` | Finance Hub; remainder in table |

## Provenance & attribution

- `data/kaduna_leads_provenance.csv` — per-row `source_type` (`osm` / `demo_fallback`), `osm_id`, `osm_category`, `imported_at`.
- `data/import_manifest.json` — counts, licence (ODbL), attribution ("OpenStreetMap contributors"), bbox.
- `data/raw/osm_kaduna_businesses.json` — cached raw Overpass response for audit.
- Fallback rows (if ever used) are explicitly `demo_fallback`; never presented as real.

## Export columns (Finance Hub download)

`name, address, phone, category, assigned_band, generated_pitch`
