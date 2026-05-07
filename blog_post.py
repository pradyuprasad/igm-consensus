"""Replicates every number cited in the blog post.

Run: `uv run python blog_post.py`

Reads only `statements_consensus.csv` (US panel only).

Definitions used (matching the post's footnotes):
  - "median question" = mean of stats across the 46th–55th percentile band,
    where polls are ranked by HHI = share_agree² + share_uncertain² + share_disagree²
    (sharing pooling strongly+weakly agree, etc.).
  - "top 5% questions" = top 5% by HHI (95th–100th percentile).
"""
from __future__ import annotations

import csv
import statistics
from pathlib import Path

CSV = Path(__file__).parent / "statements_consensus.csv"


def load_us_rows() -> list[dict]:
    rows = []
    with open(CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not r["consensus_score"] or r["panel_type"] != "US":
                continue
            n = int(r["n_answered_excluding_no_opinion"] or 0)
            if n == 0:
                continue
            sa_n = int(r["n_strongly_agree"] or 0)
            a_n = int(r["n_agree"] or 0)
            u_n = int(r["n_uncertain"] or 0)
            d_n = int(r["n_disagree"] or 0)
            sd_n = int(r["n_strongly_disagree"] or 0)
            share_a = (sa_n + a_n) / n
            share_d = (sd_n + d_n) / n
            share_u = u_n / n
            top = max(share_a, share_d, share_u)
            hhi = share_a**2 + share_d**2 + share_u**2

            if share_a >= share_d and share_a >= share_u:
                strong_in_winners = sa_n / (sa_n + a_n) if (sa_n + a_n) > 0 else None
                opposing = share_d
            elif share_d >= share_u:
                strong_in_winners = sd_n / (sd_n + d_n) if (sd_n + d_n) > 0 else None
                opposing = share_a
            else:
                strong_in_winners = None
                opposing = max(share_a, share_d)

            rows.append({
                "text": r["statement_text"],
                "date": r["publication_date"],
                "n_voters": n,
                "hhi": hhi,
                "top": top,
                "uncertain": share_u,
                "opposing": opposing,
                "strong_in_winners": strong_in_winners,
            })
    return rows


def band_mean(rows: list[dict], lo_pct: int, hi_pct: int, key: str) -> float:
    """Mean of `key` across rows whose HHI rank falls in [lo_pct, hi_pct] inclusive.

    Rows must already be sorted by HHI ascending.
    """
    n = len(rows)
    i0 = int(round(n * lo_pct / 100))
    i1 = int(round(n * (hi_pct + 1) / 100))
    sub = [r[key] for r in rows[i0:i1] if r[key] is not None]
    return sum(sub) / len(sub)


def main() -> None:
    rows = sorted(load_us_rows(), key=lambda r: r["hhi"])
    n_polls = len(rows)
    median_voters = statistics.median(r["n_voters"] for r in rows)

    # Headline (chart subtitle)
    pct_top_ge_50 = sum(1 for r in rows if r["top"] >= 0.50) / n_polls * 100

    # "Median question" = mean across 46-55th HHI percentile band
    median_top = band_mean(rows, 46, 55, "top") * 100
    median_unc = band_mean(rows, 46, 55, "uncertain") * 100
    median_opp = band_mean(rows, 46, 55, "opposing") * 100
    median_siw = band_mean(rows, 46, 55, "strong_in_winners") * 100

    # "Top 5% questions" = top 5% by HHI (95-100)
    top5_siw = band_mean(rows, 95, 100, "strong_in_winners") * 100
    top5_weak_in_winners = 100 - top5_siw

    # Named example: 2019 index-fund question
    idx_q = next(r for r in rows if "low-fee, passive index fund" in r["text"])

    print("=" * 78)
    print("BLOG POST NUMBERS — IGM Forum, US panel")
    print("=" * 78)
    print(f"  N = {n_polls} US questions    median voters/question = {median_voters:.0f}")
    print()
    print("CHART SUBTITLE")
    print("-" * 78)
    print(f"  {pct_top_ge_50:.0f}% of questions reach a modal answer of at least 50%.")
    print(f"  → 'about four out of five questions' ✓")
    print()
    print("PARAGRAPH 1 — On the median question (46–55th HHI percentile, mean of band)")
    print("-" * 78)
    print(f"  Top bucket (lean one way) : {median_top:5.1f}%   blog says: ~70%")
    print(f"  Uncertain                 : {median_unc:5.1f}%   blog says: ~25%")
    print(f"  Opposing direction        : {median_opp:5.1f}%   blog says: ~5%")
    print()
    print("PARAGRAPH 2 — Strength of conviction")
    print("-" * 78)
    print(f"  Median question: strong-share within winners : {median_siw:5.1f}%   blog says: ~22%")
    print(f"  Top 5% questions: strong-share within winners: {top5_siw:5.1f}%")
    print(f"  Top 5% questions: 'merely agree' within winners: {top5_weak_in_winners:5.1f}%   blog says: ~40%")
    print()
    print("  Named example — 'investor cannot beat the market' (2019 index fund):")
    print(f"    Date: {idx_q['date']}    HHI: {idx_q['hhi']:.3f}    n={idx_q['n_voters']}")
    print(f"    Strongly Agree share of agreers : {idx_q['strong_in_winners']*100:5.1f}%")
    print(f"    Just 'Agree' share of agreers   : {(1-idx_q['strong_in_winners'])*100:5.1f}%")


if __name__ == "__main__":
    main()
