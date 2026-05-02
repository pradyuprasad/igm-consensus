from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


BROAD_TOPIC_MAP = {
    "Monetary policy": "Macroeconomics and monetary",
    "Fiscal policy": "Public finance and fiscal policy",
    "Taxation": "Public finance and fiscal policy",
    "Public finance": "Public finance and fiscal policy",
    "Labor markets": "Labor, education, and inequality",
    "Education": "Labor, education, and inequality",
    "Inequality/redistribution": "Labor, education, and inequality",
    "Healthcare": "Health and social policy",
    "COVID/pandemic policy": "Health and social policy",
    "Trade": "International trade and globalization",
    "Immigration": "International trade and globalization",
    "International economics": "International trade and globalization",
    "Climate/environment": "Climate, energy, and environment",
    "Energy": "Climate, energy, and environment",
    "Financial regulation": "Finance, banking, and markets",
    "Banking": "Finance, banking, and markets",
    "Industrial policy": "Competition, regulation, and industrial policy",
    "Antitrust/competition": "Competition, regulation, and industrial policy",
    "Housing/urban policy": "Housing and urban economics",
    "Growth/productivity": "Growth, productivity, and technology",
    "Political economy": "Political economy and institutions",
    "Other": "Other",
}


def main() -> None:
    args = parse_args()
    source_rows = read_csv(args.input)
    rows = build_analysis_rows(
        source_rows,
        score_field=args.score_field,
        threshold=args.threshold,
    )
    report = build_report(
        rows,
        input_path=args.input,
        score_field=args.score_field,
        threshold=args.threshold,
        permutations=args.permutations,
        seed=args.seed,
        min_topic_n=args.min_topic_n,
    )
    write_json(args.output, report)
    print(f"Wrote topic consensus test report to {args.output}")


def build_analysis_rows(
    source_rows: list[dict[str, str]],
    score_field: str,
    threshold: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in source_rows:
        score = parse_float(row.get(score_field, ""))
        if score is None:
            continue
        rows.append(
            {
                "statement_id": row.get("statement_id", ""),
                "score": score,
                "high_consensus": score >= threshold,
                "direction": row.get("confidence_weighted_direction", ""),
                "fine_topics": fine_topics(row),
                "broad_topics": broad_topics(row),
            }
        )
    return rows


def build_report(
    rows: list[dict[str, Any]],
    input_path: Path,
    score_field: str,
    threshold: float,
    permutations: int,
    seed: int,
    min_topic_n: int,
) -> dict[str, Any]:
    high_count = sum(row["high_consensus"] for row in rows)
    comparable_rows = len(rows)
    overall_rate = safe_div(high_count, comparable_rows)

    broad_omnibus = permutation_omnibus_test(
        rows,
        topic_field="broad_topics",
        permutations=permutations,
        seed=seed,
        exclude_other=True,
    )
    fine_omnibus = permutation_omnibus_test(
        rows,
        topic_field="fine_topics",
        permutations=permutations,
        seed=seed + 1,
        exclude_other=True,
    )

    return {
        "metadata": {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "input_file": str(input_path),
            "script": Path(__file__).name,
        },
        "configuration": {
            "outcome": f"{score_field} >= {threshold:.2f}",
            "score_field": score_field,
            "threshold": threshold,
            "permutations": permutations,
            "seed": seed,
            "min_topic_n_for_topic_tests": min_topic_n,
            "broad_topic_map": BROAD_TOPIC_MAP,
        },
        "denominators": {
            "comparable_rows": comparable_rows,
            "overwhelming_consensus_rows": high_count,
            "overall_overwhelming_consensus_rate": overall_rate,
        },
        "method": {
            "omnibus": (
                "Permutation test. Topic memberships are held fixed, the binary "
                "high-consensus outcome is shuffled across statements, and the test "
                "statistic is the sum across topics of n_topic * "
                "(topic_rate - overall_rate)^2 / (overall_rate * (1 - overall_rate))."
            ),
            "topic_vs_rest": (
                "Two-sided exact hypergeometric topic-vs-rest tests, followed by "
                "Benjamini-Hochberg false-discovery-rate correction within each "
                "topic family."
            ),
            "multi_label_note": (
                "A statement may belong to multiple topics. The permutation omnibus "
                "test preserves this multi-label structure."
            ),
        },
        "omnibus_tests": {
            "broad_topics": broad_omnibus,
            "fine_topics": fine_omnibus,
        },
        "topic_vs_rest_tests": {
            "broad_topics": topic_tests(
                rows,
                topic_field="broad_topics",
                min_topic_n=min_topic_n,
                exclude_other=True,
            ),
            "fine_topics": topic_tests(
                rows,
                topic_field="fine_topics",
                min_topic_n=min_topic_n,
                exclude_other=True,
            ),
        },
    }


def fine_topics(row: dict[str, str]) -> list[str]:
    raw = (row.get("issue_categories") or "").strip()
    if not raw:
        return ["Other"]
    topics = [topic.strip() for topic in raw.split(";") if topic.strip()]
    return topics or ["Other"]


def broad_topics(row: dict[str, str]) -> list[str]:
    return sorted({BROAD_TOPIC_MAP.get(topic, "Other") for topic in fine_topics(row)})


def permutation_omnibus_test(
    rows: list[dict[str, Any]],
    topic_field: str,
    permutations: int,
    seed: int,
    exclude_other: bool,
) -> dict[str, Any]:
    observed_groups = group_counts(
        rows,
        topic_field=topic_field,
        highs=[row["high_consensus"] for row in rows],
        exclude_other=exclude_other,
    )
    observed_statistic = omnibus_statistic(observed_groups, overall_rate(rows))

    highs = [row["high_consensus"] for row in rows]
    rng = random.Random(seed)
    greater_or_equal = 0
    for _ in range(permutations):
        shuffled = highs[:]
        rng.shuffle(shuffled)
        shuffled_groups = group_counts(
            rows,
            topic_field=topic_field,
            highs=shuffled,
            exclude_other=exclude_other,
        )
        shuffled_statistic = omnibus_statistic(shuffled_groups, overall_rate(rows))
        if shuffled_statistic >= observed_statistic - 1e-12:
            greater_or_equal += 1

    p_value = (greater_or_equal + 1) / (permutations + 1)
    return {
        "test": "permutation_omnibus",
        "topic_field": topic_field,
        "statistic": round(observed_statistic, 6),
        "p_value": round(p_value, 6),
        "permutations": permutations,
        "seed": seed,
        "topic_count": len(observed_groups),
    }


def group_counts(
    rows: list[dict[str, Any]],
    topic_field: str,
    highs: list[bool],
    exclude_other: bool,
) -> dict[str, dict[str, int]]:
    groups: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "high": 0})
    for row, high in zip(rows, highs, strict=True):
        for topic in row[topic_field]:
            if exclude_other and topic == "Other":
                continue
            groups[topic]["n"] += 1
            groups[topic]["high"] += int(high)
    return dict(groups)


def omnibus_statistic(
    groups: dict[str, dict[str, int]],
    global_rate: float,
) -> float:
    if global_rate <= 0 or global_rate >= 1:
        return 0.0
    denominator = global_rate * (1 - global_rate)
    statistic = 0.0
    for group in groups.values():
        topic_rate = safe_div(group["high"], group["n"])
        statistic += group["n"] * (topic_rate - global_rate) ** 2 / denominator
    return statistic


def topic_tests(
    rows: list[dict[str, Any]],
    topic_field: str,
    min_topic_n: int,
    exclude_other: bool,
) -> list[dict[str, Any]]:
    total_n = len(rows)
    total_high = sum(row["high_consensus"] for row in rows)
    groups = group_rows(rows, topic_field, exclude_other=exclude_other)

    raw_tests: list[dict[str, Any]] = []
    for topic, topic_rows in groups.items():
        n = len(topic_rows)
        if n < min_topic_n:
            continue
        high = sum(row["high_consensus"] for row in topic_rows)
        scores = [row["score"] for row in topic_rows]
        high_directions = Counter(
            row["direction"] for row in topic_rows if row["high_consensus"]
        )
        raw_tests.append(
            {
                "topic": topic,
                "n": n,
                "high_consensus_count": high,
                "high_consensus_rate": safe_div(high, n),
                "difference_from_overall_rate": safe_div(high, n)
                - safe_div(total_high, total_n),
                "mean_score": mean(scores),
                "median_score": median(scores),
                "high_consensus_direction_counts": dict(sorted(high_directions.items())),
                "p_value": fisher_two_sided_topic(
                    topic_n=n,
                    topic_high=high,
                    total_n=total_n,
                    total_high=total_high,
                ),
            }
        )

    adjusted = add_bh_q_values(raw_tests)
    adjusted.sort(
        key=lambda item: (
            item["bh_q_value"],
            -abs(item["difference_from_overall_rate"]),
            item["topic"],
        )
    )
    return [round_test_values(item) for item in adjusted]


def group_rows(
    rows: list[dict[str, Any]],
    topic_field: str,
    exclude_other: bool,
) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        for topic in row[topic_field]:
            if exclude_other and topic == "Other":
                continue
            groups[topic].append(row)
    return dict(groups)


def fisher_two_sided_topic(
    topic_n: int,
    topic_high: int,
    total_n: int,
    total_high: int,
) -> float:
    observed = hypergeom_pmf(topic_high, total_n, total_high, topic_n)
    low = max(0, topic_n - (total_n - total_high))
    high = min(topic_n, total_high)
    p_value = 0.0
    for possible_high in range(low, high + 1):
        probability = hypergeom_pmf(possible_high, total_n, total_high, topic_n)
        if probability <= observed + 1e-15:
            p_value += probability
    return min(1.0, p_value)


def hypergeom_pmf(draw_high: int, total_n: int, total_high: int, draw_n: int) -> float:
    return math.exp(
        log_comb(total_high, draw_high)
        + log_comb(total_n - total_high, draw_n - draw_high)
        - log_comb(total_n, draw_n)
    )


def log_comb(n: int, k: int) -> float:
    if k < 0 or k > n:
        return float("-inf")
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def add_bh_q_values(tests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = sorted(enumerate(tests), key=lambda item: item[1]["p_value"])
    q_values = [1.0] * len(tests)
    running_min = 1.0
    m = len(tests)
    for reverse_rank, (original_index, test) in enumerate(reversed(indexed), start=1):
        rank = m - reverse_rank + 1
        q_value = min(running_min, test["p_value"] * m / rank)
        running_min = q_value
        q_values[original_index] = q_value

    output: list[dict[str, Any]] = []
    for test, q_value in zip(tests, q_values, strict=True):
        output.append({**test, "bh_q_value": min(1.0, q_value)})
    return output


def round_test_values(test: dict[str, Any]) -> dict[str, Any]:
    rounded = dict(test)
    for key in [
        "high_consensus_rate",
        "difference_from_overall_rate",
        "mean_score",
        "median_score",
        "p_value",
        "bh_q_value",
    ]:
        rounded[key] = round(rounded[key], 6)
    return rounded


def overall_rate(rows: list[dict[str, Any]]) -> float:
    return safe_div(sum(row["high_consensus"] for row in rows), len(rows))


def safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def parse_float(value: str) -> float | None:
    if value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, report: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Test whether overwhelming confidence-weighted consensus rates differ "
            "by economics topic and write a JSON report."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("statements_consensus.csv"),
        help="Input statements CSV with confidence_weighted_score and issue_categories.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("topic_consensus_tests.json"),
        help="Output JSON report.",
    )
    parser.add_argument(
        "--score-field",
        default="confidence_weighted_score",
        help="Numeric score field to threshold.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.90,
        help="Threshold defining overwhelming consensus.",
    )
    parser.add_argument(
        "--permutations",
        type=int,
        default=20_000,
        help="Number of permutations for each omnibus test.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=7,
        help="Random seed for reproducible permutation tests.",
    )
    parser.add_argument(
        "--min-topic-n",
        type=int,
        default=20,
        help="Minimum topic size for topic-vs-rest tests.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
