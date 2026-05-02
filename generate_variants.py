"""Six visual variants of the consensus chart, to compare which encoding
makes consensus-vs-not pop hardest.

Variants on the bar chart (same data, sorting, annotations):
  v_opacity.html    — bar opacity tied to H (diffuse bars fade)
  v_zones.html      — pale rose tint behind H<0.4, pale green tint behind H>0.6
  v_threshold.html  — horizontal dashed reference line at H=0.60 with label
  v_pivot.html      — non-linear (sigmoid) saturation: low-H stays gray, high-H pops
  v_texture.html    — solid for H >= 0.6, hatched for H < 0.4, fade in between

Different chart structure:
  v_dots.html       — dot-per-vote: ~30 questions sampled across H spectrum,
                      each shown as ~50 dots representing actual economist votes
"""
from __future__ import annotations

import csv
import html
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
STATEMENTS_CSV = ROOT / "statements_consensus.csv"
VOTES_CSV = ROOT / "votes.csv"


def load_statements() -> list[dict]:
    rows: list[dict] = []
    with open(STATEMENTS_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not r["consensus_score"]:
                continue
            n = int(r["n_answered_excluding_no_opinion"] or 0)
            if n == 0:
                continue
            sa = float(r["share_agree"]); sd = float(r["share_disagree"]); su = float(r["share_uncertain"])
            hhi = sa * sa + sd * sd + su * su
            top = max(sa, sd, su)
            direction = "Agree" if top == sa else ("Disagree" if top == sd else "Uncertain")
            rows.append({
                "id": r["statement_id"], "text": r["statement_text"],
                "panel": r["panel_type"], "date": r["publication_date"], "url": r["poll_url"],
                "n": n, "sa_n": int(r["n_strongly_agree"] or 0), "a_n": int(r["n_agree"] or 0),
                "u_n": int(r["n_uncertain"] or 0), "d_n": int(r["n_disagree"] or 0), "sd_n": int(r["n_strongly_disagree"] or 0),
                "share_a": sa, "share_d": sd, "share_u": su,
                "hhi": hhi, "top": top, "dir": direction,
            })
    return rows


# ---------- shared bar-chart skeleton -----------------------------------------

def make_bars(stmts: list[dict], style: str) -> str:
    rows = sorted(stmts, key=lambda r: r["hhi"])
    n = len(rows)

    width = 1200
    height = 720
    margin = {"t": 100, "r": 60, "b": 150, "l": 110}
    plot_w = width - margin["l"] - margin["r"]
    plot_h = height - margin["t"] - margin["b"]
    col_w = plot_w / n

    y_min, y_max = 1 / 3, 1.0
    def y(d: float) -> float:
        return margin["t"] + plot_h - (d - y_min) / (y_max - y_min) * plot_h

    def lerp_color(c0, c1, t):
        return f"#{int(c0[0]+(c1[0]-c0[0])*t):02x}{int(c0[1]+(c1[1]-c0[1])*t):02x}{int(c0[2]+(c1[2]-c0[2])*t):02x}"

    pale = (203, 213, 225)
    deep = (30, 41, 59)

    pre_bars: list[str] = []   # things drawn behind bars (background zones, threshold line under bars)
    post_bars: list[str] = []  # things drawn over bars (threshold line on top, etc.)

    if style == "zones":
        # rose tint where H < 0.4, green tint where H >= 0.6
        rose_top = y(0.4)
        rose_bot = margin["t"] + plot_h
        pre_bars.append(f'<rect x="{margin["l"]}" y="{rose_top:.1f}" width="{plot_w}" height="{rose_bot - rose_top:.1f}" fill="#fee2e2" fill-opacity="0.55"/>')
        green_top = y(1.0)
        green_bot = y(0.6)
        pre_bars.append(f'<rect x="{margin["l"]}" y="{green_top:.1f}" width="{plot_w}" height="{green_bot - green_top:.1f}" fill="#dcfce7" fill-opacity="0.55"/>')
        # zone labels (faint, large, behind bars)
        pre_bars.append(f'<text x="{margin["l"] + 12}" y="{(rose_top + rose_bot)/2 + 4:.1f}" font-size="22" fill="#fca5a5" font-weight="700" letter-spacing="2">DISPUTED</text>')
        pre_bars.append(f'<text x="{margin["l"] + plot_w - 12}" y="{(green_top + green_bot)/2 + 4:.1f}" font-size="22" fill="#86efac" font-weight="700" letter-spacing="2" text-anchor="end">SETTLED</text>')

    if style == "threshold":
        thresh_y = y(0.60)
        post_bars.append(f'<line x1="{margin["l"]}" y1="{thresh_y:.1f}" x2="{margin["l"] + plot_w}" y2="{thresh_y:.1f}" stroke="#dc2626" stroke-width="1.4" stroke-dasharray="6 4"/>')
        post_bars.append(f'<text x="{margin["l"] + plot_w - 8}" y="{thresh_y - 6:.1f}" text-anchor="end" font-size="11" fill="#dc2626" font-weight="600">consensus threshold (H = 0.60)</text>')

    bars: list[str] = []
    data: list[dict] = []
    defs = ""
    if style == "texture":
        defs = """<defs>
  <pattern id="hatch" patternUnits="userSpaceOnUse" width="4" height="4" patternTransform="rotate(45)">
    <rect width="4" height="4" fill="#cbd5e1"/>
    <line x1="0" y1="0" x2="0" y2="4" stroke="#94a3b8" stroke-width="1.6"/>
  </pattern>
</defs>"""

    for i, r in enumerate(rows):
        x = margin["l"] + i * col_w
        top = y(r["hhi"])
        bot = margin["t"] + plot_h
        h = r["hhi"]
        t = (h - y_min) / (y_max - y_min)

        if style == "opacity":
            col = lerp_color(pale, deep, t)
            opacity = 0.18 + 0.82 * t  # ranges 0.18 (diffuse) to 1.0 (settled)
            bars.append(f'<rect x="{x:.2f}" y="{top:.2f}" width="{col_w:.3f}" height="{bot - top:.2f}" fill="{col}" fill-opacity="{opacity:.3f}"/>')
        elif style == "pivot":
            # sigmoid centred at 0.55, steepness 14 — stays pale until median, then pops
            import math
            s = 1 / (1 + math.exp(-14 * (h - 0.55)))
            col = lerp_color(pale, deep, s)
            bars.append(f'<rect x="{x:.2f}" y="{top:.2f}" width="{col_w:.3f}" height="{bot - top:.2f}" fill="{col}"/>')
        elif style == "texture":
            if h < 0.4:
                fill = "url(#hatch)"
                bars.append(f'<rect x="{x:.2f}" y="{top:.2f}" width="{col_w:.3f}" height="{bot - top:.2f}" fill="{fill}"/>')
            elif h < 0.6:
                col = lerp_color(pale, deep, t)
                bars.append(f'<rect x="{x:.2f}" y="{top:.2f}" width="{col_w:.3f}" height="{bot - top:.2f}" fill="{col}" fill-opacity="0.85"/>')
            else:
                col = lerp_color(pale, deep, t)
                bars.append(f'<rect x="{x:.2f}" y="{top:.2f}" width="{col_w:.3f}" height="{bot - top:.2f}" fill="{col}"/>')
        else:
            # default linear gradient (zones, threshold use same bar style)
            col = lerp_color(pale, deep, t)
            bars.append(f'<rect x="{x:.2f}" y="{top:.2f}" width="{col_w:.3f}" height="{bot - top:.2f}" fill="{col}"/>')

        data.append({
            "t": r["text"], "p": r["panel"], "d": r["date"], "u": r["url"], "dir": r["dir"],
            "hhi": round(r["hhi"], 3), "top": round(r["top"] * 100),
            "sa": round(r["share_a"] * 100), "su": round(r["share_u"] * 100), "sd": round(r["share_d"] * 100),
        })

    hover_w = max(col_w, 4)
    hovers = []
    for i in range(n):
        x = margin["l"] + i * col_w - (hover_w - col_w) / 2
        hovers.append(f'<rect class="hr" x="{x:.2f}" y="{margin["t"]}" width="{hover_w:.2f}" height="{plot_h:.2f}" fill="transparent" data-i="{i}"/>')

    grid = []
    for tick in [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        yt = y(tick)
        grid.append(f'<line x1="{margin["l"]}" y1="{yt:.1f}" x2="{margin["l"] + plot_w}" y2="{yt:.1f}" stroke="#e5e7eb" stroke-width="0.6"/>')
        grid.append(f'<text x="{margin["l"] - 8}" y="{yt + 4:.1f}" text-anchor="end" font-size="11" fill="#6b7280">{tick:.2f}</text>')
    grid.append(f'<text x="{margin["l"] - 8}" y="{y(1.0) - 12:.1f}" text-anchor="end" font-size="11" fill="#111" font-weight="600">unanimous</text>')
    grid.append(f'<text x="{margin["l"] - 8}" y="{y(1 / 3) + 4:.1f}" text-anchor="end" font-size="11" fill="#111" font-weight="600">3-way diffuse</text>')
    grid.append(f'<text x="{margin["l"]}" y="{margin["t"] + plot_h + 22}" font-size="12" fill="#7c2d12" font-weight="600">← MOST DIVIDED</text>')
    grid.append(f'<text x="{margin["l"] + plot_w}" y="{margin["t"] + plot_h + 22}" text-anchor="end" font-size="12" fill="#14532d" font-weight="600">MOST UNITED →</text>')
    grid.append(f'<text x="{margin["l"] + plot_w / 2}" y="{margin["t"] + plot_h + 22}" text-anchor="middle" font-size="11" fill="#6b7280" font-style="italic">{n:,} questions, sorted by panel agreement (any direction)</text>')

    picks = [
        (10, "best forecast for the value of one bitcoin", "10%ile · Bitcoin = current price"),
        (25, "payment for human kidneys",                  "25%ile · Pay for human kidneys"),
        (50, "$15-per-hour by 2020",                       "50%ile · $15 federal min wage"),
        (75, "non-compete clauses",                        "75%ile · Non-competes hurt workers"),
        (90, "North American Free Trade Agreement",        "90%ile · NAFTA makes Americans better off"),
    ]
    annotations = []
    for pct, kw, label in picks:
        target = int(n * pct / 100)
        best_idx = None; best_dist = 10**9
        for idx, r in enumerate(rows):
            if kw.lower() in r["text"].lower():
                dist = abs(idx - target)
                if dist < best_dist:
                    best_dist = dist; best_idx = idx
        if best_idx is not None:
            annotations.append({"i": best_idx, "label": label, "hhi": rows[best_idx]["hhi"]})

    annotations.sort(key=lambda a: a["i"])
    ann_svg = []
    placed: list[tuple[float, float]] = []
    for a in annotations:
        bx = margin["l"] + a["i"] * col_w
        by = y(a["hhi"])
        lx = bx; ly = by - 12
        while any(abs(lx - px) < 130 and abs(ly - py) < 14 for px, py in placed):
            ly -= 14
        placed.append((lx, ly))
        if lx < margin["l"] + 70:
            anchor = "start"; tx = bx + 6
        elif lx > margin["l"] + plot_w - 70:
            anchor = "end"; tx = bx - 6
        else:
            anchor = "middle"; tx = bx
        ann_svg.append(f'<line x1="{bx:.1f}" y1="{by - 4:.1f}" x2="{bx:.1f}" y2="{ly + 4:.1f}" stroke="#111" stroke-width="0.5" stroke-dasharray="2 2"/>')
        ann_svg.append(f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="3" fill="#111" stroke="#fff" stroke-width="1.2"/>')
        ann_svg.append(f'<text x="{tx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" font-size="11" fill="#111" font-weight="500">{html.escape(a["label"])}</text>')

    legend = []
    grad_w = 260; grad_h = 10
    lx0 = margin["l"] + (plot_w - grad_w) / 2
    ly_g = height - 32
    legend.append('<defs><linearGradient id="hgrad" x1="0%" x2="100%"><stop offset="0%" stop-color="#cbd5e1"/><stop offset="100%" stop-color="#1e293b"/></linearGradient></defs>')
    legend.append(f'<rect x="{lx0:.1f}" y="{ly_g}" width="{grad_w}" height="{grad_h}" fill="url(#hgrad)"/>')
    legend.append(f'<text x="{lx0:.1f}" y="{ly_g + grad_h + 12}" font-size="11" fill="#374151" text-anchor="start">low concentration</text>')
    legend.append(f'<text x="{lx0 + grad_w:.1f}" y="{ly_g + grad_h + 12}" font-size="11" fill="#374151" text-anchor="end">high concentration</text>')

    style_titles = {
        "opacity":   "Opacity-coded: diffuse questions fade",
        "zones":     "Zones: disputed vs settled territories tinted",
        "threshold": "Reference line at H = 0.60 (consensus threshold)",
        "pivot":     "Sigmoid saturation: settled questions pop, contested recede",
        "texture":   "Texture: hatched bars for contested, solid for settled",
    }
    title = style_titles.get(style, "Consensus")
    subtitle = "Each thin column is one of 1,119 IGM survey questions, sorted by Herfindahl concentration H. Variant: " + style + "."

    data_json = json.dumps(data, separators=(",", ":"))
    tmpl = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>__TITLE__</title>
<style>
  body{margin:0;background:#fafaf9;color:#111827;font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif;}
  .wrap{max-width:__WIDTH__px;margin:0 auto;padding:28px 24px 32px;}
  h1{font:600 26px/1.15 ui-serif,Georgia,serif;margin:0 0 6px;}
  .sub{color:#4b5563;margin:0 0 14px;max-width:88ch;}
  svg{display:block;width:100%;height:auto;}
  .hr:hover{fill:rgba(0,0,0,0.08);cursor:pointer;}
</style></head><body><div class="wrap">
  <h1>__TITLE__</h1><p class="sub">__SUBTITLE__</p>
  <svg viewBox="0 0 __WIDTH__ __HEIGHT__" id="chart">
    __DEFS__
    __PRE__
    __GRID__
    __BARS__
    __POST__
    __ANN__
    __LEGEND__
    __HOVERS__
  </svg>
</div></body></html>
"""
    return (tmpl
        .replace("__TITLE__", title)
        .replace("__SUBTITLE__", subtitle)
        .replace("__WIDTH__", str(width))
        .replace("__HEIGHT__", str(height))
        .replace("__DEFS__", defs)
        .replace("__PRE__", "\n".join(pre_bars))
        .replace("__GRID__", "\n".join(grid))
        .replace("__BARS__", "\n".join(bars))
        .replace("__POST__", "\n".join(post_bars))
        .replace("__ANN__", "\n".join(ann_svg))
        .replace("__LEGEND__", "\n".join(legend))
        .replace("__HOVERS__", "\n".join(hovers)))


# ---------- v6: dot-per-vote, sampled across H spectrum -----------------------

def make_dots(stmts: list[dict]) -> str:
    rows = sorted(stmts, key=lambda r: r["hhi"])
    n = len(rows)
    # sample 30 questions evenly across the spectrum
    indices = [int(n * i / 29) for i in range(30)]
    indices[-1] = n - 1
    sampled = [rows[i] for i in indices]

    width = 1200
    row_h = 22
    margin_t = 130
    margin_b = 90
    n_rows = len(sampled)
    block_h = n_rows * row_h
    height = margin_t + block_h + margin_b

    text_w = 460
    bar_w = 600
    label_x = 30
    bar_x0 = label_x + text_w + 20

    # 5 vote-bucket positions across bar width
    positions = [bar_x0 + (k + 0.5) * (bar_w / 5) for k in range(5)]
    bucket_keys = ["sd_n", "d_n", "u_n", "a_n", "sa_n"]
    bucket_colors = ["#7c2d12", "#dc6063", "#94a3b8", "#4ea36d", "#14532d"]
    bucket_labels = ["Strongly Disagree", "Disagree", "Uncertain", "Agree", "Strongly Agree"]

    blocks: list[str] = []
    rng = random.Random(42)
    for i, r in enumerate(sampled):
        y = margin_t + i * row_h
        # text label (truncated)
        txt = (r["text"][:70] + "…") if len(r["text"]) > 70 else r["text"]
        blocks.append(f'<text x="{label_x}" y="{y + 14}" font-size="11" fill="#111">{html.escape(txt)}</text>')
        # H value
        blocks.append(f'<text x="{label_x + text_w + 4}" y="{y + 14}" font-size="10" fill="#6b7280" text-anchor="end">H={r["hhi"]:.2f}</text>')
        # row separator
        blocks.append(f'<line x1="{bar_x0}" y1="{y + row_h - 1}" x2="{bar_x0 + bar_w}" y2="{y + row_h - 1}" stroke="#f3f4f6"/>')
        # plot dots: each economist's vote becomes a dot at the bucket's x position, jittered
        center_y = y + row_h / 2
        for k, key in enumerate(bucket_keys):
            count = r[key]
            for v in range(count):
                # small jitter horizontally inside the bucket; vertical jitter inside the row
                jx = (rng.random() - 0.5) * (bar_w / 5 - 6)
                jy = (rng.random() - 0.5) * (row_h - 8)
                cx = positions[k] + jx
                cy = center_y + jy
                blocks.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="1.7" fill="{bucket_colors[k]}" fill-opacity="0.75"/>')

    # bucket header
    headers = []
    for k, lbl in enumerate(bucket_labels):
        headers.append(f'<text x="{positions[k]:.1f}" y="{margin_t - 14}" text-anchor="middle" font-size="10" fill="{bucket_colors[k]}" font-weight="600">{lbl}</text>')

    # vertical guides
    guides = []
    for k in range(6):
        xv = bar_x0 + k * (bar_w / 5)
        guides.append(f'<line x1="{xv:.1f}" y1="{margin_t - 6}" x2="{xv:.1f}" y2="{margin_t + block_h + 6}" stroke="#e5e7eb" stroke-width="0.6"/>')

    title = "Show the votes themselves: 30 questions, ~50 dots each"
    subtitle = ("Each row is one IGM question; each dot is one economist's vote. "
                "Top row = most diffuse (panel split across buckets). Bottom row = most united. "
                "Consensus is visible as visual clustering of dots in one bucket; "
                "no consensus is visible as scatter.")

    tmpl = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>__TITLE__</title>
<style>
  body{margin:0;background:#fafaf9;color:#111827;font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif;}
  .wrap{max-width:__WIDTH__px;margin:0 auto;padding:28px 24px 28px;}
  h1{font:600 26px/1.15 ui-serif,Georgia,serif;margin:0 0 6px;}
  .sub{color:#4b5563;margin:0 0 14px;max-width:88ch;}
  svg{display:block;width:100%;height:auto;}
</style></head><body><div class="wrap">
  <h1>__TITLE__</h1><p class="sub">__SUBTITLE__</p>
  <svg viewBox="0 0 __WIDTH__ __HEIGHT__">
    __HEADERS__
    __GUIDES__
    __BLOCKS__
  </svg>
</div></body></html>
"""
    return (tmpl
        .replace("__TITLE__", title)
        .replace("__SUBTITLE__", subtitle)
        .replace("__WIDTH__", str(width))
        .replace("__HEIGHT__", str(height))
        .replace("__HEADERS__", "\n".join(headers))
        .replace("__GUIDES__", "\n".join(guides))
        .replace("__BLOCKS__", "\n".join(blocks)))


def main() -> None:
    stmts = load_statements()
    print(f"Loaded {len(stmts)} statements")
    for style in ("opacity", "zones", "threshold", "pivot", "texture"):
        out = ROOT / f"v_{style}.html"
        out.write_text(make_bars(stmts, style), encoding="utf-8")
        print(f"wrote {out.name}")
    out = ROOT / "v_dots.html"
    out.write_text(make_dots(stmts), encoding="utf-8")
    print(f"wrote {out.name}")


if __name__ == "__main__":
    main()
