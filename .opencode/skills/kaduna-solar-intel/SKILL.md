---
name: kaduna-solar-intel
description: Maintenance playbook for the Kaduna Solar Intel Streamlit app (brand "Sol Searching") in this repository. Use when working on this app — editing pages, changing the data workflow, updating pitches/branding, running QA, or preparing a release. Captures the app-specific rules that AGENTS.md points at: real one-time OSM import, offline runtime, teardrop map pins, custom KPI grid, Finance Hub structure, Gemini model, secrets handling, and the live GitHub/Streamlit URLs.
---

# kaduna-solar-intel

App-specific maintenance rules for **Kaduna Solar Intel** (brand **Sol
Searching**). Companion to the global skills `streamlit-lead-gen` (build
pattern) and `streamlit-client-release` (deployment). Read `AGENTS.md` first;
this skill is the same knowledge in loadable form.

## Identity

- Brand: `BRAND = "Sol Searching"` in `data_layer.py`. Signature appended after
  generation, never injected into the prompt.
- Footer: `© 2026 JJMB Analytics · Designed for Sol Searching · 07061674831`
  (`CONTACT_PHONE`/`DESIGN_CREDIT` in `ui.py`).
- Hero: `assets/solar-hero.jpg` (CC0) + `assets/sun-watermark.svg` (proprietary,
  credited in `assets/ATTRIBUTIONS.md`).

## Data workflow — real, one-time, offline

- **The app never scrapes.** `scripts/import_osm_leads.py` queries Overpass
  ONCE; the app reads only frozen `data/kaduna_leads.csv` (50 rows,
  `id,name,address,phone,category,description,lat,lng`).
- Provenance: `data/kaduna_leads_provenance.csv` + `data/import_manifest.json`
  (ODbL, "© OpenStreetMap contributors").
- `data/kaduna_leads_demo.csv` is the preserved synthetic backup; fallback rows
  flagged `demo_fallback` are never presented as real.
- Engineered columns (`assigned_band`, `est_monthly_fuel`, `generated_pitch`,
  risk/reward fields) are computed in memory and **never written back to CSV**.
- Re-run an import: `python scripts/import_osm_leads.py && python scripts/validate_leads.py`.

## Page structure

`app.py` (Home) → `pages/1_Scraper.py` (Market Scan) → `pages/2_Map.py`
(Lead Map) → `pages/3_Finance_Hub.py` (Risk · Reward · Pitch).

- Shared shell in `ui.py` (CSS, sidebar, hero, footer). Never duplicate sidebar
  markup in pages.
- Map pins: compact teardrop `folium.Marker`/`DivIcon`, 20×26px, band-coloured
  (A amber / B turquoise / D coral), dark ring = selected. Render with
  `st_folium(..., use_container_width=True)`.
- KPIs: custom `div.kpi-grid` (`repeat(auto-fit, minmax(150px,1fr))`), NOT
  native `st.metric` — long values like `₦12,700,000` must never truncate.
- Headings: `.stApp [data-testid="stHeadingWithActionElements"] h1` with
  `clamp(1.9rem, 3.2vw, 2.5rem)`.
- Mobile: columns stack below 720px via media query on
  `[data-testid="stHorizontalBlock"]`.
- Finance Hub order: snapshot → 3-col decision brief (economics / priority
  queue / sales motion) → 2-col charts → 2-col pitches → advisory + assumptions
  → export. Empty state offers a Lead Map CTA.

## Gemini

- Model: **`gemini-2.5-flash`** (2.0-flash is retired — 404). Check model
  availability before changing it.
- Key: `st.secrets["GOOGLE_API_KEY"]`; fallback "API Key Missing. Pitches simulated."
- Never commit `.streamlit/secrets.toml` (gitignored). If a key was exposed,
  revoke + regenerate, then add only via Streamlit Cloud Secrets.

## QA

```powershell
python scripts/validate_leads.py
pytest
pyright .
```

Browser geometry smoke after any CSS/map change: 1440/1280/720/719/390 — no
overflow, no heading clipped, footer over no interactive element, watermark
`pointer-events: none`, all 50 pins, KPI values untruncated, columns stacked
below 720px.

## Live locations

- GitHub: `https://github.com/batestguy/kaduna-solar-lead-gen` (public, `main`)
- Streamlit: `https://kaduna-solar-lead-ge-y3wljh2pqvkadljhlytgkg.streamlit.app`

Every push to `main` redeploys. When the app's data workflow or page structure
changes, mirror the change into the global `streamlit-lead-gen` skill.

## Red flags

- Introducing runtime scraping or network calls.
- Presenting `demo_fallback` rows as real.
- Writing engineered columns back to the frozen CSV.
- Using `st.metric` for KPI cards (clips currency).
- Committing the API key or `.streamlit/secrets.toml`.
- Shipping a retired Gemini model name.
- Editing a page's data flow without updating `AGENTS.md` + `data_dictionary.md`.
