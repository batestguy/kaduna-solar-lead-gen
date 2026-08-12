import time

import streamlit as st

from data_layer import ensure_session_state, load_manifest
from ui import footer, inject_css, kpi_row, sidebar, source_badge

st.set_page_config(page_title="Market Scan · Sol Searching", page_icon="📡", layout="wide")

ensure_session_state()
inject_css()
sidebar()

manifest = load_manifest()
df = st.session_state.full_df

st.markdown('<span class="kicker">Stage 1 · Market Scan</span>', unsafe_allow_html=True)
st.title("Load the Kaduna market snapshot")

st.markdown(
    "No live scraping — this loads the one-time OpenStreetMap import saved on "
    f"**{(manifest.get('imported_at', '') or '')[:10]}**. "
    "The button stages the cached records instantly."
)
st.markdown(source_badge(), unsafe_allow_html=True)

scraped = st.session_state.get("scraped", False)

if st.button("Load Market Snapshot", type="primary", use_container_width=True):
    progress_bar = st.progress(0.0, text="Staging cached Kaduna records…")
    steps = 20
    for i in range(1, steps + 1):
        time.sleep(0.05)
        progress_bar.progress(i / steps, text=f"Staging cached records… {i * 100 // steps}%")
    progress_bar.empty()
    st.session_state.scraped = True
    st.success("Market snapshot staged — 50 businesses ready.")

if st.session_state.get("scraped", False):
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
    st.markdown("### Top fuel-spend businesses")
    st.dataframe(
        df.sort_values("est_monthly_fuel", ascending=False)[
            ["name", "category", "assigned_band", "est_monthly_fuel", "address"]
        ].head(10),
        hide_index=True,
        use_container_width=True,
    )

    if st.button("Proceed to Lead Map →", type="primary", use_container_width=True):
        st.switch_page("pages/2_Map.py")

footer()
