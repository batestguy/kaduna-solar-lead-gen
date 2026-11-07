"""Build the Sol Searching walkthrough film.

Stages (each independently re-runnable):

    login      open the live app in a real Chrome window and wait for sign-in
    probe      inspect the live app: selectors, data-editor geometry, figures
    capture    Playwright take -> .walkthrough_tmp/raw/*.webm + docs/demo/captions.json
    pills      render one amber caption PNG per beat (Pillow)
    composite  ffmpeg: trim, overlay pills + end card -> .walkthrough_tmp/master.mp4
    audio      ffmpeg: song from 0:14, fades, loudness -> .walkthrough_tmp/music.m4a
    mux        final encode -> docs/demo/sol_searching_walkthrough.mp4
    cover      docs/demo/01_cover.jpg from the first caption's midpoint

    python scripts/build_walkthrough.py --stage all

Build tooling only — no app dependencies, nothing added to requirements.txt.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / ".walkthrough_tmp"
RAW = TMP / "raw"
PILLS = TMP / "pills"
PROFILE = TMP / "chrome-profile"
DEMO = ROOT / "docs" / "demo"
CAPTIONS = DEMO / "captions.json"
TIMINGS = TMP / "timings.json"

URL = "https://kaduna-solar-lead-ge-y3wljh2pqvkadljhlytgkg.streamlit.app"
SONG = ROOT / "assets" / "music" / "let-the-sun-in.mp3"
FINAL = DEMO / "sol_searching_walkthrough.mp4"

W, H, FPS = 1600, 1000, 30
CUE_SECONDS = 14.0  # "Let the Sun In" from 0:14
END_CARD_SECONDS = 8.0

INK = (31, 41, 55)
SUN = (245, 158, 11)
TURQUOISE = (6, 182, 212)
SOFT = (255, 243, 214)


def log(*args: object) -> None:
    print(*args, flush=True)


# --------------------------------------------------------------------------- fonts


def font_path(*names: str) -> str | None:
    for name in names:
        for base in (Path("C:/Windows/Fonts"), Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"):
            candidate = base / name
            if candidate.exists():
                return str(candidate)
    return None


SEMI = lambda: font_path("seguisb.ttf", "segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf")
REGULAR = lambda: font_path("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf")


# ----------------------------------------------------------------------- playwright

CURSOR_JS = r"""
(() => {
  const CURSOR_ID = "__buf_cursor";
  function ensure() {
    if (!document.body) return;
    if (document.getElementById(CURSOR_ID)) return;
    const c = document.createElement("div");
    c.id = CURSOR_ID;
    c.style.cssText = "position:fixed;left:0;top:0;z-index:2147483647;pointer-events:none;will-change:transform;";
    c.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
      + '<path d="M3.5 1.8 L20.6 11.4 L12.6 12.7 L16.9 21.2 L13.6 22.8 L9.3 14.3 L3.5 20.4 Z"'
      + ' fill="#1F2937" stroke="#FFFFFF" stroke-width="1.8" stroke-linejoin="round"/></svg>';
    document.body.appendChild(c);
  }
  window.addEventListener("mousemove", (e) => {
    ensure();
    const c = document.getElementById(CURSOR_ID);
    if (c) c.style.transform = "translate(" + (e.clientX - 2) + "px," + (e.clientY - 1) + "px)";
  }, true);
  window.addEventListener("mousedown", (e) => {
    ensure();
    if (document.getElementById("__buf_ring")) return;
    const ring = document.createElement("div");
    ring.id = "__buf_ring";
    ring.style.cssText = "position:fixed;left:" + e.clientX + "px;top:" + e.clientY + "px;"
      + "width:34px;height:34px;margin:-17px 0 0 -17px;border:3px solid #F59E0B;border-radius:50%;"
      + "z-index:2147483646;pointer-events:none;";
    document.body.appendChild(ring);
    const t0 = performance.now();
    const step = (now) => {
      const p = Math.min((now - t0) / 340, 1);
      ring.style.transform = "scale(" + (0.9 + 0.95 * p) + ")";
      ring.style.opacity = String(0.95 * (1 - p));
      if (p < 1) requestAnimationFrame(step); else ring.remove();
    };
    requestAnimationFrame(step);
  }, true);
  ensure();
  new MutationObserver(() => ensure()).observe(document.documentElement, {childList: true, subtree: true});
})();
"""


def launch(p, recording: bool):
    PROFILE.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    kwargs = dict(
        user_data_dir=str(PROFILE),
        channel="chrome",
        headless=False,
        viewport={"width": W, "height": H},
        device_scale_factor=1,
        color_scheme="light",
        locale="en-NG",
        args=[f"--window-size={W},{H + 90}", "--hide-crash-restore-bubble"],
    )
    if recording:
        kwargs["record_video_dir"] = str(RAW)
        kwargs["record_video_size"] = {"width": W, "height": H}
    ctx = p.chromium.launch_persistent_context(**kwargs)
    ctx.add_init_script(CURSOR_JS)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.set_default_timeout(90_000)
    return ctx, page


def is_app_ready(page) -> bool:
    try:
        return page.get_by_text("Turn diesel spend into solar pipeline", exact=False).count() > 0
    except Exception:
        return False


def wait_for_app(page, limit_s: float, quiet: bool = False) -> bool:
    started = time.time()
    while time.time() - started < limit_s:
        if is_app_ready(page):
            return True
        if not quiet:
            log(f"  … waiting for the app ({int(time.time() - started)}s)")
        page.wait_for_timeout(5000)
    return is_app_ready(page)


def settle(page, ms: int = 1200) -> None:
    page.wait_for_timeout(ms)


def smooth_scroll(page, target, steps: int = 6, pause: int = 45, offset: float = 120.0) -> None:
    """Smooth-scroll to a pixel offset, a CSS selector, or a Locator.

    JS scrolling is used rather than wheel events: a wheel over the Leaflet
    map zooms the map, and a wheel over a Plotly chart zooms the chart.
    """
    # Streamlit scrolls an inner container, not the window, so ask the page
    # which element actually scrolls before computing anything.
    info = page.evaluate(
        """() => {
          const cands = [document.querySelector('[data-testid="stMain"]'),
                         document.querySelector('[data-testid="stAppViewContainer"]'),
                         document.scrollingElement];
          for (const el of cands) {
            if (el && el.scrollHeight > el.clientHeight + 20) {
              const r = el.getBoundingClientRect();
              return {top: el.scrollTop, max: el.scrollHeight - el.clientHeight, ctop: r.top};
            }
          }
          const se = document.scrollingElement;
          return {top: se ? se.scrollTop : 0,
                  max: se ? se.scrollHeight - se.clientHeight : 0,
                  ctop: 0};
        }"""
    )
    if isinstance(target, (int, float)):
        y = float(target)
    else:
        rect_top = None
        if isinstance(target, str):
            rect_top = page.evaluate(
                "(sel) => { const el = document.querySelector(sel);"
                " return el ? el.getBoundingClientRect().top : null; }",
                target,
            )
        else:
            box = target.bounding_box()
            if box:
                rect_top = box["y"]
        if rect_top is None:
            return
        y = float(info["top"]) + (float(rect_top) - float(info["ctop"])) - offset
    y = max(0.0, min(y, float(info["max"])))
    page.evaluate(
        """(y) => {
          const cands = [document.querySelector('[data-testid="stMain"]'),
                         document.querySelector('[data-testid="stAppViewContainer"]'),
                         document.scrollingElement];
          for (const el of cands) {
            if (el && el.scrollHeight > el.clientHeight + 20) {
              el.scrollTo({top: y, behavior: 'smooth'});
              return;
            }
          }
          window.scrollTo({top: y, behavior: 'smooth'});
        }""",
        y,
    )
    page.wait_for_timeout(800)


def glide(page, x: float, y: float, steps: int = 18, pause: int = 16) -> None:
    page.mouse.move(x, y, steps=steps)
    page.wait_for_timeout(pause)


def click_at(page, x: float, y: float, dwell: int = 480, after: int = 900) -> None:
    glide(page, x, y, steps=16, pause=12)
    page.wait_for_timeout(dwell)
    page.mouse.down()
    page.wait_for_timeout(90)
    page.mouse.up()
    page.wait_for_timeout(after)


def centre(page, locator) -> tuple[float, float]:
    box = locator.bounding_box()
    if not box:
        raise RuntimeError("no bounding box")
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def click_locator(page, locator, dwell: int = 480, after: int = 900) -> None:
    locator.scroll_into_view_if_needed()
    page.wait_for_timeout(250)
    x, y = centre(page, locator)
    click_at(page, x, y, dwell=dwell, after=after)


def hover_locator(page, locator, hold: int = 700) -> None:
    locator.scroll_into_view_if_needed()
    page.wait_for_timeout(250)
    x, y = centre(page, locator)
    glide(page, x, y, steps=14, pause=14)
    page.wait_for_timeout(hold)


def nav_link(page, label: str):
    return page.locator('section[data-testid="stSidebar"] a').filter(has_text=label).first


# ------------------------------------------------------------------------- login


def stage_login(args) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx, page = launch(p, recording=False)
        log("goto", args.url)
        page.goto(args.url, wait_until="domcontentloaded", timeout=180_000)
        log("")
        log("=" * 72)
        log("  CHROME IS OPEN. Sign in / wake the app in that window.")
        log("  I am waiting for the Sol Searching home page to appear.")
        log("=" * 72)
        log("")
        for name in ("Yes, get this app back up!", "Continue to app"):
            btn = page.get_by_role("button", name=name)
            if btn.count():
                try:
                    btn.first.click()
                    log("clicked", name)
                except Exception:
                    pass
        ok = wait_for_app(page, limit_s=args.wait_seconds)
        log("APP READY" if ok else "APP NOT READY")
        if ok:
            page.screenshot(path=str(TMP / "login_ready.png"))
        page.wait_for_timeout(1500)
        ctx.close()


# ------------------------------------------------------------------------- probe


def stage_probe(args) -> None:
    from playwright.sync_api import sync_playwright

    TMP.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {}
    with sync_playwright() as p:
        ctx, page = launch(p, recording=False)
        page.goto(args.url, wait_until="domcontentloaded", timeout=180_000)
        ready = wait_for_app(page, limit_s=180, quiet=True)
        report["ready"] = ready
        log("ready:", ready)
        if not ready:
            page.screenshot(path=str(TMP / "probe_not_ready.png"))
            ctx.close()
            (TMP / "probe.json").write_text(json.dumps(report, indent=2))
            return

        page.wait_for_timeout(2000)
        page.screenshot(path=str(TMP / "probe_01_home.png"))
        report["testids_home"] = page.evaluate(
            "Array.from(new Set(Array.from(document.querySelectorAll('[data-testid]'))"
            ".map(e => e.getAttribute('data-testid')))).sort()"
        )
        report["sidebar_links"] = page.evaluate(
            "Array.from(document.querySelectorAll('section[data-testid=\"stSidebar\"] a'))"
            ".map(a => ({text: a.innerText.trim(), href: a.getAttribute('href')}))"
        )

        # Market Scan
        try:
            click_locator(page, nav_link(page, "Market Scan"), after=2500)
            page.wait_for_timeout(2000)
            page.screenshot(path=str(TMP / "probe_02_market.png"))
            report["buttons_market"] = page.evaluate(
                "Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(Boolean)"
            )
            load_btn = page.get_by_role("button", name=re.compile("Load Market Snapshot", re.I)).first
            report["load_btn_count"] = load_btn.count()
            click_locator(page, load_btn, after=6000)
            page.wait_for_timeout(2500)
            page.screenshot(path=str(TMP / "probe_03_market_loaded.png"))
            report["market_loaded_text"] = page.inner_text("body")[:1500]
        except Exception as exc:
            report["market_error"] = repr(exc)
            log("market error", exc)

        # Lead Map
        try:
            proceed = page.get_by_role("button", name=re.compile("Proceed to Lead Map", re.I)).first
            click_locator(page, proceed, after=9000)
            page.wait_for_timeout(4000)
            page.screenshot(path=str(TMP / "probe_04_map.png"))
            editor = page.locator('[data-testid="stDataFrame"]').first
            report["editor_count"] = editor.count()
            if editor.count():
                box = editor.bounding_box()
                report["editor_box"] = box
                page.screenshot(path=str(TMP / "probe_04_editor.png"), clip=box)
                # try clicking row 1 checkbox then row 2
                if box:
                    clicks = []
                    for row in range(3):
                        cx = box["x"] + 26
                        cy = box["y"] + 43 + row * 35
                        click_at(page, cx, cy, dwell=300, after=3200)
                        body = page.inner_text("body")
                        line = [ln for ln in body.splitlines() if "leads selected" in ln]
                        clicks.append({"row": row, "y": cy, "line": line[:1]})
                    report["checkbox_clicks"] = clicks
                    page.screenshot(path=str(TMP / "probe_05_after_clicks.png"))
            report["map_text"] = page.inner_text("body")[-1200:]
        except Exception as exc:
            report["map_error"] = repr(exc)
            log("map error", exc)

        ctx.close()

    (TMP / "probe.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    log("probe written ->", TMP / "probe.json")


# ------------------------------------------------------------------------ capture

CURSOR_START = {"x": W - 60.0, "y": H - 80.0}
BEATS: list[dict[str, object]] = []
T_TAKE = 0.0
TAKE_VALID = False
PITCHES_REAL = True


def mark(bid: int, caption: str | None = None, anchor: str = "bottom-right") -> None:
    t = round(time.time() - T_TAKE, 2)
    BEATS.append({"id": bid, "t": t, "caption": caption, "anchor": anchor})
    log(f"  beat {bid:02d} @ {t:6.2f}s  {caption or '—'}")


def wait_for_map(page, timeout_s: float = 45.0) -> bool:
    """Wait until the folium iframe has actually painted map tiles."""
    started = time.time()
    while time.time() - started < timeout_s:
        for frame in page.frames:
            try:
                if frame.locator("img.leaflet-tile").count() > 4:
                    page.wait_for_timeout(1200)
                    return True
            except Exception:
                continue
        page.wait_for_timeout(700)
    return False


def wait_idle(page, timeout_s: float = 45.0) -> bool:
    """Wait until Streamlit is no longer running a script (the Stop button)."""
    started = time.time()
    while time.time() - started < timeout_s:
        try:
            if page.get_by_role("button", name="Stop").count() == 0:
                page.wait_for_timeout(450)
                if page.get_by_role("button", name="Stop").count() == 0:
                    return True
        except Exception:
            return True
        page.wait_for_timeout(500)
    return False


def warm_up_selection(page) -> bool:
    """Tick the five leads before the film starts.

    Every checkbox click rebuilds the folium map and reloads its tiles, which
    would leave a blank map on camera for seconds at a time. The selection is
    therefore made off-camera; the take opens on the ticks already in place.
    """
    click_locator(page, nav_link(page, "Lead Map"), after=4000)
    page.wait_for_timeout(7000)  # map iframe + tiles
    tick_leads(page)
    wait_idle(page, 20)
    page.wait_for_timeout(3000)
    return selected_count(page) == SELECTION_TARGETS


def open_finance(page) -> bool:
    """Click Save Selected until the Finance Hub actually renders."""
    for attempt in range(3):
        wait_idle(page, 25)
        save = page.get_by_role("button", name=re.compile("Save Selected", re.I)).first
        if not save.count():
            return False
        click_locator(page, save, after=2000)
        for _ in range(25):
            if page.get_by_text("Risk · Reward · Pitch", exact=False).count():
                return True
            page.wait_for_timeout(1000)
        log(f"  save click {attempt + 1} did not navigate — retrying")
    return False


def take(page) -> None:
    """Drive the film. One function so every beat is in reading order."""
    global T_TAKE, TAKE_VALID, PITCHES_REAL

    page.reload(wait_until="domcontentloaded")
    wait_for_app(page, limit_s=240)
    page.wait_for_timeout(2500)
    if not warm_up_selection(page):
        raise SystemExit("warm-up selection did not reach five leads")
    click_locator(page, nav_link(page, "Home"), after=3000)
    wait_for_app(page, limit_s=60, quiet=True)
    wait_idle(page, 20)
    page.wait_for_timeout(2000)
    T_TAKE = time.time()
    log("  take starts (warm-up trimmed)")

    # --- 1 Home hero -------------------------------------------------------
    page.evaluate("() => window.scrollTo(0, 0)")
    glide(page, CURSOR_START["x"], CURSOR_START["y"], steps=6)
    mark(1, "Diesel spend, turned into solar pipeline")
    glide(page, 1180, 620, steps=24, pause=30)
    page.wait_for_timeout(3000)

    # --- 2 KPI cards -------------------------------------------------------
    mark(2, "Fifty leads, ₦12.7m diesel every month")
    smooth_scroll(page, 520)
    kpi = page.locator("div.kpi-value").nth(1)
    if kpi.count():
        hover_locator(page, kpi, hold=3000)
    page.wait_for_timeout(3000)

    # --- 3 Data provenance --------------------------------------------------
    mark(3, "Real OpenStreetMap data, imported once")
    smooth_scroll(page, 900)
    prov = page.get_by_text("Data provenance", exact=False).first
    if prov.count():
        hover_locator(page, prov, hold=2000)
    page.wait_for_timeout(2200)

    # --- 4 -> Market Scan ---------------------------------------------------
    mark(4)
    click_locator(page, nav_link(page, "Market Scan"), after=3500)
    page.wait_for_timeout(1800)

    # --- 5 Load snapshot ----------------------------------------------------
    mark(5, "One click stages the frozen import")
    load_btn = page.get_by_role("button", name=re.compile("Load Market Snapshot", re.I)).first
    click_locator(page, load_btn, dwell=520, after=1800)
    page.wait_for_timeout(2600)  # progress bar + rerun

    # --- 6 KPI + top table --------------------------------------------------
    mark(6, "Twelve heavy users dominate the spend")
    smooth_scroll(page, 480)
    page.wait_for_timeout(1800)
    smooth_scroll(page, 1050)
    rows = page.locator('[data-testid="stDataFrame"]').first
    if rows.count():
        hover_locator(page, rows, hold=1200)
    page.wait_for_timeout(2400)

    # --- 7 -> Lead Map ------------------------------------------------------
    mark(7)
    proceed = page.get_by_role("button", name=re.compile("Proceed to Lead Map", re.I)).first
    click_locator(page, proceed, after=2500)
    log("  map ready:", wait_for_map(page, 45))
    page.wait_for_timeout(1500)

    # --- 8 pins -------------------------------------------------------------
    mark(8, "Fifty businesses, coloured by diesel band", anchor="bottom-left")
    smooth_scroll(page, 200)
    m = page.locator("iframe").first
    if m.count():
        box = m.bounding_box()
        if box:
            glide(page, box["x"] + box["width"] * 0.45, box["y"] + box["height"] * 0.5, steps=24, pause=24)
    page.wait_for_timeout(5000)

    # --- 9 the five marked leads --------------------------------------------
    mark(9, "Five leads ringed for analysis", anchor="bottom-left")
    smooth_scroll(page, 120)
    page.wait_for_timeout(1200)
    panel = page.get_by_text("Selection panel", exact=False).first
    if panel.count():
        hover_locator(page, panel, hold=1800)
    page.wait_for_timeout(2800)

    # --- 10 save selection --------------------------------------------------
    mark(10, "Five selected, ready for analysis", anchor="bottom-left")
    if not open_finance(page):
        log("  !! finance hub did not open")
    page.wait_for_timeout(3000)
    body = page.inner_text("body")
    TAKE_VALID = "₦1,500,000" in body and "5 selected businesses" in body

    log("  finance check:", "₦1,500,000" in body, "| five leads:", "5 selected businesses" in body,
        "| API box:", "API Key Missing" in body, "| take valid:", TAKE_VALID)

    # --- 11 portfolio snapshot ---------------------------------------------
    mark(11, "Portfolio snapshot: spend, saving, payback")
    smooth_scroll(page, "div.kpi-grid", offset=150)
    kpi2 = page.locator("div.kpi-value").nth(3)
    if kpi2.count():
        hover_locator(page, kpi2, hold=2400)
    page.wait_for_timeout(2800)

    # --- 12 decision brief ---------------------------------------------------
    mark(12, "Economics, priority queue, sales motion")
    smooth_scroll(page, page.locator("div.insight-card").first, offset=110)
    prio = page.get_by_text("Priority queue", exact=False).first
    if prio.count():
        hover_locator(page, prio, hold=2200)
    page.wait_for_timeout(2400)

    # --- 13 risk-reward scatter ---------------------------------------------
    mark(13, "Risk versus reward, bubbles sized by diesel")
    smooth_scroll(page, "div[data-testid='stPlotlyChart']", offset=110)
    plot = page.locator("div[data-testid='stPlotlyChart']").first
    if plot.count():
        box = plot.bounding_box()
        if box:
            for fx, fy in ((0.42, 0.35), (0.62, 0.55)):
                glide(page, box["x"] + box["width"] * fx, box["y"] + box["height"] * fy, steps=14, pause=18)
                page.wait_for_timeout(1500)
        page.wait_for_timeout(1200)

    # --- 14 diesel vs solar --------------------------------------------------
    mark(14, "Diesel bars dwarf the flat installment")
    plot2 = page.locator("div[data-testid='stPlotlyChart']").nth(1)
    if plot2.count():
        box = plot2.bounding_box()
        if box:
            for fx, fy in ((0.34, 0.42), (0.44, 0.52)):
                glide(page, box["x"] + box["width"] * fx, box["y"] + box["height"] * fy, steps=14, pause=18)
                page.wait_for_timeout(1600)
    page.wait_for_timeout(1800)

    # --- 15 pitches ----------------------------------------------------------
    mark(15, "One ready-to-send pitch per lead")
    smooth_scroll(page, page.locator("div.pitch-card").first, offset=150)
    pitch = page.locator("div.pitch-card").first
    try:
        pitch.wait_for(timeout=90_000)  # Gemini drafts on first Finance Hub render
    except Exception:
        log("  !! pitches did not render")
    if pitch.count():
        hover_locator(page, pitch, hold=1600)
    glide(page, 1150, 700, steps=20, pause=26)
    page.wait_for_timeout(3000)
    pitch_text = page.inner_text("body")
    # The canned fallback always asks for a "Reply YES"; Gemini copy does not.
    PITCHES_REAL = "Reply YES" not in pitch_text
    log("  real Gemini pitches on screen:", PITCHES_REAL)
    page.wait_for_timeout(2000)

    # --- 16 advisory ---------------------------------------------------------
    mark(16, "Advisory flags who to call first")
    smooth_scroll(page, page.get_by_text("Advisory & payback", exact=False).first, offset=110)
    adv = page.get_by_text("Advisory", exact=False).first
    if adv.count():
        hover_locator(page, adv, hold=1800)
    page.wait_for_timeout(3600)

    # --- 17 export ------------------------------------------------------------
    mark(17, "CSV hand-off for the sales rep")
    dl = page.get_by_role("button", name=re.compile("Download CSV|Download", re.I)).first
    if not dl.count():
        dl = page.get_by_text("⬇️ Download CSV", exact=False).first
    if dl.count():
        smooth_scroll(page, dl, offset=300)
        hover_locator(page, dl, hold=2600)
    page.wait_for_timeout(2600)

    # --- 18 end card ----------------------------------------------------------
    mark(18)
    page.wait_for_timeout(8200)  # card fades in over this still stretch
    TAKE_VALID = TAKE_VALID and PITCHES_REAL


# Canvas data-editor geometry (measured in .walkthrough_tmp/probe_editor2.py):
# first checkbox sits 56 px below the grid top, rows are 35 px apart, the
# checkbox centre is 46 px in from the grid's left edge.
EDITOR_HEADER = 56.0
EDITOR_ROW_H = 35.0
EDITOR_CHECKBOX_X = 46.0
SELECTION_TARGETS = 5  # ids 1-5: two Band A + three Band B, all in the first five rows
TICK_FILL = (245, 158, 11)  # app primaryColor — a ticked checkbox is filled amber


def selected_count(page) -> int:
    for line in page.inner_text("body").splitlines():
        match = re.match(r"(\d+) of \d+ leads selected", line.strip())
        if match:
            return int(match.group(1))
    return -1


def stable_box(page, editor):
    """Return the grid box only once it has stopped moving."""
    editor.scroll_into_view_if_needed()
    page.wait_for_timeout(600)
    last = None
    for _ in range(12):
        box = editor.bounding_box()
        if box and last and abs(box["y"] - last["y"]) < 1 and abs(box["x"] - last["x"]) < 1:
            return box
        last = box
        page.wait_for_timeout(200)
    return last


def slot_is_ticked(page, editor, slot: int) -> bool:
    """Read the real checkbox state from the grid's own pixels (it is a canvas)."""
    from PIL import Image

    png = editor.screenshot()  # element-relative, unaffected by page scroll
    with Image.open(io.BytesIO(png)) as im:
        cx = int(EDITOR_CHECKBOX_X)
        cy = int(EDITOR_HEADER + slot * EDITOR_ROW_H)
        crop = im.convert("RGB").crop((cx - 7, cy - 7, cx + 7, cy + 7))
        pixels = list(crop.getdata())
    mean_r = sum(px[0] for px in pixels) / len(pixels)
    # Measured in .walkthrough_tmp/probe_diff.py: a ticked box reads ~140 grey,
    # an empty one ~242 white/cream, so brightness alone is decisive.
    return mean_r < 205


def tick_slot(page, editor, slot: int, label: str) -> bool:
    """Click one checkbox and confirm it from the pixels, not the counter."""
    for attempt in range(4):
        before = selected_count(page)
        box = stable_box(page, editor)
        if not box:
            return False
        click_at(
            page,
            box["x"] + EDITOR_CHECKBOX_X,
            box["y"] + EDITOR_HEADER + slot * EDITOR_ROW_H,
            dwell=240,
            after=1400,
        )
        wait_idle(page, 20)  # a tick triggers a full Streamlit rerun
        page.wait_for_timeout(500)
        box = stable_box(page, editor)
        if not box:
            return False
        ticked = slot_is_ticked(page, editor, slot)
        after = before
        for _ in range(8):  # the count line updates a beat after the checkbox
            after = selected_count(page)
            if after == before + 1:
                break
            page.wait_for_timeout(400)
        if ticked and after == before + 1:
            log(f"  ticked {label} -> {after} selected")
            return True
        log(f"  retry {label} (ticked={ticked}, {before} -> {after})")
    return False


def tick_leads(page) -> None:
    """Tick the five demo leads inside the canvas data editor."""
    editor = page.locator('[data-testid="stDataFrame"]').first
    if not editor.count():
        log("  !! no data editor")
        return

    for slot, label in enumerate("id1 id2 id3 id4 id5".split()):
        tick_slot(page, editor, slot, label)

    got = selected_count(page)
    log(f"  selection: {got}/{SELECTION_TARGETS}")
    if got != SELECTION_TARGETS:
        log("  !! selection count wrong — the take should be re-run")


def stage_capture(args) -> None:
    from playwright.sync_api import sync_playwright

    BEATS.clear()
    global TAKE_VALID, PITCHES_REAL
    TAKE_VALID = False
    PITCHES_REAL = True
    for path in RAW.glob("*.webm"):
        path.unlink()
    DEMO.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        ctx, page = launch(p, recording=True)
        page.goto(args.url, wait_until="domcontentloaded", timeout=180_000)
        ok = wait_for_app(page, limit_s=args.wait_seconds, quiet=True)
        log("app ready:", ok)
        if not ok:
            page.screenshot(path=str(TMP / "capture_blocked.png"))
            ctx.close()
            raise SystemExit("app never became ready — run --stage login first")

        video = page.video
        t0 = time.time()
        try:
            take(page)
        except BaseException as exc:  # a broken take must never be stitched
            log("take aborted:", exc)
            take_start = round(T_TAKE - t0, 2) if T_TAKE else 0.0
            end_t = round(time.time() - T_TAKE, 2) if T_TAKE else 0.0
            ctx.close()
            write_captions(end_t, take_start)
            raise
        take_start = round(T_TAKE - t0, 2)
        end_t = round(time.time() - T_TAKE, 2)
        log("take ends at", end_t, "| warm-up trimmed:", take_start)
        if not PITCHES_REAL and args.allow_fallback_pitches:
            log("  accepting the take with fallback pitches (Gemini quota exhausted)")
            TAKE_VALID = True
        ctx.close()
        src = Path(video.path()) if video else None
        if src and src.exists():
            dest = RAW / "take01.webm"
            if dest.exists():
                dest.unlink()
            src.replace(dest)
            log("video ->", dest)

    write_captions(end_t, take_start)


def write_captions(end_t: float, take_start: float = 0.0) -> None:
    captions = []
    for i, beat in enumerate(BEATS):
        if not beat.get("caption"):
            continue
        start = float(beat["t"])
        end = float(BEATS[i + 1]["t"]) if i + 1 < len(BEATS) else end_t - END_CARD_SECONDS
        captions.append(
            {
                "id": beat["id"],
                "start": round(start, 2),
                "end": round(end, 2),
                "text": beat["caption"],
                "anchor": beat["anchor"],
            }
        )
    doc = {
        "audio": {"file": "assets/music/let-the-sun-in.mp3", "cue": "0:14", "fade_in": 1.0, "fade_out": 3.0},
        "frame": {"width": W, "height": H, "fps": FPS},
        "duration": end_t,
        "take_start": take_start,
        "take_valid": TAKE_VALID,
        "pitches": "gemini" if PITCHES_REAL else "fallback",
        "captions": captions,
        "end_card": {"start": round(end_t - END_CARD_SECONDS, 2), "end": end_t},
    }
    CAPTIONS.parent.mkdir(parents=True, exist_ok=True)
    CAPTIONS.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"captions -> {CAPTIONS} ({len(captions)} beats, {end_t:.1f}s)")


# --------------------------------------------------------------------- pills


def wrap(text: str, font, max_width: int) -> list[str]:
    words = text.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if font.getlength(trial) <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def render_pill(text: str, out: Path) -> None:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    font = ImageFont.truetype(SEMI(), 21)
    max_text_w = 560
    lines = wrap(text, font, max_text_w)
    pad_x, pad_y = 15, 9
    line_h = 30
    text_w = int(max(font.getlength(ln) for ln in lines))
    text_h = line_h * len(lines)
    width = text_w + pad_x * 2
    height = text_h + pad_y * 2
    pad = 18
    img = Image.new("RGBA", (width + pad * 2, height + pad * 2), (0, 0, 0, 0))
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        [pad, pad + 2, pad + width, pad + height + 2], radius=10, fill=(31, 41, 55, 90)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(4))
    img.alpha_composite(shadow)

    d = ImageDraw.Draw(img)
    d.rounded_rectangle([pad, pad, pad + width, pad + height], radius=10, fill=(*SUN, 245))
    y = pad + pad_y
    for line in lines:
        d.text((pad + pad_x, y), line, font=font, fill=(*INK, 255))
        y += line_h
    img.save(out)
    return None


def require_valid_take() -> dict:
    doc = json.loads(CAPTIONS.read_text(encoding="utf-8"))
    if not doc.get("take_valid"):
        raise SystemExit("captions.json is from an invalid take — re-run --stage capture")
    return doc


def stage_pills(args) -> None:
    PILLS.mkdir(parents=True, exist_ok=True)
    for old in PILLS.glob("*.png"):
        old.unlink()
    doc = require_valid_take()
    for cap in doc["captions"]:
        out = PILLS / f"cap_{int(cap['id']):02d}.png"
        render_pill(cap["text"], out)
        log("pill", out.name, cap["text"])
    log("pills ->", PILLS)


# ----------------------------------------------------------------- composite


def end_card(path: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (W, H), INK)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy = W / 2, H / 2 - 40
    for i in range(70, 0, -1):
        t = i / 70
        rx, ry = 180 + 560 * t, 110 + 380 * t
        alpha = int(3 + 30 * (1 - t) ** 1.7)
        gd.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=(*SUN, alpha))
    glow = glow.filter(__import__("PIL.ImageFilter", fromlist=["ImageFilter"]).GaussianBlur(64))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    d = ImageDraw.Draw(img)

    f_brand = ImageFont.truetype(SEMI(), 46)
    f_tag = ImageFont.truetype(REGULAR(), 24)
    f_url = ImageFont.truetype(SEMI(), 20)
    f_foot = ImageFont.truetype(REGULAR(), 18)

    def centred(text, font, y, fill):
        w = d.textlength(text, font=font)
        d.text(((W - w) / 2, y), text, font=font, fill=fill)

    centred("Sol Searching", f_brand, H / 2 - 96, SUN)
    centred("Turn diesel spend into solar pipeline", f_tag, H / 2 - 26, (255, 255, 255))
    centred(
        "kaduna-solar-lead-ge-y3wljh2pqvkadljhlytgkg.streamlit.app",
        f_url,
        H / 2 + 34,
        TURQUOISE,
    )
    centred("07061674831 · © 2026 JJMB Analytics", f_foot, H / 2 + 82, (200, 205, 214))
    img.save(path)


def stage_composite(args) -> None:
    doc = require_valid_take()
    raw = sorted(RAW.glob("*.webm"))[-1]
    take_start = float(doc.get("take_start", 0.0))
    if take_start > 0.05:
        trimmed = TMP / "trim.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", f"{take_start:.2f}", "-i", str(raw),
             "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(trimmed)],
            check=True,
        )
        raw = trimmed
    end_start = doc["end_card"]["start"]
    dur = doc["duration"]
    card = TMP / "end_card.png"
    end_card(card)

    cmd: list[str] = ["ffmpeg", "-y", "-v", "error", "-i", str(raw)]
    filters: list[str] = []

    inputs = 1

    def add_png(path: Path, seconds: float) -> int:
        nonlocal inputs
        cmd.extend(["-loop", "1", "-t", f"{seconds:.2f}", "-i", str(path)])
        idx = inputs
        inputs += 1
        return idx

    for cap in doc["captions"]:
        start, end = float(cap["start"]), float(cap["end"])
        seconds = end - start
        idx = add_png(PILLS / f"cap_{int(cap['id']):02d}.png", seconds)
        fade = 0.22
        filters.append(
            f"[{idx}:v]format=rgba,"
            f"fade=t=in:st=0:d={fade}:alpha=1,"
            f"fade=t=out:st={max(seconds - fade, 0):.2f}:d={fade}:alpha=1,"
            f"setpts=PTS-STARTPTS+{start:.2f}/TB[pill{idx}]"
        )

    # end card last
    card_idx = add_png(card, END_CARD_SECONDS)
    filters.append(
        f"[{card_idx}:v]format=rgba,fade=t=in:st=0:d=0.9:alpha=1,"
        f"setpts=PTS-STARTPTS+{end_start:.2f}/TB[card]"
    )

    # pill geometry per anchor
    geo = {}
    from PIL import Image

    for cap in doc["captions"]:
        p = PILLS / f"cap_{int(cap['id']):02d}.png"
        with Image.open(p) as im:
            pw, ph = im.size
        pad = 18
        if cap["anchor"] == "bottom-left":
            geo[int(cap["id"])] = (34 - pad, H - 34 - ph + pad)
        else:
            geo[int(cap["id"])] = (W - 34 - pw + pad, H - 34 - ph + pad)

    filters.append("[0:v]fps=30,format=yuv420p[base]")
    chain_parts = []
    prev = "[base]"
    for n, cap in enumerate(doc["captions"], start=1):
        x, y = geo[int(cap["id"])]
        out = f"[v{n}]"
        chain_parts.append(
            f"{prev}[pill{n}]overlay=x={x}:y={y}:eof_action=pass{out}"
        )
        prev = out
    chain_parts.append(f"{prev}[card]overlay=0:0:eof_action=pass[vout]")
    chain_parts.append("[vout]format=yuv420p[vfinal]")

    filter_complex = ";".join(filters + chain_parts)
    master = TMP / "master.mp4"
    cmd.extend(
        [
            "-filter_complex",
            filter_complex,
            "-map",
            "[vfinal]",
            "-t",
            f"{dur:.2f}",
            "-r",
            str(FPS),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(master),
        ]
    )
    log("composite…")
    subprocess.run(cmd, check=True, cwd=str(ROOT))
    log("master ->", master)


# --------------------------------------------------------------------- audio


def stage_audio(args) -> None:
    doc = json.loads(CAPTIONS.read_text(encoding="utf-8"))
    dur = float(doc["duration"])
    out = TMP / "music.m4a"
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-ss", str(CUE_SECONDS), "-t", f"{dur:.2f}", "-i", str(SONG),
        "-af", f"afade=t=in:st=0:d=1,afade=t=out:st={dur - 3:.2f}:d=3,loudnorm=I=-18:TP=-1.5:LRA=11",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        str(out),
    ]
    log("audio…")
    subprocess.run(cmd, check=True, cwd=str(ROOT))
    log("music ->", out)


def stage_mux(args) -> None:
    DEMO.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-i", str(TMP / "master.mp4"), "-i", str(TMP / "music.m4a"),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", "-shortest",
        str(FINAL),
    ]
    log("mux…")
    subprocess.run(cmd, check=True, cwd=str(ROOT))
    log("final ->", FINAL)


def stage_cover(args) -> None:
    doc = json.loads(CAPTIONS.read_text(encoding="utf-8"))
    first = doc["captions"][0]
    mid = (float(first["start"]) + float(first["end"])) / 2
    out = DEMO / "01_cover.jpg"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-ss", f"{mid:.2f}", "-i", str(FINAL),
         "-frames:v", "1", "-q:v", "2", str(out)],
        check=True,
        cwd=str(ROOT),
    )
    log("cover ->", out)


# ----------------------------------------------------------------------- main


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", default="all")
    parser.add_argument("--url", default=URL)
    parser.add_argument("--wait-seconds", type=float, default=900.0)
    parser.add_argument("--profile", default=None, help="Chrome profile dir (defaults to .walkthrough_tmp/chrome-profile)")
    parser.add_argument(
        "--allow-fallback-pitches",
        action="store_true",
        help="Accept a take where Gemini returned the canned fallback pitches (quota exhausted).",
    )
    args = parser.parse_args()
    if args.profile:
        global PROFILE
        PROFILE = TMP / args.profile

    stages = {
        "login": stage_login,
        "probe": stage_probe,
        "capture": stage_capture,
        "pills": stage_pills,
        "composite": stage_composite,
        "audio": stage_audio,
        "mux": stage_mux,
        "cover": stage_cover,
    }
    order = ["login", "capture", "pills", "composite", "audio", "mux", "cover"]
    selected = order if args.stage == "all" else [args.stage]
    for name in selected:
        log(f"\n=== stage: {name} ===")
        stages[name](args)


if __name__ == "__main__":
    sys.exit(main())
