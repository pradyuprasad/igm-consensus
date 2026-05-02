"""Direction-blind consensus chart.

Metric: Herfindahl concentration = sum of squared shares.
  H = share_agree² + share_disagree² + share_uncertain²
- 1.0 → panel unanimous (one bucket = 100%)
- 1/3 ≈ 0.33 → perfectly diffuse (split equally three ways — no consensus)

Captures genuine concentration, regardless of direction, and correctly ranks
60/39/1 (almost no dissent) as more settled than 60/30/10 (real dissent).
"""
from __future__ import annotations

import csv
import html
import json
from pathlib import Path

ROOT = Path(__file__).parent
STATEMENTS_CSV = ROOT / "statements_consensus.csv"

C_AGREE = "#15803d"
C_DISAGREE = "#b91c1c"
C_UNCERTAIN = "#94a3b8"


def load_statements() -> list[dict]:
    rows: list[dict] = []
    with open(STATEMENTS_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not r["consensus_score"]:
                continue
            n = int(r["n_answered_excluding_no_opinion"] or 0)
            if n == 0:
                continue
            sa = float(r["share_agree"])
            sd = float(r["share_disagree"])
            su = float(r["share_uncertain"])
            hhi = sa * sa + sd * sd + su * su
            top_share = max(sa, sd, su)
            if top_share == sa:
                direction = "Agree"
            elif top_share == sd:
                direction = "Disagree"
            else:
                direction = "Uncertain"
            # 5-bucket Likert shares for sparklines
            b_sd = int(r["n_strongly_disagree"] or 0) / n
            b_d  = int(r["n_disagree"] or 0) / n
            b_u  = int(r["n_uncertain"] or 0) / n
            b_a  = int(r["n_agree"] or 0) / n
            b_sa = int(r["n_strongly_agree"] or 0) / n
            rows.append({
                "id": r["statement_id"],
                "text": r["statement_text"],
                "panel": r["panel_type"],
                "date": r["publication_date"],
                "url": r["poll_url"],
                "n": n,
                "share_a": sa,
                "share_d": sd,
                "share_u": su,
                "hhi": hhi,
                "top": top_share,
                "dir": direction,
                "b_sd": b_sd, "b_d": b_d, "b_u": b_u, "b_a": b_a, "b_sa": b_sa,
            })
    return rows


def make_chart(
    stmts: list[dict],
    palette=(("#fde047", 0.0), ("#f97316", 0.35), ("#be123c", 0.65), ("#1e1b4b", 1.0)),
) -> str:
    # palette is a tuple of (hex, offset∈[0,1]) stops, sorted by offset.
    stops = [(int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16), o, h) for h, o in palette]

    rows = sorted(stmts, key=lambda r: r["hhi"])
    n = len(rows)

    width = 1200
    height = 720
    margin = {"t": 90, "r": 60, "b": 150, "l": 132}
    plot_w = width - margin["l"] - margin["r"]
    plot_h = height - margin["t"] - margin["b"]
    col_w = plot_w / n

    # y maps Herfindahl ∈ [1/3, 1] → [bottom, top]
    y_min, y_max = 1 / 3, 1.0
    def y(d: float) -> float:
        return margin["t"] + plot_h - (d - y_min) / (y_max - y_min) * plot_h

    # multi-stop sequential palette, darker/saturated = higher H
    def shade(h: float) -> str:
        t = max(0.0, min(1.0, (h - y_min) / (y_max - y_min)))  # 0..1
        for i in range(len(stops) - 1):
            r0, g0, b0, o0, _ = stops[i]
            r1, g1, b1, o1, _ = stops[i + 1]
            if t <= o1:
                u = (t - o0) / (o1 - o0) if o1 > o0 else 0
                rr = round(r0 + (r1 - r0) * u)
                gg = round(g0 + (g1 - g0) * u)
                bb = round(b0 + (b1 - b0) * u)
                return f"#{rr:02x}{gg:02x}{bb:02x}"
        return stops[-1][4]

    bars: list[str] = []
    data: list[dict] = []
    for i, r in enumerate(rows):
        x = margin["l"] + i * col_w
        top = y(r["hhi"])
        bot = margin["t"] + plot_h
        col = shade(r["hhi"])
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

    # gridlines + axis at evenly-spaced Herfindahl values
    grid = []
    # three named zone thresholds; (value, label, label-y-offset)
    thresholds = [
        (0.40, "↓ contested",                  +18),
        (0.50, "↑ panel has a confident answer", -6),
        (0.75, "↑ overwhelming consensus",       -6),
    ]
    threshold_vals = {t for t, _, _ in thresholds}
    for tick in [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        yt = y(tick)
        if tick in threshold_vals:
            continue  # threshold gets its own styled line below
        grid.append(f'<line x1="{margin["l"]}" y1="{yt:.1f}" x2="{margin["l"] + plot_w}" y2="{yt:.1f}" stroke="#e5e7eb" stroke-width="0.6"/>')
        grid.append(f'<text x="{margin["l"] - 8}" y="{yt + 4:.1f}" text-anchor="end" font-size="11" fill="#6b7280">{tick:.2f}</text>')

    # threshold lines: contested floor / confident / overwhelming.
    # Each gets a "pill" badge on the left side of the chart, sitting on the line.
    badge_h = 20
    char_w = 6.6
    for thr_val, label, lbl_dy in thresholds:
        yt = y(thr_val)
        grid.append(f'<line x1="{margin["l"]}" y1="{yt:.1f}" x2="{margin["l"] + plot_w}" y2="{yt:.1f}" stroke="#111" stroke-width="1.1" stroke-dasharray="6 4"/>')
        grid.append(f'<text x="{margin["l"] - 8}" y="{yt + 4:.1f}" text-anchor="end" font-size="11" fill="#111" font-weight="700">{thr_val:.2f}</text>')
        # pill label, anchored at left-of-plot, sitting centered on the line
        pill_w = len(label) * char_w + 14
        pill_x = margin["l"] + 6
        pill_y = yt - badge_h / 2
        grid.append(
            f'<rect x="{pill_x:.1f}" y="{pill_y:.1f}" width="{pill_w:.1f}" height="{badge_h}" '
            f'rx="{badge_h/2}" fill="#fafaf9" stroke="#111" stroke-width="0.9"/>'
        )
        grid.append(
            f'<text x="{pill_x + pill_w/2:.1f}" y="{yt + 4:.1f}" text-anchor="middle" font-size="11" '
            f'fill="#111" font-weight="700" letter-spacing="0.5">{label}</text>'
        )

    # callouts on the y-axis
    grid.append(f'<text x="{margin["l"] - 8}" y="{y(1.0) - 12:.1f}" text-anchor="end" font-size="11" fill="#111" font-weight="600">unanimous</text>')
    grid.append(f'<text x="{margin["l"] - 8}" y="{y(1 / 3) + 4:.1f}" text-anchor="end" font-size="11" fill="#111" font-weight="600">3-way diffuse</text>')

    # rotated y-axis title naming the metric explicitly
    yt_x = 22
    yt_y = margin["t"] + plot_h / 2
    grid.append(
        f'<text x="{yt_x}" y="{yt_y:.1f}" transform="rotate(-90 {yt_x} {yt_y:.1f})" '
        f'text-anchor="middle" font-size="12" fill="#374151" font-weight="600" letter-spacing="0.4">'
        f'Herfindahl-Hirschman Index (HHI)</text>'
    )

    # x-axis labels
    grid.append(f'<text x="{margin["l"]}" y="{margin["t"] + plot_h + 22}" font-size="12" fill="#7c2d12" font-weight="600">← MOST DIVIDED</text>')
    grid.append(f'<text x="{margin["l"] + plot_w}" y="{margin["t"] + plot_h + 22}" text-anchor="end" font-size="12" fill="#14532d" font-weight="600">MOST UNITED →</text>')
    grid.append(f'<text x="{margin["l"] + plot_w / 2}" y="{margin["t"] + plot_h + 22}" text-anchor="middle" font-size="11" fill="#6b7280" font-style="italic">{n:,} questions, sorted by panel agreement (any direction)</text>')

    # annotations: one at each of 10 / 25 / 50 / 75 / 90 percentile ranks.
    # We hand-pick a recognizable statement near each target percentile.
    picks = [
        (10, "harms from artificial intelligence", "10%ile · “AI risks are best assessed by deploying it”"),
        (25, "payment for human kidneys",                   "25%ile · Pay for human kidneys"),
        (50, "$15-per-hour by 2020",                        "50%ile · $15 federal min wage"),
        (78, "smaller in 2030 than it would have been if the country had remained", "78%ile · “Brexit shrank the UK economy”"),
        (90, "North American Free Trade Agreement",         "90%ile · NAFTA makes Americans better off"),
        (99, "Bureau of Labor Statistics are biased",        "99%ile · “BLS jobs data isn’t politically biased”"),
    ]
    annotations = []
    for pct, kw, label in picks:
        target = int(n * pct / 100)
        # find the rank closest to the target where the statement matches the keyword
        best_idx = None
        best_dist = 10**9
        for i, r in enumerate(rows):
            if kw.lower() in r["text"].lower():
                dist = abs(i - target)
                if dist < best_dist:
                    best_dist = dist
                    best_idx = i
        if best_idx is not None:
            r = rows[best_idx]
            annotations.append({
                "i": best_idx, "label": label, "hhi": r["hhi"], "dir": r["dir"],
                "b_sd": r["b_sd"], "b_d": r["b_d"], "b_u": r["b_u"], "b_a": r["b_a"], "b_sa": r["b_sa"],
            })

    annotations.sort(key=lambda a: a["i"])
    ann_svg = []
    placed: list[tuple[float, float]] = []
    # mini-sparkline geometry
    sp_w = 44
    sp_h = 18
    bucket_colors = ["#7c2d12", "#dc6063", "#94a3b8", "#4ea36d", "#14532d"]
    for idx, a in enumerate(annotations):
        bx = margin["l"] + a["i"] * col_w
        by = y(a["hhi"])
        # leave room above the dot for the sparkline + label
        lx = bx
        ly = by - 38  # label baseline 38px above dot (sparkline sits between)
        while any(abs(lx - px) < 150 and abs(ly - py) < 30 for px, py in placed):
            ly -= 32
        placed.append((lx, ly))
        if lx < margin["l"] + 80:
            anchor = "start"; tx = bx + 8
        elif lx > margin["l"] + plot_w - 80:
            anchor = "end"; tx = bx - 8
        else:
            anchor = "middle"; tx = bx
        # sparkline sits just below the label
        sp_x = bx - sp_w / 2
        sp_y_top = ly + 4
        sp_y_bot = sp_y_top + sp_h
        # dotted line from dot up to sparkline bottom
        ann_svg.append(f'<line x1="{bx:.1f}" y1="{by - 4:.1f}" x2="{bx:.1f}" y2="{sp_y_bot:.1f}" stroke="#111" stroke-width="0.5" stroke-dasharray="2 2"/>')
        ann_svg.append(f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="3" fill="#111" stroke="#fff" stroke-width="1.2"/>')
        # sparkline: 5 mini-bars (SD, D, U, A, SA)
        shares = [a["b_sd"], a["b_d"], a["b_u"], a["b_a"], a["b_sa"]]
        bar_w = sp_w / 5
        for k, share in enumerate(shares):
            if share < 0.005:
                continue
            bh = share * sp_h
            kx = sp_x + k * bar_w
            ky = sp_y_bot - bh
            ann_svg.append(f'<rect x="{kx:.2f}" y="{ky:.2f}" width="{bar_w - 0.6:.2f}" height="{bh:.2f}" fill="{bucket_colors[k]}"/>')
        # sparkline baseline
        ann_svg.append(f'<line x1="{sp_x:.2f}" y1="{sp_y_bot:.2f}" x2="{sp_x + sp_w:.2f}" y2="{sp_y_bot:.2f}" stroke="#cbd5e1" stroke-width="0.5"/>')
        # label above the sparkline; white halo so it stays readable over dark bars
        ann_svg.append(
            f'<text x="{tx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" font-size="11" '
            f'fill="#111" font-weight="500" '
            f'style="paint-order:stroke;stroke:#fafaf9;stroke-width:3px;stroke-linejoin:round;">'
            f'{html.escape(a["label"])}</text>'
        )

    # gradient legend (single hue: pale → deep slate as H rises)
    legend = []
    grad_w = 260
    grad_h = 10
    lx0 = margin["l"] + (plot_w - grad_w) / 2
    ly = height - 22
    grad_stops = "".join(f'<stop offset="{o*100:.0f}%" stop-color="{h}"/>' for _, _, _, o, h in stops)
    legend.append(f'<defs><linearGradient id="hgrad" x1="0%" x2="100%">{grad_stops}</linearGradient></defs>')
    legend.append(f'<rect x="{lx0:.1f}" y="{ly}" width="{grad_w}" height="{grad_h}" fill="url(#hgrad)"/>')
    legend.append(f'<text x="{lx0:.1f}" y="{ly + grad_h + 12}" font-size="11" fill="#374151" text-anchor="start">low concentration</text>')
    legend.append(f'<text x="{lx0 + grad_w:.1f}" y="{ly + grad_h + 12}" font-size="11" fill="#374151" text-anchor="end">high concentration</text>')

    # quick stats
    sorted_h = sorted(r["hhi"] for r in rows)
    median = sorted_h[len(sorted_h) // 2]
    pct_high = sum(1 for d in sorted_h if d >= 0.6) / len(sorted_h) * 100
    pct_diffuse = sum(1 for d in sorted_h if d < 0.4) / len(sorted_h) * 100

    pct_contested   = sum(1 for r in rows if r["hhi"] <= 0.40) / len(rows) * 100
    pct_confident   = sum(1 for r in rows if r["hhi"] >= 0.50) / len(rows) * 100
    pct_overwhelming = sum(1 for r in rows if r["hhi"] >= 0.75) / len(rows) * 100
    title = "Economists agree on more than you think."
    subtitle = (f"Across {n:,} IGM Forum survey questions: {pct_confident:.0f}% reach a confident answer (HHI ≥ 0.5), "
                f"and {pct_overwhelming:.0f}% reach overwhelming consensus (HHI ≥ 0.75). "
                f"Only {pct_contested:.0f}% are genuinely contested — including the public fights you've heard of "
                "(AI risks, kidney markets, the $15 minimum wage).")

    data_json = json.dumps(data, separators=(",", ":"))
    tmpl = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>__TITLE__</title>
<style>
  body{margin:0;background:#fafaf9;color:#111827;font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif;}
  .wrap{max-width:__WIDTH__px;margin:0 auto;padding:20px 24px 24px;}
  h1{font:600 30px/1.15 ui-serif,Georgia,serif;margin:0 0 4px;}
  .sub{color:#4b5563;margin:0 0 4px;max-width:88ch;}
  .foot{color:#6b7280;font-size:12px;margin-top:8px;border-top:1px solid #e5e7eb;padding-top:10px;}
  svg{display:block;width:100%;height:auto;}
  .hr:hover{fill:rgba(0,0,0,0.08);cursor:pointer;}
  #tip{position:fixed;pointer-events:none;background:#111827;color:#f9fafb;padding:8px 10px;border-radius:6px;font-size:12px;max-width:360px;box-shadow:0 4px 12px rgba(0,0,0,.2);opacity:0;transition:opacity .12s;z-index:10;}
  #tip .bd{margin-top:6px;font-size:11px;color:#cbd5e1;}
</style></head><body><div class="wrap">
  <h1>__TITLE__</h1><p class="sub">__SUBTITLE__</p>
  <svg viewBox="0 0 __WIDTH__ __HEIGHT__" id="chart">
    __GRID__
    __BARS__
    __ANN__
    __LEGEND__
    __HOVERS__
  </svg>
  <p class="foot">Data: Kent A. Clark Center for Global Markets (IGM Forum), 558 surveys 2011–2026. Direction-blind consensus metric: HHI = share_agree² + share_uncertain² + share_disagree² (1.0 = unanimous; 0.33 = perfectly diffuse three-way split). Hover any column for the question; click opens the source poll.</p>
</div><div id="tip"></div>
<script>
const D=__DATA__;const tip=document.getElementById('tip');const chart=document.getElementById('chart');
chart.addEventListener('mousemove',e=>{const t=e.target;if(!t.classList.contains('hr')){tip.style.opacity=0;return;}
  const r=D[+t.dataset.i];
  tip.innerHTML=`<b>${esc(r.t)}</b><div class="bd">${r.p} · ${r.d}<br>${r.top}% on ${r.dir.toLowerCase()} · HHI = ${r.hhi}<br>${r.sa}% agree · ${r.su}% uncertain · ${r.sd}% disagree</div>`;
  tip.style.opacity=1;const x=e.clientX+14;const y=e.clientY+14;
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
        .replace("__WIDTH__", str(width))
        .replace("__HEIGHT__", str(height))
        .replace("__GRID__", "\n".join(grid))
        .replace("__BARS__", "\n".join(bars))
        .replace("__ANN__", "\n".join(ann_svg))
        .replace("__LEGEND__", "\n".join(legend))
        .replace("__HOVERS__", "\n".join(hovers))
        .replace("__DATA__", data_json))


def main() -> None:
    stmts = load_statements()
    print(f"Loaded {len(stmts)} statements")
    (ROOT / "consensus.html").write_text(make_chart(stmts), encoding="utf-8")
    print("wrote consensus.html")


if __name__ == "__main__":
    main()
