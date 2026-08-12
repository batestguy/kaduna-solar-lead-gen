import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data_layer import (
    BAND_DIESEL_HOURS,
    BAND_GRID_HOURS,
    SOLAR_INSTALLMENT,
    SYSTEM_COST,
    ensure_session_state,
    generate_pitch,
    get_api_key,
)
from ui import (
    footer,
    inject_css,
    insight_card,
    kpi_row,
    pitch_card,
    priority_card,
    sidebar,
    source_badge,
)

st.set_page_config(page_title="Finance Hub · Sol Searching", page_icon="💰", layout="wide")

ensure_session_state()
inject_css()
sidebar()

st.markdown('<span class="kicker">Stage 3 · Finance Hub</span>', unsafe_allow_html=True)
st.title("Risk · Reward · Pitch")

if not st.session_state.selected_ids:
    st.markdown("### No portfolio selected yet")
    st.markdown(
        "The Finance Hub turns your chosen businesses into a solar sales portfolio — "
        "economics, a priority queue, and a ready-to-send pitch per lead."
    )
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        insight_card(
            "1 · Pick businesses",
            "<ul><li>Open the Lead Map.</li><li>Tick the businesses you want to pitch.</li></ul>",
        )
    with col_b:
        insight_card(
            "2 · Save the selection",
            "<ul><li>Click <b>Save Selected &amp; Analyse</b>.</li><li>Your leads carry over automatically.</li></ul>",
        )
    with col_c:
        insight_card(
            "3 · Read the plan",
            "<ul><li>Return here for economics, priority queue and one pitch per lead.</li></ul>",
        )
    if st.button("Go to Lead Map →", type="primary"):
        st.switch_page("pages/2_Map.py")
    footer()
    st.stop()

df = st.session_state.full_df
filtered = df[df["id"].isin(st.session_state.selected_ids)].copy()

if len(filtered) < 1:
    st.warning("Your selection contains no valid leads.")
    footer()
    st.stop()

# ── Executive header ────────────────────────────────────────────────────────────
st.markdown(
    f"**{len(filtered)} selected businesses** · {source_badge()}",
    unsafe_allow_html=True,
)
st.markdown(
    "Here is what your selected portfolio is worth on paper: how much diesel it "
    "burns, what a solar financing plan costs, what you could save every month, "
    "and which leads to call first. Grid-supply figures below are "
    "**illustrative assumptions**, not measured outage data."
)

# ── Portfolio snapshot ──────────────────────────────────────────────────────────
monthly_diesel = int(filtered["est_monthly_fuel"].sum())
monthly_solar = SOLAR_INSTALLMENT * len(filtered)
monthly_saving = monthly_diesel - monthly_solar
roi_count = int((filtered["est_monthly_fuel"] > 300000).sum())
paybacks = filtered["payback_months"].dropna()
avg_payback = round(paybacks.mean(), 1) if len(paybacks) else None

kpi_row(
    [
        ("Leads in Analysis", len(filtered), "Selected on the Lead Map"),
        ("Diesel Spend / Mo", f"₦{monthly_diesel:,}", "Estimated generator fuel"),
        ("Solar Installment / Mo", f"₦{monthly_solar:,}", f"₦85,000 × {len(filtered)}"),
        ("Potential Saving / Mo", f"₦{monthly_saving:,}", "Diesel − installment"),
        (
            "Avg Payback",
            f"{avg_payback} mo" if avg_payback else "—",
            "On eligible leads",
        ),
        ("Immediate ROI Leads", roi_count, "> ₦300k diesel / mo"),
    ]
)
st.caption(
    "Solar financing assumes a ₦3,000,000 system over 36 months at exactly ₦85,000/month "
    "per business. Saving can be negative where diesel spend is below the installment."
)
st.markdown("")

# ── Three-column decision brief ─────────────────────────────────────────────────
col_econ, col_prior, col_motion = st.columns(3)

with col_econ:
    annual_saving = monthly_saving * 12
    insight_card(
        "Portfolio economics",
        f"""
        <ul>
          <li><b>Diesel:</b> ₦{monthly_diesel:,} / mo</li>
          <li><b>Solar:</b> ₦{monthly_solar:,} / mo</li>
          <li><b>Saving:</b> ₦{monthly_saving:,} / mo</li>
          <li><b>Annualised:</b> ₦{annual_saving:,} / yr</li>
          <li><b>System value:</b> ₦{SYSTEM_COST:,} across {len(filtered)} lead(s)</li>
        </ul>
        """,
        fine="Best when diesel spend comfortably exceeds the ₦85,000 installment.",
    )

with col_prior:
    top3 = filtered.nlargest(3, "monthly_saving")
    rows = []
    for _, r in top3.iterrows():
        tier = "🟢" if r["est_monthly_fuel"] > 300000 else ("🟡" if r["est_monthly_fuel"] > 100000 else "🔴")
        channel = "SMS" if pd.notna(r["phone"]) and str(r["phone"]).strip() else "Email"
        rows.append(
            (
                r["name"],
                f"Band {r['assigned_band']} · {channel} · {tier}",
                f"₦{int(r['monthly_saving']):,}",
            )
        )
    priority_card(
        rows,
        title="Priority queue",
        fine="By modelled monthly saving — highest saving first.",
    )

with col_motion:
    insight_card(
        "Sales motion",
        "<ul>"
        "<li>Start with <b>Immediate ROI</b> leads.</li>"
        "<li>Confirm generator usage during the visit.</li>"
        "<li>Offer a free site survey.</li>"
        "<li>Validate real diesel spend before quoting.</li>"
        "<li>Move to a 36-month financing discussion.</li>"
        "</ul>",
        fine="Order matters more than volume — qualify first, quote second.",
    )

st.markdown("")

# ── Charts ──────────────────────────────────────────────────────────────────────
st.markdown("### Decision charts")
st.markdown(
    "Two views of the same portfolio: one asks *who is most exposed*, the other "
    "*how much each lead burns* versus what solar would cost."
)

col_c1, col_c2 = st.columns(2)

with col_c1:
    st.markdown("#### Risk–reward map")
    st.caption(
        "X = grid-dependency risk (hours without grid) · Y = monthly saving · "
        "bubble size = diesel spend."
    )

    fig = go.Figure()
    for band, color, label in (("A", "#F59E0B", "Band A"), ("B", "#06B6D4", "Band B"), ("D", "#FB7185", "Band D")):
        subset = filtered[filtered["assigned_band"] == band]
        if subset.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=subset["grid_risk_hours"],
                y=subset["monthly_saving"],
                mode="markers+text",
                name=label,
                text=subset["name"].apply(lambda n: n if len(n) <= 14 else n[:13] + "…"),
                textposition="top center",
                textfont={"size": 9, "color": "#4B5563"},
                marker={"size": 10 + subset["est_monthly_fuel"] / 30000, "color": color, "opacity": 0.85},
                customdata=subset[["name", "est_monthly_fuel", "payback_months"]],
                hovertemplate="<b>%{customdata[0]}</b><br>Diesel ₦%{customdata[1]:,}<br>"
                              "Saving ₦%{y:,}<br>Payback %{customdata[2]} mo<extra></extra>",
            )
        )

    fig.add_hline(y=0, line_dash="dash", line_color="#9CA3AF")
    fig.add_annotation(
        x=16, y=max(filtered["monthly_saving"].max(), 1) * 0.92,
        text="Higher reward", showarrow=False, font={"color": "#0E7490"},
    )
    fig.add_annotation(
        x=22, y=0, text="Grid-dependent → solar wins",
        showarrow=False, font={"color": "#B45309"},
    )
    fig.update_layout(
        height=440,
        xaxis_title="Grid-dependency risk (hrs/day)",
        yaxis_title="Monthly saving (₦)",
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FFFFFF",
        font={"color": "#1F2937"},
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=20, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)

with col_c2:
    st.markdown("#### Diesel vs solar — top 10 by fuel spend")
    st.caption("Orange = current diesel cost · green = the flat solar installment.")

    chart_df = filtered.nlargest(10, "est_monthly_fuel")
    names = chart_df["name"].apply(lambda n: n if len(str(n)) <= 15 else str(n)[:14] + "…")

    fig2 = go.Figure()
    fig2.add_bar(x=names, y=chart_df["est_monthly_fuel"], name="Diesel Cost", marker_color="#F59E0B")
    fig2.add_bar(
        x=names,
        y=[SOLAR_INSTALLMENT] * len(chart_df),
        name="Solar Installment",
        marker_color="#10B981",
    )
    fig2.update_layout(
        barmode="group",
        yaxis_title="₦ per month",
        xaxis_title="Business",
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FFFFFF",
        font={"color": "#1F2937"},
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=20, b=10),
    )
    st.plotly_chart(fig2, use_container_width=True)

if len(filtered) > 10:
    st.caption(f"Showing top 10 by fuel cost; {len(filtered) - 10} more below.")
    rest = filtered.drop(chart_df.index)
    st.dataframe(
        rest[["name", "category", "assigned_band", "est_monthly_fuel", "grid_risk_hours", "monthly_saving"]],
        hide_index=True,
        use_container_width=True,
    )

st.markdown("")

# ── AI pitches ──────────────────────────────────────────────────────────────────
st.markdown("### AI pitches — Sol Searching")
st.markdown(
    "One ready-to-send pitch per lead. **SMS** pitches are capped at 160 characters "
    "for leads with a phone number; **Email** pitches are drafted for the rest. "
    "The *Sol Searching* signature is appended after generation."
)
if get_api_key() is None:
    st.info("API Key Missing. Pitches simulated.")

for idx, row in filtered.iterrows():
    if row["generated_pitch"] is None:
        pitch = generate_pitch(row)
        df.at[idx, "generated_pitch"] = pitch
        st.session_state.pitches_generated = True

filtered = df[df["id"].isin(st.session_state.selected_ids)].copy()

pitches = []
for _, row in filtered.iterrows():
    channel = "SMS" if pd.notna(row["phone"]) and str(row["phone"]).strip() else "Email"
    pitches.append((f"{row['name']} · Band {row['assigned_band']}", row["generated_pitch"], channel))

for i in range(0, len(pitches), 2):
    c1, c2 = st.columns(2)
    name1, body1, ch1 = pitches[i]
    with c1:
        pitch_card(name1, body1, channel=ch1)
    if i + 1 < len(pitches):
        name2, body2, ch2 = pitches[i + 1]
        with c2:
            pitch_card(name2, body2, channel=ch2)

st.markdown("")

# ── Advisory table + assumptions ────────────────────────────────────────────────
st.markdown("### Advisory & payback")


def advisory(fuel):
    if fuel > 300000:
        return "🟢 Immediate ROI"
    if fuel > 100000:
        return "🟡 Strong Candidate"
    return "🔴 Educate First"


filtered["Advisory"] = filtered["est_monthly_fuel"].apply(advisory)

col_t, col_a = st.columns([2, 1])

with col_t:
    st.markdown("#### Per-lead numbers")
    st.dataframe(
        filtered[
            [
                "name",
                "category",
                "assigned_band",
                "est_monthly_fuel",
                "grid_gap_hours",
                "grid_risk_hours",
                "monthly_saving",
                "payback_months",
                "Advisory",
            ]
        ].rename(
            columns={
                "est_monthly_fuel": "Diesel (₦/mo)",
                "grid_gap_hours": "Own-gen gap (h)",
                "grid_risk_hours": "Grid risk (h)",
                "monthly_saving": "Saving (₦/mo)",
                "payback_months": "Payback (mo)",
            }
        ),
        hide_index=True,
        use_container_width=True,
    )
    st.caption("Payback = ₦3,000,000 ÷ monthly saving. Blank payback = saving below installment (educate first).")

with col_a:
    insight_card(
        "Model assumptions",
        "<ul>"
        f"<li>Installment: ₦{SOLAR_INSTALLMENT:,}/mo over 36 months</li>"
        f"<li>System cost: ₦{SYSTEM_COST:,}</li>"
        f"<li>Band A diesel: 10h/day → ₦450,000/mo</li>"
        f"<li>Band B diesel: 6h/day → ₦200,000/mo</li>"
        f"<li>Band D diesel: 2h/day → ₦50,000/mo</li>"
        "</ul>",
        fine="Grid-supply hours are illustrative, not measured outage data. Replace with real figures when available.",
    )

st.markdown("")

# ── Export ──────────────────────────────────────────────────────────────────────
st.markdown("### Export for sales rep")

export_cols = ["name", "address", "phone", "category", "assigned_band", "generated_pitch"]
export_df = filtered[export_cols]
csv_bytes = export_df.to_csv(index=False).encode("utf-8")

st.markdown(
    "Download the selected leads with their generated pitches as a CSV you can "
    "hand to a sales rep or import into a dialer / WhatsApp tool."
)
st.download_button(
    "⬇️ Download CSV",
    data=csv_bytes,
    file_name="sol_searching_leads_export.csv",
    mime="text/csv",
    type="primary",
)

footer()
