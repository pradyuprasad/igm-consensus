from __future__ import annotations

from collections import Counter, defaultdict
import re

from .normalize import normalize_vote


def duplicate_checks(statements: list[dict[str, object]], votes: list[dict[str, object]]) -> dict[str, int]:
    poll_urls = Counter((str(row["poll_url"]), str(row["question_label"])) for row in statements)
    statement_ids = Counter(str(row["statement_id"]) for row in statements)
    vote_keys = Counter(
        (
            str(row["statement_id"]),
            person_key(str(row["economist_name"])),
        )
        for row in votes
    )
    return {
        "duplicate_poll_urls": sum(1 for count in poll_urls.values() if count > 1),
        "duplicate_statement_ids": sum(1 for count in statement_ids.values() if count > 1),
        "duplicate_votes_within_statement": sum(1 for count in vote_keys.values() if count > 1),
    }


def distinct_vote_labels(votes: list[dict[str, object]]) -> list[dict[str, str]]:
    labels = sorted({str(row["vote_raw"]) for row in votes})
    return [
        {
            "vote_raw": label,
            "vote_normalized": normalize_vote(label),
            "ambiguous": "yes" if normalize_vote(label) == "Other / Not Applicable" and label not in {"0", "1", "2", "3", "4", "5"} else "no",
        }
        for label in labels
    ]


def consensus_by_category(statements: list[dict[str, object]]) -> dict[str, Counter]:
    result: dict[str, Counter] = defaultdict(Counter)
    for row in statements:
        for category in str(row.get("issue_categories", "")).split(";"):
            category = category.strip()
            if category:
                result[category][str(row.get("consensus_level", ""))] += 1
    return result


def consensus_by_panel(statements: list[dict[str, object]]) -> dict[str, Counter]:
    result: dict[str, Counter] = defaultdict(Counter)
    for row in statements:
        result[str(row.get("panel_type", ""))][str(row.get("consensus_level", ""))] += 1
    return result


def person_key(name: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", str(name).lower())
    tokens = [token for token in tokens if len(token) > 1]
    return "".join(tokens)
