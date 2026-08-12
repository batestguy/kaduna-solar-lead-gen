# Deployment — Kaduna Solar Lead Gen (Sol Searching)

This guide documents how this app gets from a working folder to a public
Streamlit Community Cloud URL. **Git first, Streamlit second**: Streamlit Cloud
deploys from a GitHub repository, so the repository is the reviewed source of
truth and the deployment simply points at it.

## Order of operations

1. Prepare the repo (docs, pins, ignore rules).
2. Run release QA locally.
3. Create the GitHub repository and push `main`.
4. Deploy from GitHub in Streamlit Community Cloud.
5. Add the live URL + demo walkthrough back into `README.md`.

Never skip straight to Step 4: every deploy triggers a fresh install from the
repository, so the repo must already contain `requirements.txt` and `app.py`.

## 1. Prepare the repository

These files must exist at the repo root before the first commit:

| File | Purpose |
|---|---|
| `app.py` | Streamlit entry point (deployed as the main file). |
| `requirements.txt` | Pinned dependencies Streamlit Cloud installs. |
| `.gitignore` | Excludes secrets, caches, exports, screenshots. |
| `README.md` | Client-facing description + demo walkthrough. |
| `DEPLOYMENT.md` | This file. |
| `.github/workflows/ci.yml` | CI: validate leads, pytest, pyright. |

`.streamlit/config.toml` is committed and ships with the app; it contains **no
secrets** (only theme/server/browser settings). Any `GOOGLE_API_KEY` is provided
at deploy time through Streamlit Secrets, never committed.

## 2. Release QA (run before pushing)

```powershell
conda activate appdev-conda
python scripts/validate_leads.py
pytest
pyright .
```

Browser smoke after any UI change: Home, Market Scan, Lead Map, Finance Hub at
widths 1440/1280/720/719/390 — no horizontal overflow, no heading clipped,
footer over no interactive element, KPI values untruncated, map shows all 50
pins.

## 3. GitHub

```powershell
# from the project root
git init
git add -A
git commit -m "Kaduna Solar Lead Gen v1.0 — Sol Searching"
git branch -M main
git remote add origin <repo-url>
git push -u origin main
```

- Create the repository on GitHub first (public or private — see note below).
- Confirm `.gitignore` excluded any `secrets.toml`, `.env`, `__pycache__`,
  `.pytest_cache`, and screenshot/export artifacts.
- `git status` should be clean after the push.

> **Client-sharing decision:** the repo contains real OSM-derived business data
> (names, addresses, phones) and a cached raw OSM response
> (`data/raw/osm_kaduna_businesses.json`). Decide before publishing whether that
> should be public. A **private** repository deploys on Streamlit Cloud exactly
> the same way, so private is the safe default until the decision is confirmed.

## 4. Streamlit Community Cloud

1. Go to https://share.streamlit.io (or the Deploy button in `streamlit run`).
2. Sign in with GitHub, grant repo access.
3. **Create app** → pick this repository, branch `main`, main file `app.py`.
4. Optional: choose a custom subdomain (e.g. `sol-searching`).
5. Click **Deploy**.
6. After the first deploy, open **Advanced settings → Secrets** and add:

   ```toml
   GOOGLE_API_KEY = "<your Gemini API key>"
   ```

   The app already falls back to *"API Key Missing. Pitches simulated."* when
   the key is absent, so it deploys without it, but pitches are simulated until
   a key is set.

7. Streamlit Cloud installs exactly the pins in `requirements.txt` (Python
   version from the cloud's default runtime; see `runtime.txt` if a pin is
   needed).

## 5. Finish client presentation

- Paste the live URL into `README.md`.
- Add a short feature walkthrough (Market Scan → Lead Map → Finance Hub) and a
  screenshot.
- Note data provenance and the illustrative assumptions in the client-facing
  copy.

## Rollback / redeploy

Every push to `main` triggers a redeploy. To roll back, revert the offending
commit and push, or point the Streamlit app at a different branch/commit in
**Advanced settings**. Local run stays available with `streamlit run app.py`.
