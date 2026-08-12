import base64
import os

import streamlit as st

from data_layer import BRAND, load_manifest

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HERO_PATH = os.path.join(BASE_DIR, "assets", "solar-hero.jpg")
WATERMARK_PATH = os.path.join(BASE_DIR, "assets", "sun-watermark.svg")

CONTACT_PHONE = "07061674831"
DESIGN_CREDIT = "JJMB Analytics"

NAV_PAGES = [
    ("app.py", "🏠 Home"),
    ("pages/1_Scraper.py", "📡 Market Scan"),
    ("pages/2_Map.py", "🗺️ Lead Map"),
    ("pages/3_Finance_Hub.py", "💰 Finance Hub"),
]

GLOBAL_CSS = """
<style>
  :root {
    --ink: #1F2937;
    --muted: #6B7280;
    --sun: #F59E0B;
    --turquoise: #06B6D4;
    --coral: #FB7185;
    --card: #FFFFFF;
    --soft: #FFF3D6;
  }

  /* Layout rhythm */
  .block-container { padding-top: 1.8rem; padding-bottom: 4.5rem; max-width: 1400px; }
  h1, h2, h3 { letter-spacing: -0.01em; color: var(--ink); }
  .stApp [data-testid="stHeadingWithActionElements"] h1 {
    font-size: clamp(1.9rem, 3.2vw, 2.5rem);
    line-height: 1.12;
  }
  @media (max-width: 720px) {
    .stApp [data-testid="stHeadingWithActionElements"] h1 { font-size: 1.7rem; }
  }
  #MainMenu { visibility: hidden; }
  footer { visibility: hidden; }

  /* Bright solar background with sun watermark (non-interactive, aria-hidden) */
  .stApp {
    background:
      radial-gradient(1100px 500px at 12% -8%, #FFF3D6 0%, rgba(255,243,214,0) 60%),
      radial-gradient(900px 480px at 105% 8%, #E0F2FE 0%, rgba(224,242,254,0) 55%),
      var(--bg-color, #FFF9EE);
  }
  .stApp::before {
    content: "";
    position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background-image: url("data:image/svg+xml;base64,__WATERMARK_B64__");
    background-repeat: repeat; background-size: 220px 220px;
    opacity: 0.5;
  }
  .stApp > * { position: relative; z-index: 1; }

  /* Hero banner */
  div.hero {
    position: relative; border-radius: 18px; overflow: hidden;
    border: 1px solid rgba(245,158,11,0.5);
    box-shadow: 0 14px 44px rgba(180,120,10,0.22);
    margin-bottom: 1.6rem;
  }
  div.hero img { width: 100%; display: block; object-fit: cover; }
  div.hero-inner {
    position: absolute; inset: 0;
    display: flex; flex-direction: column; justify-content: flex-end;
    padding: 1.6rem 1.8rem;
    background: linear-gradient(180deg, rgba(31,41,55,0.05) 30%, rgba(31,41,55,0.85) 100%);
  }
  div.hero-inner .eyebrow {
    color: #FCD34D; font-weight: 800; text-transform: uppercase;
    letter-spacing: 0.14em; font-size: 0.78rem; margin-bottom: 0.4rem;
  }
  div.hero-inner h1 {
    color: #FFFFFF; font-size: 2.15rem; line-height: 1.1; margin: 0 0 0.35rem; font-weight: 800;
  }
  div.hero-inner p { color: rgba(255,255,255,0.9); font-size: 1.02rem; margin: 0; max-width: 42rem; }

  /* KPI grid — custom cards, full values always visible */
  div.kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 0.8rem;
    margin-bottom: 1.2rem;
  }
  div.kpi-card {
    background: var(--card);
    border: 1px solid rgba(245,158,11,0.35);
    border-radius: 14px;
    padding: 0.9rem 1rem;
    box-shadow: 0 4px 18px rgba(180,120,10,0.12);
    min-width: 0;
  }
  div.kpi-card .kpi-label { color: var(--muted); font-size: 0.8rem; font-weight: 600; }
  div.kpi-card .kpi-value {
    color: #B45309; font-weight: 800;
    font-size: clamp(1.35rem, 2vw, 1.8rem);
    line-height: 1.2;
    word-break: break-word; overflow-wrap: anywhere;
    margin: 0.2rem 0 0;
  }
  div.kpi-card .kpi-hint { color: var(--muted); font-size: 0.72rem; margin-top: 0.3rem; }

  /* Insight / priority / assumption cards (Finance Hub) */
  div.insight-card {
    background: var(--card);
    border: 1px solid rgba(245,158,11,0.3);
    border-radius: 14px;
    padding: 0.9rem 1.1rem;
    box-shadow: 0 4px 16px rgba(180,120,10,0.1);
    height: 100%;
  }
  div.insight-card h4 { margin: 0 0 0.5rem; color: #B45309; font-size: 1rem; }
  div.insight-card ul { margin: 0; padding-left: 1.1rem; line-height: 1.55; color: #374151; }
  div.insight-card li { margin-bottom: 0.35rem; }
  div.insight-card .fine { color: var(--muted); font-size: 0.78rem; margin-top: 0.4rem; }

  /* Priority row inside an insight card */
  div.priority-row {
    display: flex; justify-content: space-between; align-items: baseline;
    gap: 0.5rem; padding: 0.35rem 0; border-bottom: 1px dashed rgba(245,158,11,0.3);
    min-width: 0;
  }
  div.priority-row:last-child { border-bottom: none; }
  div.priority-row > div { min-width: 0; }
  div.priority-row .name { color: #1F2937; font-weight: 700; font-size: 0.9rem; word-break: break-word; }
  div.priority-row .detail { color: var(--muted); font-size: 0.78rem; word-break: break-word; }
  div.priority-row .value { color: #B45309; font-weight: 800; font-size: 0.9rem; white-space: nowrap; }

  /* Channel badge on pitch cards */
  span.channel-badge {
    display: inline-block; margin-left: 0.4rem;
    background: #E0F2FE; color: #0E7490;
    border-radius: 999px; padding: 0.05rem 0.5rem;
    font-size: 0.68rem; font-weight: 800; letter-spacing: 0.04em;
    vertical-align: 0.15em;
  }
  span.channel-badge.email { background: #FEF3C7; color: #B45309; }

  /* Source badge */
  span.source-badge {
    display: inline-block;
    background: #DCFCE7; color: #15803D;
    border: 1px solid rgba(22,163,74,0.4);
    border-radius: 999px;
    padding: 0.18rem 0.7rem;
    font-size: 0.75rem; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase;
  }
  span.source-badge.warn { background: #FEF3C7; color: #B45309; border-color: rgba(245,158,11,0.5); }

  /* Section header kicker */
  span.kicker {
    display: block;
    color: var(--sun); font-weight: 800; text-transform: uppercase;
    letter-spacing: 0.16em; font-size: 0.72rem;
    margin-bottom: 0.35rem;
  }

  /* Pitch cards */
  div.pitch-card {
    background: var(--card);
    border: 1px solid rgba(245,158,11,0.3);
    border-radius: 12px;
    padding: 0.9rem 1.1rem;
    margin-bottom: 0.6rem;
    box-shadow: 0 4px 16px rgba(180,120,10,0.1);
  }
  div.pitch-card .pitch-name { color: #B45309; font-weight: 800; margin-bottom: 0.25rem; }
  div.pitch-card .pitch-body { color: #374151; line-height: 1.45; white-space: pre-wrap; }

  /* Sidebar polish */
  section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #FFF9EE 0%, #FFF3D6 100%);
    border-right: 1px solid rgba(245,158,11,0.25);
  }
  section[data-testid="stSidebar"] .stMarkdown p { margin-bottom: 0.25rem; }
  div.sidebar-brand {
    border-top: 1px solid rgba(245,158,11,0.3);
    margin-top: 1rem; padding-top: 0.8rem;
  }
  div.sidebar-brand p { color: var(--muted); font-size: 0.8rem; line-height: 1.5; margin: 0; }
  div.sidebar-brand .brand { color: #B45309; font-weight: 800; }
  div.sidebar-brand a { color: #0E7490; text-decoration: none; }

  /* In-flow page footer (normal flow, right-aligned on wide, centered on small) */
  div.app-footer {
    margin-top: 2.4rem;
    padding-top: 0.9rem;
    border-top: 1px solid rgba(245,158,11,0.35);
    color: var(--muted);
    font-size: 0.85rem;
    text-align: right;
    line-height: 1.6;
  }
  div.app-footer .credit { color: #B45309; font-weight: 700; }
  div.app-footer a { color: #0E7490; text-decoration: none; font-weight: 700; }
  @media (max-width: 720px) {
    div.app-footer { text-align: center; }
    /* Stack Streamlit columns vertically on mobile */
    [data-testid="stHorizontalBlock"] { flex-direction: column; gap: 0.8rem; }
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { width: 100% !important; min-width: 0; }
    div.kpi-grid { grid-template-columns: 1fr; }
  }
</style>
"""


def _watermark_b64():
    with open(WATERMARK_PATH, "rb") as fh:
        return base64.b64encode(fh.read()).decode("ascii")


def inject_css():
    css = GLOBAL_CSS.replace("__WATERMARK_B64__", _watermark_b64())
    st.markdown(css, unsafe_allow_html=True)


def sidebar():
    with st.sidebar:
        for path, label in NAV_PAGES:
            st.page_link(path, label=label)
        st.divider()
        st.markdown(
            f"""
            <div class="sidebar-brand">
              <p><span class="brand">{BRAND}</span></p>
              <p>Kaduna Solar Intel v1.0</p>
              <p>Data © OpenStreetMap contributors (ODbL)</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def footer():
    st.markdown(
        f"""
        <div class="app-footer">
          © 2026 <span class="credit">{DESIGN_CREDIT}</span> · Designed for {BRAND} ·
          <a href="tel:{CONTACT_PHONE}">{CONTACT_PHONE}</a>
        </div>
        """,
        unsafe_allow_html=True,
    )


def source_badge():
    manifest = load_manifest()
    real = manifest.get("real_osm_rows", 0)
    fallback = manifest.get("demo_fallback_rows", 0)
    date = (manifest.get("imported_at", "") or "")[:10]
    if fallback:
        return f'<span class="source-badge warn">Live + {fallback} fallback · OSM import {date}</span>'
    return f'<span class="source-badge">Live OSM · {real} businesses · {date}</span>'


def hero(eyebrow="Sol Searching · Kaduna Solar Intel"):
    st.markdown(
        f"""
        <div class="hero">
          <img src="data:image/jpeg;base64,{_hero_b64()}" alt="Rooftop solar panels">
          <div class="hero-inner">
            <div class="eyebrow">{eyebrow}</div>
            <h1>Turn diesel spend into solar pipeline</h1>
            <p>Real Kaduna businesses. Measured fuel exposure. One clear solar pitch.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def kicker(text):
    st.markdown(f'<span class="kicker">{text}</span>', unsafe_allow_html=True)


def kpi_row(cards):
    """cards: iterable of (label, value) or (label, value, hint)."""
    html = ['<div class="kpi-grid">']
    for card in cards:
        label = card[0]
        value = card[1]
        hint = card[2] if len(card) > 2 else None
        hint_html = f'<div class="kpi-hint">{hint}</div>' if hint else ""
        html.append(
            f'<div class="kpi-card"><div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{value}</div>{hint_html}</div>'
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def insight_card(title, body_html, fine=None):
    fine_html = f'<div class="fine">{fine}</div>' if fine else ""
    st.markdown(
        f'<div class="insight-card"><h4>{title}</h4>{body_html}{fine_html}</div>',
        unsafe_allow_html=True,
    )


def priority_card(rows, title="Priority queue", fine=None):
    """rows: iterable of (name, detail, value). Renders a titled insight card."""
    inner = []
    for name, detail, value in rows:
        inner.append(
            f'<div class="priority-row"><div><div class="name">{name}</div>'
            f'<div class="detail">{detail}</div></div><div class="value">{value}</div></div>'
        )
    fine_html = f'<div class="fine">{fine}</div>' if fine else ""
    st.markdown(
        f'<div class="insight-card"><h4>{title}</h4>{"".join(inner)}{fine_html}</div>',
        unsafe_allow_html=True,
    )


def pitch_card(name, body, channel=None):
    badge = ""
    if channel:
        cls = "email" if channel.lower() == "email" else ""
        badge = f'<span class="channel-badge {cls}">{channel}</span>'
    st.markdown(
        f'<div class="pitch-card"><div class="pitch-name">{name}{badge}</div>'
        f'<div class="pitch-body">{body}</div></div>',
        unsafe_allow_html=True,
    )


def _hero_b64():
    with open(HERO_PATH, "rb") as fh:
        return base64.b64encode(fh.read()).decode("ascii")
