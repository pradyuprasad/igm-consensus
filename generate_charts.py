"""Generate four standalone HTML visualisations of IGM survey consensus.

Outputs to project root:
  bars.html        — diverging stacked Likert bars, centred on Uncertain
  spectrum.html    — 1D beeswarm by consensus_score
  mosaic.html      — grid of 1,119 mini stacked bars
  economists.html  — PCA similarity map of US panellists
"""
from __future__ import annotations

import csv
import html
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent
STATEMENTS_CSV = ROOT / "statements_consensus.csv"
VOTES_CSV = ROOT / "votes.csv"


# ---------- shared loaders ----------------------------------------------------

def load_statements() -> list[dict]:
    rows: list[dict] = []
    with open(STATEMENTS_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not r["consensus_score"]:
                continue
            n = int(r["n_answered_excluding_no_opinion"] or 0)
            if n == 0:
                continue
            rows.append({
                "id": r["statement_id"],
                "text": r["statement_text"],
                "panel": r["panel_type"],
                "date": r["publication_date"],
                "url": r["poll_url"],
                "n": n,
                "sd": int(r["n_strongly_disagree"] or 0) / n,
                "d":  int(r["n_disagree"] or 0) / n,
                "u":  int(r["n_uncertain"] or 0) / n,
                "a":  int(r["n_agree"] or 0) / n,
                "sa": int(r["n_strongly_agree"] or 0) / n,
                "share_a": float(r["share_agree"]),
                "share_d": float(r["share_disagree"]),
                "share_u": float(r["share_uncertain"]),
                "net": float(r["net_agreement"]),
                "cs":  float(r["consensus_score"]),
                "dir": r["consensus_direction"],
            })
    return rows


PANEL_COLOR = {"US": "#2f5fb6", "Europe": "#d97706", "Finance": "#0d9488"}

# diverging palette (5-level Likert)
C_SD = "#7c2d12"   # strongly disagree   dark red-brown
C_D  = "#dc6063"   # disagree            red
C_U  = "#94a3b8"   # uncertain           slate
C_A  = "#4ea36d"   # agree               green
C_SA = "#14532d"   # strongly agree      dark green


# ---------- 1. diverging stacked Likert bars ----------------------------------

def make_bars(stmts: list[dict]) -> str:
    rows = sorted(stmts, key=lambda r: -r["net"])
    n = len(rows)

    bar_h = 1.5
    bar_w = 620
    margin_top = 110
    margin_bottom = 70
    margin_left = 50
    margin_right = 230
    plot_h = n * bar_h
    plot_w = bar_w
    width = margin_left + plot_w + margin_right
    height = margin_top + plot_h + margin_bottom
    cx = margin_left + plot_w / 2

    # pre-pick callout examples by keyword match
    annotation_keywords = [
        ("index fund", "Diversified index funds outperform stock-picking"),
        ("gold standard", "A return to the gold standard would improve welfare"),
        ("carbon tax", "Carbon taxes are an efficient climate tool"),
        ("rent control", "Rent control improves housing affordability"),
        ("$9", "A $9 minimum wage hurts low-skill employment"),
        ("steel and aluminum", "Trump-era steel/aluminium tariffs help US welfare"),
    ]
    annotations = []
    used_ids = set()
    for kw, label in annotation_keywords:
        for i, r in enumerate(rows):
            if r["id"] in used_ids:
                continue
            if kw.lower() in r["text"].lower():
                annotations.append({"i": i, "label": label, "text": r["text"], "panel": r["panel"], "url": r["url"]})
                used_ids.add(r["id"])
                break

    # build SVG bar segments as compact path-style rects
    seg_rects: list[str] = []
    hover_rects: list[str] = []
    bar_data: list[dict] = []
    for i, r in enumerate(rows):
        y = margin_top + i * bar_h
        # centre the uncertain segment on cx
        u_w = r["u"] * bar_w
        d_w = r["d"] * bar_w
        sd_w = r["sd"] * bar_w
        a_w = r["a"] * bar_w
        sa_w = r["sa"] * bar_w
        u_x = cx - u_w / 2
        d_x = u_x - d_w
        sd_x = d_x - sd_w
        a_x = u_x + u_w
        sa_x = a_x + a_w
        for x, w, c in [
            (sd_x, sd_w, C_SD),
            (d_x, d_w, C_D),
            (u_x, u_w, C_U),
            (a_x, a_w, C_A),
            (sa_x, sa_w, C_SA),
        ]:
            if w > 0.05:
                seg_rects.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{bar_h - 0.15:.2f}" fill="{c}"/>')
        hover_rects.append(
            f'<rect class="hr" x="{margin_left}" y="{y:.2f}" width="{plot_w}" height="{bar_h:.2f}" fill="transparent" data-i="{i}"/>'
        )
        bar_data.append({
            "t": r["text"], "p": r["panel"], "d": r["date"], "u": r["url"],
            "sa": round(r["sa"]*100), "a": round(r["a"]*100), "un": round(r["u"]*100),
            "di": round(r["d"]*100), "sd": round(r["sd"]*100), "n": r["n"],
        })

    # gridlines at 25/50/75
    grid = []
    for frac, label in [(-0.5, "50% disagree"), (-0.25, "25%"), (0.25, "25%"), (0.5, "50% agree")]:
        x = cx + frac * bar_w
        grid.append(f'<line x1="{x:.1f}" y1="{margin_top - 8}" x2="{x:.1f}" y2="{margin_top + plot_h + 4}" stroke="#e5e7eb" stroke-width="1"/>')
        grid.append(f'<text x="{x:.1f}" y="{margin_top - 14}" text-anchor="middle" font-size="10" fill="#6b7280">{label}</text>')

    # centre line (uncertain midpoint)
    grid.append(f'<line x1="{cx}" y1="{margin_top - 8}" x2="{cx}" y2="{margin_top + plot_h + 4}" stroke="#374151" stroke-width="1.2"/>')
    grid.append(f'<text x="{cx}" y="{margin_top - 26}" text-anchor="middle" font-size="11" fill="#374151" font-weight="600">centred on Uncertain</text>')

    # left / right axis labels
    grid.append(f'<text x="{margin_left}" y="{margin_top - 14}" font-size="11" fill="#7c2d12" font-weight="600">← economists disagree</text>')
    grid.append(f'<text x="{margin_left + plot_w}" y="{margin_top - 14}" text-anchor="end" font-size="11" fill="#14532d" font-weight="600">economists agree →</text>')

    # annotations
    ann_svg: list[str] = []
    placed_y: list[float] = []
    for a in annotations:
        i = a["i"]
        bar_y = margin_top + i * bar_h + bar_h / 2
        ax = margin_left + plot_w + 14
        ay = bar_y
        # de-overlap labels vertically
        while any(abs(ay - py) < 26 for py in placed_y):
            ay += 4
        placed_y.append(ay)
        ann_svg.append(f'<line x1="{margin_left + plot_w}" y1="{bar_y:.2f}" x2="{ax}" y2="{ay:.2f}" stroke="#111827" stroke-width="0.7"/>')
        ann_svg.append(f'<circle cx="{margin_left + plot_w}" cy="{bar_y:.2f}" r="2.4" fill="#111827"/>')
        ann_svg.append(f'<text x="{ax + 4}" y="{ay + 3.5:.2f}" font-size="11" fill="#111827">{html.escape(a["label"])}</text>')

    title = "Where economists agree — and where they don't"
    subtitle = f"{n:,} survey questions, sorted by panel agreement. One bar per question; bar segments show how the panel voted."
    footer = "Data: Kent A. Clark Center for Global Markets (IGM Forum), 558 surveys 2011–2026. Click any bar to open the source poll."

    legend_items = [
        ("Strongly disagree", C_SD), ("Disagree", C_D), ("Uncertain", C_U), ("Agree", C_A), ("Strongly agree", C_SA),
    ]
    lx = margin_left
    ly = margin_top + plot_h + 30
    legend_svg = []
    for i, (lbl, col) in enumerate(legend_items):
        ix = lx + i * 130
        legend_svg.append(f'<rect x="{ix}" y="{ly - 9}" width="14" height="10" fill="{col}"/>')
        legend_svg.append(f'<text x="{ix + 18}" y="{ly}" font-size="11" fill="#374151">{html.escape(lbl)}</text>')

    data_json = json.dumps(bar_data, separators=(",", ":"))

    tmpl = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>__TITLE__</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body{margin:0;background:#fafaf9;color:#111827;font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif;}
  .wrap{max-width:__WIDTH__px;margin:0 auto;padding:32px 24px 60px;}
  h1{font:600 28px/1.2 ui-serif,Georgia,serif;margin:0 0 6px;}
  .sub{color:#4b5563;margin:0 0 18px;font-size:14px;}
  .foot{color:#6b7280;font-size:12px;margin-top:14px;border-top:1px solid #e5e7eb;padding-top:12px;}
  svg{display:block;width:100%;height:auto;cursor:default;}
  .hr:hover{fill:rgba(0,0,0,0.05);cursor:pointer;}
  #tip{position:fixed;pointer-events:none;background:#111827;color:#f9fafb;padding:8px 10px;border-radius:6px;font-size:12px;max-width:340px;box-shadow:0 4px 12px rgba(0,0,0,.2);opacity:0;transition:opacity .12s;z-index:10;}
  #tip .panel{display:inline-block;padding:1px 6px;border-radius:3px;font-size:10px;color:#fff;margin-right:6px;}
  #tip .bd{margin-top:6px;font-size:11px;color:#cbd5e1;}
  #tip .bd b{color:#f9fafb;}
</style></head>
<body>
<div class="wrap">
  <h1>__TITLE__</h1>
  <p class="sub">__SUBTITLE__</p>
  <svg viewBox="0 0 __WIDTH__ __HEIGHT__" preserveAspectRatio="xMidYMin meet" id="chart">
    __GRID__
    __SEGS__
    __ANN__
    __LEGEND__
    __HOVERS__
  </svg>
  <p class="foot">__FOOTER__</p>
</div>
<div id="tip"></div>
<script>
const D=__DATA__;
const tip=document.getElementById('tip');
const chart=document.getElementById('chart');
const PANEL={US:'#2f5fb6',Europe:'#d97706',Finance:'#0d9488'};
chart.addEventListener('mousemove',e=>{
  const t=e.target;
  if(!t.classList.contains('hr')){tip.style.opacity=0;return;}
  const i=+t.dataset.i;const r=D[i];
  tip.innerHTML=`<span class="panel" style="background:${PANEL[r.p]}">${r.p}</span><b>${escapeHtml(r.t)}</b><div class="bd">${r.d} · n=${r.n}<br>${r.sa}% strongly agree · ${r.a}% agree · ${r.un}% uncertain · ${r.di}% disagree · ${r.sd}% strongly disagree</div>`;
  tip.style.opacity=1;
  const x=e.clientX+14;const y=e.clientY+14;
  tip.style.left=Math.min(x,window.innerWidth-360)+'px';
  tip.style.top=Math.min(y,window.innerHeight-100)+'px';
});
chart.addEventListener('mouseleave',()=>tip.style.opacity=0);
chart.addEventListener('click',e=>{
  const t=e.target;
  if(!t.classList.contains('hr'))return;
  const i=+t.dataset.i;const r=D[i];
  if(r.u)window.open(r.u,'_blank');
});
function escapeHtml(s){return s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
</script>
</body></html>
"""
    out = (tmpl
        .replace("__TITLE__", title)
        .replace("__SUBTITLE__", subtitle)
        .replace("__FOOTER__", footer)
        .replace("__WIDTH__", str(width))
        .replace("__HEIGHT__", str(int(height)))
        .replace("__GRID__", "\n".join(grid))
        .replace("__SEGS__", "\n".join(seg_rects))
        .replace("__ANN__", "\n".join(ann_svg))
        .replace("__LEGEND__", "\n".join(legend_svg))
        .replace("__HOVERS__", "\n".join(hover_rects))
        .replace("__DATA__", data_json)
    )
    return out


# ---------- 2. spectrum / 1D beeswarm -----------------------------------------

def make_spectrum(stmts: list[dict]) -> str:
    rows = stmts
    width = 1200
    height = 720
    margin = {"t": 110, "r": 60, "b": 90, "l": 60}
    plot_w = width - margin["l"] - margin["r"]
    plot_h = height - margin["t"] - margin["b"]

    # x = consensus_score 0..1 → divided ↔ converged
    # Beeswarm: deterministic vertical jitter via a force-free packing
    pts = []
    for r in rows:
        x = margin["l"] + r["cs"] * plot_w
        pts.append({"x": x, "r": r})
    # sort by x then assign y by collision
    pts.sort(key=lambda p: p["x"])
    placed: list[tuple[float, float]] = []
    cy = margin["t"] + plot_h / 2
    radius = 2.6
    for p in pts:
        candidates = []
        for dy_step in range(0, 220):
            for sign in (1, -1) if dy_step else (1,):
                y = cy + sign * dy_step * (radius * 1.05)
                if y < margin["t"] + radius or y > margin["t"] + plot_h - radius:
                    continue
                ok = True
                for px, py in placed:
                    if (px - p["x"]) ** 2 + (py - y) ** 2 < (radius * 2 - 0.2) ** 2:
                        ok = False
                        break
                if ok:
                    candidates.append(y)
                    break
            if candidates:
                break
        y = candidates[0] if candidates else cy
        placed.append((p["x"], y))
        p["y"] = y

    DIR_COLOR = {"Agree": "#15803d", "Disagree": "#b91c1c", "Uncertain": "#94a3b8"}
    circles = []
    data: list[dict] = []
    for i, p in enumerate(pts):
        r = p["r"]
        col = DIR_COLOR.get(r["dir"], "#94a3b8")
        circles.append(f'<circle cx="{p["x"]:.2f}" cy="{p["y"]:.2f}" r="{radius}" fill="{col}" fill-opacity="0.78" stroke="#fff" stroke-width="0.4" data-i="{i}" class="dot"/>')
        data.append({
            "t": r["text"], "p": r["panel"], "d": r["date"], "u": r["url"],
            "dir": r["dir"], "cs": round(r["cs"] * 100),
            "sa": round(r["share_a"]*100), "su": round(r["share_u"]*100), "sd": round(r["share_d"]*100),
        })

    # axis
    axis = []
    for frac in [0, 0.25, 0.5, 0.75, 1.0]:
        x = margin["l"] + frac * plot_w
        axis.append(f'<line x1="{x:.1f}" y1="{margin["t"] + plot_h}" x2="{x:.1f}" y2="{margin["t"] + plot_h + 6}" stroke="#9ca3af"/>')
        axis.append(f'<text x="{x:.1f}" y="{margin["t"] + plot_h + 22}" text-anchor="middle" font-size="11" fill="#6b7280">{int(frac*100)}%</text>')
    axis.append(f'<line x1="{margin["l"]}" y1="{margin["t"] + plot_h}" x2="{margin["l"] + plot_w}" y2="{margin["t"] + plot_h}" stroke="#9ca3af"/>')
    axis.append(f'<text x="{margin["l"]}" y="{margin["t"] + plot_h + 50}" font-size="13" fill="#7c2d12" font-weight="600">PANEL DIVIDED</text>')
    axis.append(f'<text x="{margin["l"] + plot_w}" y="{margin["t"] + plot_h + 50}" text-anchor="end" font-size="13" fill="#14532d" font-weight="600">PANEL CONVERGED</text>')
    axis.append(f'<text x="{margin["l"] + plot_w/2}" y="{margin["t"] + plot_h + 70}" text-anchor="middle" font-size="11" fill="#6b7280" font-style="italic">consensus strength = |% agree − % disagree|</text>')

    # legend
    legend = []
    for i, (lbl, col) in enumerate([("converged on Agree", "#15803d"), ("converged on Disagree", "#b91c1c"), ("converged on Uncertain", "#94a3b8")]):
        lx = margin["l"] + i * 200
        ly = 78
        legend.append(f'<circle cx="{lx + 6}" cy="{ly - 4}" r="5" fill="{col}" fill-opacity="0.78"/>')
        legend.append(f'<text x="{lx + 16}" y="{ly}" font-size="12" fill="#374151">{lbl}</text>')

    title = "How much do economists agree?"
    subtitle = f"Each dot is one survey question (n = {len(rows):,}). Position = how converged the panel was; colour = which way they leaned."
    footer = "Data: Kent A. Clark Center for Global Markets, 558 surveys 2011–2026. Hover for the question; click to open the source poll."

    data_json = json.dumps(data, separators=(",", ":"))

    tmpl = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>__TITLE__</title>
<style>
  body{margin:0;background:#fafaf9;color:#111827;font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif;}
  .wrap{max-width:__WIDTH__px;margin:0 auto;padding:32px 24px 50px;}
  h1{font:600 30px/1.2 ui-serif,Georgia,serif;margin:0 0 6px;}
  .sub{color:#4b5563;margin:0 0 18px;}
  .foot{color:#6b7280;font-size:12px;margin-top:14px;border-top:1px solid #e5e7eb;padding-top:12px;}
  svg{display:block;width:100%;height:auto;}
  .dot{cursor:pointer;}
  .dot:hover{stroke:#111;stroke-width:1.4;}
  #tip{position:fixed;pointer-events:none;background:#111827;color:#f9fafb;padding:8px 10px;border-radius:6px;font-size:12px;max-width:340px;box-shadow:0 4px 12px rgba(0,0,0,.2);opacity:0;transition:opacity .12s;z-index:10;}
  #tip .bd{margin-top:6px;font-size:11px;color:#cbd5e1;}
</style></head>
<body><div class="wrap">
  <h1>__TITLE__</h1><p class="sub">__SUBTITLE__</p>
  <svg viewBox="0 0 __WIDTH__ __HEIGHT__" id="chart">
    __LEGEND__
    __AXIS__
    __DOTS__
  </svg>
  <p class="foot">__FOOTER__</p>
</div>
<div id="tip"></div>
<script>
const D=__DATA__;const tip=document.getElementById('tip');const chart=document.getElementById('chart');
chart.addEventListener('mousemove',e=>{const t=e.target;if(!t.classList.contains('dot')){tip.style.opacity=0;return;}
  const r=D[+t.dataset.i];
  tip.innerHTML=`<b>${esc(r.t)}</b><div class="bd">${r.p} · ${r.d}<br>${r.sa}% agree · ${r.su}% uncertain · ${r.sd}% disagree (consensus ${r.cs}%)</div>`;
  tip.style.opacity=1;
  const x=e.clientX+14;const y=e.clientY+14;
  tip.style.left=Math.min(x,window.innerWidth-360)+'px';tip.style.top=Math.min(y,window.innerHeight-100)+'px';
});
chart.addEventListener('mouseleave',()=>tip.style.opacity=0);
chart.addEventListener('click',e=>{const t=e.target;if(t.classList.contains('dot')){const r=D[+t.dataset.i];if(r.u)window.open(r.u,'_blank');}});
function esc(s){return s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
</script></body></html>
"""
    return (tmpl
        .replace("__TITLE__", title)
        .replace("__SUBTITLE__", subtitle)
        .replace("__FOOTER__", footer)
        .replace("__WIDTH__", str(width))
        .replace("__HEIGHT__", str(height))
        .replace("__AXIS__", "\n".join(axis))
        .replace("__DOTS__", "\n".join(circles))
        .replace("__LEGEND__", "\n".join(legend))
        .replace("__DATA__", data_json)
    )


# ---------- 3. mosaic / grid of mini stacked bars -----------------------------

def make_mosaic(stmts: list[dict]) -> str:
    rows = sorted(stmts, key=lambda r: -r["net"])
    n = len(rows)
    cols = 34
    rows_count = (n + cols - 1) // cols
    cell_w = 26
    cell_h = 36
    pad = 2
    margin = {"t": 110, "r": 30, "b": 90, "l": 30}
    plot_w = cols * cell_w
    plot_h = rows_count * cell_h
    width = margin["l"] + plot_w + margin["r"]
    height = margin["t"] + plot_h + margin["b"]

    cells: list[str] = []
    data: list[dict] = []
    for i, r in enumerate(rows):
        col = i % cols
        row = i // cols
        x0 = margin["l"] + col * cell_w + pad
        y0 = margin["t"] + row * cell_h + pad
        w = cell_w - 2 * pad
        h = cell_h - 2 * pad
        # vertical mini stacked bar inside cell
        sd_h = r["sd"] * h
        d_h = r["d"] * h
        u_h = r["u"] * h
        a_h = r["a"] * h
        sa_h = r["sa"] * h
        # stack bottom→top: SD, D, U, A, SA  (so green on top reads as "agree")
        y = y0 + h
        for hh, c in [(sd_h, C_SD), (d_h, C_D), (u_h, C_U), (a_h, C_A), (sa_h, C_SA)]:
            if hh > 0.05:
                cells.append(f'<rect x="{x0:.1f}" y="{y - hh:.2f}" width="{w:.1f}" height="{hh:.2f}" fill="{c}"/>')
                y -= hh
        cells.append(f'<rect class="hr" x="{margin["l"] + col*cell_w}" y="{margin["t"] + row*cell_h}" width="{cell_w}" height="{cell_h}" fill="transparent" data-i="{i}"/>')
        data.append({
            "t": r["text"], "p": r["panel"], "d": r["date"], "u": r["url"],
            "sa": round(r["sa"]*100), "a": round(r["a"]*100), "un": round(r["u"]*100),
            "di": round(r["d"]*100), "sd": round(r["sd"]*100), "n": r["n"], "net": round(r["net"]*100),
        })

    title = "1,119 economist surveys, sorted"
    subtitle = "Each cell is one question; bar height shows how the panel split. Reads top-left → bottom-right from strongest agreement to strongest disagreement."
    footer = "Data: Kent A. Clark Center for Global Markets, 558 surveys 2011–2026. Hover for the question; click to open the source poll."

    legend_items = [("Strongly disagree", C_SD), ("Disagree", C_D), ("Uncertain", C_U), ("Agree", C_A), ("Strongly agree", C_SA)]
    legend = []
    lx0 = margin["l"]
    ly = 78
    for i, (lbl, col) in enumerate(legend_items):
        lx = lx0 + i * 150
        legend.append(f'<rect x="{lx}" y="{ly - 9}" width="14" height="10" fill="{col}"/>')
        legend.append(f'<text x="{lx + 18}" y="{ly}" font-size="11" fill="#374151">{html.escape(lbl)}</text>')

    data_json = json.dumps(data, separators=(",", ":"))

    tmpl = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>__TITLE__</title>
<style>
  body{margin:0;background:#fafaf9;color:#111827;font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif;}
  .wrap{max-width:__WIDTH__px;margin:0 auto;padding:32px 24px 50px;}
  h1{font:600 28px/1.2 ui-serif,Georgia,serif;margin:0 0 6px;}
  .sub{color:#4b5563;margin:0 0 18px;}
  .foot{color:#6b7280;font-size:12px;margin-top:14px;border-top:1px solid #e5e7eb;padding-top:12px;}
  svg{display:block;width:100%;height:auto;}
  .hr:hover{fill:rgba(0,0,0,0.07);cursor:pointer;}
  #tip{position:fixed;pointer-events:none;background:#111827;color:#f9fafb;padding:8px 10px;border-radius:6px;font-size:12px;max-width:360px;box-shadow:0 4px 12px rgba(0,0,0,.2);opacity:0;transition:opacity .12s;z-index:10;}
  #tip .bd{margin-top:6px;font-size:11px;color:#cbd5e1;}
</style></head>
<body><div class="wrap">
  <h1>__TITLE__</h1><p class="sub">__SUBTITLE__</p>
  <svg viewBox="0 0 __WIDTH__ __HEIGHT__" id="chart">
    __LEGEND__
    __CELLS__
  </svg>
  <p class="foot">__FOOTER__</p>
</div>
<div id="tip"></div>
<script>
const D=__DATA__;const tip=document.getElementById('tip');const chart=document.getElementById('chart');
chart.addEventListener('mousemove',e=>{const t=e.target;if(!t.classList.contains('hr')){tip.style.opacity=0;return;}
  const r=D[+t.dataset.i];
  tip.innerHTML=`<b>${esc(r.t)}</b><div class="bd">${r.p} · ${r.d} · n=${r.n}<br>${r.sa}% strongly agree · ${r.a}% agree · ${r.un}% uncertain · ${r.di}% disagree · ${r.sd}% strongly disagree</div>`;
  tip.style.opacity=1;
  const x=e.clientX+14;const y=e.clientY+14;
  tip.style.left=Math.min(x,window.innerWidth-380)+'px';tip.style.top=Math.min(y,window.innerHeight-110)+'px';
});
chart.addEventListener('mouseleave',()=>tip.style.opacity=0);
chart.addEventListener('click',e=>{const t=e.target;if(t.classList.contains('hr')){const r=D[+t.dataset.i];if(r.u)window.open(r.u,'_blank');}});
function esc(s){return s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
</script></body></html>
"""
    return (tmpl
        .replace("__TITLE__", title)
        .replace("__SUBTITLE__", subtitle)
        .replace("__FOOTER__", footer)
        .replace("__WIDTH__", str(width))
        .replace("__HEIGHT__", str(height))
        .replace("__CELLS__", "\n".join(cells))
        .replace("__LEGEND__", "\n".join(legend))
        .replace("__DATA__", data_json)
    )


# ---------- 4. economist similarity map (PCA on US panel) ---------------------

VOTE_NUM = {
    "Strongly Agree": 2.0, "Agree": 1.0, "Uncertain": 0.0,
    "Disagree": -1.0, "Strongly Disagree": -2.0,
}

def make_economists() -> str:
    # build economist × statement matrix from votes.csv (US panel)
    by_econ: dict[str, dict[str, float]] = defaultdict(dict)
    affil: dict[str, str] = {}
    stmt_set: set[str] = set()
    with open(VOTES_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["panel_type"] != "US":
                continue
            v = VOTE_NUM.get(r["vote_normalized"])
            if v is None:
                continue
            name = r["economist_name"].strip()
            if not name:
                continue
            sid = r["statement_id"]
            by_econ[name][sid] = v
            stmt_set.add(sid)
            if r.get("economist_affiliation"):
                affil[name] = r["economist_affiliation"]

    # restrict to economists with at least 80 votes (active panellists)
    active = {e: votes for e, votes in by_econ.items() if len(votes) >= 80}
    statements = sorted(stmt_set)
    sid_idx = {s: i for i, s in enumerate(statements)}
    econs = sorted(active)
    M = np.zeros((len(econs), len(statements)), dtype=np.float64)
    mask = np.zeros_like(M, dtype=np.float64)
    for i, e in enumerate(econs):
        for sid, v in active[e].items():
            j = sid_idx[sid]
            M[i, j] = v
            mask[i, j] = 1.0

    # impute missing with column mean (over respondents who voted)
    col_sum = M.sum(axis=0)
    col_n = mask.sum(axis=0)
    col_mean = np.where(col_n > 0, col_sum / np.maximum(col_n, 1), 0.0)
    for j in range(M.shape[1]):
        M[:, j] = np.where(mask[:, j] == 0, col_mean[j], M[:, j])

    # centre rows
    M_centered = M - M.mean(axis=0, keepdims=True)
    # PCA via SVD
    U, S, Vt = np.linalg.svd(M_centered, full_matrices=False)
    coords = U[:, :2] * S[:2]   # (n_econ × 2)
    # variance explained
    total_var = (S ** 2).sum()
    ve = (S[:2] ** 2 / total_var * 100).round(1)

    # rescale into plot coordinates
    width = 1200
    height = 900
    margin = {"t": 110, "r": 60, "b": 70, "l": 60}
    plot_w = width - margin["l"] - margin["r"]
    plot_h = height - margin["t"] - margin["b"]
    xs = coords[:, 0]
    ys = coords[:, 1]
    x_min, x_max = xs.min(), xs.max()
    y_min, y_max = ys.min(), ys.max()
    def sx(x: float) -> float:
        return margin["l"] + (x - x_min) / (x_max - x_min) * plot_w
    def sy(y: float) -> float:
        return margin["t"] + (1 - (y - y_min) / (y_max - y_min)) * plot_h

    # vote counts per economist for size encoding
    n_votes = np.array([len(active[e]) for e in econs])
    r_min, r_max = 4.0, 9.0
    radii = r_min + (n_votes - n_votes.min()) / (n_votes.max() - n_votes.min() + 1e-9) * (r_max - r_min)

    # label only the top-N most prolific so it's readable
    n_labels = min(35, len(econs))
    label_idx = set(np.argsort(-n_votes)[:n_labels].tolist())

    dots = []
    labels = []
    data = []
    for i, e in enumerate(econs):
        x = sx(xs[i]); y = sy(ys[i])
        dots.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radii[i]:.1f}" fill="#2f5fb6" fill-opacity="0.55" stroke="#1e3a8a" stroke-width="0.6" data-i="{i}" class="dot"/>')
        if i in label_idx:
            labels.append(f'<text x="{x + radii[i] + 3:.2f}" y="{y + 3:.2f}" font-size="10.5" fill="#1f2937">{html.escape(e)}</text>')
        data.append({"n": e, "a": affil.get(e, ""), "v": int(n_votes[i])})

    # axis (subtle, abstract)
    cx = margin["l"] + plot_w / 2
    cy = margin["t"] + plot_h / 2
    axis = [
        f'<line x1="{margin["l"]}" y1="{cy:.1f}" x2="{margin["l"] + plot_w}" y2="{cy:.1f}" stroke="#e5e7eb"/>',
        f'<line x1="{cx:.1f}" y1="{margin["t"]}" x2="{cx:.1f}" y2="{margin["t"] + plot_h}" stroke="#e5e7eb"/>',
        f'<text x="{margin["l"]}" y="{margin["t"] + plot_h + 28}" font-size="11" fill="#6b7280">← PC1 ({ve[0]}% of variation in voting)</text>',
        f'<text x="{margin["l"] + plot_w}" y="{margin["t"] + plot_h + 28}" text-anchor="end" font-size="11" fill="#6b7280">PC1 →</text>',
        f'<text x="{margin["l"] - 6}" y="{margin["t"] - 14}" font-size="11" fill="#6b7280">↑ PC2 ({ve[1]}%)</text>',
    ]

    title = "How similarly do US economists vote?"
    subtitle = (f"PCA of {len(econs)} active US panellists across {len(statements):,} questions. "
                "Distance ≈ how often two economists vote differently. Axes are unlabelled — they're whatever "
                "the data's biggest disagreements happen to be.")
    footer = "Data: Kent A. Clark Center for Global Markets, US Economic Experts panel. Bubble size = number of votes cast."

    data_json = json.dumps(data, separators=(",", ":"))

    tmpl = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>__TITLE__</title>
<style>
  body{margin:0;background:#fafaf9;color:#111827;font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif;}
  .wrap{max-width:__WIDTH__px;margin:0 auto;padding:32px 24px 50px;}
  h1{font:600 28px/1.2 ui-serif,Georgia,serif;margin:0 0 6px;}
  .sub{color:#4b5563;margin:0 0 18px;max-width:80ch;}
  .foot{color:#6b7280;font-size:12px;margin-top:14px;border-top:1px solid #e5e7eb;padding-top:12px;}
  svg{display:block;width:100%;height:auto;}
  .dot{cursor:pointer;}
  .dot:hover{stroke-width:1.6;stroke:#111;}
  #tip{position:fixed;pointer-events:none;background:#111827;color:#f9fafb;padding:8px 10px;border-radius:6px;font-size:12px;max-width:300px;box-shadow:0 4px 12px rgba(0,0,0,.2);opacity:0;transition:opacity .12s;z-index:10;}
  #tip .bd{margin-top:4px;font-size:11px;color:#cbd5e1;}
</style></head>
<body><div class="wrap">
  <h1>__TITLE__</h1><p class="sub">__SUBTITLE__</p>
  <svg viewBox="0 0 __WIDTH__ __HEIGHT__" id="chart">
    __AXIS__
    __DOTS__
    __LABELS__
  </svg>
  <p class="foot">__FOOTER__</p>
</div>
<div id="tip"></div>
<script>
const D=__DATA__;const tip=document.getElementById('tip');const chart=document.getElementById('chart');
chart.addEventListener('mousemove',e=>{const t=e.target;if(!t.classList.contains('dot')){tip.style.opacity=0;return;}
  const r=D[+t.dataset.i];
  tip.innerHTML=`<b>${esc(r.n)}</b><div class="bd">${esc(r.a)}<br>${r.v} votes cast</div>`;
  tip.style.opacity=1;
  const x=e.clientX+14;const y=e.clientY+14;
  tip.style.left=Math.min(x,window.innerWidth-320)+'px';tip.style.top=Math.min(y,window.innerHeight-100)+'px';
});
chart.addEventListener('mouseleave',()=>tip.style.opacity=0);
function esc(s){return (s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
</script></body></html>
"""
    return (tmpl
        .replace("__TITLE__", title)
        .replace("__SUBTITLE__", subtitle)
        .replace("__FOOTER__", footer)
        .replace("__WIDTH__", str(width))
        .replace("__HEIGHT__", str(height))
        .replace("__AXIS__", "\n".join(axis))
        .replace("__DOTS__", "\n".join(dots))
        .replace("__LABELS__", "\n".join(labels))
        .replace("__DATA__", data_json)
    )


# ---------- main --------------------------------------------------------------

def main() -> None:
    stmts = load_statements()
    print(f"Loaded {len(stmts)} statements")

    (ROOT / "bars.html").write_text(make_bars(stmts), encoding="utf-8")
    print("wrote bars.html")
    (ROOT / "spectrum.html").write_text(make_spectrum(stmts), encoding="utf-8")
    print("wrote spectrum.html")
    (ROOT / "mosaic.html").write_text(make_mosaic(stmts), encoding="utf-8")
    print("wrote mosaic.html")
    (ROOT / "economists.html").write_text(make_economists(), encoding="utf-8")
    print("wrote economists.html")


if __name__ == "__main__":
    main()
