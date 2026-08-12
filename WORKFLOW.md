# Kaduna Solar Lead Gen — Build Workflow

Brand: **Sol Searching** · Data: OpenStreetMap (ODbL) · Runtime: Streamlit (offline)

This repo is the worked example of the global skill `streamlit-lead-gen`
(`C:\Users\TOSHIBA\.claude\skills\streamlit-lead-gen\SKILL.md`). Changes to this
app's data workflow or page structure should be mirrored into that skill.

## Stages

| # | Stage | Command / Action | Gate |
|---|---|---|---|
| 0 | Baseline | Preserve synthetic data | `data/kaduna_leads_demo.csv` exists |
| 1 | One-time import | `python scripts/import_osm_leads.py` | Real OSM rows ≥ 1 |
| 2 | Data cleaning | Inside importer (normalise, dedupe) | No fabricated fields |
| 3 | Freeze dataset | Importer writes CSV + provenance + manifest | `validate_leads.py` passes |
| 4 | Documentation | This file + `data_dictionary.md` | Reproducible by another agent |
| 5 | Risk model | In-memory grid-supply + reward fields in `data_layer.py` | Assumptions labelled |
| 6 | Visual system | `.streamlit/config.toml`, `ui.py`, hero asset | Desktop + mobile render |
| 7 | Page redesign | Home, Market Scan, Map, Finance Hub | All nav flows work |
| 8 | Map refinement | `Marker` + `DivIcon` teardrop pins (20×26), band colours, dark ring = selected | All 50 pins render |
| 9 | Offline runtime | App reads only frozen files | No network calls at runtime |
| 10 | Final QA | `pytest`, pyright, browser smoke | Release-ready |
| 11 | Viewport verification | Browser geometry at 1440/1280/720/719/390 | No overflow/clipping |
| 12 | Finance Hub depth | Snapshot + 3-col brief + 2-col charts/pitches + assumptions | Full values, no truncation |

## How to re-run the one-time import

```powershell
conda activate appdev-conda
python scripts/import_osm_leads.py     # queries Overpass ONCE, saves frozen CSV
python scripts/validate_leads.py       # must pass before the app is used
```

The Streamlit app **never** calls the importer or any network endpoint. It only
reads `data/kaduna_leads.csv`.

## Data rules

- Source: OpenStreetMap via Overpass API (public, ODbL licence). Attribution:
  © OpenStreetMap contributors.
- The importer queries a Kaduna metro bounding box `(10.40, 7.30, 10.65, 7.55)`
  across `shop`, `amenity`, `office`, `craft`, `tourism=hotel`, `building=industrial`.
- Names, phones, and addresses are normalised from OSM tags only. Missing phones
  stay null; generic addresses fall back to `"Kaduna"` (never invented).
- De-duplication is by normalised business name.
- If fewer than 50 verified OSM businesses are found, the remainder are padded
  from `data/kaduna_leads_demo.csv` and flagged `demo_fallback` in the
  provenance file. They are never presented as real.
- Raw OSM response is cached at `data/raw/osm_kaduna_businesses.json` for audit.
- Do **not** use Nominatim for bulk lookups (usage policy limits throughput and
  forbids systematic POI downloads). Google Places is a future alternative that
  requires billing, an API key, quotas, and attribution.

## Generated data files

| File | Purpose |
|---|---|
| `data/kaduna_leads_demo.csv` | Frozen synthetic backup (never edited). |
| `data/kaduna_leads.csv` | App runtime source. Exactly 50 rows, strict schema. |
| `data/kaduna_leads_provenance.csv` | Per-row source (`osm` / `demo_fallback`), OSM id, category. |
| `data/import_manifest.json` | Import date, counts, licence, attribution, bbox. |
| `data/raw/osm_kaduna_businesses.json` | Raw Overpass response for audit. |

## Risk/reward model (illustrative assumptions)

Grid-supply figures are **assumptions** used to explain the pitch, not measured
outage data. Replace them when real data is available.

| Band | Diesel use (h/day) | Grid supply (h/day) | Diesel cost /month |
|---|---|---|---|
| A | 10 | 8 | ₦450,000 |
| B | 6 | 5 | ₦200,000 |
| D | 2 | 3 | ₦50,000 |

- `grid_gap = max(diesel_hours - grid_hours, 0)`
- `grid_risk = 24 - grid_hours`
- `monthly_saving = diesel_cost - SOLAR_INSTALLMENT (₦85,000)`
- `payback_months = 3,000,000 / monthly_saving`
- Reward tiers: 🟢 Immediate ROI (>₦300k) · 🟡 Strong Candidate (>₦100k) · 🔴 Educate First (≤₦100k)

## Run the app

```powershell
conda activate appdev-conda
streamlit run app.py
```

## QA commands

```powershell
python scripts/validate_leads.py
pytest
pyright .
```

### Viewport verification (after any CSS/map change)

Check the map page (and every page) at widths **1440, 1280, 720, 719, 390**:
no horizontal overflow, no heading clipped, footer over no interactive element,
watermark `pointer-events: none`, map shows all 50 teardrop pins, KPI values
untruncated (long values like `₦12,700,000` must render fully), and columns
stack vertically below 720px.

### Finance Hub layout notes

- KPI cards are a custom `div.kpi-grid` (auto-fit `minmax(150px,1fr)`) — never
  switch back to native `st.metric` or long currency values get clipped.
- Finance Hub order: snapshot → 3-col decision brief → 2-col charts → 2-col
  pitches → advisory + assumptions → export. Empty state offers a Lead Map CTA.
