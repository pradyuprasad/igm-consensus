"""Compact, screenshot-shaped variants aimed at the Twitter share path.

Outputs:
  horizon.html   — landscape diverging columns (rotated bars.html, 1200×640)
  curve.html     — distribution-of-consensus curve with annotated examples (1200×720)
  highlight.html — top 25 agreed + top 25 disagreed, fully labelled (1200×980)
"""
from __future__ import annotations

import csv
import html
import json
import math
from pathlib import Path

ROOT = Path(__file__).parent
STATEMENTS_CSV = ROOT / "statements_consensus.csv"

C_SD = "#7c2d12"
C_D  = "#dc6063"
C_U  = "#cbd5e1"
C_A  = "#4ea36d"
C_SA = "#14532d"


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


# ---------- 1. horizon.html : landscape diverging columns ---------------------

def make_horizon(stmts: list[dict]) -> str:
    rows = sorted(stmts, key=lambda r: r["net"])  # left = most disagree, right = most agree
    n = len(rows)
    width = 1200
    height = 700
    margin = {"t": 70, "r": 60, "b": 130, "l": 80}
    plot_w = width - margin["l"] - margin["r"]
    plot_h = height - margin["t"] - margin["b"]
    col_w = plot_w / n
    cy = margin["t"] + plot_h / 2
    half = plot_h / 2

    cols: list[str] = []
    data: list[dict] = []
    for i, r in enumerate(rows):
        x = margin["l"] + i * col_w
        u_h = r["u"] * half  # uncertain split top + bottom of zero
        d_h = r["d"] * half * 2
        sd_h = r["sd"] * half * 2
        a_h = r["a"] * half * 2
        sa_h = r["sa"] * half * 2
        # central uncertain band centred on cy
        cols.append(f'<rect x="{x:.2f}" y="{cy - u_h/2:.2f}" width="{col_w:.3f}" height="{u_h:.2f}" fill="{C_U}"/>')
        # downward (disagree)
        y = cy + u_h / 2
        for hh, c in [(d_h, C_D), (sd_h, C_SD)]:
            if hh > 0.05:
                cols.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{col_w:.3f}" height="{hh:.2f}" fill="{c}"/>')
                y += hh
        # upward (agree)
        y = cy - u_h / 2
        for hh, c in [(a_h, C_A), (sa_h, C_SA)]:
            if hh > 0.05:
                cols.append(f'<rect x="{x:.2f}" y="{y - hh:.2f}" width="{col_w:.3f}" height="{hh:.2f}" fill="{c}"/>')
                y -= hh
        data.append({
            "t": r["text"], "p": r["panel"], "d": r["date"], "u": r["url"],
            "sa": round(r["sa"]*100), "a": round(r["a"]*100), "un": round(r["u"]*100),
            "di": round(r["d"]*100), "sd": round(r["sd"]*100),
        })

    # transparent hover columns wider than 1px
    hover_w = max(col_w, 4)
    hovers = []
    for i in range(n):
        x = margin["l"] + i * col_w - (hover_w - col_w) / 2
        hovers.append(f'<rect class="hr" x="{x:.2f}" y="{margin["t"]}" width="{hover_w:.2f}" height="{plot_h:.2f}" fill="transparent" data-i="{i}"/>')

    # zero line
    grid = [
        f'<line x1="{margin["l"]}" y1="{cy}" x2="{margin["l"] + plot_w}" y2="{cy}" stroke="#374151" stroke-width="0.8" stroke-dasharray="4 4"/>',
    ]
    # axis labels (right-side, out of the way)
    grid.append(f'<text x="{margin["l"] + plot_w + 4}" y="{margin["t"] + 6}" font-size="10" fill="#14532d" font-weight="600">100%</text>')
    grid.append(f'<text x="{margin["l"] + plot_w + 4}" y="{margin["t"] + plot_h + 2}" font-size="10" fill="#7c2d12" font-weight="600">100%</text>')
    grid.append(f'<text x="{margin["l"] + plot_w + 4}" y="{cy + 4}" font-size="10" fill="#475569">0%</text>')

    # x-axis labels
    grid.append(f'<text x="{margin["l"]}" y="{margin["t"] + plot_h + 22}" font-size="12" fill="#7c2d12" font-weight="600">← MOST CONTESTED</text>')
    grid.append(f'<text x="{margin["l"] + plot_w}" y="{margin["t"] + plot_h + 22}" text-anchor="end" font-size="12" fill="#14532d" font-weight="600">MOST AGREED →</text>')
    grid.append(f'<text x="{margin["l"] + plot_w/2}" y="{margin["t"] + plot_h + 22}" text-anchor="middle" font-size="11" fill="#6b7280" font-style="italic">{n:,} questions, sorted</text>')

    # annotations
    annotations = []
    keywords = [
        ("index fund", "Index funds beat stock-picking"),
        ("gold standard", "Gold standard would help"),
        ("carbon tax", "Carbon taxes are efficient"),
        ("rent control", "Rent control hurts supply"),
        ("steel and aluminum", "Trump steel/aluminium tariffs help US"),
        ("$15", "$15 federal minimum wage helps"),
        ("Phillips Curve", "Phillips Curve still useful"),
    ]
    used = set()
    for kw, label in keywords:
        for i, r in enumerate(rows):
            if r["id"] in used:
                continue
            if kw.lower() in r["text"].lower():
                annotations.append({"i": i, "label": label, "net": r["net"]})
                used.add(r["id"])
                break

    ann_svg = []
    # sort annotations by column position so we can spread labels across the bottom
    annotations.sort(key=lambda a: a["i"])
    label_row_y = [margin["t"] + plot_h + 50, margin["t"] + plot_h + 70]
    used_xy: list[tuple[float, float, str]] = []
    for idx, a in enumerate(annotations):
        bx = margin["l"] + a["i"] * col_w
        # alternate rows
        ay = label_row_y[idx % 2]
        # clamp label x to SVG bounds (label is ~150px wide)
        label_w_approx = max(60, min(180, len(a["label"]) * 6.5))
        tx = max(margin["l"] - 30 + label_w_approx / 2, min(margin["l"] + plot_w + 30 - label_w_approx / 2, bx))
        # text anchor middle but offset if needed to avoid edges
        if tx < margin["l"] + 70:
            anchor = "start"; tx_text = max(4, bx - 10)
        elif tx > margin["l"] + plot_w - 70:
            anchor = "end"; tx_text = min(width - 6, bx + 10)
        else:
            anchor = "middle"; tx_text = tx
        ann_svg.append(f'<line x1="{bx:.1f}" y1="{margin["t"] + plot_h:.1f}" x2="{bx:.1f}" y2="{ay - 8:.1f}" stroke="#111" stroke-width="0.6" stroke-dasharray="2 2"/>')
        ann_svg.append(f'<circle cx="{bx:.1f}" cy="{margin["t"] + plot_h:.1f}" r="2.6" fill="#111"/>')
        ann_svg.append(f'<text x="{tx_text:.1f}" y="{ay:.1f}" text-anchor="{anchor}" font-size="11" fill="#111" font-weight="500">{html.escape(a["label"])}</text>')

    legend = []
    legend_items = [("strongly agree", C_SA), ("agree", C_A), ("uncertain", C_U), ("disagree", C_D), ("strongly disagree", C_SD)]
    # bottom-centred, well below the chart and annotations
    legend_widths = [110, 70, 90, 80, 130]
    total = sum(legend_widths)
    cursor = margin["l"] + (plot_w - total) / 2
    ly = height - 18
    for (lbl, col), w in zip(legend_items, legend_widths):
        legend.append(f'<rect x="{cursor:.1f}" y="{ly - 9}" width="13" height="10" fill="{col}"/>')
        legend.append(f'<text x="{cursor + 17:.1f}" y="{ly}" font-size="11" fill="#374151">{html.escape(lbl)}</text>')
        cursor += w

    title = "Where economists agree — and where they don't"
    subtitle = f"Each thin column is one of {n:,} survey questions. Bars rise above the line for agreement, fall below for disagreement, sorted left-to-right by net agreement."

    data_json = json.dumps(data, separators=(",", ":"))
    tmpl = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>__TITLE__</title>
<style>
  body{margin:0;background:#fafaf9;color:#111827;font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif;}
  .wrap{max-width:__WIDTH__px;margin:0 auto;padding:28px 24px 32px;}
  h1{font:600 30px/1.15 ui-serif,Georgia,serif;margin:0 0 6px;}
  .sub{color:#4b5563;margin:0 0 14px;max-width:80ch;}
  .foot{color:#6b7280;font-size:12px;margin-top:8px;border-top:1px solid #e5e7eb;padding-top:10px;}
  svg{display:block;width:100%;height:auto;}
  .hr:hover{fill:rgba(0,0,0,0.07);cursor:pointer;}
  #tip{position:fixed;pointer-events:none;background:#111827;color:#f9fafb;padding:8px 10px;border-radius:6px;font-size:12px;max-width:340px;box-shadow:0 4px 12px rgba(0,0,0,.2);opacity:0;transition:opacity .12s;z-index:10;}
  #tip .bd{margin-top:6px;font-size:11px;color:#cbd5e1;}
</style></head><body><div class="wrap">
  <h1>__TITLE__</h1><p class="sub">__SUBTITLE__</p>
  <svg viewBox="0 0 __WIDTH__ __HEIGHT__" id="chart">
    __LEGEND__
    __GRID__
    __COLS__
    __ANN__
    __HOVERS__
  </svg>
  <p class="foot">Data: Kent A. Clark Center for Global Markets (IGM Forum), 558 surveys 2011–2026. Hover a column for the question; click to open the source poll.</p>
</div><div id="tip"></div>
<script>
const D=__DATA__;const tip=document.getElementById('tip');const chart=document.getElementById('chart');
const PANEL={US:'#2f5fb6',Europe:'#d97706',Finance:'#0d9488'};
chart.addEventListener('mousemove',e=>{const t=e.target;if(!t.classList.contains('hr')){tip.style.opacity=0;return;}
  const r=D[+t.dataset.i];
  tip.innerHTML=`<b>${esc(r.t)}</b><div class="bd">${r.p} · ${r.d}<br>${r.sa}% strongly agree · ${r.a}% agree · ${r.un}% uncertain · ${r.di}% disagree · ${r.sd}% strongly disagree</div>`;
  tip.style.opacity=1;const x=e.clientX+14;const y=e.clientY+14;
  tip.style.left=Math.min(x,window.innerWidth-360)+'px';tip.style.top=Math.min(y,window.innerHeight-110)+'px';
});
chart.addEventListener('mouseleave',()=>tip.style.opacity=0);
chart.addEventListener('click',e=>{const t=e.target;if(t.classList.contains('hr')){const r=D[+t.dataset.i];if(r.u)window.open(r.u,'_blank');}});
function esc(s){return s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
</script></body></html>
"""
    return (tmpl
        .replace("__TITLE__", title)
        .replace("__SUBTITLE__", subtitle)
        .replace("__WIDTH__", str(width))
        .replace("__HEIGHT__", str(height))
        .replace("__GRID__", "\n".join(grid))
        .replace("__COLS__", "\n".join(cols))
        .replace("__ANN__", "\n".join(ann_svg))
        .replace("__LEGEND__", "\n".join(legend))
        .replace("__HOVERS__", "\n".join(hovers))
        .replace("__DATA__", data_json))


# ---------- 2. curve.html : distribution + annotated examples -----------------

def make_curve(stmts: list[dict]) -> str:
    """Histogram of net_agreement with annotated landmark questions."""
    rows = stmts
    width = 1200
    height = 720
    margin = {"t": 110, "r": 60, "b": 110, "l": 60}
    plot_w = width - margin["l"] - margin["r"]
    plot_h = height - margin["t"] - margin["b"]

    # bin net_agreement into 60 bins from -1 to 1
    n_bins = 60
    edges = [(-1 + 2 * i / n_bins) for i in range(n_bins + 1)]
    bin_counts = [0] * n_bins
    bin_rows: list[list[dict]] = [[] for _ in range(n_bins)]
    for r in rows:
        b = min(int((r["net"] + 1) / 2 * n_bins), n_bins - 1)
        bin_counts[b] += 1
        bin_rows[b].append(r)
    max_count = max(bin_counts)

    def x(net: float) -> float:
        return margin["l"] + (net + 1) / 2 * plot_w
    def y_count(c: float) -> float:
        return margin["t"] + plot_h - (c / max_count) * plot_h

    # bars
    bw = plot_w / n_bins
    bars = []
    for i, c in enumerate(bin_counts):
        if c == 0:
            continue
        x0 = margin["l"] + i * bw
        h = (c / max_count) * plot_h
        # colour by sign of bin midpoint
        mid = -1 + (i + 0.5) * 2 / n_bins
        if mid > 0.15:
            col = "#4ea36d"
        elif mid < -0.15:
            col = "#dc6063"
        else:
            col = "#94a3b8"
        bars.append(f'<rect x="{x0 + 1:.2f}" y="{y_count(c):.2f}" width="{bw - 2:.2f}" height="{h:.2f}" fill="{col}" fill-opacity="0.85"/>')

    # axis
    axis = []
    for tick in [-1, -0.75, -0.5, -0.25, 0, 0.25, 0.5, 0.75, 1]:
        xt = x(tick)
        axis.append(f'<line x1="{xt:.1f}" y1="{margin["t"] + plot_h}" x2="{xt:.1f}" y2="{margin["t"] + plot_h + 5}" stroke="#9ca3af"/>')
        label = "0" if tick == 0 else f"{int(tick * 100):+d}%"
        axis.append(f'<text x="{xt:.1f}" y="{margin["t"] + plot_h + 18}" text-anchor="middle" font-size="11" fill="#6b7280">{label}</text>')
    axis.append(f'<line x1="{margin["l"]}" y1="{margin["t"] + plot_h}" x2="{margin["l"] + plot_w}" y2="{margin["t"] + plot_h}" stroke="#9ca3af"/>')
    axis.append(f'<text x="{margin["l"]}" y="{margin["t"] + plot_h + 60}" font-size="13" fill="#7c2d12" font-weight="600">PANEL DISAGREES</text>')
    axis.append(f'<text x="{margin["l"] + plot_w}" y="{margin["t"] + plot_h + 60}" text-anchor="end" font-size="13" fill="#14532d" font-weight="600">PANEL AGREES</text>')
    axis.append(f'<text x="{margin["l"] + plot_w/2}" y="{margin["t"] + plot_h + 80}" text-anchor="middle" font-size="11" fill="#6b7280" font-style="italic">net agreement = % agree − % disagree</text>')

    # annotations: pick interesting examples by keyword
    keywords = [
        ("index fund", "Diversified index funds beat stock-picking", "right"),
        ("Phillips Curve", "Phillips Curve still useful", "neutral"),
        ("gold standard", "Return to the gold standard", "left"),
        ("rent control", "Rent control hurts supply", "right"),
        ("$15", "$15 federal minimum wage", "neutral"),
        ("steel and aluminum", "Steel/aluminium tariffs help US", "left"),
        ("carbon tax", "Carbon taxes are efficient", "right"),
        ("immigration", "More immigration grows GDP", "right"),
        ("debt", "Federal debt is a serious problem", "neutral"),
    ]
    annotations = []
    used = set()
    for kw, label, _ in keywords:
        for r in rows:
            if r["id"] in used:
                continue
            if kw.lower() in r["text"].lower():
                annotations.append({"r": r, "label": label})
                used.add(r["id"])
                break

    # plot dots for each annotated point (on top of the histogram)
    ann_svg = []
    placed: list[tuple[float, float]] = []
    for a in annotations:
        r = a["r"]
        xp = x(r["net"])
        b = min(int((r["net"] + 1) / 2 * n_bins), n_bins - 1)
        bin_top_y = y_count(bin_counts[b])
        ann_svg.append(f'<circle cx="{xp:.2f}" cy="{bin_top_y - 5:.2f}" r="3.6" fill="#111" stroke="#fff" stroke-width="1.2"/>')
        label_y = bin_top_y - 18
        while any(abs(xp - px) < 150 and abs(label_y - py) < 16 for px, py in placed):
            label_y -= 14
        placed.append((xp, label_y))
        # left edge → start, right edge → end, otherwise middle
        if xp < margin["l"] + 80:
            anchor = "start"; tx = xp + 6
        elif xp > margin["l"] + plot_w - 80:
            anchor = "end"; tx = xp - 6
        else:
            anchor = "middle"; tx = xp
        ann_svg.append(f'<line x1="{xp:.1f}" y1="{bin_top_y - 8:.1f}" x2="{xp:.1f}" y2="{label_y + 4:.1f}" stroke="#111" stroke-width="0.5"/>')
        ann_svg.append(f'<text x="{tx:.1f}" y="{label_y:.1f}" text-anchor="{anchor}" font-size="11" fill="#111">{html.escape(a["label"])}</text>')

    # callouts: counts above zero / below zero / near zero
    n_pos = sum(1 for r in rows if r["net"] > 0.5)
    n_neg = sum(1 for r in rows if r["net"] < -0.5)
    n_mid = sum(1 for r in rows if -0.2 <= r["net"] <= 0.2)
    callouts = [
        f'<text x="{x(0.85):.1f}" y="{margin["t"] + plot_h - 10:.1f}" text-anchor="middle" font-size="13" fill="#14532d" font-weight="700">{n_pos} questions</text>',
        f'<text x="{x(0.85):.1f}" y="{margin["t"] + plot_h + 4:.1f}" text-anchor="middle" font-size="11" fill="#14532d">strong agreement</text>',
        f'<text x="{x(-0.85):.1f}" y="{margin["t"] + plot_h - 10:.1f}" text-anchor="middle" font-size="13" fill="#7c2d12" font-weight="700">{n_neg} questions</text>',
        f'<text x="{x(-0.85):.1f}" y="{margin["t"] + plot_h + 4:.1f}" text-anchor="middle" font-size="11" fill="#7c2d12">strong disagreement</text>',
    ]

    title = "What economists actually disagree about"
    subtitle = (f"Distribution of {len(rows):,} IGM survey questions by net panel agreement (% agree − % disagree). "
                "Most settled questions sit at the edges; the contested ones cluster near zero.")

    tmpl = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>__TITLE__</title>
<style>
  body{margin:0;background:#fafaf9;color:#111827;font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif;}
  .wrap{max-width:__WIDTH__px;margin:0 auto;padding:28px 24px 28px;}
  h1{font:600 32px/1.15 ui-serif,Georgia,serif;margin:0 0 6px;}
  .sub{color:#4b5563;margin:0 0 14px;max-width:80ch;}
  .foot{color:#6b7280;font-size:12px;margin-top:6px;border-top:1px solid #e5e7eb;padding-top:10px;}
  svg{display:block;width:100%;height:auto;}
</style></head><body><div class="wrap">
  <h1>__TITLE__</h1><p class="sub">__SUBTITLE__</p>
  <svg viewBox="0 0 __WIDTH__ __HEIGHT__">
    __BARS__
    __AXIS__
    __CALLOUTS__
    __ANN__
  </svg>
  <p class="foot">Data: Kent A. Clark Center for Global Markets (IGM Forum), 558 surveys 2011–2026.</p>
</div></body></html>
"""
    return (tmpl
        .replace("__TITLE__", title)
        .replace("__SUBTITLE__", subtitle)
        .replace("__WIDTH__", str(width))
        .replace("__HEIGHT__", str(height))
        .replace("__BARS__", "\n".join(bars))
        .replace("__AXIS__", "\n".join(axis))
        .replace("__CALLOUTS__", "\n".join(callouts))
        .replace("__ANN__", "\n".join(ann_svg)))


# ---------- 3. highlight.html : top 25 + bottom 25 fully labelled -------------

def make_highlight(stmts: list[dict]) -> str:
    asc = sorted(stmts, key=lambda r: r["net"])
    bot = asc[:25]                   # most disagreed
    top = list(reversed(asc[-25:]))  # most agreed

    width = 1200
    row_h = 18
    n_rows = 25
    margin = {"t": 130, "b": 90}
    block_h = n_rows * row_h
    height = margin["t"] + 2 * block_h + 100 + margin["b"]

    text_w = 520
    bar_max = 360
    label_x = 30
    bar_x0 = label_x + text_w + 20

    def render_block(rows_, y0: float, color_for_text: str, header: str) -> list[str]:
        out = [f'<text x="{label_x}" y="{y0 - 14}" font-size="14" fill="{color_for_text}" font-weight="700">{header}</text>']
        for i, r in enumerate(rows_):
            y = y0 + i * row_h
            txt = (r["text"][:90] + "…") if len(r["text"]) > 90 else r["text"]
            out.append(f'<text x="{label_x}" y="{y + 12}" font-size="12" fill="#111">{html.escape(txt)}</text>')
            # bar
            agree_w = r["share_a"] * bar_max
            dis_w = r["share_d"] * bar_max
            unc_w = r["share_u"] * bar_max
            x = bar_x0
            for ww, c in [(dis_w, C_D), (unc_w, C_U), (agree_w, C_A)]:
                if ww > 0.5:
                    out.append(f'<rect x="{x:.2f}" y="{y + 4}" width="{ww:.2f}" height="{row_h - 6}" fill="{c}"/>')
                    x += ww
            # numeric
            pct = round(r["share_a"] * 100) if r["net"] >= 0 else round(r["share_d"] * 100)
            out.append(f'<text x="{bar_x0 + bar_max + 10}" y="{y + 12}" font-size="11" fill="#374151">{pct}%</text>')
            # panel pill
            pcol = {"US": "#2f5fb6", "Europe": "#d97706", "Finance": "#0d9488"}[r["panel"]]
            out.append(f'<text x="{bar_x0 + bar_max + 50}" y="{y + 12}" font-size="10" fill="{pcol}">{r["panel"]} · {r["date"][:4]}</text>')
        return out

    top_y = margin["t"]
    bot_y = top_y + block_h + 80

    blocks = (
        render_block(top, top_y, "#14532d", "MOST AGREED — top 25 questions where the panel converged on AGREE")
        + render_block(bot, bot_y, "#7c2d12", "MOST DISAGREED — top 25 questions where the panel converged on DISAGREE")
    )

    # axis for each bar block: 0–100% scale
    axes = []
    for ay in [top_y - 8, bot_y - 8]:
        for frac in [0, 0.25, 0.5, 0.75, 1]:
            ax = bar_x0 + frac * bar_max
            axes.append(f'<line x1="{ax:.1f}" y1="{ay}" x2="{ax:.1f}" y2="{ay + 4}" stroke="#9ca3af"/>')
            axes.append(f'<text x="{ax:.1f}" y="{ay - 4}" text-anchor="middle" font-size="9" fill="#9ca3af">{int(frac*100)}%</text>')

    legend = []
    legend.append(f'<rect x="{bar_x0}" y="50" width="14" height="10" fill="{C_D}"/>')
    legend.append(f'<text x="{bar_x0 + 18}" y="59" font-size="11" fill="#374151">disagree</text>')
    legend.append(f'<rect x="{bar_x0 + 100}" y="50" width="14" height="10" fill="{C_U}"/>')
    legend.append(f'<text x="{bar_x0 + 118}" y="59" font-size="11" fill="#374151">uncertain</text>')
    legend.append(f'<rect x="{bar_x0 + 200}" y="50" width="14" height="10" fill="{C_A}"/>')
    legend.append(f'<text x="{bar_x0 + 218}" y="59" font-size="11" fill="#374151">agree</text>')

    title = "What economists strongly agree (and disagree) about"
    subtitle = "The 25 questions with the strongest consensus in each direction, out of 1,119 IGM surveys."

    tmpl = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>__TITLE__</title>
<style>
  body{margin:0;background:#fafaf9;color:#111827;font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif;}
  .wrap{max-width:__WIDTH__px;margin:0 auto;padding:28px 24px 28px;}
  h1{font:600 30px/1.15 ui-serif,Georgia,serif;margin:0 0 6px;}
  .sub{color:#4b5563;margin:0 0 14px;}
  .foot{color:#6b7280;font-size:12px;margin-top:6px;border-top:1px solid #e5e7eb;padding-top:10px;}
  svg{display:block;width:100%;height:auto;}
</style></head><body><div class="wrap">
  <h1>__TITLE__</h1><p class="sub">__SUBTITLE__</p>
  <svg viewBox="0 0 __WIDTH__ __HEIGHT__">
    __LEGEND__
    __AXES__
    __BLOCKS__
  </svg>
  <p class="foot">Data: Kent A. Clark Center for Global Markets (IGM Forum), 558 surveys 2011–2026.</p>
</div></body></html>
"""
    return (tmpl
        .replace("__TITLE__", title)
        .replace("__SUBTITLE__", subtitle)
        .replace("__WIDTH__", str(width))
        .replace("__HEIGHT__", str(height))
        .replace("__BLOCKS__", "\n".join(blocks))
        .replace("__AXES__", "\n".join(axes))
        .replace("__LEGEND__", "\n".join(legend)))


# ---------- main --------------------------------------------------------------

def main() -> None:
    stmts = sorted(_load(), key=lambda r: r["net"]) if False else _load()
    print(f"Loaded {len(stmts)} statements")
    (ROOT / "horizon.html").write_text(make_horizon(stmts), encoding="utf-8")
    print("wrote horizon.html")
    (ROOT / "curve.html").write_text(make_curve(stmts), encoding="utf-8")
    print("wrote curve.html")
    (ROOT / "highlight.html").write_text(make_highlight(stmts), encoding="utf-8")
    print("wrote highlight.html")


def _load() -> list[dict]:
    return load_statements()


if __name__ == "__main__":
    main()
