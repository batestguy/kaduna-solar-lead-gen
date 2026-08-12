import streamlit as st

from data_layer import ensure_session_state, load_manifest
from ui import footer, hero, inject_css, kpi_row, sidebar, source_badge

st.set_page_config(page_title="Sol Searching · Kaduna Solar Intel", page_icon="☀️", layout="wide")

ensure_session_state()
inject_css()
sidebar()

df = st.session_state.full_df
manifest = load_manifest()

hero()

st.markdown(source_badge(), unsafe_allow_html=True)

band_a = int((df["assigned_band"] == "A").sum())
band_b = int((df["assigned_band"] == "B").sum())
band_d = int((df["assigned_band"] == "D").sum())
total_exposure = int(df["est_monthly_fuel"].sum())

kpi_row(
    [
        ("Live Leads", len(df)),
        ("Diesel Exposure / Mo", f"₦{total_exposure:,}"),
        ("Band A · Heavy", band_a),
        ("Band B · Medium", band_b),
        ("Band D · Light", band_d),
    ]
)

st.markdown("")
col_a, col_b = st.columns([2, 1])

with col_a:
    st.markdown("### The play")
    st.markdown(
        "- **Market Scan** — load the one-time OpenStreetMap import (no live scraping).\n"
        "- **Lead Map** — pick businesses; compact pins colour-track your selection.\n"
        "- **Finance Hub** — risk/reward per business, a diesel-vs-solar chart, "
        "and Sol Searching pitches ready for WhatsApp/email."
    )

with col_b:
    st.markdown("### Data provenance")
    st.markdown(
        f"- **Source:** {manifest.get('source', 'OpenStreetMap')}\n"
        f"- **Licence:** {manifest.get('license', 'ODbL')}\n"
        f"- **Imported:** {(manifest.get('imported_at', '') or '')[:19]}\n"
        f"- **Rows:** {len(df)} verified businesses"
    )
    st.caption("Attribution: © OpenStreetMap contributors.")

footer()
