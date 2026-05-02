"""Two structural reframes of the consensus story.

Outputs:
  topics.html  — strip plot of H by issue category. Where does consensus live?
  shapes.html  — mosaic of mini-Likert sparklines. The viewer reads consensus
                 from the shape (peaked vs flat) rather than from a summary number.
"""
from __future__ import annotations

import csv
import html
import json
import random
import statistics
from collections import defaultdict
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
            sa = float(r["share_agree"]); sd = float(r["share_disagree"]); su = float(r["share_uncertain"])
            hhi = sa * sa + sd * sd + su * su
            rows.append({
                "id": r["statement_id"], "text": r["statement_text"],
                "panel": r["panel_type"], "date": r["publication_date"], "url": r["poll_url"],
                "n": n,
                "sa": int(r["n_strongly_agree"] or 0) / n,
                "a":  int(r["n_agree"] or 0) / n,
                "u":  int(r["n_uncertain"] or 0) / n,
                "d":  int(r["n_disagree"] or 0) / n,
                "sd": int(r["n_strongly_disagree"] or 0) / n,
                "share_a": sa, "share_d": sd, "share_u": su,
                "hhi": hhi,
                "categories": [c.strip() for c in (r.get("issue_categories") or "").split(";") if c.strip()],
            })
    return rows


# ---------- A. topics.html — strip plot by issue category ---------------------

def make_topics(stmts: list[dict]) -> str:
    # bucket questions by category. A question with multiple categories appears in each.
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in stmts:
        for c in r["categories"]:
            by_cat[c].append(r)

    # drop tiny categories and "Other"
    cats = [c for c, rs in by_cat.items() if len(rs) >= 15 and c.lower() != "other"]
    cats.sort(key=lambda c: -statistics.median(r["hhi"] for r in by_cat[c]))

    width = 1200
    row_h = 38
    n_rows = len(cats)
    margin = {"t": 110, "r": 60, "b": 90, "l": 220}
    plot_w = width - margin["l"] - margin["r"]
    plot_h = n_rows * row_h
    height = margin["t"] + plot_h + margin["b"]

    h_min, h_max = 1 / 3, 1.0
    def x(h: float) -> float:
        return margin["l"] + (h - h_min) / (h_max - h_min) * plot_w

    # palette: same slate gradient
    def shade(h: float) -> str:
        t = (h - h_min) / (h_max - h_min)
        r0, g0, b0 = 203, 213, 225
        r1, g1, b1 = 30, 41, 59
        return f"#{int(r0+(r1-r0)*t):02x}{int(g0+(g1-g0)*t):02x}{int(b0+(b1-b0)*t):02x}"

    rng = random.Random(42)
    bg_strips: list[str] = []
    dots: list[str] = []
    medians: list[str] = []
    labels: list[str] = []
    for ri, cat in enumerate(cats):
        ys = margin["t"] + ri * row_h
        # alternating row tint
        if ri % 2 == 0:
            bg_strips.append(f'<rect x="{margin["l"]}" y="{ys}" width="{plot_w}" height="{row_h}" fill="#f8fafc"/>')
        rs = by_cat[cat]
        med = statistics.median(r["hhi"] for r in rs)
        # category label + count + median
        labels.append(f'<text x="{margin["l"] - 12}" y="{ys + row_h/2 + 4:.1f}" text-anchor="end" font-size="12" fill="#111" font-weight="500">{html.escape(cat)}</text>')
        labels.append(f'<text x="{margin["l"] - 12}" y="{ys + row_h/2 + 18:.1f}" text-anchor="end" font-size="10" fill="#9ca3af">{len(rs)} questions · median H {med:.2f}</text>')
        # dots, y-jittered inside row
        for r in rs:
            jx = x(r["hhi"])
            jy = ys + row_h * 0.5 + (rng.random() - 0.5) * (row_h - 14)
            dots.append(f'<circle cx="{jx:.2f}" cy="{jy:.2f}" r="3" fill="{shade(r["hhi"])}" fill-opacity="0.7" stroke="#fff" stroke-width="0.4"/>')
        # median tick
        mx = x(med)
        medians.append(f'<line x1="{mx:.1f}" y1="{ys + 5}" x2="{mx:.1f}" y2="{ys + row_h - 5}" stroke="#dc2626" stroke-width="2"/>')

    # axis
    axis = []
    for tick in [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        xt = x(tick)
        axis.append(f'<line x1="{xt:.1f}" y1="{margin["t"]}" x2="{xt:.1f}" y2="{margin["t"] + plot_h + 6}" stroke="#e5e7eb" stroke-width="0.6"/>')
        axis.append(f'<text x="{xt:.1f}" y="{margin["t"] + plot_h + 22}" text-anchor="middle" font-size="11" fill="#6b7280">{tick:.2f}</text>')
    axis.append(f'<text x="{margin["l"]}" y="{margin["t"] - 14}" font-size="11" fill="#7c2d12" font-weight="600">← MORE DIVIDED</text>')
    axis.append(f'<text x="{margin["l"] + plot_w}" y="{margin["t"] - 14}" text-anchor="end" font-size="11" fill="#14532d" font-weight="600">MORE UNITED →</text>')
    axis.append(f'<text x="{margin["l"] + plot_w/2}" y="{margin["t"] + plot_h + 42}" text-anchor="middle" font-size="11" fill="#6b7280" font-style="italic">Herfindahl concentration H — direction-blind, 1.0 = unanimous, 0.33 = perfectly diffuse</text>')

    # red bar legend
    axis.append(f'<line x1="{margin["l"] + 8}" y1="{margin["t"] - 30}" x2="{margin["l"] + 18}" y2="{margin["t"] - 30}" stroke="#dc2626" stroke-width="2"/>')
    axis.append(f'<text x="{margin["l"] + 22}" y="{margin["t"] - 26}" font-size="11" fill="#dc2626">topic median</text>')

    title = "Where consensus lives — and where it doesn't"
    subtitle = ("Each dot is one IGM survey question, plotted by its Herfindahl concentration H within its issue category. "
                "Topics are sorted by median H (top = most settled, bottom = most contested). Red ticks mark each topic's median.")

    tmpl = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>__TITLE__</title>
<style>
  body{margin:0;background:#fafaf9;color:#111827;font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif;}
  .wrap{max-width:__WIDTH__px;margin:0 auto;padding:28px 24px 28px;}
  h1{font:600 28px/1.15 ui-serif,Georgia,serif;margin:0 0 6px;}
  .sub{color:#4b5563;margin:0 0 14px;max-width:88ch;}
  .foot{color:#6b7280;font-size:12px;margin-top:6px;border-top:1px solid #e5e7eb;padding-top:10px;}
  svg{display:block;width:100%;height:auto;}
</style></head><body><div class="wrap">
  <h1>__TITLE__</h1><p class="sub">__SUBTITLE__</p>
  <svg viewBox="0 0 __WIDTH__ __HEIGHT__">
    __BG__
    __AXIS__
    __DOTS__
    __MEDIANS__
    __LABELS__
  </svg>
  <p class="foot">Data: Kent A. Clark Center for Global Markets (IGM Forum). A question with multiple issue tags appears in each row.</p>
</div></body></html>
"""
    return (tmpl
        .replace("__TITLE__", title).replace("__SUBTITLE__", subtitle)
        .replace("__WIDTH__", str(width)).replace("__HEIGHT__", str(height))
        .replace("__BG__", "\n".join(bg_strips))
        .replace("__AXIS__", "\n".join(axis))
        .replace("__DOTS__", "\n".join(dots))
        .replace("__MEDIANS__", "\n".join(medians))
        .replace("__LABELS__", "\n".join(labels)))


# ---------- C. shapes.html — mosaic of 5-bucket Likert sparklines -------------

def make_shapes(stmts: list[dict]) -> str:
    rows = sorted(stmts, key=lambda r: r["hhi"])
    n = len(rows)
    cols = 40
    n_rows = (n + cols - 1) // cols
    cell_w = 26
    cell_h = 30
    pad_x = 2
    pad_y = 4
    margin = {"t": 130, "r": 30, "b": 110, "l": 30}
    plot_w = cols * cell_w
    plot_h = n_rows * cell_h
    width = margin["l"] + plot_w + margin["r"]
    height = margin["t"] + plot_h + margin["b"]

    cells: list[str] = []
    data: list[dict] = []
    for i, r in enumerate(rows):
        col = i % cols
        row = i // cols
        x0 = margin["l"] + col * cell_w + pad_x
        y0 = margin["t"] + row * cell_h + pad_y
        w = cell_w - 2 * pad_x
        h = cell_h - 2 * pad_y
        # 5 mini-bars: SD, D, U, A, SA — height proportional to share
        bar_w = w / 5
        for k, (share, color) in enumerate([(r["sd"], C_SD), (r["d"], C_D), (r["u"], C_U), (r["a"], C_A), (r["sa"], C_SA)]):
            if share < 0.005:
                continue
            bh = share * h
            bx = x0 + k * bar_w
            by = y0 + h - bh
            cells.append(f'<rect x="{bx:.2f}" y="{by:.2f}" width="{bar_w - 0.4:.2f}" height="{bh:.2f}" fill="{color}"/>')
        # cell baseline
        cells.append(f'<line x1="{x0:.2f}" y1="{y0 + h:.2f}" x2="{x0 + w:.2f}" y2="{y0 + h:.2f}" stroke="#e5e7eb" stroke-width="0.4"/>')
        # transparent hover overlay
        cells.append(f'<rect class="hr" x="{margin["l"] + col*cell_w}" y="{margin["t"] + row*cell_h}" width="{cell_w}" height="{cell_h}" fill="transparent" data-i="{i}"/>')
        data.append({
            "t": r["text"], "p": r["panel"], "d": r["date"], "u": r["url"],
            "hhi": round(r["hhi"], 3),
            "sa": round(r["sa"]*100), "a": round(r["a"]*100), "un": round(r["u"]*100),
            "di": round(r["d"]*100), "sd": round(r["sd"]*100),
        })

    # legend showing how to read a sparkline
    leg_x = margin["l"] + 20; leg_y = 70
    leg_w = 26; leg_h = 30
    legend = []
    legend.append(f'<text x="{leg_x}" y="{leg_y - 8}" font-size="11" fill="#374151" font-weight="600">how to read a cell</text>')
    # example: a settled cell (peak on agree)
    example = [(0.02, C_SD), (0.05, C_D), (0.08, C_U), (0.55, C_A), (0.30, C_SA)]
    for k, (share, color) in enumerate(example):
        bh = share * (leg_h - 8)
        bw = (leg_w - 4) / 5
        bx = leg_x + k * bw
        by = leg_y + leg_h - bh - 4
        legend.append(f'<rect x="{bx:.2f}" y="{by:.2f}" width="{bw - 0.4:.2f}" height="{bh:.2f}" fill="{color}"/>')
    legend.append(f'<line x1="{leg_x}" y1="{leg_y + leg_h - 4}" x2="{leg_x + leg_w - 4}" y2="{leg_y + leg_h - 4}" stroke="#9ca3af" stroke-width="0.5"/>')
    legend.append(f'<text x="{leg_x + leg_w + 8}" y="{leg_y + leg_h - 8}" font-size="11" fill="#374151">tall single peak = panel converged</text>')

    # second example: contested
    leg_x2 = leg_x + 380
    legend.append(f'<text x="{leg_x2}" y="{leg_y - 8}" font-size="11" fill="#374151" font-weight="600">contested cell</text>')
    example2 = [(0.20, C_SD), (0.20, C_D), (0.20, C_U), (0.20, C_A), (0.20, C_SA)]
    for k, (share, color) in enumerate(example2):
        bh = share * (leg_h - 8)
        bw = (leg_w - 4) / 5
        bx = leg_x2 + k * bw
        by = leg_y + leg_h - bh - 4
        legend.append(f'<rect x="{bx:.2f}" y="{by:.2f}" width="{bw - 0.4:.2f}" height="{bh:.2f}" fill="{color}"/>')
    legend.append(f'<line x1="{leg_x2}" y1="{leg_y + leg_h - 4}" x2="{leg_x2 + leg_w - 4}" y2="{leg_y + leg_h - 4}" stroke="#9ca3af" stroke-width="0.5"/>')
    legend.append(f'<text x="{leg_x2 + leg_w + 8}" y="{leg_y + leg_h - 8}" font-size="11" fill="#374151">flat = panel split across buckets</text>')

    # bucket key
    legend.append(f'<text x="{margin["l"] + plot_w - 20}" y="{margin["t"] - 24}" text-anchor="end" font-size="11" fill="#6b7280">bars left → right: strongly disagree, disagree, uncertain, agree, strongly agree</text>')

    # sort direction labels
    legend.append(f'<text x="{margin["l"]}" y="{margin["t"] + plot_h + 22}" font-size="12" fill="#7c2d12" font-weight="600">← MOST DIVIDED</text>')
    legend.append(f'<text x="{margin["l"] + plot_w}" y="{margin["t"] + plot_h + 22}" text-anchor="end" font-size="12" fill="#14532d" font-weight="600">MOST UNITED →</text>')
    legend.append(f'<text x="{margin["l"] + plot_w/2}" y="{margin["t"] + plot_h + 22}" text-anchor="middle" font-size="11" fill="#6b7280" font-style="italic">{n:,} questions · reading order: top-left → bottom-right</text>')

    title = "1,119 votes shapes"
    subtitle = ("Each cell is one IGM question. The 5 little bars show what fraction of the panel chose strongly disagree / "
                "disagree / uncertain / agree / strongly agree. Sorted top-left → bottom-right by Herfindahl concentration: "
                "early cells are flat (panel split), late cells are sharply peaked (panel converged). The shape is the consensus.")

    data_json = json.dumps(data, separators=(",", ":"))
    tmpl = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>__TITLE__</title>
<style>
  body{margin:0;background:#fafaf9;color:#111827;font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif;}
  .wrap{max-width:__WIDTH__px;margin:0 auto;padding:28px 24px 28px;}
  h1{font:600 26px/1.15 ui-serif,Georgia,serif;margin:0 0 6px;}
  .sub{color:#4b5563;margin:0 0 14px;max-width:96ch;}
  .foot{color:#6b7280;font-size:12px;margin-top:6px;border-top:1px solid #e5e7eb;padding-top:10px;}
  svg{display:block;width:100%;height:auto;}
  .hr:hover{fill:rgba(0,0,0,0.07);cursor:pointer;}
  #tip{position:fixed;pointer-events:none;background:#111827;color:#f9fafb;padding:8px 10px;border-radius:6px;font-size:12px;max-width:380px;box-shadow:0 4px 12px rgba(0,0,0,.2);opacity:0;transition:opacity .12s;z-index:10;}
  #tip .bd{margin-top:6px;font-size:11px;color:#cbd5e1;}
</style></head><body><div class="wrap">
  <h1>__TITLE__</h1><p class="sub">__SUBTITLE__</p>
  <svg viewBox="0 0 __WIDTH__ __HEIGHT__" id="chart">
    __LEGEND__
    __CELLS__
  </svg>
  <p class="foot">Data: Kent A. Clark Center for Global Markets (IGM Forum). Hover any cell for the question.</p>
</div><div id="tip"></div>
<script>
const D=__DATA__;const tip=document.getElementById('tip');const chart=document.getElementById('chart');
chart.addEventListener('mousemove',e=>{const t=e.target;if(!t.classList.contains('hr')){tip.style.opacity=0;return;}
  const r=D[+t.dataset.i];
  tip.innerHTML=`<b>${esc(r.t)}</b><div class="bd">${r.p} · ${r.d} · H = ${r.hhi}<br>${r.sd}% strongly disagree · ${r.di}% disagree · ${r.un}% uncertain · ${r.a}% agree · ${r.sa}% strongly agree</div>`;
  tip.style.opacity=1;const x=e.clientX+14;const y=e.clientY+14;
  tip.style.left=Math.min(x,window.innerWidth-400)+'px';tip.style.top=Math.min(y,window.innerHeight-110)+'px';
});
chart.addEventListener('mouseleave',()=>tip.style.opacity=0);
chart.addEventListener('click',e=>{const t=e.target;if(t.classList.contains('hr')){const r=D[+t.dataset.i];if(r.u)window.open(r.u,'_blank');}});
function esc(s){return s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
</script></body></html>
"""
    return (tmpl
        .replace("__TITLE__", title).replace("__SUBTITLE__", subtitle)
        .replace("__WIDTH__", str(width)).replace("__HEIGHT__", str(height))
        .replace("__LEGEND__", "\n".join(legend))
        .replace("__CELLS__", "\n".join(cells))
        .replace("__DATA__", data_json))


def main() -> None:
    stmts = load_statements()
    print(f"Loaded {len(stmts)} statements")
    (ROOT / "topics.html").write_text(make_topics(stmts), encoding="utf-8")
    print("wrote topics.html")
    (ROOT / "shapes.html").write_text(make_shapes(stmts), encoding="utf-8")
    print("wrote shapes.html")


if __name__ == "__main__":
    main()
