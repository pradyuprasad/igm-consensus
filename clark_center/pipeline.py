from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

from .categories import fetch_category_lookup
from .dictionary import data_dictionary_rows
from .discover import discover_poll_urls
from .http_client import HttpClient
from .metrics import statement_metrics, weighted_metrics
from .normalize import parse_confidence
from .parser import (
    build_html_vote_lookup,
    html_votes_as_vote_rows,
    parse_csv_votes,
    parse_poll_page,
    question_by_label,
)
from .quality import distinct_vote_labels, duplicate_checks
from .quality import person_key as quality_person_key
from .reporting import write_analysis_summary, write_methodology
from .util import decimal, ensure_dir, stable_id, url_slug, write_csv


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"

STATEMENT_FIELDS = [
    "statement_id",
    "poll_id",
    "poll_title",
    "poll_url",
    "panel_type",
    "publication_date",
    "topic_or_category",
    "question_label",
    "statement_text",
    "poll_context",
    "n_respondents",
    "n_answered_excluding_no_opinion",
    "n_strongly_agree",
    "n_agree",
    "n_uncertain",
    "n_disagree",
    "n_strongly_disagree",
    "n_no_opinion",
    "n_missing_or_did_not_answer",
    "share_agree",
    "share_disagree",
    "share_uncertain",
    "net_agreement",
    "majority_position",
    "consensus_level",
    "polarization_score",
    "source_csv_url",
    "extraction_method",
    "extraction_notes",
    "issue_categories",
    "category_source",
    "category_confidence",
    "weighted_share_strongly_agree",
    "weighted_share_agree_only",
    "weighted_share_uncertain",
    "weighted_share_disagree_only",
    "weighted_share_strongly_disagree",
    "weighted_share_agree",
    "weighted_share_disagree",
    "weighted_net_agreement",
    "weighted_polarization_score",
]

VOTE_FIELDS = [
    "vote_id",
    "statement_id",
    "poll_id",
    "poll_title",
    "poll_url",
    "panel_type",
    "publication_date",
    "question_label",
    "statement_text",
    "economist_name",
    "economist_affiliation",
    "economist_profile_url",
    "vote_raw",
    "vote_normalized",
    "confidence_raw",
    "confidence_numeric",
    "comment",
    "cited_resource_or_link",
    "source_csv_url",
    "extraction_method",
    "extraction_notes",
]

SOURCE_LOG_FIELDS = [
    "timestamp_utc",
    "resource_type",
    "url",
    "status_code",
    "bytes_downloaded",
    "local_path",
    "notes",
]

FAILED_FIELDS = ["poll_url", "poll_id", "issue_type", "details"]

DATA_DICTIONARY_FIELDS = [
    "table_name",
    "column_name",
    "definition",
    "data_type",
    "allowed_values",
    "notes",
]


def run() -> None:
    args = _parse_args()
    ensure_dir(DATA_DIR)
    ensure_dir(RAW_DIR)
    client = HttpClient(RAW_DIR, delay_seconds=args.delay, use_cache=not args.refresh)

    print("Discovering poll URLs...")
    poll_urls = discover_poll_urls(client)
    if args.limit:
        poll_urls = poll_urls[: args.limit]
    print(f"Discovered {len(poll_urls)} poll pages.")

    print("Fetching source category metadata...")
    category_lookup = fetch_category_lookup(client)

    statements: list[dict[str, object]] = []
    votes: list[dict[str, object]] = []
    failed: list[dict[str, object]] = []
    processed_pages = 0
    csv_backed_pages: list[dict[str, object]] = []

    for index, poll_url in enumerate(poll_urls, start=1):
        if index == 1 or index % 25 == 0:
            print(f"Processing {index}/{len(poll_urls)}: {poll_url}")
        try:
            html = client.fetch_text(poll_url, "page", f"{url_slug(poll_url)}.html")
            poll = parse_poll_page(poll_url, html, category_lookup)
            if not poll.questions:
                failed.append(
                    {
                        "poll_url": poll_url,
                        "poll_id": poll.poll_id,
                        "issue_type": "no_questions_found",
                        "details": "No poll statements could be parsed from the page.",
                    }
                )
                continue
            html_lookup = build_html_vote_lookup(poll)
            extraction_method = "html"
            csv_text = ""
            raw_vote_rows: list[dict[str, str]] = []
            if poll.source_csv_url and not poll.is_special:
                try:
                    csv_text = client.fetch_text(poll.source_csv_url, "csv", f"{poll.poll_id}.csv")
                    raw_vote_rows = parse_csv_votes(poll, csv_text, html_lookup)
                    if raw_vote_rows:
                        extraction_method = "mixed"
                        csv_backed_pages.append({"poll": poll, "csv_text": csv_text})
                    else:
                        failed.append(
                            {
                                "poll_url": poll_url,
                                "poll_id": poll.poll_id,
                                "issue_type": "csv_malformed_or_empty",
                                "details": "Official CSV was present but no vote rows could be parsed; using HTML fallback.",
                            }
                        )
                except RuntimeError as exc:
                    failed.append(
                        {
                            "poll_url": poll_url,
                            "poll_id": poll.poll_id,
                            "issue_type": "csv_download_failed",
                            "details": str(exc),
                        }
                    )
            if not raw_vote_rows:
                raw_vote_rows = html_votes_as_vote_rows(poll)
                extraction_method = "html"
            if not raw_vote_rows:
                failed.append(
                    {
                        "poll_url": poll_url,
                        "poll_id": poll.poll_id,
                        "issue_type": "no_votes_found",
                        "details": "No individual vote rows could be parsed from CSV or HTML.",
                    }
                )
            page_statements, page_votes = _build_rows(poll, raw_vote_rows, extraction_method)
            statements.extend(page_statements)
            votes.extend(page_votes)
            processed_pages += 1
        except Exception as exc:  # noqa: BLE001 - failures belong in the deliverable log.
            failed.append(
                {
                    "poll_url": poll_url,
                    "poll_id": "",
                    "issue_type": "page_processing_failed",
                    "details": repr(exc),
                }
            )

    sample_checks = _csv_vs_page_checks(csv_backed_pages, args.sample_check_size)
    duplicate_summary = duplicate_checks(statements, votes)
    duplicate_summary["duplicate_poll_urls"] = len(poll_urls) - len(set(poll_urls))
    vote_label_rows = distinct_vote_labels(votes)
    date_issues = [row for row in statements if not row.get("publication_date")]
    panel_counts = Counter(str(row.get("panel_type", "")) for row in statements)
    coverage = {
        "total_poll_pages_discovered": len(poll_urls),
        "total_poll_pages_successfully_processed": processed_pages,
        "total_statements_extracted": len(statements),
        "total_vote_rows_extracted": len(votes),
        "csv_backed_pages": len(csv_backed_pages),
        "html_only_or_special_pages": processed_pages - len(csv_backed_pages),
        "failed_or_ambiguous_records": len(failed),
    }

    failed.extend(_quality_failures(sample_checks, duplicate_summary, vote_label_rows, date_issues))

    write_csv(ROOT / "statements.csv", statements, STATEMENT_FIELDS)
    write_csv(ROOT / "votes.csv", votes, VOTE_FIELDS)
    write_csv(ROOT / "data_dictionary.csv", data_dictionary_rows(), DATA_DICTIONARY_FIELDS)
    write_csv(ROOT / "source_log.csv", [entry.__dict__ for entry in client.source_log], SOURCE_LOG_FIELDS)
    write_csv(ROOT / "failed_or_ambiguous_pages.csv", failed, FAILED_FIELDS)
    write_methodology(
        ROOT / "methodology.md",
        coverage,
        sample_checks,
        duplicate_summary,
        vote_label_rows,
        date_issues,
        panel_counts,
    )
    write_analysis_summary(ROOT / "analysis_summary.md", statements)
    print("Done.")
    for key, value in coverage.items():
        print(f"{key}: {value}")


def _build_rows(
    poll,
    raw_vote_rows: list[dict[str, str]],
    extraction_method: str,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    q_by_label = question_by_label(poll)
    votes_by_question: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in raw_vote_rows:
        votes_by_question[row["question_label"]].append(row)

    statement_rows: list[dict[str, object]] = []
    vote_rows: list[dict[str, object]] = []
    for question in poll.questions:
        statement_id = stable_id(poll.poll_id, question.label, max_len=110)
        q_votes = votes_by_question.get(question.label, [])
        statement_text = question.text or _first_vote_statement_text(q_votes)
        metrics = statement_metrics(q_votes)
        weighted = weighted_metrics(question.weighted_page_percentages)
        notes = "; ".join(poll.extraction_notes)
        statement_row = {
            "statement_id": statement_id,
            "poll_id": poll.poll_id,
            "poll_title": poll.poll_title,
            "poll_url": poll.poll_url,
            "panel_type": poll.panel_type,
            "publication_date": poll.publication_date,
            "topic_or_category": poll.topic_or_category,
            "question_label": question.label,
            "statement_text": statement_text,
            "poll_context": poll.poll_context,
            "source_csv_url": poll.source_csv_url,
            "extraction_method": extraction_method,
            "extraction_notes": notes,
            "issue_categories": poll.issue_categories,
            "category_source": poll.category_source,
            "category_confidence": poll.category_confidence,
        }
        statement_row.update(metrics)
        statement_row.update(weighted)
        statement_rows.append(statement_row)
        seen_names: Counter[str] = Counter()
        for vote in q_votes:
            seen_names[vote["economist_name"]] += 1
            disambiguator = str(seen_names[vote["economist_name"]])
            vote_id = stable_id(statement_id, vote["economist_name"], disambiguator, max_len=130)
            vote_rows.append(
                {
                    "vote_id": vote_id,
                    "statement_id": statement_id,
                    "poll_id": poll.poll_id,
                    "poll_title": poll.poll_title,
                    "poll_url": poll.poll_url,
                    "panel_type": poll.panel_type,
                    "publication_date": poll.publication_date,
                    "question_label": question.label,
                    "statement_text": statement_text or vote.get("statement_text", ""),
                    "economist_name": vote["economist_name"],
                    "economist_affiliation": vote.get("economist_affiliation", ""),
                    "economist_profile_url": vote.get("economist_profile_url", ""),
                    "vote_raw": vote.get("vote_raw", ""),
                    "vote_normalized": vote.get("vote_normalized", ""),
                    "confidence_raw": vote.get("confidence_raw", ""),
                    "confidence_numeric": parse_confidence(vote.get("confidence_raw", "")),
                    "comment": vote.get("comment", ""),
                    "cited_resource_or_link": vote.get("cited_resource_or_link", ""),
                    "source_csv_url": poll.source_csv_url,
                    "extraction_method": extraction_method,
                    "extraction_notes": notes,
                }
            )
    return statement_rows, vote_rows


def _first_vote_statement_text(votes: list[dict[str, str]]) -> str:
    for vote in votes:
        text = vote.get("statement_text", "")
        if text:
            return text
    return ""


def _csv_vs_page_checks(csv_backed_pages: list[dict[str, object]], sample_size: int) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []
    if not csv_backed_pages:
        return checks
    if len(csv_backed_pages) <= sample_size:
        sample = csv_backed_pages
    else:
        step = max(1, len(csv_backed_pages) // sample_size)
        sample = csv_backed_pages[::step][:sample_size]
    for item in sample:
        poll = item["poll"]
        csv_text = str(item["csv_text"])
        try:
            html_lookup = build_html_vote_lookup(poll)
            csv_votes = parse_csv_votes(poll, csv_text, html_lookup)
            details: list[str] = []
            if len({vote["question_label"] for vote in csv_votes}) != len(poll.questions):
                details.append("question count mismatch")
            csv_names = {quality_person_key(vote["economist_name"]) for vote in csv_votes}
            html_names = {quality_person_key(vote.economist_name) for vote in poll.html_votes}
            if html_names and not html_names.issubset(csv_names):
                missing = sorted(html_names - csv_names)[:5]
                details.append(f"HTML names missing from CSV parse: {missing}")
            for question in poll.questions:
                q_votes = [vote for vote in csv_votes if vote["question_label"] == question.label]
                n = len(q_votes)
                if not n or not question.unweighted_page_percentages:
                    continue
                csv_counts = Counter(vote["vote_normalized"] for vote in q_votes)
                for raw_label, percentage in question.unweighted_page_percentages.items():
                    normalized = _normalize_page_label(raw_label)
                    expected = round((percentage / 100.0) * n)
                    actual = csv_counts.get(normalized, 0)
                    if abs(actual - expected) > 1:
                        details.append(
                            f"{question.label} count mismatch for {raw_label}: csv={actual}, page≈{expected}"
                        )
            checks.append(
                {
                    "poll_url": poll.poll_url,
                    "status": "failed" if details else "passed",
                    "details": "; ".join(details),
                }
            )
        except Exception as exc:  # noqa: BLE001 - report quality failure.
            checks.append({"poll_url": poll.poll_url, "status": "failed", "details": repr(exc)})
    return checks


def _normalize_page_label(raw_label: str) -> str:
    from .normalize import normalize_vote

    return normalize_vote(raw_label)


def _quality_failures(
    sample_checks: list[dict[str, object]],
    duplicate_summary: dict[str, int],
    vote_label_rows: list[dict[str, str]],
    date_issues: list[dict[str, object]],
) -> list[dict[str, object]]:
    failures: list[dict[str, object]] = []
    for row in sample_checks:
        if row.get("status") != "passed":
            failures.append(
                {
                    "poll_url": row.get("poll_url", ""),
                    "poll_id": "",
                    "issue_type": "csv_vs_page_check_failed",
                    "details": row.get("details", ""),
                }
            )
    for key, value in duplicate_summary.items():
        if value:
            failures.append(
                {
                    "poll_url": "",
                    "poll_id": "",
                    "issue_type": key,
                    "details": str(value),
                }
            )
    ambiguous = [row for row in vote_label_rows if row["ambiguous"] == "yes"]
    for row in ambiguous:
        failures.append(
            {
                "poll_url": "",
                "poll_id": "",
                "issue_type": "ambiguous_vote_label",
                "details": f"{row['vote_raw']} -> {row['vote_normalized']}",
            }
        )
    for row in date_issues:
        failures.append(
            {
                "poll_url": row.get("poll_url", ""),
                "poll_id": row.get("poll_id", ""),
                "issue_type": "missing_or_ambiguous_date",
                "details": str(row.get("publication_date", "")),
            }
        )
    return failures


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Clark Center Forum survey dataset.")
    parser.add_argument("--limit", type=int, default=0, help="Process only the first N poll pages for debugging.")
    parser.add_argument("--delay", type=float, default=0.18, help="Delay between HTTP requests in seconds.")
    parser.add_argument("--sample-check-size", type=int, default=20, help="Number of CSV-backed pages to sample for CSV-vs-page checks.")
    parser.add_argument("--refresh", action="store_true", help="Ignore the raw cache and redownload all sources.")
    return parser.parse_args()
