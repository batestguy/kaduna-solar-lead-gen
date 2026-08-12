import folium
import streamlit as st
from streamlit_folium import st_folium

from data_layer import ensure_session_state
from ui import footer, inject_css, sidebar, source_badge

st.set_page_config(page_title="Lead Map · Sol Searching", page_icon="🗺️", layout="wide")

ensure_session_state()
inject_css()
sidebar()

df = st.session_state.full_df

st.markdown('<span class="kicker">Stage 2 · Lead Map</span>', unsafe_allow_html=True)
st.title("Select businesses to analyse")
st.markdown(source_badge(), unsafe_allow_html=True)

BAND_COLORS = {"A": "#F59E0B", "B": "#06B6D4", "D": "#FB7185"}

col_map, col_select = st.columns([2, 1], gap="medium")

with col_select:
    st.subheader("Selection panel")
    st.caption("Tick `selected` to include a business in the Finance Hub.")

    if "selected" not in df.columns:
        df["selected"] = df["id"].isin(st.session_state.selected_ids)

    panel_cols = [
        "selected",
        "name",
        "category",
        "assigned_band",
        "est_monthly_fuel",
        "phone",
    ]

    edited = st.data_editor(
        df[panel_cols],
        hide_index=True,
        disabled=[c for c in panel_cols if c != "selected"],
        column_config={
            "selected": st.column_config.CheckboxColumn("Selected", help="Include in analysis"),
            "name": st.column_config.TextColumn("Business", width="medium"),
            "category": st.column_config.TextColumn("Category"),
            "assigned_band": st.column_config.TextColumn("Band", width="small"),
            "est_monthly_fuel": st.column_config.NumberColumn("Diesel (₦/mo)", format="₦%,d", width="medium"),
            "phone": st.column_config.TextColumn("Phone"),
        },
        key="lead_editor",
        num_rows="fixed",
    )

    st.session_state.full_df.loc[edited.index, "selected"] = edited["selected"].astype(bool)

    if st.button("🔄 Refresh Map", use_container_width=True):
        st.rerun()

    if st.button("Save Selected & Analyse →", type="primary", use_container_width=True):
        selected = st.session_state.full_df.loc[
            st.session_state.full_df["selected"], "id"
        ].astype(int).tolist()
        st.session_state.selected_ids = selected
        st.switch_page("pages/3_Finance_Hub.py")

with col_map:
    st.subheader("Kaduna leads")
    st.caption("Coloured by band — amber A · turquoise B · coral D. Selected leads get a dark ring.")

    map_df = st.session_state.full_df
    selected_count = int(map_df["selected"].sum())

    m = folium.Map(
        location=[10.5264, 7.4388],
        zoom_start=12,
        tiles="CartoDB Voyager",
        control_scale=True,
    )

    def pin_icon(color, selected):
        stroke = "#1F2937" if selected else "#FFFFFF"
        svg = f"""
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="26" viewBox="0 0 20 26">
          <path d="M10 25 C10 25 1.5 15.5 1.5 9.5 A8.5 8.5 0 0 1 18.5 9.5 C18.5 15.5 10 25 10 25 Z"
                fill="{color}" stroke="{stroke}" stroke-width="2"/>
          <circle cx="10" cy="9.5" r="2.6" fill="#FFFFFF"/>
        </svg>
        """
        return folium.DivIcon(html=svg, icon_size=(20, 26), icon_anchor=(10, 25))

    legend_html = """
    <div style="background:#FFFFFF; padding:8px 12px; border-radius:8px;
                font-family:sans-serif; font-size:12px; box-shadow:0 1px 5px rgba(0,0,0,.25);
                border:1px solid #FDE68A; line-height:1.7">
      <b style="color:#B45309">Leads by band</b><br>
      <svg xmlns="http://www.w3.org/2000/svg" width="12" height="16" viewBox="0 0 20 26">
        <path d="M10 25 C10 25 1.5 15.5 1.5 9.5 A8.5 8.5 0 0 1 18.5 9.5 C18.5 15.5 10 25 10 25 Z"
              fill="#F59E0B" stroke="#FFFFFF" stroke-width="2"/></svg> Band A &nbsp;heavy<br>
      <svg xmlns="http://www.w3.org/2000/svg" width="12" height="16" viewBox="0 0 20 26">
        <path d="M10 25 C10 25 1.5 15.5 1.5 9.5 A8.5 8.5 0 0 1 18.5 9.5 C18.5 15.5 10 25 10 25 Z"
              fill="#06B6D4" stroke="#FFFFFF" stroke-width="2"/></svg> Band B &nbsp;medium<br>
      <svg xmlns="http://www.w3.org/2000/svg" width="12" height="16" viewBox="0 0 20 26">
        <path d="M10 25 C10 25 1.5 15.5 1.5 9.5 A8.5 8.5 0 0 1 18.5 9.5 C18.5 15.5 10 25 10 25 Z"
              fill="#FB7185" stroke="#FFFFFF" stroke-width="2"/></svg> Band D &nbsp;light<br>
      <svg xmlns="http://www.w3.org/2000/svg" width="12" height="16" viewBox="0 0 20 26">
        <path d="M10 25 C10 25 1.5 15.5 1.5 9.5 A8.5 8.5 0 0 1 18.5 9.5 C18.5 15.5 10 25 10 25 Z"
              fill="#F59E0B" stroke="#1F2937" stroke-width="2"/></svg> Selected
    </div>
    """
    legend = folium.Element(legend_html)
    m.get_root().html.add_child(legend)  # type: ignore[attr-defined]

    for _, row in map_df.iterrows():
        color = BAND_COLORS.get(str(row["assigned_band"]), "#9CA3AF")
        folium.Marker(
            location=[float(row["lat"]), float(row["lng"])],
            icon=pin_icon(color, bool(row["selected"])),
            tooltip=row["name"],
            popup=(
                f"<b>{row['name']}</b><br>{row['category']} · Band {row['assigned_band']}"
                f"<br>Diesel ₦{row['est_monthly_fuel']:,}/mo<br>{row['address']}"
            ),
        ).add_to(m)

    st_folium(m, height=560, use_container_width=True)

    st.markdown(f"**{selected_count}** of {len(map_df)} leads selected.")

footer()
