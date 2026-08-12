# Kaduna Solar Lead Gen — Sol Searching

Turn real Kaduna businesses into a solar sales pipeline. Select leads on a map,
and get portfolio economics, a priority queue, ready-to-send pitches, and a
CSV export for your sales rep.

**Built with Streamlit** · Data: OpenStreetMap (ODbL) · Runs fully offline at
runtime — no live scraping.

🔗 **Live demo:** https://kaduna-solar-lead-ge-y3wljh2pqvkadljhlytgkg.streamlit.app

## What it does

| Stage | Page | What you get |
|---|---|---|
| 1 | **Market Scan** | Loads the one-time OpenStreetMap import (50 verified businesses, no live scraping). |
| 2 | **Lead Map** | Band-coloured pins on a Kaduna map; tick businesses to build a portfolio. |
| 3 | **Finance Hub** | Portfolio snapshot, 3-column decision brief, diesel-vs-solar charts, one pitch per lead, and a sales CSV. |

### The pitch engine

- Each selected lead gets a short **SMS** pitch (≤160 chars, when a phone number
  exists) or a **professional email** otherwise.
- The **Sol Searching** signature is appended after generation.
- Pitches are generated with Gemini Flash; without an API key the app clearly
  shows *"API Key Missing. Pitches simulated."* and falls back to canned text.

## Getting started

```powershell
conda activate appdev-conda   # Python 3.13; see ENVIRONMENTS.md
streamlit run app.py
```

Then open http://localhost:8501.

Dependencies are pinned in `requirements.txt`. Run QA with:

```powershell
python scripts/validate_leads.py
pytest
pyright .
```

## Data & honesty

- **Source:** OpenStreetMap via the Overpass API, imported once (ODbL licence).
  Attribution: © OpenStreetMap contributors.
- `data/kaduna_leads.csv` is a frozen 50-row snapshot. The app never scrapes and
  makes no network calls at runtime.
- Band fuel estimates and grid-supply hours are **illustrative assumptions**
  used to explain the pitch, not measured outage data — labelled as such in the
  UI.
- Full provenance lives in `data/kaduna_leads_provenance.csv` and
  `data/import_manifest.json`.

## Project layout

```
app.py                        # Home
pages/1_Scraper.py            # Market Scan
pages/2_Map.py                # Lead Map (folium, teardrop pins)
pages/3_Finance_Hub.py        # Risk · Reward · Pitch
ui.py                         # shared shell (CSS, sidebar, footer)
data_layer.py                 # business logic, prompts, risk model
data/                         # frozen CSV + provenance + manifest
scripts/                      # one-time import + validation
tests/                        # pipeline tests
```

See `WORKFLOW.md` (build stages), `data_dictionary.md` (schema), and
`DEPLOYMENT.md` (Git → Streamlit).

## Branding

Sidebar, hero, footer and all pitches carry the **Sol Searching** brand.
© 2026 JJMB Analytics · Designed for Sol Searching.
