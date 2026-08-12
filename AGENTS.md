# AGENTS.md

## What this repo is

A built Streamlit app ("Kaduna Solar Intel", brand **Sol Searching**) that turns
real Kaduna business leads into solar pitches. `document details.txt` is the
original spec. `WORKFLOW.md` documents the build stages. `ENVIRONMENTS.md`
documents machine envs.

This repo is the **reference implementation** for the global skill
`streamlit-lead-gen` (installed at `C:\Users\TOSHIBA\.claude\skills\
streamlit-lead-gen\SKILL.md`). When building a similar lead-gen app, load that
skill; this repo is its worked example. If this app changes its data workflow or
page structure, update the skill to match.

App-specific maintenance rules live in the **local skill** `kaduna-solar-intel`
(`.opencode/skills/kaduna-solar-intel/SKILL.md`) — brand, page structure, data
rules, Gemini model, secrets, QA, and live URLs. Deployment follows the global
`streamlit-client-release` skill (`C:\Users\TOSHIBA\.claude\skills\
streamlit-client-release\SKILL.md`).

## Data workflow — real, one-time, offline

- **The app never scrapes.** `scripts/import_osm_leads.py` queries the Overpass
  API ONCE, normalises/deduplicates, and freezes `data/kaduna_leads.csv` (50 rows,
  columns `id,name,address,phone,category,description,lat,lng`).
- Re-run: `python scripts/import_osm_leads.py && python scripts/validate_leads.py`.
- Provenance: `data/kaduna_leads_provenance.csv` + `data/import_manifest.json`
  (ODbL, attribution "OpenStreetMap contributors", import timestamp).
- `data/kaduna_leads_demo.csv` is the preserved synthetic backup; fallback rows
  (if any) are flagged `demo_fallback` and never presented as real.
- Engineered columns (`assigned_band`, `est_monthly_fuel`, `generated_pitch`,
  risk/reward fields) are computed in memory and never written back to the CSV.

## Page structure

`app.py` (Home) → `pages/1_Scraper.py` (Market Scan: stages cached data) →
`pages/2_Map.py` (Lead Map: `st.data_editor` + compact teardrop
`folium.Marker`/`DivIcon` pins, 20×26px, band-coloured, dark ring = selected) →
`pages/3_Finance_Hub.py` (portfolio snapshot, 3-col decision brief, 2-col charts,
2-col pitches, assumptions, export).

- Shared shell lives in `ui.py` (CSS, sidebar, hero, KPI cards). Do not duplicate
  sidebar markup in pages.
- KPI cards are a custom `div.kpi-grid` (auto-fit `minmax(150px,1fr)`), not native
  `st.metric`, so long currency values like `₦12,700,000` always render fully.
  Cards are `(label, value)` or `(label, value, hint)`; native metrics are not used.
- Page headings are sized with `clamp(1.9rem, 3.2vw, 2.5rem)` against
  `[data-testid="stHeadingWithActionElements"] h1` in `ui.py`; the map renders
  with `st_folium(..., use_container_width=True)` so it fills its column.
- Columns auto-stack vertically below 720px via a media query on
  `[data-testid="stHorizontalBlock"]`.
- Required Gemini prompt templates live in `data_layer.py`; the `Sol Searching`
  signature is appended after generation, never injected into the prompt.
- Brand is `BRAND = "Sol Searching"` in `data_layer.py`.
- Grid-supply hours are illustrative assumptions (`BAND_GRID_HOURS`); labelled as
  assumptions in the UI.

## Environment

- Use `appdev-conda` (`conda activate appdev-conda`, Python 3.13): streamlit 1.61.1,
  pandas 3.0.5, plotly 6.9.0, folium 0.20.0, streamlit-folium 0.27.4,
  google-generativeai 0.8.6. Never install into `base`.
- Run with `streamlit run app.py`, not `python app.py`.
- `GOOGLE_API_KEY` via `st.secrets`; fallback "API Key Missing. Pitches simulated."
- Hero image is `assets/solar-hero.jpg` (CC0, credited in `assets/ATTRIBUTIONS.md`).

## QA

```powershell
python scripts/validate_leads.py
pytest
pyright .
```

Browser geometry smoke (after any CSS/map change): at widths 1440, 1280, 720,
719, and 390 — no horizontal overflow, no heading clipped, footer over no
interactive element, watermark `pointer-events: none`, map shows all 50 pins,
KPI values untruncated, columns stacked below 720px.
