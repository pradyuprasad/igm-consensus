"""Variance-focused variants: where economists actually disagree with each other.

Outputs:
  horizon_polar.html — diverging columns sorted by polarization (panel converged → panel split)
  scatter.html       — 2D scatter: net agreement × polarization (1,119 dots)
  divided.html       — top 30 most-polarized questions, fully labelled
"""
from __future__ import annotations

import csv
import html
import json
from pathlib import Path

ROOT = Path(__file__).parent
STATEMENTS_CSV = ROOT / "statements_consensus.csv"

C_SD = "#7c2d12"
C_D  = "#dc6063"
C_U  = "#cbd5e1"
C_A  = "#4ea36d"
C_SA = "#14532d"
PANEL_COLOR = {"US": "#2f5fb6", "Europe": "#d97706", "Finance": "#0d9488"}


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
                "pol": float(r["polarization_score"]),
                "cs":  float(r["consensus_score"]),
                "dir": r["consensus_direction"],
            })
    return rows


def find_by_kw(rows: list[dict], kw: str, used: set) -> dict | None:
    for r in rows:
        if r["id"] in used:
            continue
        if kw.lower() in r["text"].lower():
            used.add(r["id"])
            return r
    return None


# ---------- A. horizon sorted by polarization --------------------------------

def make_horizon_polar(stmts: list[dict]) -> str:
    rows = sorted(stmts, key=lambda r: r["pol"])  # left = converged, right = split
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
        u_h = r["u"] * half
        d_h = r["d"] * half * 2
        sd_h = r["sd"] * half * 2
        a_h = r["a"] * half * 2
        sa_h = r["sa"] * half * 2
        cols.append(f'<rect x="{x:.2f}" y="{cy - u_h/2:.2f}" width="{col_w:.3f}" height="{u_h:.2f}" fill="{C_U}"/>')
        y = cy + u_h / 2
        for hh, c in [(d_h, C_D), (sd_h, C_SD)]:
            if hh > 0.05:
                cols.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{col_w:.3f}" height="{hh:.2f}" fill="{c}"/>')
                y += hh
        y = cy - u_h / 2
        for hh, c in [(a_h, C_A), (sa_h, C_SA)]:
            if hh > 0.05:
                cols.append(f'<rect x="{x:.2f}" y="{y - hh:.2f}" width="{col_w:.3f}" height="{hh:.2f}" fill="{c}"/>')
                y -= hh
        data.append({
            "t": r["text"], "p": r["panel"], "d": r["date"], "u": r["url"],
            "sa": round(r["sa"]*100), "a": round(r["a"]*100), "un": round(r["u"]*100),
            "di": round(r["d"]*100), "sd": round(r["sd"]*100),
            "pol": round(r["pol"]*100, 1),
        })

    hover_w = max(col_w, 4)
    hovers = []
    for i in range(n):
        x = margin["l"] + i * col_w - (hover_w - col_w) / 2
        hovers.append(f'<rect class="hr" x="{x:.2f}" y="{margin["t"]}" width="{hover_w:.2f}" height="{plot_h:.2f}" fill="transparent" data-i="{i}"/>')

    grid = [
        f'<line x1="{margin["l"]}" y1="{cy}" x2="{margin["l"] + plot_w}" y2="{cy}" stroke="#374151" stroke-width="0.8" stroke-dasharray="4 4"/>',
        f'<text x="{margin["l"] + plot_w + 4}" y="{margin["t"] + 6}" font-size="10" fill="#14532d" font-weight="600">100%</text>',
        f'<text x="{margin["l"] + plot_w + 4}" y="{margin["t"] + plot_h + 2}" font-size="10" fill="#7c2d12" font-weight="600">100%</text>',
        f'<text x="{margin["l"] + plot_w + 4}" y="{cy + 4}" font-size="10" fill="#475569">0%</text>',
        f'<text x="{margin["l"]}" y="{margin["t"] + plot_h + 22}" font-size="12" fill="#14532d" font-weight="600">← PANEL CONVERGED</text>',
        f'<text x="{margin["l"] + plot_w}" y="{margin["t"] + plot_h + 22}" text-anchor="end" font-size="12" fill="#7c2d12" font-weight="600">PANEL SPLIT →</text>',
        f'<text x="{margin["l"] + plot_w/2}" y="{margin["t"] + plot_h + 22}" text-anchor="middle" font-size="11" fill="#6b7280" font-style="italic">{n:,} questions, sorted by how divided the panel was</text>',
    ]

    used = set()
    keywords = [
        ("index fund", "Index funds beat stock-picking"),
        ("gold standard", "Gold standard would help"),
        ("rent control", "Rent control hurts supply"),
        ("$15", "$15 federal minimum wage"),
        ("steel and aluminum", "Trump steel/aluminium tariffs"),
        ("Bitcoin", "Bitcoin will replace fiat"),
        ("immigration", "More immigration grows GDP"),
    ]
    annotations = []
    for kw, label in keywords:
        r = find_by_kw(rows, kw, used)
        if r:
            for i, rr in enumerate(rows):
                if rr["id"] == r["id"]:
                    annotations.append({"i": i, "label": label, "pol": r["pol"]})
                    break

    annotations.sort(key=lambda a: a["i"])
    label_row_y = [margin["t"] + plot_h + 50, margin["t"] + plot_h + 70]
    ann_svg = []
    for idx, a in enumerate(annotations):
        bx = margin["l"] + a["i"] * col_w
        ay = label_row_y[idx % 2]
        if bx < margin["l"] + 70:
            anchor = "start"; tx_text = max(4, bx - 10)
        elif bx > margin["l"] + plot_w - 70:
            anchor = "end"; tx_text = min(width - 6, bx + 10)
        else:
            anchor = "middle"; tx_text = bx
        ann_svg.append(f'<line x1="{bx:.1f}" y1="{margin["t"] + plot_h:.1f}" x2="{bx:.1f}" y2="{ay - 8:.1f}" stroke="#111" stroke-width="0.6" stroke-dasharray="2 2"/>')
        ann_svg.append(f'<circle cx="{bx:.1f}" cy="{margin["t"] + plot_h:.1f}" r="2.6" fill="#111"/>')
        ann_svg.append(f'<text x="{tx_text:.1f}" y="{ay:.1f}" text-anchor="{anchor}" font-size="11" fill="#111" font-weight="500">{html.escape(a["label"])}</text>')

    legend = []
    legend_items = [("strongly agree", C_SA), ("agree", C_A), ("uncertain", C_U), ("disagree", C_D), ("strongly disagree", C_SD)]
    legend_widths = [110, 70, 90, 80, 130]
    total = sum(legend_widths)
    cursor = margin["l"] + (plot_w - total) / 2
    ly = height - 18
    for (lbl, col), w in zip(legend_items, legend_widths):
        legend.append(f'<rect x="{cursor:.1f}" y="{ly - 9}" width="13" height="10" fill="{col}"/>')
        legend.append(f'<text x="{cursor + 17:.1f}" y="{ly}" font-size="11" fill="#374151">{html.escape(lbl)}</text>')
        cursor += w

    title = "Where economists are actually divided"
    subtitle = (f"Each thin column is one of {n:,} survey questions. Sorted by polarization "
                "— from settled questions on the left (everyone agreed, disagreed, or was uncertain) to genuinely contested ones on the right (~50/50 split).")

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
    __GRID__
    __COLS__
    __ANN__
    __LEGEND__
    __HOVERS__
  </svg>
  <p class="foot">Data: Kent A. Clark Center for Global Markets (IGM Forum), 558 surveys 2011–2026. Polarization = min(% agree, % disagree); higher = more split panel. Hover for the question; click opens the source poll.</p>
</div><div id="tip"></div>
<script>
const D=__DATA__;const tip=document.getElementById('tip');const chart=document.getElementById('chart');
chart.addEventListener('mousemove',e=>{const t=e.target;if(!t.classList.contains('hr')){tip.style.opacity=0;return;}
  const r=D[+t.dataset.i];
  tip.innerHTML=`<b>${esc(r.t)}</b><div class="bd">${r.p} · ${r.d} · polarization ${r.pol}%<br>${r.sa}% strongly agree · ${r.a}% agree · ${r.un}% uncertain · ${r.di}% disagree · ${r.sd}% strongly disagree</div>`;
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


# ---------- B. 2D scatter: net agreement × polarization ---------------------

def make_scatter(stmts: list[dict]) -> str:
    width = 1200
    height = 760
    margin = {"t": 110, "r": 60, "b": 100, "l": 70}
    plot_w = width - margin["l"] - margin["r"]
    plot_h = height - margin["t"] - margin["b"]

    def x(net: float) -> float:
        return margin["l"] + (net + 1) / 2 * plot_w
    def y(pol: float) -> float:
        return margin["t"] + plot_h - (pol / 0.5) * plot_h

    # boundary: |net| + 2*pol ≤ 1   →   pol ≤ (1 - |net|) / 2
    bound = []
    for k in range(0, 101):
        net = -1 + k * 0.02
        pol = max(0.0, (1 - abs(net)) / 2)
        bound.append(f"{x(net):.1f},{y(pol):.1f}")
    bound_path = f'<polyline points="{" ".join(bound)}" fill="none" stroke="#9ca3af" stroke-dasharray="3 3" stroke-width="1"/>'

    # gridlines
    grid = [bound_path]
    for tick in [-1, -0.5, 0, 0.5, 1]:
        xt = x(tick)
        grid.append(f'<line x1="{xt:.1f}" y1="{margin["t"]}" x2="{xt:.1f}" y2="{margin["t"] + plot_h}" stroke="#f3f4f6"/>')
        label = "0" if tick == 0 else f"{int(tick * 100):+d}%"
        grid.append(f'<text x="{xt:.1f}" y="{margin["t"] + plot_h + 18}" text-anchor="middle" font-size="11" fill="#6b7280">{label}</text>')
    for tick in [0, 0.1, 0.2, 0.3, 0.4, 0.5]:
        yt = y(tick)
        grid.append(f'<line x1="{margin["l"]}" y1="{yt:.1f}" x2="{margin["l"] + plot_w}" y2="{yt:.1f}" stroke="#f3f4f6"/>')
        grid.append(f'<text x="{margin["l"] - 8}" y="{yt + 4:.1f}" text-anchor="end" font-size="11" fill="#6b7280">{int(tick*100)}%</text>')

    # axis labels
    grid.append(f'<text x="{margin["l"]}" y="{margin["t"] + plot_h + 42}" font-size="12" fill="#7c2d12" font-weight="600">PANEL DISAGREES ←</text>')
    grid.append(f'<text x="{margin["l"] + plot_w}" y="{margin["t"] + plot_h + 42}" text-anchor="end" font-size="12" fill="#14532d" font-weight="600">→ PANEL AGREES</text>')
    grid.append(f'<text x="{margin["l"] + plot_w/2}" y="{margin["t"] + plot_h + 60}" text-anchor="middle" font-size="11" fill="#6b7280" font-style="italic">net agreement (% agree − % disagree)</text>')
    grid.append(f'<text x="20" y="{margin["t"] - 16}" font-size="11" fill="#6b7280" font-weight="600">↑ panel SPLIT</text>')
    grid.append(f'<text x="20" y="{margin["t"] + plot_h - 4}" font-size="11" fill="#6b7280" font-weight="600">panel CONVERGED</text>')

    # quadrant captions
    grid.append(f'<text x="{x(-0.7):.1f}" y="{y(0.06):.1f}" font-size="13" fill="#7c2d12" font-weight="700" text-anchor="middle">settled — DISAGREE</text>')
    grid.append(f'<text x="{x(0.7):.1f}" y="{y(0.06):.1f}" font-size="13" fill="#14532d" font-weight="700" text-anchor="middle">settled — AGREE</text>')
    grid.append(f'<text x="{x(0):.1f}" y="{y(0.46):.1f}" font-size="13" fill="#374151" font-weight="700" text-anchor="middle">contested — split panel</text>')

    # dots: colour = direction of lean (faded when small polarization, vivid when high)
    dots = []
    data = []
    for i, r in enumerate(stmts):
        if r["dir"] == "Agree":
            col = "#15803d"
        elif r["dir"] == "Disagree":
            col = "#b91c1c"
        else:
            col = "#94a3b8"
        cx = x(r["net"]); cy = y(r["pol"])
        dots.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="3" fill="{col}" fill-opacity="0.6" stroke="#fff" stroke-width="0.4" data-i="{i}" class="dot"/>')
        data.append({
            "t": r["text"], "p": r["panel"], "d": r["date"], "u": r["url"],
            "net": round(r["net"]*100), "pol": round(r["pol"]*100, 1),
            "sa": round(r["share_a"]*100), "su": round(r["share_u"]*100), "sd": round(r["share_d"]*100),
        })

    # annotations: pick examples from corners + middle-top
    used = set()
    keywords = [
        ("index fund", "Index funds beat stock-picking"),
        ("gold standard", "Gold standard would help"),
        ("rent control", "Rent control hurts supply"),
        ("$15", "$15 federal minimum wage helps"),
        ("steel and aluminum", "Trump tariffs help US"),
        ("Bitcoin", "Bitcoin will replace fiat"),
        ("carbon tax", "Carbon taxes are efficient"),
    ]
    annotations = []
    for kw, label in keywords:
        r = find_by_kw(stmts, kw, used)
        if r:
            annotations.append({"r": r, "label": label})

    ann_svg = []
    placed: list[tuple[float, float]] = []
    for a in annotations:
        r = a["r"]
        cx = x(r["net"]); cy = y(r["pol"])
        ann_svg.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="4.5" fill="#111" stroke="#fff" stroke-width="1.4"/>')
        # label position: above the dot, with stagger
        lx = cx; ly = cy - 12
        while any(abs(lx - px) < 130 and abs(ly - py) < 16 for px, py in placed):
            ly -= 14
        placed.append((lx, ly))
        if lx < margin["l"] + 80:
            anchor = "start"; tx = cx + 8
        elif lx > margin["l"] + plot_w - 80:
            anchor = "end"; tx = cx - 8
        else:
            anchor = "middle"; tx = cx
        ann_svg.append(f'<line x1="{cx:.1f}" y1="{cy - 5:.1f}" x2="{cx:.1f}" y2="{ly + 4:.1f}" stroke="#111" stroke-width="0.5"/>')
        ann_svg.append(f'<text x="{tx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" font-size="11" fill="#111" font-weight="500">{html.escape(a["label"])}</text>')

    title = "Two ways to read economist surveys"
    subtitle = ("Each dot is one of 1,119 IGM survey questions. Horizontal: which way the panel leaned. "
                "Vertical: how split they were. Most questions sit at the bottom corners (settled). "
                "The genuinely contested ones rise to the top centre.")

    data_json = json.dumps(data, separators=(",", ":"))
    tmpl = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>__TITLE__</title>
<style>
  body{margin:0;background:#fafaf9;color:#111827;font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif;}
  .wrap{max-width:__WIDTH__px;margin:0 auto;padding:28px 24px 28px;}
  h1{font:600 30px/1.15 ui-serif,Georgia,serif;margin:0 0 6px;}
  .sub{color:#4b5563;margin:0 0 14px;max-width:84ch;}
  .foot{color:#6b7280;font-size:12px;margin-top:6px;border-top:1px solid #e5e7eb;padding-top:10px;}
  svg{display:block;width:100%;height:auto;}
  .dot{cursor:pointer;}
  .dot:hover{stroke:#111;stroke-width:1.4;}
  #tip{position:fixed;pointer-events:none;background:#111827;color:#f9fafb;padding:8px 10px;border-radius:6px;font-size:12px;max-width:360px;box-shadow:0 4px 12px rgba(0,0,0,.2);opacity:0;transition:opacity .12s;z-index:10;}
  #tip .bd{margin-top:6px;font-size:11px;color:#cbd5e1;}
</style></head><body><div class="wrap">
  <h1>__TITLE__</h1><p class="sub">__SUBTITLE__</p>
  <svg viewBox="0 0 __WIDTH__ __HEIGHT__" id="chart">
    __GRID__
    __DOTS__
    __ANN__
  </svg>
  <p class="foot">Data: Kent A. Clark Center for Global Markets (IGM Forum). The dashed boundary is the math limit: |net| + 2·polarization ≤ 1.</p>
</div><div id="tip"></div>
<script>
const D=__DATA__;const tip=document.getElementById('tip');const chart=document.getElementById('chart');
chart.addEventListener('mousemove',e=>{const t=e.target;if(!t.classList.contains('dot')){tip.style.opacity=0;return;}
  const r=D[+t.dataset.i];
  tip.innerHTML=`<b>${esc(r.t)}</b><div class="bd">${r.p} · ${r.d}<br>net ${r.net>=0?'+':''}${r.net}% · polarization ${r.pol}%<br>${r.sa}% agree · ${r.su}% uncertain · ${r.sd}% disagree</div>`;
  tip.style.opacity=1;const x=e.clientX+14;const y=e.clientY+14;
  tip.style.left=Math.min(x,window.innerWidth-380)+'px';tip.style.top=Math.min(y,window.innerHeight-110)+'px';
});
chart.addEventListener('mouseleave',()=>tip.style.opacity=0);
chart.addEventListener('click',e=>{const t=e.target;if(t.classList.contains('dot')){const r=D[+t.dataset.i];if(r.u)window.open(r.u,'_blank');}});
function esc(s){return s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
</script></body></html>
"""
    return (tmpl
        .replace("__TITLE__", title)
        .replace("__SUBTITLE__", subtitle)
        .replace("__WIDTH__", str(width))
        .replace("__HEIGHT__", str(height))
        .replace("__GRID__", "\n".join(grid))
        .replace("__DOTS__", "\n".join(dots))
        .replace("__ANN__", "\n".join(ann_svg))
        .replace("__DATA__", data_json))


# ---------- C. divided.html: top 30 most-polarized ---------------------------

def make_divided(stmts: list[dict]) -> str:
    rows = sorted(stmts, key=lambda r: -r["pol"])[:30]

    width = 1200
    row_h = 26
    margin_t = 130
    margin_b = 80
    block_h = len(rows) * row_h
    height = margin_t + block_h + margin_b

    text_w = 600
    bar_max = 360
    label_x = 30
    bar_x0 = label_x + text_w + 20

    blocks: list[str] = []
    for i, r in enumerate(rows):
        y = margin_t + i * row_h
        rank = i + 1
        txt = (r["text"][:110] + "…") if len(r["text"]) > 110 else r["text"]
        blocks.append(f'<text x="{label_x}" y="{y + 16}" font-size="12" fill="#9ca3af">{rank}.</text>')
        blocks.append(f'<text x="{label_x + 26}" y="{y + 16}" font-size="12" fill="#111">{html.escape(txt)}</text>')
        # split bar
        x = bar_x0
        seg = [(r["sd"], C_SD), (r["d"], C_D), (r["u"], C_U), (r["a"], C_A), (r["sa"], C_SA)]
        for share, col in seg:
            ww = share * bar_max
            if ww > 0.5:
                blocks.append(f'<rect x="{x:.2f}" y="{y + 6}" width="{ww:.2f}" height="{row_h - 12}" fill="{col}"/>')
            x += ww
        # numeric
        agree_pct = round(r["share_a"] * 100)
        dis_pct = round(r["share_d"] * 100)
        blocks.append(f'<text x="{bar_x0 + bar_max + 10}" y="{y + 16}" font-size="11" fill="#374151">{agree_pct}% / {dis_pct}%</text>')
        # panel + date
        pcol = PANEL_COLOR.get(r["panel"], "#374151")
        blocks.append(f'<text x="{bar_x0 + bar_max + 80}" y="{y + 16}" font-size="10" fill="{pcol}">{r["panel"]} · {r["date"][:4]}</text>')

    # axis above the block
    axes = []
    for frac in [0, 0.25, 0.5, 0.75, 1]:
        ax = bar_x0 + frac * bar_max
        axes.append(f'<line x1="{ax:.1f}" y1="{margin_t - 26}" x2="{ax:.1f}" y2="{margin_t - 22}" stroke="#9ca3af"/>')
        axes.append(f'<text x="{ax:.1f}" y="{margin_t - 30}" text-anchor="middle" font-size="9" fill="#9ca3af">{int(frac*100)}%</text>')
    axes.append(f'<text x="{label_x}" y="{margin_t - 22}" font-size="11" fill="#374151" font-weight="600">QUESTION</text>')
    axes.append(f'<text x="{bar_x0 + bar_max + 10}" y="{margin_t - 22}" font-size="11" fill="#374151" font-weight="600">agree / disagree</text>')

    # legend
    legend = []
    for i, (lbl, col) in enumerate([("strongly disagree", C_SD), ("disagree", C_D), ("uncertain", C_U), ("agree", C_A), ("strongly agree", C_SA)]):
        lx = bar_x0 + i * 110
        legend.append(f'<rect x="{lx}" y="80" width="13" height="10" fill="{col}"/>')
        legend.append(f'<text x="{lx + 17}" y="89" font-size="11" fill="#374151">{html.escape(lbl)}</text>')

    title = "The 30 questions where economists are most divided"
    subtitle = "Out of 1,119 IGM surveys, ranked by polarization (panel split closest to 50/50). These are the questions on which the economics profession itself disagrees."

    tmpl = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>__TITLE__</title>
<style>
  body{margin:0;background:#fafaf9;color:#111827;font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif;}
  .wrap{max-width:__WIDTH__px;margin:0 auto;padding:28px 24px 28px;}
  h1{font:600 30px/1.15 ui-serif,Georgia,serif;margin:0 0 6px;}
  .sub{color:#4b5563;margin:0 0 14px;max-width:84ch;}
  .foot{color:#6b7280;font-size:12px;margin-top:6px;border-top:1px solid #e5e7eb;padding-top:10px;}
  svg{display:block;width:100%;height:auto;}
</style></head><body><div class="wrap">
  <h1>__TITLE__</h1><p class="sub">__SUBTITLE__</p>
  <svg viewBox="0 0 __WIDTH__ __HEIGHT__">
    __LEGEND__
    __AXES__
    __BLOCKS__
  </svg>
  <p class="foot">Data: Kent A. Clark Center for Global Markets (IGM Forum), 558 surveys 2011–2026. Polarization = min(% agree, % disagree).</p>
</div></body></html>
"""
    return (tmpl
        .replace("__TITLE__", title)
        .replace("__SUBTITLE__", subtitle)
        .replace("__WIDTH__", str(width))
        .replace("__HEIGHT__", str(height))
        .replace("__LEGEND__", "\n".join(legend))
        .replace("__AXES__", "\n".join(axes))
        .replace("__BLOCKS__", "\n".join(blocks)))


# ---------- main -------------------------------------------------------------

def main() -> None:
    stmts = load_statements()
    print(f"Loaded {len(stmts)} statements")
    (ROOT / "horizon_polar.html").write_text(make_horizon_polar(stmts), encoding="utf-8")
    print("wrote horizon_polar.html")
    (ROOT / "scatter.html").write_text(make_scatter(stmts), encoding="utf-8")
    print("wrote scatter.html")
    (ROOT / "divided.html").write_text(make_divided(stmts), encoding="utf-8")
    print("wrote divided.html")


if __name__ == "__main__":
    main()
