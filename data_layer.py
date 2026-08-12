import json
import os
import random

import pandas as pd
import streamlit as st

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CSV_PATH = os.path.join(DATA_DIR, "kaduna_leads.csv")
PROVENANCE_PATH = os.path.join(DATA_DIR, "kaduna_leads_provenance.csv")
MANIFEST_PATH = os.path.join(DATA_DIR, "import_manifest.json")

CSV_REQUIRED_COLUMNS = ["id", "name", "address", "phone", "category", "description", "lat", "lng"]
CSV_EXPECTED_ROWS = 50

KADUNA_CENTER_LAT = 10.5264
KADUNA_CENTER_LNG = 7.4388

BRAND = "Sol Searching"

BAND_FUEL_COST = {"A": 450000, "B": 200000, "D": 50000}
SOLAR_INSTALLMENT = 85000
SYSTEM_COST = 3000000

# Illustrative grid-supply assumptions per band (hours/day). NOT measured data.
BAND_DIESEL_HOURS = {"A": 10, "B": 6, "D": 2}
BAND_GRID_HOURS = {"A": 8, "B": 5, "D": 3}

BAND_A_KEYWORDS = [
    "factory", "manufacturing", "processing", "cold chain", "cold storage",
    "cold room", "freezer", "hospital", "bottling", "plant", "block makers",
    "blast freezer", "industrial", "metal fabrication", "logistics",
]
BAND_B_KEYWORDS = [
    "restaurant", "eatery", "grill", "pharmacy", "school", "salon",
    "auto repair", "supermarket", "bakery", "laundry", "printing",
    "guest house", "clinic", "office", "department store",
]
BAND_D_KEYWORDS = [
    "kiosk", "boutique", "phone repair", "barber", "bookstore",
    "tailoring", "fashion", "accessories", "greengrocer", "amenity",
]


def assign_band(row):
    text = f"{row['category']} {row['description']}".lower()
    for band, keywords in (("A", BAND_A_KEYWORDS), ("B", BAND_B_KEYWORDS), ("D", BAND_D_KEYWORDS)):
        if any(kw in text for kw in keywords):
            return band
    return "B"


def load_provenance():
    if not os.path.exists(PROVENANCE_PATH):
        return {}
    prov = pd.read_csv(PROVENANCE_PATH, dtype={"id": int})
    return dict(zip(prov["id"], prov["source_type"]))


def load_manifest():
    if not os.path.exists(MANIFEST_PATH):
        return {}
    with open(MANIFEST_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def load_and_process_csv():
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"Missing data file: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH, dtype={"phone": str, "id": int})
    if len(df) != CSV_EXPECTED_ROWS:
        raise ValueError(f"CSV must contain exactly {CSV_EXPECTED_ROWS} rows, found {len(df)}")
    missing = [c for c in CSV_REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")

    df["assigned_band"] = df.apply(assign_band, axis=1)
    df["est_monthly_fuel"] = df["assigned_band"].map(lambda b: BAND_FUEL_COST[b]).astype(int)
    df["generated_pitch"] = None

    rng = random.Random(42)
    df["lat"] = df.apply(
        lambda r: r["lat"] if pd.notna(r["lat"]) else KADUNA_CENTER_LAT + rng.uniform(-0.05, 0.05),
        axis=1,
    )
    df["lng"] = df.apply(
        lambda r: r["lng"] if pd.notna(r["lng"]) else KADUNA_CENTER_LNG + rng.uniform(-0.05, 0.05),
        axis=1,
    )

    # Risk / reward fields (illustrative assumptions).
    df["diesel_hours"] = df["assigned_band"].map(lambda b: BAND_DIESEL_HOURS[b]).astype(int)
    df["grid_hours"] = df["assigned_band"].map(lambda b: BAND_GRID_HOURS[b]).astype(int)
    df["grid_gap_hours"] = (df["diesel_hours"] - df["grid_hours"]).clip(lower=0)
    df["grid_risk_hours"] = 24 - df["grid_hours"]
    df["monthly_saving"] = (df["est_monthly_fuel"] - SOLAR_INSTALLMENT).clip(lower=0)
    df["payback_months"] = df.apply(
        lambda r: round(SYSTEM_COST / r["monthly_saving"], 1) if r["monthly_saving"] > 0 else None,
        axis=1,
    )
    df["source_type"] = df["id"].map(lambda i: load_provenance().get(int(i), "demo_fallback"))

    return df


def ensure_session_state():
    if "full_df" not in st.session_state:
        st.session_state.full_df = load_and_process_csv()
    if "selected_ids" not in st.session_state:
        st.session_state.selected_ids = []
    if "pitches_generated" not in st.session_state:
        st.session_state.pitches_generated = False


def get_api_key():
    try:
        return st.secrets["GOOGLE_API_KEY"]
    except Exception:
        return None


def sms_prompt(row):
    return (
        f"You are a solar expert in Kaduna. Create a persuasive 160-character SMS for a "
        f"{row['category']} business named {row['name']} to reduce their "
        f"₦{row['est_monthly_fuel']} monthly fuel cost."
    )


def email_prompt(row):
    return (
        f"Write a professional 250-word email to {row['name']} at {row['address']} "
        f"introducing solar financing options."
    )


def simulated_pitch(row):
    signature = f"— {BRAND}"
    if pd.notna(row["phone"]) and str(row["phone"]).strip():
        body = (
            f"Hi {row['name']}! Cut your ₦{row['est_monthly_fuel']}/month diesel bill "
            f"with solar. Free Kaduna site survey this week. Reply YES."
        )
        return f"{body} {signature}"[:160]
    return (
        f"Dear {row['name']},\n\n"
        f"Running your {row['category'].lower()} costs about ₦{row['est_monthly_fuel']} in "
        f"diesel every month. With solar financing from {BRAND}, you can stabilise power "
        f"and cut that cost. Reply to schedule a free assessment at {row['address']}.\n\n"
        f"Best regards,\n{BRAND}"
    )


def generate_pitch(row):
    api_key = get_api_key()
    if not api_key:
        return simulated_pitch(row)
    try:
        import google.generativeai as genai  # type: ignore

        genai.configure(api_key=api_key)  # type: ignore
        model = genai.GenerativeModel("gemini-2.0-flash")  # type: ignore
        if pd.notna(row["phone"]) and str(row["phone"]).strip():
            response = model.generate_content(sms_prompt(row))
            pitch = response.text.strip()
            if len(pitch) > 160:
                pitch = pitch[:160]
        else:
            response = model.generate_content(email_prompt(row))
            pitch = response.text.strip()
        if not pitch:
            return simulated_pitch(row)
        # Append brand signature without disturbing the mandated prompt template.
        if pd.notna(row["phone"]) and str(row["phone"]).strip():
            return f"{pitch} — {BRAND}"[:160]
        return f"{pitch}\n\n{BRAND}"
    except Exception:
        return simulated_pitch(row)
