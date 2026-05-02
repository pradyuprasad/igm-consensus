from __future__ import annotations

from collections import Counter
from pathlib import Path

from .categories import ISSUE_CATEGORIES
from .quality import consensus_by_category, consensus_by_panel


def write_methodology(
    path: Path,
    coverage: dict[str, object],
    sample_checks: list[dict[str, object]],
    duplicate_summary: dict[str, int],
    vote_label_rows: list[dict[str, str]],
    date_issues: list[dict[str, object]],
    panel_counts: Counter,
) -> None:
    lines = [
        "# Methodology",
        "",
        "Primary source: https://kentclarkcenter.org/surveys/",
        "",
        "The extractor discovers survey URLs from the Clark Center survey and survey-special sitemaps, checks robots.txt, downloads each poll page, and then prefers the official `Download Poll Data` CSV when present. HTML is still parsed for page metadata, statement text, panel type, source topics, profile URLs, affiliations, visible chart percentages, and fallback votes when no CSV is present.",
        "",
        "Run command: `uv run main.py` from this directory. Raw pages and CSVs are cached under `data/raw/`; regenerated deliverables are written at the project root. Use `uv run main.py --refresh` to ignore the cache and redownload all sources.",
        "",
        "Unweighted agreement metrics are computed only from the raw vote labels. Confidence-weighted chart values, when exposed by the page JavaScript, are stored in the `weighted_*` columns and are not mixed with the unweighted counts.",
        "",
        "Survey-special crisis pages use 0-5 numeric importance ratings rather than agree/disagree votes. They are retained, with numeric ratings mapped to `Other / Not Applicable` and agreement shares left blank.",
        "",
        "Allowed issue categories: " + "; ".join(ISSUE_CATEGORIES),
        "",
        "## Coverage Check",
        "",
    ]
    for key, value in coverage.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## CSV vs Page Check", ""])
    passed = sum(1 for row in sample_checks if row.get("status") == "passed")
    lines.append(f"Sampled {len(sample_checks)} CSV-backed poll pages; {passed} passed the text/name/count comparison.")
    for row in sample_checks:
        if row.get("status") != "passed":
            lines.append(f"- {row.get('poll_url')}: {row.get('status')} - {row.get('details')}")
    lines.extend(["", "## Duplicate Check", ""])
    for key, value in duplicate_summary.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Vote-Label Check", ""])
    ambiguous = [row for row in vote_label_rows if row["ambiguous"] == "yes"]
    lines.append(f"Distinct raw vote labels: {len(vote_label_rows)}")
    lines.append(f"Ambiguous labels: {len(ambiguous)}")
    if ambiguous:
        for row in ambiguous[:40]:
            lines.append(f"- {row['vote_raw']} -> {row['vote_normalized']}")
    lines.extend(["", "## Date Check", ""])
    lines.append(f"Missing or ambiguous publication dates: {len(date_issues)}")
    for row in date_issues[:40]:
        lines.append(f"- {row.get('poll_url')}: {row.get('publication_date')}")
    lines.extend(["", "## Panel Check", ""])
    for panel, count in sorted(panel_counts.items()):
        lines.append(f"- {panel or 'Unknown'}: {count} statements")
    lines.extend(
        [
            "",
            "## Reproducibility",
            "",
            "1. `uv sync` to install the locked environment.",
            "2. `uv run main.py` to reuse cached raw sources where available, fetch missing sources, rebuild CSV outputs, run quality checks, and rewrite the methodology and analysis summaries.",
            "3. `uv run main.py --refresh` to force a fresh redownload of all source pages and official CSVs.",
            "4. Inspect `source_log.csv` for every source URL used, whether it was fetched or reused from cache.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_analysis_summary(path: Path, statements: list[dict[str, object]]) -> None:
    lines = ["# Analysis Summary", ""]
    lines.extend(_top_section("Top 20 Strongest Agreement", statements, "share_agree", reverse=True))
    lines.extend(_top_section("Top 20 Strongest Disagreement", statements, "share_disagree", reverse=True))
    lines.extend(_top_section("Top 20 Most Polarized", statements, "polarization_score", reverse=True))
    lines.extend(_top_section("Top 20 Highest Uncertainty", statements, "share_uncertain", reverse=True))
    lines.extend(["## Consensus By Issue Category", ""])
    lines.extend(_counter_table(consensus_by_category(statements)))
    lines.extend(["", "## Consensus By Panel Type", ""])
    lines.extend(_counter_table(consensus_by_panel(statements)))
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- The strongest agreement/disagreement lists use unweighted vote shares and exclude No Opinion and missing responses from denominators.",
            "- Polarization is `min(share_agree, share_disagree)`, so high values indicate substantial camps on both sides.",
            "- Numeric crisis survey-special ratings are included for completeness but are not comparable to agree/disagree shares.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _top_section(title: str, rows: list[dict[str, object]], key: str, reverse: bool) -> list[str]:
    eligible = [row for row in rows if str(row.get(key, ""))]
    eligible.sort(key=lambda row: float(str(row.get(key, "0"))), reverse=reverse)
    lines = [f"## {title}", "", "| Rank | Value | Panel | Date | Statement |", "|---:|---:|---|---|---|"]
    for index, row in enumerate(eligible[:20], start=1):
        statement = str(row.get("statement_text", "")).replace("|", "\\|")
        if len(statement) > 180:
            statement = statement[:177] + "..."
        lines.append(
            f"| {index} | {row.get(key)} | {row.get('panel_type')} | {row.get('publication_date')} | "
            f"[{statement}]({row.get('poll_url')}) |"
        )
    lines.append("")
    return lines


def _counter_table(counters: dict[str, Counter]) -> list[str]:
    levels = [
        "Strong consensus agree",
        "Moderate consensus agree",
        "Split / disagreement",
        "Moderate consensus disagree",
        "Strong consensus disagree",
        "Uncertain consensus",
    ]
    lines = ["| Group | Total | " + " | ".join(levels) + " |"]
    lines.append("|---|---:|" + "|".join("---:" for _ in levels) + "|")
    for group in sorted(counters):
        counter = counters[group]
        total = sum(counter.values())
        values = " | ".join(str(counter.get(level, 0)) for level in levels)
        lines.append(f"| {group} | {total} | {values} |")
    return lines
